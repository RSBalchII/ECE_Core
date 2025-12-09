"""
Security middleware and utilities for ECE_Core.
Implements API key authentication and audit logging.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# API KEY AUTHENTICATION
# ============================================================================

security = HTTPBearer(auto_error=False)

async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> bool:
    """
    Verify API key from Authorization header.
    Returns True if authentication is disabled or key is valid.
    Raises HTTPException if authentication is required but fails.
    """
    # If auth not required, allow all requests
    if not settings.ece_require_auth:
        logger.info("Auth check skipped (ece_require_auth=False)")
        return True
    
    # If auth required but no credentials provided
    if credentials is None:
        logger.warning("Auth failed: No credentials provided")
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide API key in Authorization header."
        )
    
    # Verify API key
    if credentials.credentials != settings.ece_api_key:
        logger.warning(f"Auth failed: Invalid API key attempt. Received: {credentials.credentials[:4]}...")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return True

# ============================================================================
# AUDIT LOGGING
# ============================================================================

class AuditLogger:
    """Audit logger for security-sensitive operations."""
    
    def __init__(self):
        self.enabled = settings.audit_log_enabled
        self.log_path = Path(settings.audit_log_path)
        
        # Create log directory if needed
        if self.enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            # Initialize log file if it doesn't exist
            if not self.log_path.exists():
                self.log_path.touch()
    
    def log(self, event_type: str, details: dict):
        """Log a security event."""
        if not self.enabled:
            return
        
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "event_type": event_type,
                **details
            }
            
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(f"{log_entry}\n")
            
            # Also log to application logger
            logger.info(f"AUDIT: {event_type} - {details}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log_tool_call(self, session_id: str, tool_name: str, arguments: dict, result: str):
        """Log a tool execution."""
        if settings.audit_log_tool_calls:
            self.log("tool_call", {
                "session_id": session_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result_preview": str(result)[:100]
            })
    
    def log_memory_access(self, session_id: str, operation: str, details: dict):
        """Log memory access operations."""
        if settings.audit_log_memory_access:
            self.log("memory_access", {
                "session_id": session_id,
                "operation": operation,
                **details
            })
    
    def log_auth_attempt(self, success: bool, details: dict):
        """Log authentication attempts."""
        self.log("auth_attempt", {
            "success": success,
            **details
        })

# Global audit logger instance
audit_logger = AuditLogger()
