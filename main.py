import click
import subprocess
import time
from yaspin import yaspin
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
from llm import get_llm, refine_query, filter_results, generate_summary
from llm_utils import get_model_choices
from screenshot import capture_screenshots_batch, get_screenshot_metadata
from memory import get_memory

MODEL_CHOICES = get_model_choices()


@click.group()
@click.version_option()
def robin():
    """Robin: AI-Powered Dark Web OSINT Tool."""
    pass


@robin.command()
@click.option(
    "--model",
    "-m",
    default="gpt-5-mini",
    show_default=True,
    type=click.Choice(MODEL_CHOICES),
    help="Select LLM model to use (e.g., gpt4o, claude sonnet 3.5, ollama models)",
)
@click.option("--query", "-q", required=True, type=str, help="Dark web search query")
@click.option(
    "--threads",
    "-t",
    default=5,
    show_default=True,
    type=int,
    help="Number of threads to use for scraping (Default: 5)",
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Filename to save the final intelligence summary. If not provided, a filename based on the current date and time is used.",
)
@click.option(
    "--screenshots",
    "-s",
    default=0,
    type=int,
    help="Number of screenshots to capture (0-10). Default: 0 (disabled)",
)
@click.option(
    "--mcp-enable/--mcp-disable",
    default=True,
    help="Enable MCP tools (default: enabled)",
)
@click.option(
    "--mcp-config",
    type=str,
    help="Path to MCP config file (overrides environment variables)",
)
@click.option(
    "--mcp-verbose",
    is_flag=True,
    help="Show detailed MCP tool execution logs",
)
def cli(model, query, threads, output, screenshots, mcp_enable, mcp_config, mcp_verbose):
    """Run Robin in CLI mode.\n
    Example commands:\n
    - robin -m gpt4o -q "ransomware payments" -t 12\n
    - robin --model claude-3-5-sonnet-latest --query "sensitive credentials exposure" --threads 8 --output filename\n
    - robin -m llama3.1 -q "zero days" --screenshots 5\n
    """
    # Initialize memory and track investigation time
    memory = get_memory()
    start_time = time.time()
    session_id = memory.start_session()

    # Check for similar past investigations
    similar = memory.get_similar_investigations(query, limit=3)
    if similar:
        click.echo("\n💡 [MEMORY] Found similar past investigations:")
        for inv in similar:
            click.echo(f"   - '{inv['query']}' ({inv['timestamp'][:10]})")

    # Initialize MCP client
    mcp_client = None
    if mcp_enable:
        try:
            from mcp_client import initialize_mcp_client
            mcp_client = initialize_mcp_client(
                config_path=mcp_config,
                verbose=mcp_verbose
            )
            if mcp_client and mcp_client.connections:
                click.echo(f"\n🔧 [MCP] Connected to {len(mcp_client.connections)} servers with {len(mcp_client.tools)} tools")
            elif mcp_client:
                click.echo(f"\n🔧 [MCP] Using {len(mcp_client.tools)} Robin built-in tools")
        except Exception as e:
            click.echo(f"\n⚠️  [MCP] Failed to initialize: {e}. Continuing without MCP tools.")
            mcp_client = None

    llm = get_llm(model, mcp_client=mcp_client, enable_mcp=mcp_enable)

    # Show spinner while processing the query
    with yaspin(text="Processing...", color="cyan") as sp:
        refined_query = refine_query(llm, query)

        search_results = get_search_results(
            refined_query.replace(" ", "+"), max_workers=threads
        )

        search_filtered = filter_results(llm, refined_query, search_results)

        scraped_results = scrape_multiple(search_filtered, max_workers=threads)
        sp.ok("✔")

    # Capture screenshots if requested
    screenshot_metadata = None
    if screenshots > 0:
        click.echo(f"\n[INFO] Capturing {min(screenshots, 10)} screenshots...")
        with yaspin(text="Taking screenshots...", color="yellow") as sp:
            screenshot_results = capture_screenshots_batch(
                search_filtered, max_screenshots=min(screenshots, 10)
            )
            screenshot_metadata = get_screenshot_metadata(screenshot_results)
            sp.ok("✔")
        click.echo(f"[INFO] Screenshots: {screenshot_metadata['successful']}/{screenshot_metadata['total']} successful")
        if screenshot_metadata['successful'] > 0:
            click.echo(f"[INFO] Screenshots saved in: screenshots/")

    # Generate the intelligence summary.
    summary = generate_summary(llm, query, scraped_results)

    # Append screenshot information to summary if available
    if screenshot_metadata and screenshot_metadata['successful'] > 0:
        summary += "\n\n---\n\n## 📸 Screenshots Captured\n\n"
        summary += f"Successfully captured {screenshot_metadata['successful']} screenshots:\n\n"
        for url, result in screenshot_metadata['results'].items():
            if result['success']:
                summary += f"- **{result['title'] or 'Untitled'}**\n"
                summary += f"  - URL: `{url}`\n"
                summary += f"  - Screenshot: `{result['path']}`\n\n"

    # Save or print the summary
    if not output:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"summary_{now}.md"
    else:
        filename = output + ".md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
        click.echo(f"\n\n[OUTPUT] Final intelligence summary saved to {filename}")
        if screenshot_metadata and screenshot_metadata['successful'] > 0:
            click.echo(f"[OUTPUT] {screenshot_metadata['successful']} screenshots saved to screenshots/")

    # Save investigation to memory
    duration = int(time.time() - start_time)
    investigation_id = memory.save_investigation(
        query=query,
        refined_query=refined_query,
        model=model,
        summary=summary,
        result_count=len(search_results),
        filtered_count=len(search_filtered),
        screenshot_count=screenshot_metadata['successful'] if screenshot_metadata else 0,
        duration_seconds=duration,
        summary_file=filename,
        session_id=session_id
    )

    # Save search results
    filtered_urls = [r['link'] for r in search_filtered]
    memory.save_search_results(investigation_id, search_results, filtered_urls)

    # Extract and save entities
    memory.extract_and_save_entities(investigation_id, summary)

    # End session
    memory.end_session(session_id)

    # Show memory stats
    stats = memory.get_statistics()
    click.echo(f"\n📊 [MEMORY] Investigation saved! Total: {stats['total_investigations']} investigations, {stats['total_entities']} entities tracked")


@robin.command()
@click.option(
    "--ui-port",
    default=8501,
    show_default=True,
    type=int,
    help="Port for the Streamlit UI",
)
@click.option(
    "--ui-host",
    default="localhost",
    show_default=True,
    type=str,
    help="Host for the Streamlit UI",
)
def ui(ui_port, ui_host):
    """Run Robin in Web UI mode."""
    import sys, os

    # Use streamlit's internet CLI entrypoint
    from streamlit.web import cli as stcli

    # When PyInstaller one-file, data files livei n _MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)

    ui_script = os.path.join(base, "ui.py")
    # Build sys.argv
    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        f"--server.port={ui_port}",
        f"--server.address={ui_host}",
        "--global.developmentMode=false",
    ]
    # This will never return until streamlit exits
    sys.exit(stcli.main())


@robin.command()
@click.option(
    "--port",
    default=9060,
    show_default=True,
    type=int,
    help="Port for the MCP server",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    type=str,
    help="Host for the MCP server",
)
def serve(port, host):
    """Run Robin as MCP server (expose OSINT tools to other applications).\n
    This command starts Robin's MCP server, making its 6 OSINT tools available to external applications:\n
    - dark_web_search: Search 21 dark web engines\n
    - scrape_onion_site: Scrape .onion URLs\n
    - extract_entities: Extract IOCs from text\n
    - tor_web_fetch: Fetch URLs via Tor\n
    - crypto_analysis: Validate crypto addresses\n
    - onion_reputation: Check domain reputation\n
    \nExample:\n
    - robin serve\n
    - robin serve --port 9060 --host 0.0.0.0
    """
    import asyncio

    click.echo(f"🚀 Starting Robin MCP server on {host}:{port}")
    click.echo("📡 Exposing 6 OSINT tools:")
    click.echo("   1. dark_web_search - Search 21 dark web engines")
    click.echo("   2. scrape_onion_site - Scrape .onion URLs")
    click.echo("   3. extract_entities - Extract IOCs from text")
    click.echo("   4. tor_web_fetch - Fetch URLs via Tor")
    click.echo("   5. crypto_analysis - Validate crypto addresses")
    click.echo("   6. onion_reputation - Check domain reputation")
    click.echo("\nPress CTRL+C to stop the server...\n")

    async def run_server():
        try:
            from mcp_server import RobinMCPServer

            server = RobinMCPServer(port=port, host=host)
            await server.start()

            # Keep server running until interrupted
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                click.echo("\n🛑 Shutting down MCP server...")
                await server.stop()
                click.echo("✅ Server stopped successfully")

        except ImportError as e:
            click.echo(f"❌ Error: MCP server dependencies not installed")
            click.echo(f"   Install required packages: pip install mcp httpx anyio")
            click.echo(f"   Details: {e}")
        except Exception as e:
            click.echo(f"❌ Server error: {e}")

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        click.echo("\n🛑 Server interrupted")


if __name__ == "__main__":
    robin()
