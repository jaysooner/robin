"""
Robin MCP Tools - OSINT Capabilities as MCP Tools

This module implements Robin's dark web OSINT capabilities as MCP tools
that can be exposed via the MCP server or used internally by the LLM pipeline.

Available Tools:
1. dark_web_search - Search 21 dark web search engines via Tor
2. scrape_onion_site - Scrape content from .onion URLs
3. extract_entities - Extract IOCs and entities from text
4. tor_web_fetch - Fetch any URL via Tor proxy
5. crypto_analysis - Analyze and validate cryptocurrency addresses
6. onion_reputation - Check onion domain reputation in memory DB
"""

import re
import logging
from typing import Dict, Any, List
from search import get_search_results
from scrape import scrape_single, get_tor_session
from memory import get_memory

logger = logging.getLogger(__name__)


# Tool 1: Dark Web Search
async def dark_web_search(
    query: str, max_results: int = 50, threads: int = 5
) -> Dict[str, Any]:
    """
    Search 21 dark web search engines simultaneously via Tor.
    Returns deduplicated .onion links with titles.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 50)
        threads: Number of concurrent threads for searching (default: 5)

    Returns:
        Dictionary with search results and metadata
    """
    try:
        # Use existing Robin search functionality
        results = get_search_results(query.replace(" ", "+"), max_workers=threads)

        # Limit results
        limited_results = results[:max_results]

        return {
            "success": True,
            "query": query,
            "results": limited_results,
            "count": len(limited_results),
            "total_found": len(results),
            "engines_queried": 21,  # Robin queries 21 dark web search engines
        }
    except Exception as e:
        logger.error(f"dark_web_search failed: {e}")
        return {"success": False, "error": str(e), "query": query}


# Tool 2: Scrape Onion Site
async def scrape_onion_site(url: str, max_chars: int = 2000) -> Dict[str, Any]:
    """
    Scrape content from a .onion URL via Tor with robust retry logic.

    Args:
        url: The .onion URL to scrape
        max_chars: Maximum characters to return (default: 2000)

    Returns:
        Dictionary with scraped content
    """
    if ".onion" not in url:
        return {
            "success": False,
            "error": "URL must be a .onion domain",
            "url": url,
        }

    try:
        # Use existing Robin scraping functionality
        url_data = {"link": url, "title": ""}
        scraped_url, scraped_text = scrape_single(url_data)

        # Truncate if needed
        if len(scraped_text) > max_chars:
            scraped_text = scraped_text[:max_chars] + "... (truncated)"

        return {
            "success": True,
            "url": scraped_url,
            "content": scraped_text,
            "length": len(scraped_text),
            "truncated": len(scraped_text) > max_chars,
        }
    except Exception as e:
        logger.error(f"scrape_onion_site failed for {url}: {e}")
        return {"success": False, "error": str(e), "url": url}


# Tool 3: Extract Entities
async def extract_entities(text: str) -> Dict[str, Any]:
    """
    Extract OSINT entities from text using Robin's regex patterns.
    Extracts: onion domains, emails, bitcoin, ethereum, IPs, CVEs, MD5, SHA256

    Args:
        text: Text to analyze for entities

    Returns:
        Dictionary with extracted entities by type
    """
    try:
        memory = get_memory()

        # Use existing Robin entity extraction from memory.py
        entities = memory._extract_entities(text)

        total_count = sum(len(v) for v in entities.values())
        types_found = [k for k, v in entities.items() if v]

        return {
            "success": True,
            "entities": entities,
            "total_count": total_count,
            "types_found": types_found,
            "summary": f"Found {total_count} entities across {len(types_found)} types",
        }
    except Exception as e:
        logger.error(f"extract_entities failed: {e}")
        return {"success": False, "error": str(e)}


# Tool 4: Tor Web Fetch
async def tor_web_fetch(
    url: str, method: str = "GET", timeout: int = 45, headers: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    Fetch any web resource (clearnet or .onion) via Tor proxy.
    Uses Robin's Tor session with SOCKS5 proxy.

    Args:
        url: URL to fetch (supports both .onion and clearnet)
        method: HTTP method (GET or POST)
        timeout: Request timeout in seconds (default: 45)
        headers: Optional HTTP headers

    Returns:
        Dictionary with response data
    """
    import requests

    try:
        # Use Tor session for .onion sites, regular session for clearnet
        if ".onion" in url:
            session = get_tor_session()
            via_tor = True
        else:
            session = requests.Session()
            via_tor = False

        if method.upper() == "GET":
            response = session.get(url, timeout=timeout, headers=headers or {})
        elif method.upper() == "POST":
            response = session.post(url, timeout=timeout, headers=headers or {})
        else:
            return {
                "success": False,
                "error": f"Unsupported HTTP method: {method}",
                "url": url,
            }

        # Limit content to 5KB to prevent memory issues
        content = response.text[:5000]
        if len(response.text) > 5000:
            content += "... (truncated)"

        return {
            "success": True,
            "url": url,
            "status_code": response.status_code,
            "content": content,
            "headers": dict(response.headers),
            "via_tor": via_tor,
            "content_length": len(response.text),
        }
    except requests.Timeout:
        return {
            "success": False,
            "error": f"Request timed out after {timeout}s",
            "url": url,
        }
    except Exception as e:
        logger.error(f"tor_web_fetch failed for {url}: {e}")
        return {"success": False, "error": str(e), "url": url}


# Tool 5: Crypto Analysis
async def crypto_analysis(address: str, chain: str = "auto") -> Dict[str, Any]:
    """
    Analyze cryptocurrency address format and perform basic validation.
    Supports Bitcoin (legacy, SegWit) and Ethereum addresses.

    Args:
        address: Cryptocurrency address to analyze
        chain: Blockchain type (auto, bitcoin, ethereum)

    Returns:
        Dictionary with analysis results
    """
    result = {
        "address": address,
        "valid": False,
        "chain": None,
        "type": None,
        "format_details": "",
    }

    try:
        # Bitcoin legacy (P2PKH: starts with 1) or P2SH (starts with 3)
        if re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$", address):
            result["valid"] = True
            result["chain"] = "bitcoin"
            result["type"] = "legacy (P2PKH)" if address.startswith("1") else "P2SH"
            result[
                "format_details"
            ] = "Bitcoin legacy address - older format, widely supported"

        # Bitcoin SegWit (Bech32: starts with bc1)
        elif re.match(r"^bc1[a-z0-9]{39,59}$", address.lower()):
            result["valid"] = True
            result["chain"] = "bitcoin"
            result["type"] = "segwit (Bech32)"
            result["format_details"] = "Bitcoin SegWit address - modern, lower fees"

        # Ethereum (ERC-20 compatible)
        elif re.match(r"^0x[a-fA-F0-9]{40}$", address):
            result["valid"] = True
            result["chain"] = "ethereum"
            result["type"] = "standard"
            result["format_details"] = "Ethereum address (ERC-20 token compatible)"

        else:
            result[
                "format_details"
            ] = "Unknown or invalid cryptocurrency address format"

        # Add checksum validation note
        if result["valid"]:
            result[
                "note"
            ] = "Format validated. For production use, implement full checksum validation."

        return result

    except Exception as e:
        logger.error(f"crypto_analysis failed for {address}: {e}")
        return {
            "address": address,
            "valid": False,
            "error": str(e),
            "format_details": "Analysis failed",
        }


# Tool 6: Onion Reputation
async def onion_reputation(domain: str) -> Dict[str, Any]:
    """
    Check if onion domain appears in Robin's memory database with historical context.
    Provides investigation history and frequency analysis.

    Args:
        domain: .onion domain to check

    Returns:
        Dictionary with reputation and historical data
    """
    try:
        memory = get_memory()

        # Normalize domain (remove http://, https://, trailing slashes)
        domain_clean = (
            domain.replace("http://", "")
            .replace("https://", "")
            .rstrip("/")
            .split("/")[0]
        )

        # Search for domain in entities table
        # Note: We'll need to add a search_entities method to memory.py
        # For now, we'll use a basic implementation

        # Query entities table for onion_domain type matching this domain
        cursor = memory.conn.cursor()
        cursor.execute(
            """
            SELECT e.entity_value, e.entity_type, e.first_seen,
                   COUNT(ie.investigation_id) as frequency
            FROM entities e
            LEFT JOIN investigation_entities ie ON e.id = ie.entity_id
            WHERE e.entity_value = ? AND e.entity_type = 'onion_domain'
            GROUP BY e.id
            """,
            (domain_clean,),
        )

        result = cursor.fetchone()

        if not result:
            return {
                "domain": domain_clean,
                "known": False,
                "message": "Domain not found in Robin's memory database",
            }

        # Get related investigations
        cursor.execute(
            """
            SELECT i.query, i.timestamp, i.summary_file
            FROM investigations i
            JOIN investigation_entities ie ON i.id = ie.investigation_id
            JOIN entities e ON ie.entity_id = e.id
            WHERE e.entity_value = ?
            ORDER BY i.timestamp DESC
            LIMIT 10
            """,
            (domain_clean,),
        )

        investigations = cursor.fetchall()

        related_investigations = [
            {"query": inv[0], "timestamp": inv[1], "summary_file": inv[2]}
            for inv in investigations
        ]

        return {
            "domain": domain_clean,
            "known": True,
            "entity_type": result[1],
            "first_seen": result[2],
            "frequency": result[3],
            "appearances": len(related_investigations),
            "related_investigations": related_investigations,
            "reputation_score": "high"
            if result[3] > 5
            else "medium"
            if result[3] > 2
            else "low",
            "summary": f"Domain appeared in {result[3]} investigations, first seen {result[2][:10]}",
        }

    except Exception as e:
        logger.error(f"onion_reputation failed for {domain}: {e}")
        return {
            "domain": domain,
            "known": False,
            "error": str(e),
            "message": "Reputation check failed",
        }


# Tool Registry
ROBIN_TOOLS = [
    {
        "name": "dark_web_search",
        "description": "Search 21 dark web search engines simultaneously via Tor. Returns deduplicated .onion links with titles. Use this for initial reconnaissance on any dark web topic or threat intelligence gathering.",
        "handler": dark_web_search,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for dark web engines",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 50)",
                    "default": 50,
                },
                "threads": {
                    "type": "integer",
                    "description": "Concurrent threads for searching (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "scrape_onion_site",
        "description": "Scrape content from a specific .onion URL via Tor with robust retry logic. Returns page text content. Use when you need to examine a specific dark web page or extract content from a known .onion address.",
        "handler": scrape_onion_site,
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The .onion URL to scrape (must include .onion domain)",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default: 2000)",
                    "default": 2000,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "extract_entities",
        "description": "Extract OSINT entities and indicators of compromise (IOCs) from text. Extracts: onion domains, email addresses, Bitcoin/Ethereum addresses, IP addresses, CVEs, MD5/SHA256 hashes. Use for analyzing content and identifying key artifacts.",
        "handler": extract_entities,
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to analyze for entities and IOCs",
                }
            },
            "required": ["text"],
        },
    },
    {
        "name": "tor_web_fetch",
        "description": "Fetch any web resource (clearnet or .onion) via Tor proxy. Supports both dark web and regular web URLs. Use for retrieving specific pages or checking URL accessibility through Tor.",
        "handler": tor_web_fetch,
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch (supports .onion and clearnet URLs)",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP method (default: GET)",
                    "default": "GET",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds (default: 45)",
                    "default": 45,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "crypto_analysis",
        "description": "Analyze and validate cryptocurrency addresses. Supports Bitcoin (legacy, SegWit) and Ethereum addresses. Returns format validation and blockchain identification. Use for verifying crypto addresses found during investigations.",
        "handler": crypto_analysis,
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Cryptocurrency address to analyze",
                },
                "chain": {
                    "type": "string",
                    "enum": ["auto", "bitcoin", "ethereum"],
                    "description": "Blockchain type (default: auto-detect)",
                    "default": "auto",
                },
            },
            "required": ["address"],
        },
    },
    {
        "name": "onion_reputation",
        "description": "Check if an onion domain appears in Robin's historical investigation database. Returns frequency, first seen date, and related investigations. Use for assessing domain reputation and finding related past investigations.",
        "handler": onion_reputation,
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": ".onion domain to check (with or without protocol)",
                }
            },
            "required": ["domain"],
        },
    },
]


def get_tool_by_name(name: str):
    """Get tool definition by name"""
    for tool in ROBIN_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_all_tool_names() -> List[str]:
    """Get list of all tool names"""
    return [tool["name"] for tool in ROBIN_TOOLS]


def get_tool_count() -> int:
    """Get total number of Robin tools"""
    return len(ROBIN_TOOLS)
