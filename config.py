import os
from dotenv import load_dotenv

load_dotenv()

# Configuration variables loaded from the .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# MCP Configuration
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
MCP_CLIENT_ENABLED = os.getenv("MCP_CLIENT_ENABLED", "true").lower() == "true"
MCP_SERVER_ENABLED = os.getenv("MCP_SERVER_ENABLED", "false").lower() == "true"
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "9060"))
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVERS = os.getenv("MCP_SERVERS", "{}")
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "30"))
MCP_MAX_RETRIES = int(os.getenv("MCP_MAX_RETRIES", "2"))
MCP_DEBUG = os.getenv("MCP_DEBUG", "false").lower() == "true"
