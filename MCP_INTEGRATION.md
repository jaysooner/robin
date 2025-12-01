# MCP Integration Guide

This document provides comprehensive documentation for Robin's Model Context Protocol (MCP) integration.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Built-in OSINT Tools](#built-in-osint-tools)
- [Client Mode (Consuming Tools)](#client-mode-consuming-tools)
- [Server Mode (Exposing Tools)](#server-mode-exposing-tools)
- [Configuration](#configuration)
- [LLM Provider Support](#llm-provider-support)
- [Pipeline Integration](#pipeline-integration)
- [Web UI Integration](#web-ui-integration)
- [External MCP Servers](#external-mcp-servers)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)
- [Examples](#examples)

---

## Overview

Robin implements the Model Context Protocol (MCP) in a dual role:

1. **MCP Client**: Connects to external MCP servers and consumes their tools
2. **MCP Server**: Exposes Robin's 6 OSINT capabilities as tools for external applications

### Key Features

✅ **Enabled by Default**: MCP tools are active out-of-the-box with graceful fallback
✅ **6 Built-in Tools**: Always available, even without external servers
✅ **Tool-Enhanced Investigations**: LLMs can use tools across all 3 pipeline stages
✅ **Provider Agnostic**: Best-effort support for Claude, GPT, Ollama, Gemini
✅ **Backward Compatible**: Existing workflows unchanged when MCP disabled
✅ **Real-time Feedback**: Streaming output with tool execution indicators

---

## Quick Start

### Using MCP Tools (Default Behavior)

```bash
# MCP is enabled by default with 6 built-in OSINT tools
python main.py cli -m claude-sonnet-4-5 -q "ransomware payments"
```

The LLM can now use tools like `dark_web_search`, `extract_entities`, etc., during the investigation.

### Disabling MCP

```bash
# Run without MCP tools
python main.py cli -m gpt-5-mini -q "data leaks" --mcp-disable
```

### Running as MCP Server

```bash
# Expose Robin's tools to external applications
python main.py serve

# Custom configuration
python main.py serve --port 9060 --host 0.0.0.0
```

External applications can now connect to Robin and use its OSINT tools!

---

## Architecture

### Module Overview

```
robin/
├── mcp_config.py      # Configuration management
├── mcp_client.py      # MCP client (consume tools)
├── mcp_server.py      # MCP server (expose tools)
├── mcp_tools.py       # 6 OSINT tool implementations
└── mcp_bridge.py      # LangChain ↔ MCP integration
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      User Query                             │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           main.py/ui.py: Initialize MCPClient               │
│         - Connect to external servers (optional)            │
│         - Load Robin's 6 built-in tools (always)            │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              llm.py: get_llm(mcp_client=...)                │
│         - Detect if LLM supports tool calling               │
│         - Bind tools to LLM instance                        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          Pipeline Stage (refine/filter/summarize)           │
│         - LLM processes task                                │
│         - LLM decides if tool use needed                    │
│         - If yes: tool executes, result fed back            │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Final Intelligence Report                  │
│         (May include tool-enhanced insights)                │
└─────────────────────────────────────────────────────────────┘
```

---

## Built-in OSINT Tools

Robin provides 6 powerful OSINT tools that are **always available** when MCP is enabled:

### 1. dark_web_search

**Purpose**: Search 21 dark web search engines simultaneously via Tor

**Parameters**:
- `query` (string, required): Search query
- `max_results` (integer, default: 50): Maximum results to return
- `threads` (integer, default: 5): Concurrent threads for searching

**Returns**: Deduplicated .onion links with titles

**Example Use Case**: Initial reconnaissance on any dark web topic

```python
{
  "success": True,
  "query": "ransomware payments",
  "results": [{"title": "...", "link": "http://example.onion"}, ...],
  "count": 50,
  "total_found": 127,
  "engines_queried": 21
}
```

### 2. scrape_onion_site

**Purpose**: Scrape content from specific .onion URLs via Tor

**Parameters**:
- `url` (string, required): The .onion URL to scrape
- `max_chars` (integer, default: 2000): Maximum characters to return

**Returns**: Page text content

**Example Use Case**: Examine specific dark web pages found during search

```python
{
  "success": True,
  "url": "http://example.onion/page",
  "content": "...",
  "length": 1847,
  "truncated": False
}
```

### 3. extract_entities

**Purpose**: Extract IOCs and entities from text using regex patterns

**Extracts**:
- Onion domains
- Email addresses
- Bitcoin addresses
- Ethereum addresses
- IPv4 addresses
- CVE identifiers
- MD5 hashes
- SHA256 hashes

**Parameters**:
- `text` (string, required): Text to analyze

**Returns**: Extracted entities by type

**Example Use Case**: Analyze scraped content for indicators of compromise

```python
{
  "success": True,
  "entities": {
    "onion_domain": ["example.onion"],
    "email": ["user@example.com"],
    "bitcoin": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
    "ipv4": ["192.168.1.1"],
    ...
  },
  "total_count": 15,
  "types_found": ["onion_domain", "email", "bitcoin", "ipv4"]
}
```

### 4. tor_web_fetch

**Purpose**: Fetch any web resource (clearnet or .onion) via Tor proxy

**Parameters**:
- `url` (string, required): URL to fetch
- `method` (string, default: "GET"): HTTP method (GET or POST)
- `timeout` (integer, default: 45): Request timeout in seconds

**Returns**: Response content and metadata

**Example Use Case**: Check URL accessibility through Tor, retrieve specific pages

```python
{
  "success": True,
  "url": "http://example.onion",
  "status_code": 200,
  "content": "...",
  "headers": {...},
  "via_tor": True,
  "content_length": 5000
}
```

### 5. crypto_analysis

**Purpose**: Analyze and validate cryptocurrency addresses

**Supports**:
- Bitcoin (legacy P2PKH, P2SH, SegWit Bech32)
- Ethereum (standard ERC-20 compatible)

**Parameters**:
- `address` (string, required): Cryptocurrency address to analyze
- `chain` (string, default: "auto"): Blockchain type (auto, bitcoin, ethereum)

**Returns**: Format validation and chain identification

**Example Use Case**: Verify crypto addresses found during investigations

```python
{
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "valid": True,
  "chain": "bitcoin",
  "type": "legacy (P2PKH)",
  "format_details": "Bitcoin legacy address - older format, widely supported"
}
```

### 6. onion_reputation

**Purpose**: Check if onion domain appears in Robin's historical investigation database

**Parameters**:
- `domain` (string, required): .onion domain to check

**Returns**: Reputation data and related investigations

**Example Use Case**: Assess domain reputation, find related past investigations

```python
{
  "domain": "example.onion",
  "known": True,
  "first_seen": "2025-01-15 10:30:00",
  "frequency": 8,
  "appearances": 8,
  "reputation_score": "high",
  "related_investigations": [
    {
      "query": "ransomware forums",
      "timestamp": "2025-02-01 14:20:00",
      "summary_file": "summary_2025-02-01_14-20-00.md"
    },
    ...
  ]
}
```

---

## Client Mode (Consuming Tools)

### Automatic Initialization

MCP client initializes automatically when Robin starts (unless disabled):

**CLI Mode**:
```bash
python main.py cli -m claude-sonnet-4-5 -q "threat actors"
```

**Web UI Mode**:
```bash
python main.py ui
```

### Client Behavior

1. **Load Built-in Tools**: Robin's 6 OSINT tools are always available
2. **Connect to External Servers**: Attempts to connect to servers configured in `.env`
3. **Tool Discovery**: Discovers tools from connected servers
4. **Tool Binding**: Binds all tools to LLM if it supports function calling
5. **Graceful Fallback**: Continues with built-in tools even if external connections fail

### CLI Options

```bash
# Enable MCP (default)
python main.py cli -m claude-sonnet-4-5 -q "query"

# Disable MCP
python main.py cli -m gpt-5-mini -q "query" --mcp-disable

# Custom config file
python main.py cli -m claude-sonnet-4-5 -q "query" --mcp-config ./mcp-config.json

# Verbose logging
python main.py cli -m claude-sonnet-4-5 -q "query" --mcp-verbose
```

### Status Messages

When MCP client initializes, you'll see:

```
🔧 [MCP] Using 6 Robin built-in tools
```

Or if external servers are connected:

```
🔧 [MCP] Connected to 2 servers with 15 tools
```

---

## Server Mode (Exposing Tools)

### Starting the Server

```bash
# Default (127.0.0.1:9060)
python main.py serve

# Custom host/port
python main.py serve --port 9060 --host 0.0.0.0

# Listen on all interfaces
python main.py serve --host 0.0.0.0
```

### Server Output

```
🚀 Starting Robin MCP server on 127.0.0.1:9060
📡 Exposing 6 OSINT tools:
   1. dark_web_search - Search 21 dark web engines
   2. scrape_onion_site - Scrape .onion URLs
   3. extract_entities - Extract IOCs from text
   4. tor_web_fetch - Fetch URLs via Tor
   5. crypto_analysis - Validate crypto addresses
   6. onion_reputation - Check domain reputation

Press CTRL+C to stop the server...
```

### Stopping the Server

Press `CTRL+C` to gracefully shut down:

```
🛑 Shutting down MCP server...
✅ Server stopped successfully
```

### Connecting External Clients

Once the server is running, external applications can connect to:

- **Protocol**: MCP over HTTP
- **Endpoint**: `http://127.0.0.1:9060` (or your configured host:port)
- **Available Tools**: 6 OSINT tools

**Note**: Full MCP protocol implementation requires `mcp>=1.0.0` package. The server structure is ready and will work once the package is installed.

---

## Configuration

### Environment Variables (.env)

```bash
# Enable/Disable MCP entirely
MCP_ENABLED=true

# Client configuration
MCP_CLIENT_ENABLED=true

# Server configuration
MCP_SERVER_ENABLED=false
MCP_SERVER_PORT=9060
MCP_SERVER_HOST=127.0.0.1

# External MCP servers (JSON format)
# Format: {"server_name": "protocol://endpoint", ...}
MCP_SERVERS={}

# Example with external servers:
# MCP_SERVERS={"filesystem": "stdio://~/.mcp/servers/filesystem", "web_search": "http://localhost:3000/mcp"}

# Connection settings
MCP_TIMEOUT=30
MCP_MAX_RETRIES=2

# Debug logging
MCP_DEBUG=false
```

### Configuration File (Optional)

Create `mcp-config.json`:

```json
{
  "enabled": true,
  "client_enabled": true,
  "server_enabled": false,
  "server_port": 9060,
  "server_host": "127.0.0.1",
  "servers": {
    "filesystem": "stdio://~/.mcp/servers/filesystem",
    "web_search": "http://localhost:3000/mcp"
  },
  "timeout": 30,
  "max_retries": 2,
  "debug": false
}
```

Use with:
```bash
python main.py cli -m claude-sonnet-4-5 -q "query" --mcp-config ./mcp-config.json
```

---

## LLM Provider Support

### Native Tool Support

✅ **Claude (ChatAnthropic)**: Full native tool support via `bind_tools()`
- All Claude models support tool calling
- Best performance and reliability
- Recommended for tool-heavy investigations

✅ **OpenAI GPT (ChatOpenAI)**: Full native tool support via `bind_tools()`
- GPT-4.1, GPT-5.1, GPT-5-mini, GPT-5-nano all support tools
- Excellent tool calling capabilities

### Best-Effort Support

⚠️ **Ollama (ChatOllama)**: Model-dependent support
- **Supported**: llama3.1, llama3.2, mistral, mixtral, qwen2.5
- **Unsupported**: Other Ollama models fall back to standard chains
- Tool binding only works with tool-capable models

✅ **Google Gemini (ChatGoogleGenerativeAI)**: Native tool support
- Gemini models support tool calling when available

⚠️ **OpenRouter**: Model-dependent support
- Depends on underlying model's tool capabilities
- Tool-capable models work, others fall back gracefully

### Provider Detection

Robin automatically detects LLM tool capabilities:

```python
from llm_utils import supports_tool_calling

llm = get_llm("claude-sonnet-4-5")
if supports_tool_calling(llm):
    print("✅ This LLM supports tool calling")
else:
    print("⚠️ This LLM will use standard chains")
```

### Fallback Behavior

When an LLM doesn't support tools:
1. Standard LCEL chains are used (existing behavior)
2. Investigation proceeds normally without tool use
3. No errors or warnings (graceful fallback)

---

## Pipeline Integration

MCP tools are available in **all 3 pipeline stages**. The LLM decides when to use them.

### Stage 1: Query Refinement

```python
refined_query = refine_query(llm, user_input, use_tools=False)
```

**Default**: Tools **disabled** in query refinement (set to `False`)
**Why**: Query refinement is fast and doesn't typically need external tools

**Enable if needed**:
```python
refined_query = refine_query(llm, user_input, use_tools=True)
```

### Stage 2: Result Filtering

```python
filtered_results = filter_results(llm, query, results, use_tools=False)
```

**Default**: Tools **disabled** in filtering (set to `False`)
**Why**: Filtering is typically based on titles/links and doesn't need tool execution

**Enable if needed**:
```python
filtered_results = filter_results(llm, query, results, use_tools=True)
```

### Stage 3: Summary Generation

```python
summary = generate_summary(llm, query, content, use_tools=True)
```

**Default**: Tools **enabled** in summary generation (set to `True`)
**Why**: This is where tool-enhanced analysis provides the most value

**LLM can use tools like**:
- `extract_entities` to find IOCs in scraped content
- `crypto_analysis` to validate discovered addresses
- `onion_reputation` to check domain history
- `dark_web_search` for additional context
- `scrape_onion_site` for deep-dive analysis

### Controlling Tool Usage

```python
# Disable tools for specific stage
summary = generate_summary(llm, query, content, use_tools=False)

# Or disable entirely via CLI
python main.py cli -m claude-sonnet-4-5 -q "query" --mcp-disable
```

---

## Web UI Integration

### MCP Sidebar Section

The Streamlit UI includes a dedicated MCP Tools section in the sidebar:

#### When MCP Enabled with External Servers

```
🔧 MCP Tools
☑ Enable MCP Tools ✓

✅ 2 servers connected
🛠️ 15 tools available

▸ 🔌 Connected Servers
  filesystem: 3 tools
  web_search: 6 tools

▸ 🛠️ Available Tools
  • dark_web_search: Search 21 dark web engines...
  • scrape_onion_site: Scrape .onion URLs...
  • extract_entities: Extract IOCs from text...
  • tor_web_fetch: Fetch URLs via Tor...
  • crypto_analysis: Validate crypto addresses...
  • onion_reputation: Check domain reputation...
  • [+ 9 external tools]
```

#### When MCP Enabled with Built-in Tools Only

```
🔧 MCP Tools
☑ Enable MCP Tools ✓

✅ 6 Robin built-in tools

▸ 🛠️ Available Tools
  • dark_web_search
  • scrape_onion_site
  • extract_entities
  • tor_web_fetch
  • crypto_analysis
  • onion_reputation
```

#### When MCP Disabled

```
🔧 MCP Tools
☐ Enable MCP Tools

ℹ️ MCP tools disabled
```

### Real-time Tool Execution Feedback

During investigations, tool usage is displayed:

```
📝 Generating Intelligence Summary...

[🔧 Using tool: extract_entities]
[✓ Tool completed]

[🔧 Using tool: crypto_analysis]
[✓ Tool completed]
```

### Toggle MCP On/Off

Users can enable/disable MCP tools per investigation using the checkbox. Changes take effect immediately for the next investigation.

---

## External MCP Servers

### Connecting to External Servers

Add external MCP servers to `.env`:

```bash
MCP_SERVERS={"filesystem": "stdio://~/.mcp/servers/filesystem", "web_search": "http://localhost:3000/mcp", "database": "ws://localhost:4000/mcp"}
```

### Supported Protocols

- **stdio://**: Standard input/output protocol
- **http:// / https://**: HTTP-based MCP protocol
- **ws:// / wss://**: WebSocket-based MCP protocol

### Server Configuration Format

```json
{
  "server_name": "protocol://endpoint",
  "filesystem": "stdio://~/.mcp/servers/filesystem",
  "web_search": "http://localhost:3000/mcp",
  "database": "ws://localhost:4000/mcp"
}
```

### Connection Behavior

1. Robin attempts to connect to all configured servers at startup
2. If connection fails, a warning is logged but Robin continues
3. Successfully connected servers' tools are added to available tools
4. Robin's 6 built-in tools are always available regardless of external connections

### Example: Using Multiple Servers

```bash
# Set in .env
MCP_SERVERS={"brave_search": "http://localhost:3000/mcp", "filesystem": "stdio://~/.mcp/filesystem"}

# Run investigation
python main.py cli -m claude-sonnet-4-5 -q "ransomware operators"
```

Output:
```
🔧 [MCP] Connected to 2 servers with 12 tools
  - Robin built-in: 6 tools
  - brave_search: 3 tools
  - filesystem: 3 tools
```

---

## Troubleshooting

### MCP Client Not Initializing

**Symptom**: No MCP status message, tools not available

**Possible Causes**:
1. `MCP_ENABLED=false` or `MCP_CLIENT_ENABLED=false` in `.env`
2. `--mcp-disable` flag used in CLI
3. Import error with MCP modules

**Solution**:
```bash
# Check environment variables
grep MCP .env

# Verify MCP modules exist
ls -la mcp_*.py

# Try with verbose logging
python main.py cli -m claude-sonnet-4-5 -q "test" --mcp-verbose
```

### Tools Not Being Used

**Symptom**: Investigation completes but no tool execution messages

**Possible Causes**:
1. LLM doesn't support tool calling (check provider support above)
2. Tools disabled for that pipeline stage (`use_tools=False`)
3. LLM chose not to use tools (not needed for that query)

**Solution**:
```python
# Check if LLM supports tools
from llm_utils import supports_tool_calling
llm = get_llm("your-model")
print(supports_tool_calling(llm))  # Should be True

# Enable tools in all stages (modify llm.py temporarily)
refine_query(llm, query, use_tools=True)
filter_results(llm, query, results, use_tools=True)
generate_summary(llm, query, content, use_tools=True)
```

### External Server Connection Failures

**Symptom**: Warning messages about failed server connections

**Possible Causes**:
1. Server not running at specified endpoint
2. Incorrect protocol or endpoint in configuration
3. Network/firewall issues

**Solution**:
```bash
# Verify server is running
curl http://localhost:3000/mcp

# Check MCP_SERVERS format
echo $MCP_SERVERS

# Test with only built-in tools
MCP_SERVERS={} python main.py cli -m claude-sonnet-4-5 -q "test"
```

### MCP Server Won't Start

**Symptom**: Error when running `python main.py serve`

**Possible Causes**:
1. Port already in use
2. Missing MCP dependencies
3. Permission issues

**Solution**:
```bash
# Check if port is in use
lsof -i :9060

# Try different port
python main.py serve --port 9061

# Install MCP dependencies
pip install mcp>=1.0.0 httpx anyio

# Check permissions
sudo netstat -tulpn | grep 9060
```

### ImportError: No module named 'mcp'

**Symptom**: Import errors when using external MCP servers

**Cause**: Full MCP protocol requires `mcp` package

**Solution**:
```bash
# Install MCP package
pip install mcp>=1.0.0

# Or install all dependencies
pip install -r requirements.txt
```

**Note**: Robin's built-in tools work without the `mcp` package. The package is only needed for connecting to external MCP servers or running as a full MCP server.

### Tool Execution Errors

**Symptom**: `[✗ Tool error: ...]` messages during investigation

**Possible Causes**:
1. Tool parameter validation failed
2. Tor not running (for onion-related tools)
3. Tool execution timeout

**Solution**:
```bash
# Check Tor is running
curl --socks5-hostname 127.0.0.1:9050 http://check.torproject.org

# Start Tor if needed
sudo service tor start

# Increase timeout in .env
MCP_TIMEOUT=60
```

---

## API Reference

### mcp_client.py

#### `initialize_mcp_client(config_path=None, verbose=False)`

Initialize MCP client with configuration.

**Parameters**:
- `config_path` (str, optional): Path to MCP config JSON file
- `verbose` (bool): Enable verbose logging

**Returns**: `MCPClient` instance or `None` if disabled

**Example**:
```python
from mcp_client import initialize_mcp_client

client = initialize_mcp_client(verbose=True)
if client:
    print(f"Loaded {len(client.tools)} tools")
```

#### `MCPClient.get_langchain_tools()`

Get all tools as LangChain Tool objects.

**Returns**: List of LangChain `Tool` instances

**Example**:
```python
tools = client.get_langchain_tools()
for tool in tools:
    print(f"Tool: {tool.name}")
```

#### `MCPClient.get_status()`

Get client status information.

**Returns**: Dictionary with status details

**Example**:
```python
status = client.get_status()
print(f"Enabled: {status['enabled']}")
print(f"Total tools: {status['total_tools']}")
print(f"External tools: {status['external_tools']}")
```

### mcp_bridge.py

#### `supports_tools(llm)`

Detect if LLM instance supports tool calling.

**Parameters**:
- `llm`: LangChain LLM instance

**Returns**: `bool` - True if supports tools

**Example**:
```python
from mcp_bridge import supports_tools

llm = get_llm("claude-sonnet-4-5")
if supports_tools(llm):
    print("✅ Tool calling supported")
```

#### `bind_tools_to_llm(llm, mcp_client, model_choice)`

Bind MCP tools to LLM instance.

**Parameters**:
- `llm`: LangChain LLM instance
- `mcp_client`: MCPClient instance
- `model_choice` (str): Model name for logging

**Returns**: LLM instance with tools bound

**Example**:
```python
from mcp_bridge import bind_tools_to_llm

llm = get_llm("claude-sonnet-4-5")
llm_with_tools = bind_tools_to_llm(llm, client, "claude-sonnet-4-5")
```

#### `create_tool_enabled_chain(llm, prompt_template, streaming=True)`

Create chain that can use tools or fall back to standard chain.

**Parameters**:
- `llm`: LangChain LLM instance (possibly with tools)
- `prompt_template`: ChatPromptTemplate
- `streaming` (bool): Enable streaming

**Returns**: Agent executor or standard chain

### mcp_server.py

#### `RobinMCPServer(port=9060, host='127.0.0.1')`

MCP server exposing Robin's OSINT tools.

**Parameters**:
- `port` (int): Server port
- `host` (str): Server host

**Methods**:
- `async start()`: Start the server
- `async stop()`: Stop the server
- `get_status()`: Get server status
- `get_tools_info()`: Get tool information

**Example**:
```python
import asyncio
from mcp_server import RobinMCPServer

async def run():
    server = RobinMCPServer(port=9060)
    await server.start()
    # Server is now running

asyncio.run(run())
```

### mcp_tools.py

#### Tool Functions

All tool functions are async and return dictionaries with results.

**Common Return Format**:
```python
{
    "success": bool,
    "error": str (if success=False),
    ... # Tool-specific fields
}
```

**Available Functions**:
- `async dark_web_search(query, max_results=50, threads=5)`
- `async scrape_onion_site(url, max_chars=2000)`
- `async extract_entities(text)`
- `async tor_web_fetch(url, method="GET", timeout=45)`
- `async crypto_analysis(address, chain="auto")`
- `async onion_reputation(domain)`

---

## Examples

### Example 1: Basic Investigation with MCP

```bash
# Run investigation with MCP tools enabled (default)
python main.py cli -m claude-sonnet-4-5 -q "ransomware payment methods"
```

**Output**:
```
🔧 [MCP] Using 6 Robin built-in tools

Processing...
[🔧 Using tool: dark_web_search]
[✓ Tool completed]

[🔧 Using tool: extract_entities]
[✓ Tool completed]

[🔧 Using tool: crypto_analysis]
[✓ Tool completed]

[OUTPUT] Final intelligence summary saved to summary_2025-02-01_14-30-15.md
```

### Example 2: Investigation Without MCP

```bash
# Disable MCP for comparison
python main.py cli -m claude-sonnet-4-5 -q "ransomware payment methods" --mcp-disable
```

**Output**:
```
Processing...

[OUTPUT] Final intelligence summary saved to summary_2025-02-01_14-35-20.md
```

No tool usage messages - standard pipeline only.

### Example 3: Web UI with MCP

```bash
python main.py ui
```

1. Navigate to `http://localhost:8501`
2. Enable "MCP Tools" checkbox in sidebar (enabled by default)
3. Select model: `claude-sonnet-4-5`
4. Enter query: "threat actor groups"
5. Run investigation
6. Watch real-time tool execution feedback in the UI

### Example 4: Running as MCP Server

**Terminal 1 - Start Robin MCP Server**:
```bash
python main.py serve --host 0.0.0.0 --port 9060
```

**Terminal 2 - External Application**:
```python
# Example: Connect to Robin from another app
import requests

# Call dark_web_search tool
response = requests.post(
    "http://localhost:9060/tools/dark_web_search",
    json={"query": "data leaks", "max_results": 20}
)
results = response.json()
print(f"Found {results['count']} results")
```

### Example 5: Programmatic Tool Use

```python
import asyncio
from mcp_tools import dark_web_search, extract_entities

async def investigate():
    # Search dark web
    search_results = await dark_web_search("threat actors", max_results=10)
    print(f"Found {search_results['count']} results")

    # Extract entities from first result title
    first_result = search_results['results'][0]
    entities = await extract_entities(first_result['title'])
    print(f"Entities: {entities['total_count']}")

asyncio.run(investigate())
```

### Example 6: Custom MCP Configuration

**Create `mcp-custom.json`**:
```json
{
  "enabled": true,
  "client_enabled": true,
  "servers": {
    "my_server": "http://localhost:3000/mcp"
  },
  "timeout": 60,
  "debug": true
}
```

**Run with custom config**:
```bash
python main.py cli -m claude-sonnet-4-5 -q "investigation" --mcp-config ./mcp-custom.json --mcp-verbose
```

---

## Summary

Robin's MCP integration provides:

✅ **6 Powerful OSINT Tools** always available
✅ **Dual Role** as both client and server
✅ **Seamless Integration** into existing workflows
✅ **Provider Flexibility** with best-effort support
✅ **User Control** via CLI flags and UI toggles
✅ **Graceful Fallback** when disabled or unavailable

**Get Started**: MCP is enabled by default - just run Robin and tools will be available!

For questions or issues, refer to the [Troubleshooting](#troubleshooting) section or check the main [CLAUDE.md](CLAUDE.md) documentation.
