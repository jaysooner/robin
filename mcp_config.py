"""
MCP Configuration Management

This module handles Model Context Protocol (MCP) configuration,
including loading server endpoints from environment variables,
parsing configuration files, and providing defaults.
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPConfig:
    """MCP configuration manager"""

    def __init__(
        self,
        enabled: bool = True,
        client_enabled: bool = True,
        server_enabled: bool = False,
        server_port: int = 9060,
        server_host: str = "127.0.0.1",
        servers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 2,
        debug: bool = False,
    ):
        self.enabled = enabled
        self.client_enabled = client_enabled
        self.server_enabled = server_enabled
        self.server_port = server_port
        self.server_host = server_host
        self.servers = servers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Load MCP configuration from environment variables"""
        enabled = os.getenv("MCP_ENABLED", "true").lower() == "true"
        client_enabled = os.getenv("MCP_CLIENT_ENABLED", "true").lower() == "true"
        server_enabled = os.getenv("MCP_SERVER_ENABLED", "false").lower() == "true"
        server_port = int(os.getenv("MCP_SERVER_PORT", "9060"))
        server_host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
        timeout = int(os.getenv("MCP_TIMEOUT", "30"))
        max_retries = int(os.getenv("MCP_MAX_RETRIES", "2"))
        debug = os.getenv("MCP_DEBUG", "false").lower() == "true"

        # Parse MCP_SERVERS JSON
        servers_json = os.getenv("MCP_SERVERS", "{}")
        try:
            servers = json.loads(servers_json) if servers_json else {}
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse MCP_SERVERS JSON: {e}. Using empty dict.")
            servers = {}

        return cls(
            enabled=enabled,
            client_enabled=client_enabled,
            server_enabled=server_enabled,
            server_port=server_port,
            server_host=server_host,
            servers=servers,
            timeout=timeout,
            max_retries=max_retries,
            debug=debug,
        )

    @classmethod
    def from_file(cls, config_path: str) -> "MCPConfig":
        """Load MCP configuration from JSON file"""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file {config_path} not found. Using defaults.")
            return cls.from_env()

        try:
            with open(path, "r") as f:
                config_data = json.load(f)

            return cls(
                enabled=config_data.get("enabled", True),
                client_enabled=config_data.get("client_enabled", True),
                server_enabled=config_data.get("server_enabled", False),
                server_port=config_data.get("server_port", 9060),
                server_host=config_data.get("server_host", "127.0.0.1"),
                servers=config_data.get("servers", {}),
                timeout=config_data.get("timeout", 30),
                max_retries=config_data.get("max_retries", 2),
                debug=config_data.get("debug", False),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return cls.from_env()

    def validate(self) -> bool:
        """Validate configuration"""
        if not isinstance(self.server_port, int) or not (1 <= self.server_port <= 65535):
            logger.error(f"Invalid MCP_SERVER_PORT: {self.server_port}. Must be 1-65535.")
            return False

        if not isinstance(self.timeout, int) or self.timeout < 1:
            logger.error(f"Invalid MCP_TIMEOUT: {self.timeout}. Must be >= 1.")
            return False

        if not isinstance(self.servers, dict):
            logger.error(f"Invalid MCP_SERVERS: must be a dict, got {type(self.servers)}")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "enabled": self.enabled,
            "client_enabled": self.client_enabled,
            "server_enabled": self.server_enabled,
            "server_port": self.server_port,
            "server_host": self.server_host,
            "servers": self.servers,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "debug": self.debug,
        }

    def __repr__(self) -> str:
        return f"MCPConfig(enabled={self.enabled}, servers={len(self.servers)}, port={self.server_port})"


def load_mcp_config(config_path: Optional[str] = None) -> MCPConfig:
    """
    Load MCP configuration from file or environment variables

    Args:
        config_path: Path to JSON configuration file (optional)

    Returns:
        MCPConfig instance
    """
    if config_path:
        config = MCPConfig.from_file(config_path)
    else:
        config = MCPConfig.from_env()

    if not config.validate():
        logger.warning("MCP configuration validation failed. Some features may not work.")

    if config.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Loaded MCP config: {config.to_dict()}")

    return config


# Default configuration instance
def get_default_config() -> MCPConfig:
    """Get default MCP configuration"""
    return MCPConfig.from_env()
