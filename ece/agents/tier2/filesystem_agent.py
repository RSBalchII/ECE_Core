"""
Filesystem Agent for the External Context Engine (ECE).

This module implements the FileSystemAgent, which provides filesystem operations
as UTCP tools.
"""

import os
import httpx
from typing import Dict, Any, List
import asyncio
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import logging
import subprocess
import json

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("filesystem")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Initialize FastAPI app
app = FastAPI(
    title="ECE FileSystem Agent",
    description="The FileSystemAgent provides filesystem operations as UTCP tools.",
    version="1.0.0",
)


class ListDirectoryRequest(BaseModel):
    """Request model for list_directory operation."""

    path: str = "."
    include_hidden: bool = False


class ReadFileRequest(BaseModel):
    """Request model for read_file operation."""

    file_path: str


class WriteFileRequest(BaseModel):
    """Request model for write_file operation."""

    file_path: str
    content: str


class ExecuteCommandRequest(BaseModel):
    """Request model for execute_command operation."""

    command: str


class FileSystemAgent:
    """
    The FileSystemAgent provides filesystem operations as UTCP tools.
    """

    def __init__(self):
        """Initialize the FileSystemAgent."""
        self.name = "FileSystemAgent"
        self.version = "1.0.0"

    def list_directory(
        self, *, path: str = ".", include_hidden: bool = False
    ) -> Dict[str, Any]:
        """
        List the contents of a directory.

        Args:
            path: The directory path to list
            include_hidden: Whether to include hidden files and directories

        Returns:
            Dictionary containing the directory listing
        """
        try:
            # Validate that the path exists and is a directory
            if not os.path.exists(path):
                raise FileNotFoundError(f"Path does not exist: {path}")
            if not os.path.isdir(path):
                raise NotADirectoryError(f"Path is not a directory: {path}")

            # Get the directory listing
            all_items = os.listdir(path)

            # Filter out hidden files if requested
            if not include_hidden:
                items = [item for item in all_items if not item.startswith(".")]
            else:
                items = all_items

            # Categorize items as files or directories
            files = []
            directories = []

            for item in items:
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    directories.append(item)
                else:
                    files.append(item)

            return {
                "success": True,
                "path": os.path.abspath(path),
                "directories": sorted(directories),
                "files": sorted(files),
                "total_items": len(directories) + len(files),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }

    def read_file(self, *, file_path: str) -> Dict[str, Any]:
        """
        Read the contents of a file.

        Args:
            file_path: The path to the file to read

        Returns:
            Dictionary containing the file content
        """
        try:
            # Validate that the path exists and is a file
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File does not exist: {file_path}")
            if not os.path.isfile(file_path):
                raise IsADirectoryError(f"Path is not a file: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            return {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "content": content,
                "size": len(content),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }

    def write_file(self, *, file_path: str, content: str) -> Dict[str, Any]:
        """
        Write content to a file.

        Args:
            file_path: The path to the file to write
            content: The content to write to the file

        Returns:
            Dictionary containing the operation result
        """
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "size": len(content),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }

    def execute_command(self, *, command: str) -> Dict[str, Any]:
        """
        Execute a shell command.

        Args:
            command: The shell command to execute

        Returns:
            Dictionary containing the command execution result
        """
        try:
            # Execute the command and capture output
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # Set a timeout to prevent hanging
            )

            return {
                "success": result.returncode == 0,
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out after 30 seconds",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }


# Create an instance of the FileSystemAgent
fs_agent = FileSystemAgent()


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE FileSystem Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/list_directory")
async def list_directory_get_endpoint(path: str = ".", include_hidden: bool = False):
    """
    GET endpoint to list directory contents.

    Args:
        path: The directory path to list
        include_hidden: Whether to include hidden files and directories

    Returns:
        Directory listing result
    """
    try:
        result = fs_agent.list_directory(path=path, include_hidden=include_hidden)
        return result
    except Exception as e:
        logger.error(f"Error listing directory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/list_directory")
async def list_directory_post_endpoint(request: Request):
    """
    POST endpoint to list directory contents that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Directory listing result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            path = body.get("path", ".")
            include_hidden = body.get("include_hidden", False)
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                path = form.get("path", ".")
                include_hidden = form.get("include_hidden", "false").lower() == "true"
            except:
                # If both fail, use query parameters or defaults
                path = request.query_params.get("path", ".")
                include_hidden = (
                    request.query_params.get("include_hidden", "false").lower()
                    == "true"
                )

        result = fs_agent.list_directory(path=path, include_hidden=include_hidden)
        return result
    except Exception as e:
        logger.error(f"Error listing directory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/read_file")
async def read_file_get_endpoint(file_path: str):
    """
    GET endpoint to read file contents.

    Args:
        file_path: The path to the file to read

    Returns:
        File content result
    """
    try:
        result = fs_agent.read_file(file_path=file_path)
        return result
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/read_file")
async def read_file_post_endpoint(request: Request):
    """
    POST endpoint to read file contents that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        File content result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            file_path = body.get("file_path")
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                file_path = form.get("file_path")
            except:
                # If both fail, use query parameters
                file_path = request.query_params.get("file_path")

        if not file_path:
            raise HTTPException(status_code=400, detail="file_path is required")

        result = fs_agent.read_file(file_path=file_path)
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/write_file")
async def write_file_get_endpoint(file_path: str, content: str):
    """
    GET endpoint to write content to a file.

    Args:
        file_path: The path to the file to write
        content: The content to write to the file

    Returns:
        Write operation result
    """
    try:
        result = fs_agent.write_file(file_path=file_path, content=content)
        return result
    except Exception as e:
        logger.error(f"Error writing file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/write_file")
async def write_file_post_endpoint(request: Request):
    """
    POST endpoint to write content to a file that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Write operation result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            file_path = body.get("file_path")
            content = body.get("content")
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                file_path = form.get("file_path")
                content = form.get("content")
            except:
                # If both fail, use query parameters
                file_path = request.query_params.get("file_path")
                content = request.query_params.get("content")

        if not file_path:
            raise HTTPException(status_code=400, detail="file_path is required")
        if content is None:
            raise HTTPException(status_code=400, detail="content is required")

        result = fs_agent.write_file(file_path=file_path, content=content)
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error writing file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/execute_command")
async def execute_command_get_endpoint(command: str):
    """
    GET endpoint to execute a shell command.

    Args:
        command: The shell command to execute

    Returns:
        Command execution result
    """
    try:
        result = fs_agent.execute_command(command=command)
        return result
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute_command")
async def execute_command_post_endpoint(request: Request):
    """
    POST endpoint to execute a shell command that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Command execution result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            command = body.get("command")
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                command = form.get("command")
            except:
                # If both fail, use query parameters
                command = request.query_params.get("command")

        if not command:
            raise HTTPException(status_code=400, detail="command is required")

        result = fs_agent.execute_command(command=command)
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual endpoint for tool discovery."""
    # Create UTCP Manual with tools provided by this agent
    manual = UtcpManual(
        manual_version="1.0.0",
        utcp_version="1.0.2",
        tools=[
            Tool(
                name="list_directory",
                description="List the contents of a directory",
                tags=["filesystem", "directory", "list"],
                inputs={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The directory path to list",
                            "default": ".",
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Whether to include hidden files and directories",
                            "default": False,
                        },
                    },
                    "required": [],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the operation was successful",
                        },
                        "path": {
                            "type": "string",
                            "description": "The absolute path of the directory",
                        },
                        "directories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of subdirectories",
                        },
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of files",
                        },
                        "total_items": {
                            "type": "integer",
                            "description": "Total number of items in the directory",
                        },
                        "error": {
                            "type": "string",
                            "description": "Error message if operation failed",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp of the operation",
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="filesystem_list_directory",
                    call_template_type="http",
                    url="http://localhost:8006/list_directory",
                    http_method="POST",
                    content_type="application/json",
                ),
            ),
            Tool(
                name="read_file",
                description="Read the contents of a file",
                tags=["filesystem", "file", "read"],
                inputs={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file to read",
                        }
                    },
                    "required": ["file_path"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the operation was successful",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "The absolute path of the file",
                        },
                        "content": {
                            "type": "string",
                            "description": "The content of the file",
                        },
                        "size": {
                            "type": "integer",
                            "description": "Size of the file in characters",
                        },
                        "error": {
                            "type": "string",
                            "description": "Error message if operation failed",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp of the operation",
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="filesystem_read_file",
                    call_template_type="http",
                    url="http://localhost:8006/read_file",
                    http_method="POST",
                    content_type="application/json",
                ),
            ),
            Tool(
                name="write_file",
                description="Write content to a file",
                tags=["filesystem", "file", "write"],
                inputs={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file",
                        },
                    },
                    "required": ["file_path", "content"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the operation was successful",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "The absolute path of the file",
                        },
                        "size": {
                            "type": "integer",
                            "description": "Size of the written content in characters",
                        },
                        "error": {
                            "type": "string",
                            "description": "Error message if operation failed",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp of the operation",
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="filesystem_write_file",
                    call_template_type="http",
                    url="http://localhost:8006/write_file",
                    http_method="POST",
                    content_type="application/json",
                ),
            ),
            Tool(
                name="execute_command",
                description="Execute a shell command",
                tags=["filesystem", "command", "shell"],
                inputs={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute",
                        }
                    },
                    "required": ["command"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the command executed successfully",
                        },
                        "command": {
                            "type": "string",
                            "description": "The executed command",
                        },
                        "stdout": {
                            "type": "string",
                            "description": "Standard output of the command",
                        },
                        "stderr": {
                            "type": "string",
                            "description": "Standard error output of the command",
                        },
                        "return_code": {
                            "type": "integer",
                            "description": "Return code of the command",
                        },
                        "error": {
                            "type": "string",
                            "description": "Error message if operation failed",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp of the operation",
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="filesystem_execute_command",
                    call_template_type="http",
                    url="http://localhost:8006/execute_command",
                    http_method="POST",
                    content_type="application/json",
                ),
            ),
        ],
    )
    return manual


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "filesystem_agent:app", host="0.0.0.0", port=8006, reload=True, log_level="info"
    )
