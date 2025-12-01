"""
MCP Bridge - LangChain ↔ MCP Integration Layer

This module provides the integration layer between LangChain and the Model Context Protocol (MCP).
It handles tool conversion, capability detection, and provider-specific tool binding.
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


class StreamingToolHandler(BaseCallbackHandler):
    """
    Custom callback handler for streaming with tool execution feedback.
    Provides visual feedback when tools are being used.
    """

    def __init__(
        self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None
    ):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback
        self.in_tool_call = False

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Stream tokens when not in tool execution"""
        if not self.in_tool_call:
            self.buffer += token
            if "\n" in token or len(self.buffer) >= self.buffer_limit:
                print(self.buffer, end="", flush=True)
                if self.ui_callback:
                    self.ui_callback(self.buffer)
                self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        """Flush remaining buffer at LLM completion"""
        if self.buffer and not self.in_tool_call:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Signal tool execution start"""
        self.in_tool_call = True
        tool_name = serialized.get("name", "unknown")
        msg = f"\n[🔧 Using tool: {tool_name}]\n"
        print(msg, flush=True)
        if self.ui_callback:
            self.ui_callback(msg)

    def on_tool_end(self, output: str, **kwargs) -> None:
        """Signal tool execution end"""
        self.in_tool_call = False
        msg = "[✓ Tool completed]\n"
        print(msg, flush=True)
        if self.ui_callback:
            self.ui_callback(msg)

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Handle tool execution errors"""
        self.in_tool_call = False
        msg = f"[✗ Tool error: {str(error)}]\n"
        print(msg, flush=True)
        if self.ui_callback:
            self.ui_callback(msg)


def supports_tools(llm) -> bool:
    """
    Detect if an LLM instance supports tool/function calling.

    Args:
        llm: LangChain LLM instance

    Returns:
        True if LLM supports tools, False otherwise
    """
    # Claude and OpenAI have native tool support
    if isinstance(llm, (ChatAnthropic, ChatOpenAI)):
        return True

    # Ollama: Only certain models support tools
    if isinstance(llm, ChatOllama):
        tool_capable_models = [
            "llama3.1",
            "llama3.2",
            "mistral",
            "mixtral",
            "qwen2.5",
        ]
        model_name = llm.model.lower()
        return any(m in model_name for m in tool_capable_models)

    # Check for Google Gemini (if available)
    if "ChatGoogleGenerativeAI" in str(type(llm)):
        return True

    return False


def mcp_to_langchain_tool(mcp_tool: Dict[str, Any]) -> Tool:
    """
    Convert an MCP tool definition to a LangChain Tool.

    Args:
        mcp_tool: MCP tool dictionary with name, description, handler, parameters

    Returns:
        LangChain Tool instance
    """
    import asyncio

    tool_name = mcp_tool["name"]
    tool_description = mcp_tool["description"]
    tool_handler = mcp_tool["handler"]

    def sync_wrapper(**kwargs):
        """Wrapper to run async tool handlers synchronously"""
        try:
            # Run the async handler
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running (e.g., in Jupyter), use nest_asyncio
                import nest_asyncio

                nest_asyncio.apply()
            result = asyncio.run(tool_handler(**kwargs))
            return str(result)
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return f"Error: {str(e)}"

    return Tool(
        name=tool_name,
        description=tool_description,
        func=sync_wrapper,
    )


def bind_tools_to_llm(llm, mcp_client, model_choice: str):
    """
    Bind MCP tools to an LLM instance based on provider capabilities.

    Args:
        llm: LangChain LLM instance
        mcp_client: MCPClient instance with available tools
        model_choice: Model name for logging

    Returns:
        LLM instance with tools bound (or original LLM if unsupported)
    """
    if not supports_tools(llm):
        logger.info(
            f"Model {model_choice} doesn't support tool calling - using standard chain"
        )
        return llm

    try:
        # Get LangChain tools from MCP client
        tools = mcp_client.get_langchain_tools()

        if not tools:
            logger.warning("No tools available from MCP client")
            return llm

        # Claude and OpenAI: Use bind_tools()
        if isinstance(llm, (ChatAnthropic, ChatOpenAI)):
            llm_with_tools = llm.bind_tools(tools)
            logger.info(f"Bound {len(tools)} tools to {model_choice}")
            # Mark LLM as MCP-enabled
            llm_with_tools._mcp_enabled = True
            llm_with_tools._mcp_tools = tools
            return llm_with_tools

        # Ollama: Use bind_tools() for compatible models
        if isinstance(llm, ChatOllama) and supports_tools(llm):
            llm_with_tools = llm.bind_tools(tools)
            logger.info(f"Bound {len(tools)} tools to Ollama model {llm.model}")
            llm_with_tools._mcp_enabled = True
            llm_with_tools._mcp_tools = tools
            return llm_with_tools

        return llm

    except Exception as e:
        logger.error(f"Failed to bind tools to {model_choice}: {e}")
        return llm


def create_tool_enabled_chain(
    llm, prompt_template: ChatPromptTemplate, streaming: bool = True
):
    """
    Create a chain that can use tools if available, or fall back to standard chain.

    Args:
        llm: LangChain LLM instance (possibly with tools bound)
        prompt_template: ChatPromptTemplate for the chain
        streaming: Whether to enable streaming output

    Returns:
        LangChain chain (agent executor if tools available, standard chain otherwise)
    """
    # Check if LLM has tools bound
    if not hasattr(llm, "_mcp_enabled") or not llm._mcp_enabled:
        # No tools - use standard chain
        chain = prompt_template | llm | StrOutputParser()
        return chain

    # LLM has tools - create agent executor
    try:
        from langchain.agents import create_tool_calling_agent, AgentExecutor

        tools = llm._mcp_tools

        # Create agent that can use tools
        agent = create_tool_calling_agent(llm, tools, prompt_template)

        # Wrap in executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=5,  # Prevent infinite loops
            return_intermediate_steps=False,
        )

        logger.debug(
            f"Created tool-enabled chain with {len(tools)} tools, max_iterations=5"
        )
        return agent_executor

    except ImportError:
        logger.warning(
            "langchain.agents not available - falling back to standard chain"
        )
        chain = prompt_template | llm | StrOutputParser()
        return chain
    except Exception as e:
        logger.error(f"Failed to create tool-enabled chain: {e}. Using standard chain.")
        chain = prompt_template | llm | StrOutputParser()
        return chain


def create_standard_chain(prompt_template: ChatPromptTemplate, llm):
    """
    Create a standard LCEL chain without tools.

    Args:
        prompt_template: ChatPromptTemplate
        llm: LangChain LLM instance

    Returns:
        Standard LCEL chain
    """
    return prompt_template | llm | StrOutputParser()


def get_tool_binding_strategy(llm) -> str:
    """
    Determine the tool binding strategy for a given LLM.

    Args:
        llm: LangChain LLM instance

    Returns:
        Strategy name: 'native', 'agent', or 'none'
    """
    if isinstance(llm, (ChatAnthropic, ChatOpenAI)):
        return "native"
    elif isinstance(llm, ChatOllama) and supports_tools(llm):
        return "agent"
    else:
        return "none"


def extract_tool_calls(response: Any) -> List[Dict[str, Any]]:
    """
    Extract tool calls from LLM response if present.

    Args:
        response: LLM response object

    Returns:
        List of tool call dictionaries
    """
    tool_calls = []

    # Check for tool_calls in AIMessage
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            tool_calls.append(
                {
                    "name": tool_call.get("name"),
                    "args": tool_call.get("args", {}),
                    "id": tool_call.get("id"),
                }
            )

    return tool_calls


def format_tool_result(tool_name: str, result: Any) -> str:
    """
    Format tool execution result for display.

    Args:
        tool_name: Name of the tool
        result: Tool execution result

    Returns:
        Formatted string
    """
    if isinstance(result, dict):
        if result.get("success"):
            return f"[Tool {tool_name} completed successfully]"
        else:
            error = result.get("error", "Unknown error")
            return f"[Tool {tool_name} failed: {error}]"
    return f"[Tool {tool_name} returned: {str(result)[:100]}]"


# Default: No tools available
def create_no_tools_chain(prompt_template: ChatPromptTemplate, llm):
    """
    Create chain when no MCP tools are available.
    This is the backward-compatible path.

    Args:
        prompt_template: ChatPromptTemplate
        llm: LangChain LLM instance

    Returns:
        Standard LCEL chain
    """
    return create_standard_chain(prompt_template, llm)
