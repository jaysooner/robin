# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Robin is an AI-powered dark web OSINT (Open Source Intelligence) tool that leverages LLMs to conduct investigations on the dark web. It refines search queries, fetches results from multiple dark web search engines via Tor, filters results for relevance, scrapes content, and generates intelligence summaries.

**Key characteristics:**
- Built for dark web investigations using Tor SOCKS proxy (127.0.0.1:9050)
- Multi-LLM support: OpenAI (GPT), Anthropic (Claude), Google (Gemini), Ollama (local models), and OpenRouter
- Two operational modes: CLI mode and Web UI mode (Streamlit)
- Uses LangChain for LLM orchestration with streaming responses
- **MCP Integration**: Both MCP client (consume external tools) and MCP server (expose Robin's 6 OSINT tools)
- Tool-enabled investigations: LLMs can use tools across all pipeline stages (optional, enabled by default)

## Prerequisites and Setup

**Required:**
- Python 3.10+
- Tor service running in background on port 9050 (`apt install tor` on Linux/WSL or `brew install tor` on Mac)
- At least one LLM API key configured

**Configuration:**
1. Copy `.env.example` to `.env`
2. Add API keys:
   - `OPENAI_API_KEY` - for GPT models
   - `ANTHROPIC_API_KEY` - for Claude models
   - `GOOGLE_API_KEY` - for Gemini models
   - `OLLAMA_BASE_URL` - for local Ollama (e.g., `http://127.0.0.1:11434`)
   - `OPENROUTER_BASE_URL` and `OPENROUTER_API_KEY` - for OpenRouter

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## Running the Application

### CLI Mode
```bash
# Basic usage
python main.py cli -m gpt-5-mini -q "your search query"

# With custom threads and output
python main.py cli -m claude-sonnet-4-5 -q "ransomware payments" -t 12 -o report_name

# Using Ollama local model
python main.py cli -m llama3.1 -q "zero days" -t 8
```

### Web UI Mode
```bash
# Default (localhost:8501)
python main.py ui

# Custom host/port
python main.py ui --ui-port 8080 --ui-host 0.0.0.0
```

### Docker Mode (Web UI)
```bash
docker run --rm \
  -v "$(pwd)/.env:/app/.env" \
  --add-host=host.docker.internal:host-gateway \
  -p 8501:8501 \
  apurvsg/robin:latest ui --ui-port 8501 --ui-host 0.0.0.0
```

## Architecture

### Core Workflow Pipeline
The application follows a sequential 5-stage pipeline orchestrated by `main.py`:

1. **Query Refinement** (`llm.py:refine_query`)
   - Takes user input and optimizes it for dark web search engines
   - Uses LLM with system prompt that removes logical operators and enhances relevance

2. **Multi-Engine Search** (`search.py:get_search_results`)
   - Queries 15+ dark web search engines concurrently via Tor SOCKS proxy
   - Engines hardcoded in `SEARCH_ENGINE_ENDPOINTS` (Ahmia, OnionLand, Torgle, etc.)
   - Uses ThreadPoolExecutor for parallel fetching
   - Deduplicates results by link

3. **LLM-Based Filtering** (`llm.py:filter_results`)
   - LLM analyzes all search results and selects top 20 most relevant
   - Falls back to title-only mode if rate limit errors occur
   - Returns indices which are mapped back to original results

4. **Content Scraping** (`scrape.py:scrape_multiple`)
   - Fetches actual content from filtered .onion URLs via Tor
   - Uses robust retry logic (3 retries with exponential backoff)
   - Extracts text using BeautifulSoup, removes scripts/styles
   - Truncates to 2000 chars per page, falls back to title on failure
   - ThreadPoolExecutor for concurrent scraping

5. **Intelligence Summary Generation** (`llm.py:generate_summary`)
   - LLM analyzes scraped content and generates structured report with:
     - Source links referenced
     - Investigation artifacts (emails, crypto addresses, domains, threat actors, etc.)
     - Key insights (3-5 specific, actionable findings)
     - Next investigative steps and suggested queries
   - Streams output in real-time using LangChain callbacks

### Module Responsibilities

**`config.py`** - Environment variable loading
- Loads all API keys and base URLs from `.env` using `python-dotenv`

**`llm_utils.py`** - LLM model registry and dynamic model discovery
- `_llm_config_map`: Maps model names to LangChain classes and constructor params
- `fetch_ollama_models()`: Dynamically discovers locally available Ollama models via HTTP API
- `get_model_choices()`: Returns combined list of hardcoded + Ollama models
- `resolve_model_config()`: Case-insensitive model name resolution
- `BufferedStreamingHandler`: Custom callback for streaming LLM output with buffering

**`llm.py`** - LLM operations and prompts
- `get_llm()`: Factory function that instantiates configured LLM instance
- Contains all system prompts for refinement, filtering, and summary generation
- All LLM calls use LangChain LCEL (LangChain Expression Language) chains: `prompt | llm | parser`

**`search.py`** - Dark web search engine integration
- Hardcoded list of 15 .onion search engine endpoints
- Uses Tor SOCKS5 proxy at `127.0.0.1:9050`
- Rotates user agents from `USER_AGENTS` list
- Returns list of `{"title": str, "link": str}` dicts

**`scrape.py`** - Content extraction from .onion sites
- `get_tor_session()`: Creates requests Session with retry adapter
- `scrape_single()`: Scrapes one URL with 45s timeout for Tor latency
- `scrape_multiple()`: Parallel scraping with ThreadPoolExecutor
- BeautifulSoup parsing with script/style removal and whitespace normalization

**`main.py`** - CLI entrypoint using Click
- Two subcommands: `cli` and `ui`
- `cli`: Runs full pipeline and saves summary to markdown file
- `ui`: Launches Streamlit server (delegates to `ui.py`)
- Uses `yaspin` for CLI spinner animations

**`ui.py`** - Streamlit web interface
- Mirrors CLI pipeline but with live UI updates
- Caches search and scrape results with `@st.cache_data(ttl=200)`
- Real-time streaming summary using custom callback injected into LLM
- Download button generates base64-encoded markdown file
- Memory integration with history, entity stats, and export capabilities

**`memory.py`** - Persistent memory and context management
- `RobinMemory`: SQLite-based class for investigation tracking
- Tables: investigations, search_results, entities, investigation_entities, sessions
- `_extract_entities()`: Regex-based extraction of 8 entity types (onion domains, emails, bitcoin, ethereum, IPs, CVEs, MD5, SHA256)
- `get_similar_investigations()`: Keyword-based similarity matching for context-aware suggestions
- `export_database()`: JSON export for backup/sharing
- `cleanup_old_data()`: Remove investigations older than X days
- Singleton pattern via `get_memory()` function

**`mcp_config.py`** - MCP configuration management
- `MCPConfig`: Configuration class for MCP settings
- `load_mcp_config()`: Load config from environment or file
- Supports stdio, HTTP, and WebSocket MCP protocols

**`mcp_client.py`** - MCP client for consuming external tools
- `MCPClient`: Connects to external MCP servers and discovers tools
- `initialize_mcp_client()`: Factory function for client initialization
- Provides Robin's 6 built-in OSINT tools always available
- Graceful fallback when external servers unavailable

**`mcp_server.py`** - MCP server exposing Robin's tools
- `RobinMCPServer`: MCP server implementation
- Exposes 6 OSINT tools: dark_web_search, scrape_onion_site, extract_entities, tor_web_fetch, crypto_analysis, onion_reputation
- Run with: `python main.py serve`

**`mcp_tools.py`** - Robin's OSINT tools as MCP tools
- 6 tool implementations using existing Robin functions
- Tool schemas in JSON Schema format
- Async handlers for all tools

**`mcp_bridge.py`** - LangChain ↔ MCP integration layer
- `supports_tools()`: Detect LLM tool calling capabilities
- `bind_tools_to_llm()`: Provider-specific tool binding
- `create_tool_enabled_chain()`: Agent executor for tool use
- `StreamingToolHandler`: Enhanced callback for tool execution feedback

## MCP Integration

Robin supports Model Context Protocol (MCP) as both a **client** (consume external tools) and **server** (expose OSINT tools). See [MCP_INTEGRATION.md](MCP_INTEGRATION.md) for detailed documentation.

### Quick Start

**Using MCP Tools (Client Mode)**:
```bash
# MCP enabled by default with 6 built-in OSINT tools
python main.py cli -m claude-sonnet-4-5 -q "ransomware payments"

# Disable MCP
python main.py cli -m gpt-5-mini -q "data leaks" --mcp-disable

# With verbose logging
python main.py cli -m claude-sonnet-4-5 -q "zero days" --mcp-verbose
```

**Running as MCP Server**:
```bash
# Start MCP server to expose Robin's tools
python main.py serve

# Custom host/port
python main.py serve --port 9060 --host 0.0.0.0
```

**Configuration** (`.env`):
```bash
MCP_ENABLED=true
MCP_CLIENT_ENABLED=true
MCP_SERVER_ENABLED=false
MCP_SERVER_PORT=9060
MCP_SERVERS={}  # JSON dict of external servers
```

### 6 Built-in OSINT Tools

1. **dark_web_search** - Search 21 dark web engines simultaneously
2. **scrape_onion_site** - Scrape .onion URL content via Tor
3. **extract_entities** - Extract IOCs (emails, crypto, IPs, CVEs, hashes)
4. **tor_web_fetch** - Fetch any URL via Tor proxy
5. **crypto_analysis** - Validate Bitcoin/Ethereum addresses
6. **onion_reputation** - Check domain reputation in memory DB

### How It Works

- **Tool Binding**: Tools automatically bind to LLMs that support function calling (Claude, GPT, Ollama)
- **Pipeline Integration**: Tools available in all 3 stages (query refinement, result filtering, summary generation)
- **Graceful Fallback**: Works perfectly when disabled or unavailable
- **Provider Support**: Best-effort support across all LLM providers

### Web UI Integration

The Streamlit UI includes:
- **MCP Tools checkbox** in sidebar (enabled by default)
- **Connected Servers** expander showing external connections
- **Available Tools** expander listing all tools
- **Real-time feedback** during tool execution

## Adding New LLM Models

Models are configured in `llm_utils.py:_llm_config_map`:

```python
'model-name': {
    'class': ChatOpenAI,  # or ChatAnthropic, ChatGoogleGenerativeAI, ChatOllama
    'constructor_params': {
        'model_name': 'provider/model-id',  # for OpenAI-compatible
        'model': 'model-id',  # for Claude/Gemini/Ollama
        'base_url': OPENROUTER_BASE_URL,  # optional for custom endpoints
        'api_key': API_KEY  # optional override
    }
}
```

Common parameters (temperature, streaming, callbacks) are in `_common_llm_params` and merged automatically.

For Ollama models: just run `ollama pull <model>` - they're auto-discovered via the `/api/tags` endpoint.

## Adding New Search Engines

Add endpoint URL to `search.py:SEARCH_ENGINE_ENDPOINTS` list. The endpoint must:
- Be an .onion URL accessible via Tor
- Accept query parameter (use `{query}` placeholder)
- Return HTML with `<a>` tags containing .onion links

Example:
```python
"http://example.onion/search?q={query}"
```

## Memory System

Robin includes persistent memory using SQLite (`robin_memory.db`):

**Automatic Tracking:**
- All investigations saved with metadata (query, model, timestamps, results)
- Entity extraction from summaries (onion domains, emails, crypto addresses, IPs, CVEs, hashes)
- Session tracking with investigation grouping
- Search results and filtering status

**Features in CLI:**
- Shows similar past investigations before running query
- Displays memory statistics after investigation completes
- Automatic entity extraction and storage

**Features in UI:**
- Sidebar shows investigation count and entity statistics
- Investigation history expander (last 10 investigations)
- Entity breakdown expander (count by type)
- Memory management expander (export to JSON, cleanup old data)
- Similar investigations expander when entering query
- Status message includes memory save confirmation

**API Usage:**
```python
from memory import get_memory

memory = get_memory()  # Singleton instance
session_id = memory.start_session()
investigation_id = memory.save_investigation(...)
memory.save_search_results(investigation_id, results, filtered_urls)
memory.extract_and_save_entities(investigation_id, summary_text)
memory.end_session(session_id)
```

## Common Gotchas

1. **Tor must be running** - The tool will hang or timeout if Tor service isn't active on port 9050
2. **Ollama base URL in Docker** - Use `http://host.docker.internal:11434` for Docker mode, `http://127.0.0.1:11434` otherwise
3. **Rate limiting** - OpenAI rate limits trigger fallback to truncated title-only filtering (see `llm.py:filter_results`)
4. **Streaming in UI** - The `BufferedStreamingHandler` callback must be re-injected before each LLM call in Streamlit
5. **Thread count** - Higher thread counts speed up search/scrape but may trigger rate limits or Tor circuit issues
6. **Model name matching** - Model selection is case-insensitive via `_normalize_model_name()`
7. **Memory database** - `robin_memory.db` grows over time; use cleanup feature to remove old investigations
8. **Entity extraction** - Uses regex patterns, may miss non-standard formats (this is expected behavior)
9. **MCP tool support** - Only Claude, OpenAI GPT, and some Ollama models (llama3.1, mistral) support tool calling; others use standard chains
10. **MCP dependencies** - Full MCP protocol requires `mcp>=1.0.0` package; built-in tools work without it
11. **Tool execution timing** - Tool calls may increase investigation duration; LLM decides when to use tools
12. **Async tool handlers** - All MCP tools are async; `nest-asyncio` handles event loop conflicts

## Output Format

CLI mode saves summaries as `summary_YYYY-MM-DD_HH-MM-SS.md` (or custom `-o` name).

Summary structure (defined in `llm.py:generate_summary` prompt):
1. Input Query
2. Source Links Referenced for Analysis
3. Investigation Artifacts (IOCs, actor names, etc.)
4. Key Insights (3-5 bullets)
5. Next Steps (suggested queries and investigation paths)

## Testing the Pipeline

To verify Tor connectivity and search engines:
```bash
curl --socks5-hostname 127.0.0.1:9050 http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion
```

To test with minimal API usage:
```bash
python main.py cli -m gpt-5-mini -q "test" -t 2
```
