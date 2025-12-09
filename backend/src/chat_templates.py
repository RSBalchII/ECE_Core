"""
Chat template management for different LLM models.
Supports various chat formats including Qwen3, Gemma3, and standard OpenAI format.
"""
from typing import List, Dict, Optional
from jinja2 import Template


class ChatTemplate:
    """Base class for chat templates"""

    def format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None) -> str:
        raise NotImplementedError()


class OpenAIChatTemplate(ChatTemplate):
    """Standard OpenAI chat format"""

    def format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None) -> str:
        # For API compatibility, we just return the messages as-is with system prompt added
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)
        return formatted_messages


class Qwen3ChatTemplate(ChatTemplate):
    """Qwen3 chat template format - direct implementation"""

    def format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None) -> str:
        # Add system prompt to messages if provided
        all_messages = []
        if system_prompt and not (messages and messages[0].get("role") == "system"):
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        result = []

        if tools:
            # Include tools in the system message
            result.append("SYSTEM")
            if all_messages and all_messages[0].get("role") == "system":
                result.append(all_messages[0]["content"])
                result.append("")  # Empty line
            result.append("In this environment you have access to a set of tools you can use to answer the user's question. You can use one tool per message, and will receive the result of that tool use in the user's response. You use tools step-by-step to accomplish a given task, with each tool use informed by the result of the previous tool use.")
            result.append("")
            result.append("Tool Use Rules")
            result.append("Here are the rules you should always follow to solve your task:")
            result.append("1. Always use the right arguments for the tools. Never use variable names as the action arguments, use the value instead.")
            result.append("2. Call a tool only when needed: do not call the search agent if you do not need information, try to solve the task yourself.")
            result.append("3. If no tool call is needed, just answer the question directly.")
            result.append("4. Never re-do a tool call that you previously did with the exact same parameters.")
            result.append("5. When you have sufficient information to answer the user's question, answer directly without using more tools.")
            result.append("Now Begin!")
            result.append("")
            result.append("# Tools")
            result.append("")
            result.append("You may call one or more functions to assist with the user query.")
            result.append("")
            result.append("You are provided with function signatures within <tools></tools> XML tags:")
            result.append("<tools>")
            for tool in tools:
                import json
                result.append(json.dumps(tool))
            result.append("</tools>")
            result.append("")
            result.append("To use a tool, respond with: TOOL_CALL: tool_name(param1=value1, param2=value2)")
            result.append("Do not use any other format for tool calls. Do not generate JSON objects for tools.")
            result.append("")


            # Process remaining messages (skip the system message we already handled)
            start_idx = 1 if all_messages and all_messages[0].get("role") == "system" else 0
            for i, message in enumerate(all_messages[start_idx:]):
                role = message.get("role", "")
                content = message.get("content", "")

                if role == "user" or (role == "system" and i > 0):  # Additional system messages after first
                    result.append(f"USER")
                    result.append(content)
                    result.append("")
                elif role == "assistant":
                    result.append("ASSISTANT")
                    result.append(content)
                    result.append("")
                elif role == "tool":
                    result.append("USER")
                    result.append(content)
                    result.append("")

        # No tools version
        if all_messages and all_messages[0].get("role") == "system":
            result.append("SYSTEM")
            result.append(all_messages[0]["content"])
            result.append("USER")
        else:
            result.append("SYSTEM")
            result.append("You are a helpful assistant.")
            result.append("USER")

        # Process remaining messages
        start_idx = 1 if all_messages and all_messages[0].get("role") == "system" else 0
        for message in all_messages[start_idx:]:
            role = message.get("role", "")
            content = message.get("content", "")

            if role == "user":
                result.append(content)
                result.append("ASSISTANT")
            elif role == "assistant":
                result.append(content)
                result.append("")
            elif role == "tool":
                result.append(content)
                result.append("USER")

        return "\n".join(result).strip()


class Qwen3ThinkingChatTemplate(ChatTemplate):
    """Qwen3 chat template with explicit thinking token support"""

    def format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None) -> str:
        # Add system prompt to messages if provided
        all_messages = []
        if system_prompt and not (messages and messages[0].get("role") == "system"):
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        # Build the formatted conversation with explicit thinking tokens
        result = []

        if tools:
            # Include tools in the system message
            result.append("SYSTEM")
            if all_messages and all_messages[0].get("role") == "system":
                result.append(all_messages[0]["content"])
                result.append("")  # Empty line
            result.append("In this environment you have access to a set of tools you can use to answer the user's question. You can use one tool per message, and will receive the result of that tool use in the user's response. You use tools step-by-step to accomplish a given task, with each tool use informed by the result of the previous tool use.")
            result.append("")
            result.append("Tool Use Rules")
            result.append("Here are the rules you should always follow to solve your task:")
            result.append("1. Always use the right arguments for the tools. Never use variable names as the action arguments, use the value instead.")
            result.append("2. Call a tool only when needed: do not call the search agent if you do not need information, try to solve the task yourself.")
            result.append("3. If no tool call is needed, just answer the question directly.")
            result.append("4. Never re-do a tool call that you previously did with the exact same parameters.")
            result.append("5. When you have sufficient information to answer the user's question, answer directly without using more tools.")
            result.append("Now Begin!")
            result.append("")
            result.append("# Tools")
            result.append("")
            result.append("You may call one or more functions to assist with the user query.")
            result.append("")
            result.append("You are provided with function signatures within <tools></tools> XML tags:")
            result.append("<tools>")
            for tool in tools:
                import json
                result.append(json.dumps(tool))
            result.append("</tools>")
            result.append("")
            result.append("To use a tool, respond with: TOOL_CALL: tool_name(param1=value1, param2=value2)")
            result.append("Do not use any other format for tool calls. Do not generate JSON objects for tools.")
            result.append("")


            # Process remaining messages (skip the system message we already handled)
            start_idx = 1 if all_messages and all_messages[0].get("role") == "system" else 0
            for i, message in enumerate(all_messages[start_idx:]):
                role = message.get("role", "")
                content = message.get("content", "")

                if role == "user" or (role == "system" and i > 0):  # Additional system messages after first
                    result.append(f"USER")
                    result.append(content)
                    result.append("")
                elif role == "assistant":
                    result.append("ASSISTANT")
                    result.append(content)
                    result.append("")
                elif role == "tool":
                    result.append("USER")
                    result.append(content)
                    result.append("")

        else:
            # No tools version - with explicit thinking token support
            if all_messages and all_messages[0].get("role") == "system":
                result.append("SYSTEM")
                result.append(all_messages[0]["content"])
                result.append("USER")
            else:
                result.append("SYSTEM")
                result.append("You are a helpful assistant.")
                result.append("USER")

            # Process remaining messages
            start_idx = 1 if all_messages and all_messages[0].get("role") == "system" else 0
            for message in all_messages[start_idx:]:
                role = message.get("role", "")
                content = message.get("content", "")

                if role == "user":
                    result.append(content)
                    result.append("ASSISTANT")
                elif role == "assistant":
                    result.append(content)
                    result.append("")
                elif role == "tool":
                    result.append(content)
                    result.append("USER")

        return "\n".join(result).strip()


class Gemma3ChatTemplate(ChatTemplate):
    """Gemma-3 chat template for creative writing - with minimal tool support"""

    def format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None) -> str:
        # Gemma uses the <start_of_turn> and <end_of_turn> format
        result = []

        # Handle system prompt and tools in a simple way for Gemma
        combined_system = ""
        if system_prompt:
            combined_system = system_prompt

        if tools and len(tools) > 0:
            # Add minimal tool instructions to system message
            tool_desc = "\n\nYou have access to tools. To use a tool, respond with: TOOL_CALL: tool_name(param1=value1, param2=value2)"
            combined_system += tool_desc

        if combined_system:
            result.append(f"<start_of_turn>system")
            result.append(combined_system)
            result.append(f"<end_of_turn>")

        # Process messages
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            if role == "user":
                result.append(f"<start_of_turn>user")
                result.append(content)
                result.append(f"<end_of_turn>")
            elif role == "assistant":
                result.append(f"<start_of_turn>model")
                result.append(content)
                result.append(f"<end_of_turn>")
            elif role == "tool":
                # Handle tool responses by presenting them back to the user
                result.append(f"<start_of_turn>user")
                result.append(f"Tool result: {content}")
                result.append(f"<end_of_turn>")
            elif role == "system" and not system_prompt:  # Additional system messages
                result.append(f"<start_of_turn>system")
                result.append(content)
                result.append(f"<end_of_turn>")

        # Add final model turn marker for generation
        result.append(f"<start_of_turn>model")

        return "\n".join(result)


class MinimalChatTemplate(ChatTemplate):
    """Minimal template for simpler models that get confused by complex formatting"""

    def format_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None, tools: Optional[List[Dict]] = None) -> str:
        result = []

        # Simple system message
        if system_prompt:
            result.append(f"SYSTEM: {system_prompt}")

        # Add minimal tool instruction if tools are available
        if tools:
            result.append("You can use tools. Format: TOOL_CALL: tool_name(param=value)")

        # Process messages in a simple format
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            if role == "user":
                result.append(f"USER: {content}")
            elif role == "assistant":
                result.append(f"ASSISTANT: {content}")
            elif role == "tool":
                result.append(f"TOOL RESULT: {content}")

        # Add final prompt for assistant response
        result.append("ASSISTANT:")

        return "\n".join(result)


class ChatTemplateManager:
    """Manager for different chat templates"""

    def __init__(self):
        self.templates = {
            "openai": OpenAIChatTemplate(),
            "qwen3": Qwen3ChatTemplate(),
            "qwen3-thinking": Qwen3ThinkingChatTemplate(),  # Enhanced template with thinking token support
            "gemma3": Gemma3ChatTemplate(),  # Added Gemma 3 template
            "minimal": MinimalChatTemplate(),  # Minimal template for simpler models
        }

    def get_template(self, template_name: str) -> ChatTemplate:
        return self.templates.get(template_name, self.templates["openai"])

    def register_template(self, name: str, template: ChatTemplate):
        self.templates[name] = template


# Global template manager instance
chat_template_manager = ChatTemplateManager()