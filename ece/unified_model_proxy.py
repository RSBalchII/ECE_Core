"""
Unified Model Proxy System for ECE and llama.cpp

This module provides a single endpoint that routes between the External Context Engine (ECE)
and standalone llama.cpp models, allowing a unified interface to both systems.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import httpx
import uvicorn
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    """Configuration for model backends"""

    ece_endpoint: str = "http://localhost:8000"  # ECE orchestrator
    llama_cpp_endpoint: str = "http://localhost:8091/v1"  # llama.cpp model server
    active_backend: str = "llama_cpp"  # Either "ece" or "llama_cpp"
    timeout: int = 30


class SessionManager:
    """Manages session state that persists across backend switches"""

    def __init__(self):
        self._sessions = {}  # In-memory session storage
        self._active_sessions = set()  # Track active sessions

    def create_session(self, session_id: str = None) -> str:
        """Create a new session and return its ID"""
        import uuid

        if not session_id:
            session_id = str(uuid.uuid4())

        self._sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(),
            "last_accessed": datetime.now(),
            "history": [],
            "context": {},
        }

        self._active_sessions.add(session_id)
        return session_id

    def get_session(self, session_id: str) -> dict:
        """Get session data"""
        session = self._sessions.get(session_id)
        if session:
            session["last_accessed"] = datetime.now()
        return session

    def update_session_context(self, session_id: str, context: dict):
        """Update the context for a session"""
        session = self._sessions.get(session_id)
        if session:
            session["context"].update(context)
            session["last_accessed"] = datetime.now()

    def add_to_history(self, session_id: str, entry: dict):
        """Add an entry to the session history"""
        session = self._sessions.get(session_id)
        if session:
            session["history"].append(entry)
            session["last_accessed"] = datetime.now()

    def delete_session(self, session_id: str):
        """Delete a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._active_sessions.discard(session_id)

    def list_sessions(self) -> list:
        """List all session IDs"""
        return list(self._sessions.keys())


class ModelLifecycleManager:
    """Manages model lifecycle across both ECE and llama.cpp backends"""

    def __init__(
        self,
        ece_client: httpx.AsyncClient,
        llama_cpp_client: httpx.AsyncClient,
        active_backend: str,
    ):
        self.ece_client = ece_client
        self.llama_cpp_client = llama_cpp_client
        self.active_backend = active_backend
        self._model_cache = {}  # Cache for model states

    async def start_model(self, model_name: str, backend: str = None) -> bool:
        """Start a model on the specified backend"""
        try:
            if backend == "ece" or (backend is None and self.active_backend == "ece"):
                # For ECE, start the model through its model management endpoint
                response = await self.ece_client.post(
                    "/models/start", json={"model_name": model_name}
                )
            elif backend == "llama_cpp" or (
                backend is None and self.active_backend == "llama_cpp"
            ):
                # For llama.cpp, we would typically start the server
                # In this proxy setup, we'll check if the server is available
                try:
                    response = await self.llama_cpp_client.get("/models")
                    return response.status_code == 200
                except:
                    # If we can't connect, the server might not be running
                    logger.warning(
                        "llama.cpp server not available, please start it manually"
                    )
                    return False
            else:
                raise ValueError(
                    f"Unknown backend: {backend if backend else self.active_backend}"
                )

            if response.status_code in [200, 201]:
                logger.info(
                    f"Successfully started model: {model_name} on backend: {backend}"
                )
                self._model_cache[model_name] = {
                    "status": "running",
                    "backend": backend,
                }
                return True
            else:
                logger.error(
                    f"Failed to start model: {model_name}, status: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"Error starting model {model_name}: {e}")
            return False

    async def stop_model(self, model_name: str, backend: str = None) -> bool:
        """Stop a model on the specified backend"""
        try:
            if backend == "ece" or (backend is None and self.active_backend == "ece"):
                response = await self.ece_client.post(
                    "/models/stop", json={"model_name": model_name}
                )
            elif backend == "llama_cpp" or (
                backend is None and self.active_backend == "llama_cpp"
            ):
                # llama.cpp models are typically stopped with server shutdown
                # For this proxy, we'll just update our cache
                response = await self.llama_cpp_client.get("/health")
            else:
                raise ValueError(
                    f"Unknown backend: {backend if backend else self.active_backend}"
                )

            if response.status_code in [200, 204]:
                logger.info(
                    f"Successfully stopped model: {model_name} on backend: {backend}"
                )
                self._model_cache[model_name] = {
                    "status": "stopped",
                    "backend": backend,
                }
                return True
            else:
                logger.error(
                    f"Failed to stop model: {model_name}, status: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"Error stopping model {model_name}: {e}")
            return False

    async def list_models(self, backend: str = None) -> dict:
        """List available models from the specified backend"""
        try:
            actual_backend = backend or self.active_backend

            if actual_backend == "ece":
                response = await self.ece_client.get("/v1/models")
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"ECE backend models request failed: {response.status_code} - {response.text}"
                    )
                    return {
                        "error": f"ECE backend error: {response.status_code}",
                        "data": [],
                    }
            elif actual_backend == "llama_cpp":
                response = await self.llama_cpp_client.get("/v1/models", timeout=10)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"llama.cpp backend models request failed: {response.status_code} - {response.text}"
                    )
                    return {
                        "error": f"llama.cpp backend error: {response.status_code}",
                        "data": [],
                    }
            else:
                return {"error": f"Unknown backend: {actual_backend}", "data": []}
        except Exception as e:
            logger.error(f"Error listing models: {str(e)}")
            return {"error": f"Error listing models: {str(e)}", "data": []}

    async def get_model_status(self, model_name: str = None) -> dict:
        """Get status of model(s)"""
        if model_name:
            return self._model_cache.get(
                model_name, {"status": "unknown", "backend": "unknown"}
            )
        else:
            return self._model_cache


class UnifiedModelProxy:
    """Unified proxy for routing between ECE and llama.cpp models"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.ece_client = httpx.AsyncClient(
            base_url=config.ece_endpoint, timeout=config.timeout
        )
        self.llama_cpp_client = httpx.AsyncClient(
            base_url=config.llama_cpp_endpoint, timeout=config.timeout
        )
        self.active_backend = config.active_backend

        # Initialize model lifecycle manager
        self.model_lifecycle_manager = ModelLifecycleManager(
            self.ece_client, self.llama_cpp_client, self.active_backend
        )

        # Initialize session manager for persisting state across backend switches
        self.session_manager = SessionManager()

    def set_backend(self, backend: str):
        """Switch the active backend"""
        if backend in ["ece", "llama_cpp"]:
            self.active_backend = backend
            # Update the model lifecycle manager's backend as well
            self.model_lifecycle_manager.active_backend = backend
            logger.info(f"Switched active backend to: {backend}")
            return True
        return False

    def get_active_backend(self) -> str:
        """Get the currently active backend"""
        return self.active_backend

    async def get_current_model(self) -> str:
        """Get the currently active model from the backend"""
        try:
            if self.active_backend == "ece":
                # Query the ECE for the current model info
                response = await self.ece_client.get("/models/current", timeout=5)
                if response.status_code == 200:
                    model_info = response.json()
                    return model_info.get("model", "unknown_model")
            elif self.active_backend == "llama_cpp":
                # Query the llama.cpp server for its current model
                response = await self.llama_cpp_client.get("/v1/models", timeout=5)
                if response.status_code == 200:
                    models_info = response.json()
                    # In llama.cpp, the current model isn't directly available from /models,
                    # so we might need to track it separately or use a different endpoint
                    data = models_info.get("data", [])
                    if data and isinstance(data, list):
                        # Return the first model as a placeholder
                        if len(data) > 0 and isinstance(data[0], dict):
                            return data[0].get("id", "unknown_model")
            return "unknown_model"
        except Exception as e:
            logger.warning(f"Could not get current model: {str(e)}")
            return "unknown_model"

    async def health_check(self, backend: str) -> bool:
        """Check if the specified backend is healthy"""
        try:
            if backend == "ece":
                response = await self.ece_client.get("/health", timeout=10)
            elif backend == "llama_cpp":
                # For llama.cpp, check if the models endpoint is available
                response = await self.llama_cpp_client.get("/v1/models", timeout=10)
            else:
                return False
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {backend}: {e}")
            return False

    async def route_request(
        self,
        path: str,
        method: str,
        body: Optional[Dict] = None,
        query_params: Optional[Dict] = None,
    ) -> Any:
        """Route the request to the appropriate backend with proper query parameter handling"""
        try:
            if self.active_backend == "ece":
                # For ECE backend, adjust paths that need /v1 prefix
                if path in ["/chat/completions", "/models", "/embeddings"]:
                    path = f"/v1{path}"

                if method.upper() == "GET":
                    # For GET requests, pass query parameters
                    response = await self.ece_client.get(path, params=query_params)
                elif method.upper() == "POST":
                    # For POST requests, send body if available
                    response = await self.ece_client.post(
                        path, json=body, params=query_params
                    )
                elif method.upper() == "PUT":
                    response = await self.ece_client.put(
                        path, json=body, params=query_params
                    )
                elif method.upper() == "DELETE":
                    response = await self.ece_client.delete(path, params=query_params)
                else:
                    raise HTTPException(
                        status_code=405, detail=f"Method {method} not allowed"
                    )
            elif self.active_backend == "llama_cpp":
                # For llama.cpp, we need different path handling
                if path == "/chat/completions":
                    path = "/v1/chat/completions"
                elif path == "/models":
                    path = "/v1/models"
                elif path == "/embeddings":
                    path = "/v1/embeddings"

                if method.upper() == "GET":
                    response = await self.llama_cpp_client.get(
                        path, params=query_params
                    )
                elif method.upper() == "POST":
                    response = await self.llama_cpp_client.post(
                        path, json=body, params=query_params
                    )
                elif method.upper() == "PUT":
                    response = await self.llama_cpp_client.put(
                        path, json=body, params=query_params
                    )
                elif method.upper() == "DELETE":
                    response = await self.llama_cpp_client.delete(
                        path, params=query_params
                    )
                else:
                    raise HTTPException(
                        status_code=405, detail=f"Method {method} not allowed"
                    )
            else:
                raise HTTPException(
                    status_code=500, detail=f"Unknown backend: {self.active_backend}"
                )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Backend request failed: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code, detail=response.text
                )
        except httpx.RequestError as e:
            logger.error(f"Request error in route_request: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Request error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in route_request: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    async def chat_completions_proxy(self, request_data: Dict) -> Any:
        """Specialized handler for chat completions that work with both backends"""
        if self.active_backend == "ece":
            # Transform OpenAI format to ECE format
            messages = request_data.get("messages", [])
            if messages:
                # Extract the last message as the prompt
                prompt = messages[-1].get("content", "")

                # Optionally include context from earlier messages
                context_messages = messages[:-1] if len(messages) > 1 else []

                ece_request = {
                    "prompt": prompt,
                    "context": [msg.get("content", "") for msg in context_messages],
                }

                # Add other parameters if needed
                if "temperature" in request_data:
                    ece_request["temperature"] = request_data["temperature"]

                return await self.route_request("/process_prompt", "POST", ece_request)
            else:
                raise HTTPException(status_code=400, detail="No messages provided")
        else:  # llama_cpp
            return await self.route_request("/chat/completions", "POST", request_data)

    async def models_list_proxy(self) -> Any:
        """Handler for listing available models"""
        if self.active_backend == "ece":
            return await self.route_request("/v1/models", "GET")
        else:  # llama_cpp
            return await self.route_request("/models", "GET")

    async def close(self):
        """Close the HTTP clients"""
        await self.ece_client.aclose()
        await self.llama_cpp_client.aclose()


# Global proxy instance
proxy: Optional[UnifiedModelProxy] = None

# Create a default config for the app when imported directly
default_config = ModelConfig()


def create_app(config: ModelConfig) -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(title="Unified Model Proxy", version="1.0.0")
    global proxy
    proxy = UnifiedModelProxy(config)

    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting up Unified Model Proxy")
        # Perform initial health checks
        ece_healthy = await proxy.health_check("ece")
        llama_cpp_healthy = await proxy.health_check("llama_cpp")
        logger.info(f"ECE health: {ece_healthy}, llama.cpp health: {llama_cpp_healthy}")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down Unified Model Proxy")
        if proxy:
            await proxy.close()

    @app.get("/health")
    async def health_check():
        """Health check endpoint for the proxy itself"""
        return {"status": "healthy", "active_backend": proxy.get_active_backend()}

    @app.get("/backend")
    async def get_backend():
        """Get the currently active backend"""
        return {"active_backend": proxy.get_active_backend()}

    @app.post("/backend/switch")
    async def switch_backend(request: Request):
        """Switch the active backend"""
        data = await request.json()
        backend = data.get("backend")
        session_id = data.get("session_id")  # Optional session ID to preserve context

        if proxy.set_backend(backend):
            response_data = {
                "message": f"Switched to {backend}",
                "active_backend": backend,
            }

            # If a session ID was provided, we can potentially preserve context across the switch
            if session_id:
                session = proxy.session_manager.get_session(session_id)
                if session:
                    # Add information about the backend switch to the session history
                    switch_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "event": "backend_switch",
                        "from_backend": proxy.active_backend,
                        "to_backend": backend,
                        "message": f"Switched from {proxy.active_backend} to {backend}",
                    }
                    proxy.session_manager.add_to_history(session_id, switch_entry)
                    response_data["session_context_preserved"] = True
                    response_data["session_id"] = session_id

            return response_data
        else:
            raise HTTPException(status_code=400, detail=f"Invalid backend: {backend}")

    @app.get("/v1/models")
    async def list_models():
        """List available models from the active backend"""
        return await proxy.models_list_proxy()

    @app.post("/v1/chat/completions")
    async def chat_completions_handler(request: Request):
        """Handle chat completions requests"""
        request_data = await request.json()
        return await proxy.chat_completions_proxy(request_data)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def proxy_all(path: str, request: Request):
        """Generic proxy for all other endpoints"""
        method = request.method
        body = None
        query_params = dict(request.query_params)

        if method in ["POST", "PUT"]:
            try:
                body = await request.json()
            except:
                # If JSON parsing fails, pass an empty body
                body = {}

        return await proxy.route_request(f"/{path}", method, body, query_params)

    # Model lifecycle management endpoints
    @app.post("/models/start")
    async def start_model(request: Request):
        """Start a model on a specific backend"""
        data = await request.json()
        model_name = data.get("model_name")
        backend = data.get("backend", proxy.get_active_backend())

        if not model_name:
            raise HTTPException(status_code=400, detail="Model name is required")

        success = await proxy.model_lifecycle_manager.start_model(model_name, backend)
        if success:
            return {
                "message": f"Successfully started {model_name} on {backend}",
                "success": True,
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to start {model_name} on {backend}"
            )

    @app.post("/models/stop")
    async def stop_model(request: Request):
        """Stop a model on a specific backend"""
        data = await request.json()
        model_name = data.get("model_name")
        backend = data.get("backend", proxy.get_active_backend())

        if not model_name:
            raise HTTPException(status_code=400, detail="Model name is required")

        success = await proxy.model_lifecycle_manager.stop_model(model_name, backend)
        if success:
            return {
                "message": f"Successfully stopped {model_name} on {backend}",
                "success": True,
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to stop {model_name} on {backend}"
            )

    @app.get("/models/available")
    async def list_available_models(backend: str = None):
        """List available models from a specific backend"""
        models_info = await proxy.model_lifecycle_manager.list_models(backend)
        return models_info

    @app.get("/models/status")
    async def get_model_status_api(model_name: str = None):
        """Get status of model(s)"""
        status = await proxy.get_model_status(model_name)
        return status

    # Tool access endpoints that work with both backends
    @app.get("/tools/discover")
    async def discover_tools():
        """Discover available tools from both backends"""
        try:
            # Get tools from ECE
            try:
                ece_response = await proxy.ece_client.get(
                    "/utcp"
                )  # ECE exposes UTCP endpoints
                ece_tools = (
                    ece_response.json()
                    if ece_response.status_code == 200
                    else {"tools": []}
                )
            except Exception as e:
                logger.warning(f"Could not fetch ECE tools: {e}")
                ece_tools = {"tools": []}

            # For llama.cpp, there are no tools by default, but we can return a standard response
            llama_cpp_tools = {"tools": []}

            return {
                "ece_tools": ece_tools,
                "llama_cpp_tools": llama_cpp_tools,
                "active_backend": proxy.get_active_backend(),
            }
        except Exception as e:
            logger.error(f"Error discovering tools: {e}")
            return {
                "ece_tools": {"tools": []},
                "llama_cpp_tools": {"tools": []},
                "error": str(e),
            }

    @app.post("/tools/call")
    async def call_tool_post(request: Request):
        """Call a specific tool on the appropriate backend (POST method)"""
        data = await request.json()
        tool_id = data.get("tool_id")
        tool_params = data.get("params", {})

        return await _handle_tool_call(tool_id, tool_params)

    @app.get("/tools/call")
    async def call_tool_get(tool_id: str, params: str = "{}"):
        """Call a specific tool on the appropriate backend (GET method)"""
        try:
            tool_params = json.loads(params) if params else {}
        except json.JSONDecodeError:
            tool_params = {}

        return await _handle_tool_call(tool_id, tool_params)

    async def _handle_tool_call(tool_id: str, tool_params: dict):
        """Internal function to handle tool calls from both GET and POST endpoints"""
        if not tool_id:
            raise HTTPException(status_code=400, detail="Tool ID is required")

        # Determine which backend should handle the tool
        # For now, we'll route to ECE since it has the tool system
        try:
            # Try calling the tool endpoint on ECE
            response = await proxy.ece_client.post(
                f"/tools/{tool_id}", json=tool_params
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"Tool {tool_id} not found on ECE, trying alternative approach"
                )
                # If the direct tool call fails, try to process through the orchestrator
                # with a special prompt asking it to use the tool
                tool_prompt = (
                    f"Please use the {tool_id} tool with parameters: {tool_params}"
                )
                result = await proxy.route_request(
                    "/process_prompt", "POST", {"prompt": tool_prompt}
                )
                return {"result": result, "tool_used": tool_id}
        except Exception as e:
            logger.error(f"Error calling tool {tool_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error calling tool {tool_id}: {str(e)}"
            )

    # Session management endpoints
    @app.post("/sessions/create")
    async def create_session(request: Request):
        """Create a new session"""
        data = await request.json()
        session_id = data.get("session_id")

        new_session_id = proxy.session_manager.create_session(session_id)
        return {"session_id": new_session_id, "message": "Session created successfully"}

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        """Get session information"""
        session = proxy.session_manager.get_session(session_id)
        if session:
            return session
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    @app.post("/sessions/{session_id}/context")
    async def update_session_context(session_id: str, request: Request):
        """Update session context"""
        data = await request.json()
        context = data.get("context", {})

        proxy.session_manager.update_session_context(session_id, context)
        return {"session_id": session_id, "message": "Context updated successfully"}

    @app.post("/sessions/{session_id}/history")
    async def add_to_session_history(session_id: str, request: Request):
        """Add to session history"""
        data = await request.json()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": data.get("role"),
            "content": data.get("content"),
            "backend": proxy.active_backend,
        }

        proxy.session_manager.add_to_history(session_id, entry)
        return {"session_id": session_id, "message": "History updated successfully"}

    @app.get("/sessions")
    async def list_sessions():
        """List all sessions"""
        session_ids = proxy.session_manager.list_sessions()
        return {"sessions": session_ids, "count": len(session_ids)}

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str):
        """Delete a session"""
        proxy.session_manager.delete_session(session_id)
        return {"session_id": session_id, "message": "Session deleted successfully"}

    return app


# Create the app instance using the default config
# This allows direct import of 'app' when using uvicorn
app = create_app(default_config)


async def main():
    """Run the proxy server"""
    config = ModelConfig()
    app = create_app(config)

    logger.info(f"Starting Unified Model Proxy on port 8080")
    logger.info(f"Active backend: {config.active_backend}")
    logger.info(f"ECE endpoint: {config.ece_endpoint}")
    logger.info(f"llama.cpp endpoint: {config.llama_cpp_endpoint}")

    # Run the server
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
