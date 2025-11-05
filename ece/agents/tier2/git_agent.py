"""
Git Agent for the External Context Engine (ECE).

This module implements a Git agent that provides Git operations
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

    logger = get_logger("git")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Initialize FastAPI app
app = FastAPI(
    title="ECE Git Agent",
    description="The GitAgent provides Git operations as UTCP tools.",
    version="1.0.0",
)


class GitCloneRequest(BaseModel):
    """Request model for git clone operation."""

    repo_url: str
    destination_path: str


class GitStatusRequest(BaseModel):
    """Request model for git status operation."""

    repo_path: str


class GitLogRequest(BaseModel):
    """Request model for git log operation."""

    repo_path: str
    max_commits: int = 10


class GitAgent:
    """
    The GitAgent provides Git operations as UTCP tools.
    """

    def __init__(self):
        """Initialize the GitAgent."""
        self.name = "GitAgent"
        self.version = "1.0.0"

    def clone_repo(self, *, repo_url: str, destination_path: str) -> Dict[str, Any]:
        """
        Clone a Git repository.

        Args:
            repo_url: URL of the repository to clone
            destination_path: Local path where to clone the repository

        Returns:
            Dictionary containing the operation result
        """
        try:
            # Validate inputs
            if not repo_url:
                raise ValueError("Repository URL is required")
            if not destination_path:
                raise ValueError("Destination path is required")

            # Create destination directory if it doesn't exist
            os.makedirs(destination_path, exist_ok=True)

            # Execute git clone command
            result = subprocess.run(
                ["git", "clone", repo_url, destination_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "repo_url": repo_url,
                    "destination_path": os.path.abspath(destination_path),
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
            else:
                return {
                    "success": False,
                    "error": f"Git clone failed: {result.stderr}",
                    "repo_url": repo_url,
                    "destination_path": destination_path,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Git clone timed out after 5 minutes",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }

    def get_status(self, *, repo_path: str) -> Dict[str, Any]:
        """
        Get the status of a Git repository.

        Args:
            repo_path: Path to the Git repository

        Returns:
            Dictionary containing the repository status
        """
        try:
            # Validate that the path exists and is a Git repository
            if not os.path.exists(repo_path):
                raise FileNotFoundError(f"Path does not exist: {repo_path}")

            # Change to repository directory
            original_cwd = os.getcwd()
            os.chdir(repo_path)

            # Execute git status command
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Change back to original directory
            os.chdir(original_cwd)

            if result.returncode == 0:
                # Parse the status output
                lines = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
                changes = []

                for line in lines:
                    if line.strip():
                        status = line[:2].strip()
                        file_path = line[3:].strip()
                        changes.append({"status": status, "file": file_path})

                return {
                    "success": True,
                    "repo_path": os.path.abspath(repo_path),
                    "changes": changes,
                    "clean": len(changes) == 0,
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
            else:
                # Change back to original directory in case of error
                os.chdir(original_cwd)

                return {
                    "success": False,
                    "error": f"Git status failed: {result.stderr}",
                    "repo_path": repo_path,
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
        except subprocess.TimeoutExpired:
            # Change back to original directory in case of timeout
            os.chdir(original_cwd)

            return {
                "success": False,
                "error": "Git status timed out",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            # Change back to original directory in case of error
            os.chdir(original_cwd)

            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }

    def get_log(self, *, repo_path: str, max_commits: int = 10) -> Dict[str, Any]:
        """
        Get the commit log of a Git repository.

        Args:
            repo_path: Path to the Git repository
            max_commits: Maximum number of commits to retrieve

        Returns:
            Dictionary containing the commit log
        """
        try:
            # Validate that the path exists and is a Git repository
            if not os.path.exists(repo_path):
                raise FileNotFoundError(f"Path does not exist: {repo_path}")

            # Change to repository directory
            original_cwd = os.getcwd()
            os.chdir(repo_path)

            # Execute git log command with formatting
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--max-count={max_commits}",
                    "--pretty=format:%H|%an|%ae|%ad|%s",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Change back to original directory
            os.chdir(original_cwd)

            if result.returncode == 0:
                # Parse the log output
                lines = (
                    result.stdout.strip().split("\n") if result.stdout.strip() else []
                )
                commits = []

                for line in lines:
                    if line.strip():
                        parts = line.split("|", 4)
                        if len(parts) == 5:
                            commits.append(
                                {
                                    "hash": parts[0],
                                    "author_name": parts[1],
                                    "author_email": parts[2],
                                    "date": parts[3],
                                    "subject": parts[4],
                                }
                            )

                return {
                    "success": True,
                    "repo_path": os.path.abspath(repo_path),
                    "commits": commits,
                    "count": len(commits),
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
            else:
                # Change back to original directory in case of error
                os.chdir(original_cwd)

                return {
                    "success": False,
                    "error": f"Git log failed: {result.stderr}",
                    "repo_path": repo_path,
                    "timestamp": __import__("datetime").datetime.now().isoformat(),
                }
        except subprocess.TimeoutExpired:
            # Change back to original directory in case of timeout
            os.chdir(original_cwd)

            return {
                "success": False,
                "error": "Git log timed out",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            # Change back to original directory in case of error
            os.chdir(original_cwd)

            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }


# Create an instance of the GitAgent
git_agent = GitAgent()


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Git Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/clone")
async def clone_get_endpoint(repo_url: str, destination_path: str):
    """
    GET endpoint to clone a Git repository.

    Args:
        repo_url: URL of the repository to clone
        destination_path: Local path where to clone the repository

    Returns:
        Clone operation result
    """
    try:
        result = git_agent.clone_repo(
            repo_url=repo_url, destination_path=destination_path
        )
        return result
    except Exception as e:
        logger.error(f"Error cloning repository: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clone")
async def clone_post_endpoint(request: Request):
    """
    POST endpoint to clone a Git repository that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Clone operation result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            repo_url = body.get("repo_url")
            destination_path = body.get("destination_path")
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                repo_url = form.get("repo_url")
                destination_path = form.get("destination_path")
            except:
                # If both fail, use query parameters
                repo_url = request.query_params.get("repo_url")
                destination_path = request.query_params.get("destination_path")

        if not repo_url:
            raise HTTPException(status_code=400, detail="repo_url is required")
        if not destination_path:
            raise HTTPException(status_code=400, detail="destination_path is required")

        result = git_agent.clone_repo(
            repo_url=repo_url, destination_path=destination_path
        )
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error cloning repository: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def status_get_endpoint(repo_path: str):
    """
    GET endpoint to get the status of a Git repository.

    Args:
        repo_path: Path to the Git repository

    Returns:
        Repository status result
    """
    try:
        result = git_agent.get_status(repo_path=repo_path)
        return result
    except Exception as e:
        logger.error(f"Error getting repository status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/status")
async def status_post_endpoint(request: Request):
    """
    POST endpoint to get the status of a Git repository that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Repository status result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            repo_path = body.get("repo_path")
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                repo_path = form.get("repo_path")
            except:
                # If both fail, use query parameters
                repo_path = request.query_params.get("repo_path")

        if not repo_path:
            raise HTTPException(status_code=400, detail="repo_path is required")

        result = git_agent.get_status(repo_path=repo_path)
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting repository status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/log")
async def log_get_endpoint(repo_path: str, max_commits: int = 10):
    """
    GET endpoint to get the commit log of a Git repository.

    Args:
        repo_path: Path to the Git repository
        max_commits: Maximum number of commits to retrieve

    Returns:
        Commit log result
    """
    try:
        result = git_agent.get_log(repo_path=repo_path, max_commits=max_commits)
        return result
    except Exception as e:
        logger.error(f"Error getting repository log: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/log")
async def log_post_endpoint(request: Request):
    """
    POST endpoint to get the commit log of a Git repository that handles both JSON body and form data.

    Args:
        request: Request object that may contain JSON body or form data

    Returns:
        Commit log result
    """
    try:
        # Try to get parameters from JSON body first
        try:
            body = await request.json()
            repo_path = body.get("repo_path")
            max_commits = body.get("max_commits", 10)
        except:
            # If JSON parsing fails, try to get from form data
            try:
                form = await request.form()
                repo_path = form.get("repo_path")
                max_commits = int(form.get("max_commits", 10))
            except:
                # If both fail, use query parameters
                repo_url = request.query_params.get("repo_path")
                max_commits = int(request.query_params.get("max_commits", 10))

        if not repo_path:
            raise HTTPException(status_code=400, detail="repo_path is required")

        result = git_agent.get_log(repo_path=repo_path, max_commits=max_commits)
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting repository log: {str(e)}")
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
                name="clone_repo",
                description="Clone a Git repository",
                tags=["git", "repository", "clone"],
                inputs={
                    "type": "object",
                    "properties": {
                        "repo_url": {
                            "type": "string",
                            "description": "URL of the repository to clone",
                        },
                        "destination_path": {
                            "type": "string",
                            "description": "Local path where to clone the repository",
                        },
                    },
                    "required": ["repo_url", "destination_path"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the operation was successful",
                        },
                        "repo_url": {
                            "type": "string",
                            "description": "URL of the cloned repository",
                        },
                        "destination_path": {
                            "type": "string",
                            "description": "Local path where the repository was cloned",
                        },
                        "stdout": {
                            "type": "string",
                            "description": "Standard output of the git clone command",
                        },
                        "stderr": {
                            "type": "string",
                            "description": "Standard error output of the git clone command",
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
                    name="git_clone_repo",
                    call_template_type="http",
                    url="http://localhost:8009/clone",
                    http_method="POST",
                    content_type="application/json",
                ),
            ),
            Tool(
                name="get_status",
                description="Get the status of a Git repository",
                tags=["git", "repository", "status"],
                inputs={
                    "type": "object",
                    "properties": {
                        "repo_path": {
                            "type": "string",
                            "description": "Path to the Git repository",
                        }
                    },
                    "required": ["repo_path"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the operation was successful",
                        },
                        "repo_path": {
                            "type": "string",
                            "description": "Absolute path of the repository",
                        },
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "status": {
                                        "type": "string",
                                        "description": "Status indicator (M for modified, A for added, D for deleted, etc.)",
                                    },
                                    "file": {
                                        "type": "string",
                                        "description": "File path relative to repository root",
                                    },
                                },
                            },
                            "description": "List of changes in the repository",
                        },
                        "clean": {
                            "type": "boolean",
                            "description": "Whether the repository is clean (no changes)",
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
                    name="git_get_status",
                    call_template_type="http",
                    url="http://localhost:8009/status",
                    http_method="POST",
                    content_type="application/json",
                ),
            ),
            Tool(
                name="get_log",
                description="Get the commit log of a Git repository",
                tags=["git", "repository", "log"],
                inputs={
                    "type": "object",
                    "properties": {
                        "repo_path": {
                            "type": "string",
                            "description": "Path to the Git repository",
                        },
                        "max_commits": {
                            "type": "integer",
                            "description": "Maximum number of commits to retrieve",
                            "default": 10,
                        },
                    },
                    "required": ["repo_path"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the operation was successful",
                        },
                        "repo_path": {
                            "type": "string",
                            "description": "Absolute path of the repository",
                        },
                        "commits": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "hash": {
                                        "type": "string",
                                        "description": "Commit hash",
                                    },
                                    "author_name": {
                                        "type": "string",
                                        "description": "Author name",
                                    },
                                    "author_email": {
                                        "type": "string",
                                        "description": "Author email",
                                    },
                                    "date": {
                                        "type": "string",
                                        "description": "Commit date",
                                    },
                                    "subject": {
                                        "type": "string",
                                        "description": "Commit subject/message",
                                    },
                                },
                            },
                            "description": "List of commits",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of commits retrieved",
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
                    name="git_get_log",
                    call_template_type="http",
                    url="http://localhost:8009/log",
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
        "git_agent:app", host="0.0.0.0", port=8009, reload=True, log_level="info"
    )
