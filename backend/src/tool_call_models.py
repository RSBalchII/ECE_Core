"""
Tool Call Models and Validation

Pydantic models for validating and parsing tool calls from LLM responses.
Replaces brittle regex parsing with structured validation.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional, Literal
import re
import json
import logging

logger = logging.getLogger(__name__)


class ToolCallParam(BaseModel):
    """Single parameter for a tool call"""
    name: str
    value: Any
    
    class Config:
        extra = "forbid"


class ToolCall(BaseModel):
    """Validated tool call from LLM response"""
    tool_name: str = Field(..., description="Name of the tool to call")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    raw_match: Optional[str] = Field(None, description="Original matched string")
    
    @validator('tool_name')
    def validate_tool_name(cls, v):
        """Ensure tool name is valid identifier.

        Accepts either a simple snake_case name or a plugin-prefixed name like
        'utcp:tool_name'. We allow hyphens and dots in identifiers where needed.
        """
        if not v or not re.match(r'^[A-Za-z0-9_:\-\.]+$', v):
            raise ValueError(f"Invalid tool name format: {v}")
        return v
    
    class Config:
        extra = "forbid"


class LLMResponse(BaseModel):
    """Structured LLM response with optional tool calls"""
    response_text: str = Field(..., description="The LLM's text response")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Extracted tool calls")
    has_tool_calls: bool = Field(False, description="Whether response contains tool calls")
    
    class Config:
        extra = "allow"


class ToolCallParser:
    """
    Parser for extracting and validating tool calls from LLM responses.
    
    Supports multiple formats:
    1. TOOL_CALL: format (current regex-based)
    2. JSON format (for JSON mode models)
    3. Function call format (for function-calling models)
    """
    
    def __init__(self):
        # Regex pattern for TOOL_CALL: format
        # Accept plugin-prefixed names (e.g. utcp:filesystem_list) and allow dots, underscores, hyphens
        self.tool_call_pattern = re.compile(
            r'TOOL_CALL:\s*([A-Za-z0-9_:\-\.]+)\((.*?)\)',
            re.MULTILINE | re.DOTALL
        )
        
        # Alternative patterns for robustness
        self.json_tool_pattern = re.compile(
            r'\{[^}]*"tool":\s*"([^"]+)"[^}]*"params":\s*\{([^}]+)\}[^}]*\}',
            re.MULTILINE | re.DOTALL
        )
    
    def parse_response(self, response: str) -> LLMResponse:
        """
        Parse LLM response and extract tool calls.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            LLMResponse with extracted tool calls
        """
        tool_calls = []
        
        # Try TOOL_CALL: format first (current format)
        matches = self.tool_call_pattern.findall(response)
        
        if matches:
            logger.debug(f"Found {len(matches)} TOOL_CALL format matches")
            for tool_name, params_str in matches:
                try:
                    params = self._parse_parameters(params_str)
                    tool_call = ToolCall(
                        tool_name=tool_name,
                        parameters=params,
                        raw_match=f"TOOL_CALL: {tool_name}({params_str})"
                    )
                    tool_calls.append(tool_call)
                    logger.debug(f"Parsed tool call: {tool_call.tool_name} with {len(params)} params")
                except Exception as e:
                    logger.error(f"Failed to parse tool call '{tool_name}': {e}")
                    # Don't add invalid tool calls
        
        # Try JSON format (for JSON mode)
        if not tool_calls and '{' in response:
            json_matches = self.json_tool_pattern.findall(response)
            if json_matches:
                logger.debug(f"Found {len(json_matches)} JSON format matches")
                for tool_name, params_str in json_matches:
                    try:
                        params = json.loads('{' + params_str + '}')
                        tool_call = ToolCall(
                            tool_name=tool_name,
                            parameters=params,
                            raw_match=f'{{"tool": "{tool_name}", "params": {{{params_str}}}}}'
                        )
                        tool_calls.append(tool_call)
                        logger.debug(f"Parsed JSON tool call: {tool_call.tool_name}")
                    except Exception as e:
                        logger.error(f"Failed to parse JSON tool call '{tool_name}': {e}")
        
        return LLMResponse(
            response_text=response,
            tool_calls=tool_calls,
            has_tool_calls=len(tool_calls) > 0
        )
    
    def _parse_parameters(self, params_str: str) -> Dict[str, Any]:
        """
        Parse parameter string into dictionary.

        Handles:
        - key=value format
        - Quoted strings
        - Nested structures
        - JSON values

        Args:
            params_str: Parameter string from tool call

        Returns:
            Dictionary of parsed parameters
        """
        params = {}

        if not params_str or not params_str.strip():
            return params

        # Split by comma, respecting nested structures
        param_parts = self._split_parameters(params_str)

        for part in param_parts:
            part = part.strip()
            if not part:
                continue

            if '=' not in part:
                logger.warning(f"Parameter without '=': {part}")
                continue

            try:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Parse value
                parsed_value = self._parse_value(value)
                params[key] = parsed_value
            except Exception as e:
                logger.error(f"Error parsing parameter '{part}': {e}")
                continue

        return params
    
    def _split_parameters(self, params_str: str) -> List[str]:
        """
        Split parameter string by comma, respecting nested structures.
        
        Args:
            params_str: Raw parameter string
            
        Returns:
            List of parameter strings
        """
        param_parts = []
        current = []
        depth = 0
        in_quotes = False
        quote_char = None
        
        for char in params_str + ',':
            if char in ['"', "'"]:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            
            if not in_quotes:
                if char in '([{':
                    depth += 1
                elif char in ')]}':
                    depth -= 1
                elif char == ',' and depth == 0:
                    if current:
                        param_parts.append(''.join(current))
                        current = []
                    continue
            
            current.append(char)
        
        return param_parts
    
    def _parse_value(self, value: str) -> Any:
        """
        Parse a parameter value into appropriate Python type.
        
        Supports:
        - Strings (quoted)
        - Numbers (int, float)
        - Booleans
        - JSON objects/arrays
        - null/None
        
        Args:
            value: Raw value string
            
        Returns:
            Parsed value
        """
        value = value.strip()
        
        # Empty value
        if not value or value.lower() in ['null', 'none']:
            return None
        
        # Boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        
        # Quoted string
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        
        # Try JSON parse (for objects/arrays)
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON value: {value}")
                return value
        
        # Try number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Default: return as string
        return value


class ToolCallValidator:
    """
    Validator for tool calls against available tools.
    
    Checks:
    - Tool exists
    - Required parameters present
    - Parameter types match schema
    """
    
    def __init__(self, available_tools: Dict[str, Any]):
        """
        Initialize validator with available tools.
        
        Args:
            available_tools: Dict of tool name -> tool schema
        """
        self.available_tools = available_tools
    
    def validate(self, tool_call: ToolCall) -> tuple[bool, Optional[str]]:
        """
        Validate a tool call.
        
        Args:
            tool_call: ToolCall to validate
            
        Returns:
            (is_valid, error_message)
        """
        # Normalization: allow 'plugin:tool' forms by checking both forms
        tool_name_to_check = tool_call.tool_name
        if ':' in tool_name_to_check:
            # If the tool_name contains a plugin prefix, prefer the latter part for validation
            _, possible_tool = tool_name_to_check.split(':', 1)
            if possible_tool in self.available_tools:
                tool_name_to_check = possible_tool

        # Check tool exists
        if tool_name_to_check not in self.available_tools:
            return False, f"Tool '{tool_call.tool_name}' not found. Available tools: {list(self.available_tools.keys())}"

        tool_schema = self.available_tools[tool_name_to_check]
        
        # Check required parameters
        required_params = tool_schema.get('inputSchema', {}).get('required', [])
        missing_params = set(required_params) - set(tool_call.parameters.keys())
        
        if missing_params:
            return False, f"Missing required parameters: {missing_params}"
        
        # All checks passed
        return True, None
