"""
Custom exceptions for ECE_Core and Anchor

Simple, focused exception hierarchy for better error handling.
"""


class ECEError(Exception):
    """Base exception for all ECE_Core errors"""
    pass


class ConfigurationError(ECEError):
    """Configuration loading or validation failed"""
    pass


class MemoryError(ECEError):
    """Memory system (Redis/Neo4j) errors"""
    pass


class LLMError(ECEError):
    """LLM communication errors"""
    pass


class ToolCallError(ECEError):
    """Tool call parsing or execution errors"""
    pass


class MCPError(ECEError):
    """MCP server connection or tool errors"""
    pass


class ValidationError(ECEError):
    """Input validation errors"""
    pass
