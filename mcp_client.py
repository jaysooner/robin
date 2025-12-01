"""
MCP Client - Client for consuming external MCP servers

This module implements the MCP client that connects to external MCP servers,
discovers their tools, and executes tool calls from the LLM.
"""

import logging
from typing import Dict, List, Optional, Any
from mcp_config import MCPConfig, load_mcp_config
from mcp_tools import ROBIN_TOOLS
from mcp_bridge import mcp_to_langchain_tool

logger = logging.getLogger(__name__)


class MCPConnection:
    """Represents a connection to a single MCP server"""

    def __init__(self, name: str, endpoint: str):
        self.name = name
        self.endpoint = endpoint
        self.tools = []
        self.connected = False

    def __repr__(self):
        return f"MCPConnection(name={self.name}, connected={self.connected}, tools={len(self.tools)})"


class MCPClient:
    """
    MCP Client for connecting to external MCP servers and using their tools.

    This client can:
    - Connect to multiple MCP servers (stdio, HTTP, WebSocket)
    - Discover available tools from each server
    - Execute tool calls from LLMs
    - Handle connection failures gracefully
    - Provide Robin's own tools alongside external tools
    """

    def __init__(self, config: MCPConfig, enabled: bool = True):
        self.config = config
        self.enabled = enabled and config.enabled and config.client_enabled
        self.connections: Dict[str, MCPConnection] = {}
        self.tools = []
        self._initialized = False
        self._langchain_tools = []

    def initialize(self) -> bool:
        """
        Initialize MCP client and connect to configured servers.

        Returns:
            True if at least one connection successful, False otherwise
        """
        if not self.enabled:
            logger.info("MCP client disabled")
            return False

        logger.info("Initializing MCP client...")

        # First, add Robin's own tools (always available)
        self._add_robin_tools()

        # Then try to connect to external MCP servers
        if self.config.servers:
            for server_name, endpoint in self.config.servers.items():
                try:
                    self._connect_to_server(server_name, endpoint)
                except Exception as e:
                    logger.warning(
                        f"Failed to connect to MCP server '{server_name}' at {endpoint}: {e}"
                    )
                    # Continue with other servers

        self._initialized = True

        # Log summary
        if self.connections:
            logger.info(
                f"MCP client initialized with {len(self.connections)} external servers and {len(self.tools)} total tools"
            )
        else:
            logger.info(
                f"MCP client initialized with Robin's {len(self.tools)} built-in tools (no external servers)"
            )

        return True

    def _add_robin_tools(self):
        """Add Robin's built-in OSINT tools to the tools list"""
        self.tools.extend(ROBIN_TOOLS)
        logger.info(f"Added {len(ROBIN_TOOLS)} Robin built-in tools")

    def _connect_to_server(self, name: str, endpoint: str):
        """
        Connect to an external MCP server and discover its tools.

        Args:
            name: Server name (for identification)
            endpoint: Server endpoint (stdio://, http://, ws://)
        """
        logger.debug(f"Connecting to MCP server '{name}' at {endpoint}")

        connection = MCPConnection(name, endpoint)

        try:
            # Parse endpoint protocol
            if endpoint.startswith("stdio://"):
                tools = self._connect_stdio(endpoint)
            elif endpoint.startswith("http://") or endpoint.startswith("https://"):
                tools = self._connect_http(endpoint)
            elif endpoint.startswith("ws://") or endpoint.startswith("wss://"):
                tools = self._connect_websocket(endpoint)
            else:
                raise ValueError(f"Unsupported MCP protocol: {endpoint}")

            connection.tools = tools
            connection.connected = True
            self.connections[name] = connection
            self.tools.extend(tools)

            logger.info(
                f"Connected to '{name}': {len(tools)} tools discovered"
            )

        except Exception as e:
            logger.error(f"Failed to connect to '{name}': {e}")
            raise

    def _connect_stdio(self, endpoint: str) -> List[Dict[str, Any]]:
        """
        Connect to MCP server via stdio protocol.

        Args:
            endpoint: stdio:// endpoint

        Returns:
            List of tool definitions
        """
        # TODO: Implement stdio MCP client once mcp package is installed
        # For now, return empty list
        logger.info(
            f"stdio MCP protocol not yet implemented. Install 'mcp' package and implement this method."
        )
        return []

    def _connect_http(self, endpoint: str) -> List[Dict[str, Any]]:
        """
        Connect to MCP server via HTTP protocol.

        Args:
            endpoint: http:// or https:// endpoint

        Returns:
            List of tool definitions
        """
        # TODO: Implement HTTP MCP client once mcp package is installed
        # For now, return empty list
        logger.info(
            f"HTTP MCP protocol not yet implemented. Install 'mcp' package and implement this method."
        )
        return []

    def _connect_websocket(self, endpoint: str) -> List[Dict[str, Any]]:
        """
        Connect to MCP server via WebSocket protocol.

        Args:
            endpoint: ws:// or wss:// endpoint

        Returns:
            List of tool definitions
        """
        # TODO: Implement WebSocket MCP client once mcp package is installed
        # For now, return empty list
        logger.info(
            f"WebSocket MCP protocol not yet implemented. Install 'mcp' package and implement this method."
        )
        return []

    def get_langchain_tools(self):
        """
        Get all tools as LangChain Tool objects.

        Returns:
            List of LangChain Tool instances
        """
        if not self._langchain_tools:
            # Convert MCP tools to LangChain tools
            for mcp_tool in self.tools:
                try:
                    lc_tool = mcp_to_langchain_tool(mcp_tool)
                    self._langchain_tools.append(lc_tool)
                except Exception as e:
                    logger.error(
                        f"Failed to convert tool '{mcp_tool.get('name')}' to LangChain: {e}"
                    )

        return self._langchain_tools

    async def execute_tool(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool by name with given parameters.

        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters

        Returns:
            Tool execution result
        """
        # Find the tool
        tool = None
        for t in self.tools:
            if t["name"] == tool_name:
                tool = t
                break

        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        try:
            # Execute the tool handler
            handler = tool["handler"]
            result = await handler(**params)
            return result
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            return {"success": False, "error": str(e)}

    def reconnect(self):
        """Attempt to reconnect to all disconnected servers"""
        logger.info("Attempting to reconnect to MCP servers...")
        for name, conn in self.connections.items():
            if not conn.connected:
                try:
                    self._connect_to_server(name, conn.endpoint)
                except Exception as e:
                    logger.warning(f"Reconnection to '{name}' failed: {e}")

    def get_tool_count(self) -> int:
        """Get total number of available tools"""
        return len(self.tools)

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return sum(1 for conn in self.connections.values() if conn.connected)

    def is_enabled(self) -> bool:
        """Check if MCP client is enabled"""
        return self.enabled

    def get_status(self) -> Dict[str, Any]:
        """
        Get MCP client status.

        Returns:
            Status dictionary
        """
        return {
            "enabled": self.enabled,
            "initialized": self._initialized,
            "connections": len(self.connections),
            "active_connections": self.get_connection_count(),
            "total_tools": self.get_tool_count(),
            "robin_tools": len(ROBIN_TOOLS),
            "external_tools": self.get_tool_count() - len(ROBIN_TOOLS),
        }

    def __repr__(self):
        return f"MCPClient(enabled={self.enabled}, connections={len(self.connections)}, tools={len(self.tools)})"


def initialize_mcp_client(
    config_path: Optional[str] = None, verbose: bool = False
) -> Optional[MCPClient]:
    """
    Initialize MCP client with configuration.

    Args:
        config_path: Optional path to MCP config file
        verbose: Enable verbose logging

    Returns:
        MCPClient instance or None if disabled/failed
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        # Load configuration
        config = load_mcp_config(config_path)

        if not config.enabled or not config.client_enabled:
            logger.info("MCP client disabled by configuration")
            return None

        # Create and initialize client
        client = MCPClient(config)

        if not client.initialize():
            logger.warning("MCP client initialization returned False")

        # Always return client even if no external servers connected
        # Robin's built-in tools are still available
        return client

    except Exception as e:
        logger.error(f"Failed to initialize MCP client: {e}")
        # Return None for graceful fallback
        return None


def get_mcp_client_if_enabled() -> Optional[MCPClient]:
    """
    Get MCP client if enabled, otherwise return None.
    Convenience function for conditional MCP usage.

    Returns:
        MCPClient instance or None
    """
    return initialize_mcp_client()
