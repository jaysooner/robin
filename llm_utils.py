import requests
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Callable, Optional, List
from langchain_anthropic import ChatAnthropic
# from langchain_google_genai import ChatGoogleGenerativeAI  # Requires Python 3.10+
from langchain_core.callbacks.base import BaseCallbackHandler
from config import OLLAMA_BASE_URL, OPENROUTER_BASE_URL, OPENROUTER_API_KEY, GOOGLE_API_KEY


class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60, ui_callback: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.buffer_limit = buffer_limit
        self.ui_callback = ui_callback

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            print(self.buffer, end="", flush=True)
            if self.ui_callback:
                self.ui_callback(self.buffer)
            self.buffer = ""


# --- Configuration Data ---
# Instantiate common dependencies once
_common_callbacks = [BufferedStreamingHandler(buffer_limit=60)]

# Define common parameters for most LLMs
_common_llm_params = {
    "temperature": 0,
    "streaming": True,
    "callbacks": _common_callbacks,
}

# Map input model choices (lowercased) to their configuration
# Each config includes the class and any model-specific constructor parameters
_llm_config_map = {
    'gpt-4.1': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-4.1'} 
    },
    'gpt-5.1': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5.1'} 
    },
    'gpt-5-mini': {
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5-mini'} 
    },
    'gpt-5-nano': { 
        'class': ChatOpenAI,
        'constructor_params': {'model_name': 'gpt-5-nano'} 
    },
    'claude-sonnet-4-5': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-sonnet-4-5'}
    },
    'claude-sonnet-4-0': {
        'class': ChatAnthropic,
        'constructor_params': {'model': 'claude-sonnet-4-0'}
    },
    # Gemini models require Python 3.10+ (langchain_google_genai)
    # 'gemini-2.5-flash': {
    #     'class': ChatGoogleGenerativeAI,
    #     'constructor_params': {'model': 'gemini-2.5-flash', 'google_api_key': GOOGLE_API_KEY }
    # },
    # 'gemini-2.5-flash-lite': {
    #     'class': ChatGoogleGenerativeAI,
    #     'constructor_params': {'model': 'gemini-2.5-flash-lite', 'google_api_key': GOOGLE_API_KEY}
    # },
    # 'gemini-2.5-pro': {
    #     'class': ChatGoogleGenerativeAI,
    #     'constructor_params': {'model': 'gemini-2.5-pro', 'google_api_key': GOOGLE_API_KEY}
    # },
    'gpt-5.1-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'openai/gpt-5.1',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'gpt-5-mini-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'openai/gpt-5-mini',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'claude-sonnet-4.5-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'anthropic/claude-sonnet-4.5',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'grok-4.1-fast-openrouter': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'x-ai/grok-4.1-fast',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY  # Use OpenRouter API key
        }
    },
    'grok-4.1-fast-free': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'x-ai/grok-4.1-fast:free',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    # Additional OpenRouter Models (Free Tier)
    'deepseek-r1-free': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'deepseek/deepseek-r1:free',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'llama-3.1-8b-free': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'meta-llama/llama-3.1-8b-instruct:free',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'llama-3.3-70b-free': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'meta-llama/llama-3.3-70b-instruct:free',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'mistral-7b-free': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'mistralai/mistral-7b-instruct:free',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'qwen-2.5-7b-free': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'qwen/qwen-2.5-7b-instruct:free',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    # OpenRouter Premium Models
    'deepseek-r1': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'deepseek/deepseek-r1',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'claude-opus-4': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'anthropic/claude-opus-4',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    'grok-2': {
        'class': ChatOpenAI,
        'constructor_params': {
            'model_name': 'x-ai/grok-2',
            'base_url': OPENROUTER_BASE_URL,
            'api_key': OPENROUTER_API_KEY
        }
    },
    # Local Ollama Models (commented out - uncomment after installing models)
    # 'llama3.2': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'llama3.2:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'llama3.1': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'llama3.1:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'gemma2': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'gemma2:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'deepseek-r1-local': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'deepseek-r1:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'mistral': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'mistral:latest', 'base_url': OLLAMA_BASE_URL}
    # },
    
    # Add more models here easily:
    # 'mistral7b': {
    #     'class': ChatOllama,
    #     'constructor_params': {'model': 'mistral:7b', 'base_url': OLLAMA_BASE_URL}
    # },
    # 'gpt3.5': {
    #      'class': ChatOpenAI,
    #      'constructor_params': {'model_name': 'gpt-3.5-turbo', 'base_url': OLLAMA_BASE_URL}
    # }
}


def _normalize_model_name(name: str) -> str:
    return name.strip().lower()


def _get_ollama_base_url() -> Optional[str]:
    if not OLLAMA_BASE_URL:
        return None
    return OLLAMA_BASE_URL.rstrip("/") + "/"


def fetch_ollama_models() -> List[str]:
    """
    Retrieve the list of locally available Ollama models by querying the Ollama HTTP API.
    Returns an empty list if the API isn't reachable or the base URL is not defined.
    """
    base_url = _get_ollama_base_url()
    if not base_url:
        return []

    try:
        resp = requests.get(urljoin(base_url, "api/tags"), timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        available = []
        for m in models:
            name = m.get("name") or m.get("model")
            if name:
                available.append(name)
        return available
    except (requests.RequestException, ValueError):
        return []


def get_model_choices() -> List[str]:
    """
    Combine the statically configured cloud models with the locally available Ollama models.
    """
    base_models = list(_llm_config_map.keys())
    dynamic_models = fetch_ollama_models()

    normalized = {_normalize_model_name(m): m for m in base_models}
    for dm in dynamic_models:
        key = _normalize_model_name(dm)
        if key not in normalized:
            normalized[key] = dm

    # Preserve the order: original base models first, then the dynamic ones in alphabetical order
    ordered_dynamic = sorted(
        [name for key, name in normalized.items() if name not in base_models],
        key=_normalize_model_name,
    )
    return base_models + ordered_dynamic


def resolve_model_config(model_choice: str):
    """
    Resolve a model choice (case-insensitive) to the corresponding configuration.
    Supports both the predefined remote models and any locally installed Ollama models.
    """
    model_choice_lower = _normalize_model_name(model_choice)
    config = _llm_config_map.get(model_choice_lower)
    if config:
        return config

    for ollama_model in fetch_ollama_models():
        if _normalize_model_name(ollama_model) == model_choice_lower:
            return {
                "class": ChatOllama,
                "constructor_params": {"model": ollama_model, "base_url": OLLAMA_BASE_URL},
            }

    return None


def supports_tool_calling(llm_instance) -> bool:
    """
    Detect if an LLM instance supports tool/function calling.

    Args:
        llm_instance: LangChain LLM instance

    Returns:
        True if the LLM supports tool calling, False otherwise
    """
    # Claude and OpenAI have native tool support
    if isinstance(llm_instance, (ChatAnthropic, ChatOpenAI)):
        return True

    # Ollama: Only certain models support tools
    if isinstance(llm_instance, ChatOllama):
        tool_capable_models = ['llama3.1', 'llama3.2', 'mistral', 'mixtral', 'qwen2.5']
        model_name = llm_instance.model.lower()
        return any(m in model_name for m in tool_capable_models)

    # Check for Google Gemini (if available)
    if 'ChatGoogleGenerativeAI' in str(type(llm_instance)):
        return True

    return False
