import logging
import importlib
import pkgutil
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PluginManager:
    """
    Manages discovery and execution of plugins.
    Currently supports UTCPPlugin.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.plugins = {}
        self.enabled = True

    def discover(self) -> List[str]:
        """
        Discover and initialize available plugins.
        """
        discovered = []
        
        # Hardcoded discovery for now, can be dynamic later
        # Try to load UTCP plugin
        try:
            from plugins.utcp_plugin.plugin import UTCPPlugin
            self.plugins['utcp'] = UTCPPlugin(self.config)
            discovered.append('utcp')
            logger.info("UTCP Plugin loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not load UTCP Plugin: {e}")
        except Exception as e:
            logger.error(f"Error initializing UTCP Plugin: {e}")

        # Try to load Mgrep Plugin
        try:
            from plugins.mgrep.plugin import MgrepPlugin
            self.plugins['mgrep'] = MgrepPlugin(self.config)
            discovered.append('mgrep')
            logger.info("Mgrep Plugin loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not load Mgrep Plugin: {e}")
        except Exception as e:
            logger.error(f"Error initializing Mgrep Plugin: {e}")

        # Try to load Example Tools plugin (used in tests)
        try:
            from plugins.example_tools.plugin import ExampleToolsPlugin
            self.plugins['example_tools'] = ExampleToolsPlugin(self.config)
            discovered.append('example_tools')
            logger.info("Example Tools Plugin loaded successfully")
        except ImportError:
            # Not critical; tests may override discovery in CI
            logger.debug("Example Tools Plugin not present; skipping")
        except Exception as e:
            logger.error(f"Error initializing Example Tools plugin: {e}")

        return discovered

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Aggregate tools from all loaded plugins.
        """
        all_tools = []
        for name, plugin in self.plugins.items():
            try:
                tools = plugin.discover_tools()
                all_tools.extend(tools)
            except Exception as e:
                logger.error(f"Error getting tools from plugin {name}: {e}")
        return all_tools

    def lookup_plugin_for_tool(self, tool_name: str) -> Optional[str]:
        """
        Find which plugin provides a specific tool.
        """
        for name, plugin in self.plugins.items():
            # This is a simplification. Ideally plugins verify if they own a tool.
            # For UTCP, we might need to check if the tool is in its list.
            # For now, if we only have UTCP, assume it's there if it's valid.
            # A better approach is to cache tool->plugin mapping in list_tools
            tools = plugin.discover_tools()
            for tool in tools:
                if tool['name'] == tool_name:
                    return name
        return None

    async def execute_tool(self, tool_identifier: str, **kwargs) -> Any:
        """
        Execute a tool. tool_identifier should be 'plugin_name:tool_name'.
        """
        if ':' not in tool_identifier:
            return {"error": "Invalid tool identifier format. Expected 'plugin:tool'"}
        
        plugin_name, tool_name = tool_identifier.split(':', 1)
        
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return {"error": f"Plugin {plugin_name} not found"}
        
        try:
            res = plugin.execute_tool(tool_name, kwargs)
            # If plugin returns a coroutine, await it
            if hasattr(res, '__await__'):
                return await res
            return res
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} in plugin {plugin_name}: {e}")
            return {"error": str(e)}
