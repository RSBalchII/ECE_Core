"""
Test suite for ECE_Core security features.
Tests API authentication, audit logging, and security middleware.
"""
import pytest
import asyncio
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from src.security import verify_api_key, audit_logger, AuditLogger
from src.config import settings
from pathlib import Path
import tempfile
import os

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_audit_log():
    """Create temporary audit log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)

@pytest.fixture
def test_audit_logger(temp_audit_log):
    """Create audit logger instance for testing."""
    original_path = settings.audit_log_path
    original_enabled = settings.audit_log_enabled
    
    settings.audit_log_path = temp_audit_log
    settings.audit_log_enabled = True
    
    logger = AuditLogger()
    
    yield logger
    
    # Restore original settings
    settings.audit_log_path = original_path
    settings.audit_log_enabled = original_enabled

# ============================================================================
# API KEY AUTHENTICATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_verify_api_key_auth_disabled():
    """Test that auth bypass works when disabled."""
    original = settings.ece_require_auth
    settings.ece_require_auth = False
    
    result = await verify_api_key(None)
    assert result is True
    
    settings.ece_require_auth = original

@pytest.mark.asyncio
async def test_verify_api_key_no_credentials():
    """Test that missing credentials raise 401."""
    original_auth = settings.ece_require_auth
    settings.ece_require_auth = True
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(None)
    
    assert exc_info.value.status_code == 401
    
    settings.ece_require_auth = original_auth

@pytest.mark.asyncio
async def test_verify_api_key_invalid():
    """Test that invalid key raises 403."""
    original_auth = settings.ece_require_auth
    original_key = settings.ece_api_key
    
    settings.ece_require_auth = True
    settings.ece_api_key = "correct-key"
    
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="wrong-key"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(credentials)
    
    assert exc_info.value.status_code == 403
    
    settings.ece_require_auth = original_auth
    settings.ece_api_key = original_key

@pytest.mark.asyncio
async def test_verify_api_key_valid():
    """Test that valid key succeeds."""
    original_auth = settings.ece_require_auth
    original_key = settings.ece_api_key
    
    settings.ece_require_auth = True
    settings.ece_api_key = "test-key"
    
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-key"
    )
    
    result = await verify_api_key(credentials)
    assert result is True
    
    settings.ece_require_auth = original_auth
    settings.ece_api_key = original_key

# ============================================================================
# AUDIT LOGGING TESTS
# ============================================================================

def test_audit_logger_init(temp_audit_log):
    """Test audit logger initialization."""
    settings.audit_log_enabled = True
    settings.audit_log_path = temp_audit_log
    
    logger = AuditLogger()
    assert logger.enabled is True
    assert logger.log_path == Path(temp_audit_log)

def test_audit_logger_log_event(test_audit_logger, temp_audit_log):
    """Test logging a generic event."""
    test_audit_logger.log("test_event", {"key": "value"})
    
    # Read log file
    with open(temp_audit_log, 'r') as f:
        log_content = f.read()
    
    assert "test_event" in log_content
    assert "key" in log_content

def test_audit_logger_tool_call(test_audit_logger, temp_audit_log):
    """Test logging tool calls."""
    original = settings.audit_log_tool_calls
    settings.audit_log_tool_calls = True
    
    test_audit_logger.log_tool_call(
        session_id="test-session",
        tool_name="test_tool",
        arguments={"arg1": "value1"},
        result="success"
    )
    
    with open(temp_audit_log, 'r') as f:
        log_content = f.read()
    
    assert "tool_call" in log_content
    assert "test_tool" in log_content
    
    settings.audit_log_tool_calls = original

def test_audit_logger_disabled(temp_audit_log):
    """Test that disabled logger doesn't write."""
    settings.audit_log_enabled = False
    settings.audit_log_path = temp_audit_log
    
    logger = AuditLogger()
    logger.log("test_event", {"key": "value"})
    
    # Log file should be empty or not contain event
    if os.path.exists(temp_audit_log):
        with open(temp_audit_log, 'r') as f:
            log_content = f.read()
        assert "test_event" not in log_content

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_audit_logger_creates_directory():
    """Test that audit logger creates log directory if missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "subdir" / "audit.log"
        
        settings.audit_log_enabled = True
        settings.audit_log_path = str(log_path)
        
        logger = AuditLogger()
        logger.log("test", {})
        
        assert log_path.exists()
        assert log_path.parent.exists()
