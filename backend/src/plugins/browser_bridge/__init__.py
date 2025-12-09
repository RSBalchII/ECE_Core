"""
Browser Bridge Plugin - Chrome Extension Integration for ECE

This plugin provides a bridge between web browsers and the Executive Cognitive Enhancement system.
It includes both the backend API endpoints and the Chrome extension source code.
"""
from .plugin import router

__all__ = ["router"]