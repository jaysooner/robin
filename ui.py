import base64
import time
import streamlit as st
from datetime import datetime
from pathlib import Path
from scrape import scrape_multiple
from search import get_search_results
from llm_utils import BufferedStreamingHandler, get_model_choices
from llm import get_llm, refine_query, filter_results, generate_summary
from screenshot import capture_screenshots_batch, get_screenshot_metadata
from memory import get_memory


# Cache expensive backend calls
@st.cache_data(ttl=200, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return get_search_results(refined_query.replace(" ", "+"), max_workers=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int):
    return scrape_multiple(filtered, max_workers=threads)


# Streamlit page configuration
st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
)

# Initialize memory
if 'memory' not in st.session_state:
    st.session_state.memory = get_memory()
    st.session_state.session_id = st.session_state.memory.start_session()

    # Initialize MCP client
    try:
        from config import MCP_CLIENT_ENABLED
        from mcp_client import initialize_mcp_client

        if MCP_CLIENT_ENABLED:
            st.session_state.mcp_client = initialize_mcp_client()
        else:
            st.session_state.mcp_client = None
    except Exception as e:
        st.session_state.mcp_client = None

# Custom CSS for styling
st.markdown(
    """
    <style>
            .colHeight {
                max-height: 40vh;
                overflow-y: auto;
                text-align: center;
            }
            .pTitle {
                font-weight: bold;
                color: #FF4B4B;
                margin-bottom: 0.5em;
            }
            .aStyle {
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
                padding-left: 0px;
                text-align: center;
            }
    </style>""",
    unsafe_allow_html=True,
)


# Sidebar
st.sidebar.title("🕵️ Robin")
st.sidebar.text("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown("---")
st.sidebar.markdown(
    """Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/)
    🔗 [GitHub](https://github.com/apurvsinghgautam/robin)"""
)
st.sidebar.markdown("---")

# Configuration Section
st.sidebar.subheader("⚙️ Configuration")
model_options = get_model_choices()
default_model_index = (
    next(
        (idx for idx, name in enumerate(model_options) if name.lower() == "gpt-5-mini"),
        0,
    )
    if model_options
    else 0
)
model = st.sidebar.selectbox(
    "🤖 Select LLM Model",
    model_options,
    index=default_model_index,
    key="model_select",
    help="Choose an AI model for query refinement, filtering, and summarization"
)

# Model info
if "free" in model.lower():
    st.sidebar.success("✅ Free model selected")
elif "grok" in model.lower() or "deepseek" in model.lower() or "llama" in model.lower():
    st.sidebar.info("ℹ️ Using OpenRouter")

threads = st.sidebar.slider(
    "🧵 Scraping Threads",
    1, 20, 8,
    key="thread_slider",
    help="More threads = faster scraping, but may trigger rate limits"
)

screenshots = st.sidebar.slider(
    "📸 Screenshots",
    0, 10, 0,
    key="screenshot_slider",
    help="Number of .onion page screenshots to capture (0 = disabled)"
)

if screenshots > 0:
    st.sidebar.warning(f"⚠️ Will capture {screenshots} screenshots (slower)")

# MCP Configuration Section
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 MCP Tools")

mcp_enabled = st.sidebar.checkbox(
    "Enable MCP Tools",
    value=True,
    key="mcp_enabled",
    help="Allow LLM to use external tools during investigations (default: enabled)"
)

if mcp_enabled and st.session_state.mcp_client:
    if st.session_state.mcp_client.connections:
        st.sidebar.success(f"✅ {len(st.session_state.mcp_client.connections)} servers connected")
        st.sidebar.caption(f"🛠️ {len(st.session_state.mcp_client.tools)} tools available")

        with st.sidebar.expander("🔌 Connected Servers"):
            for name, conn in st.session_state.mcp_client.connections.items():
                tool_count = len(conn.tools) if hasattr(conn, 'tools') else 0
                st.write(f"**{name}**: {tool_count} tools")

        with st.sidebar.expander("🛠️ Available Tools"):
            for tool in st.session_state.mcp_client.tools:
                tool_name = tool.get('name', 'Unknown')
                tool_desc = tool.get('description', '')
                st.caption(f"• **{tool_name}**: {tool_desc[:60]}...")
    elif st.session_state.mcp_client.tools:
        st.sidebar.success(f"✅ {len(st.session_state.mcp_client.tools)} Robin built-in tools")
        with st.sidebar.expander("🛠️ Available Tools"):
            for tool in st.session_state.mcp_client.tools:
                tool_name = tool.get('name', 'Unknown')
                st.caption(f"• {tool_name}")
    else:
        st.sidebar.warning("⚠️ No tools available")
else:
    st.sidebar.info("ℹ️ MCP tools disabled")

# Statistics Section
st.sidebar.markdown("---")
st.sidebar.subheader("📊 System Info")
st.sidebar.metric("Available Models", len(model_options))
st.sidebar.metric("Search Engines", "21")

# Memory Statistics
memory_stats = st.session_state.memory.get_statistics()
st.sidebar.metric("Total Investigations", memory_stats['total_investigations'])
st.sidebar.metric("Entities Tracked", memory_stats['total_entities'])
st.sidebar.caption("💡 **Tip:** Use 8-12 threads for optimal performance")

# About Section
with st.sidebar.expander("ℹ️ About Robin"):
    st.markdown("""
    **Robin** searches 21+ dark web search engines via Tor, filters results with AI,
    and generates comprehensive intelligence reports.

    **Pipeline:**
    1. 🔍 Query Refinement
    2. 🌐 Dark Web Search
    3. 🎯 AI Filtering
    4. 📡 Content Scraping
    5. 📝 Intelligence Summary
    """)

# Investigation History
with st.sidebar.expander("📜 Investigation History"):
    history = st.session_state.memory.get_investigation_history(limit=10)
    if history:
        for inv in history:
            st.markdown(f"**{inv['query'][:50]}{'...' if len(inv['query']) > 50 else ''}**")
            st.caption(f"🤖 {inv['model']} | ⏱️ {inv['timestamp'][:16]} | 📊 {inv['filtered_count']} results")
            if inv['summary_file']:
                st.caption(f"📄 {inv['summary_file']}")
            st.markdown("---")
    else:
        st.info("No investigations yet. Run your first query!")

# Entity Statistics
with st.sidebar.expander("🔍 Entity Breakdown"):
    entity_stats = st.session_state.memory.get_entity_statistics()
    if entity_stats:
        for entity_type, count in entity_stats.items():
            st.metric(entity_type.replace('_', ' ').title(), count)
    else:
        st.info("No entities tracked yet.")

# Memory Management
with st.sidebar.expander("💾 Memory Management"):
    st.markdown("**Export/Import Database**")

    # Export functionality
    if st.button("📤 Export Memory to JSON", use_container_width=True):
        export_filename = f"robin_memory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            st.session_state.memory.export_database(export_filename)
            st.success(f"✅ Exported to {export_filename}")

            # Provide download link
            import json
            with open(export_filename, 'r') as f:
                export_data = f.read()
            b64 = base64.b64encode(export_data.encode()).decode()
            href = f'<a href="data:application/json;base64,{b64}" download="{export_filename}">📥 Download Export</a>'
            st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Export failed: {e}")

    st.markdown("---")

    # Cleanup old data
    st.markdown("**Cleanup Old Data**")
    days_old = st.number_input("Days to keep", min_value=7, max_value=365, value=90)
    if st.button("🗑️ Delete Old Investigations", use_container_width=True):
        try:
            deleted = st.session_state.memory.cleanup_old_data(days_old)
            st.success(f"✅ Deleted {deleted} old investigations")
        except Exception as e:
            st.error(f"Cleanup failed: {e}")


# Main UI - logo and input
_, logo_col, _ = st.columns(3)
with logo_col:
    st.image(".github/assets/robin_logo.png", width=200)

# Display text box and button
with st.form("search_form", clear_on_submit=True):
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "Enter Dark Web Search Query",
        placeholder="Enter Dark Web Search Query",
        label_visibility="collapsed",
        key="query_input",
    )
    run_button = col_button.form_submit_button("Run")

# Display a status message
status_slot = st.empty()
# Pre-allocate three placeholders-one per card
cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in cols]
# Summary placeholders
summary_container_placeholder = st.empty()


# Process the query
if run_button and query:
    # clear old state
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        st.session_state.pop(k, None)

    # Track investigation start time
    investigation_start_time = time.time()

    # Check for similar past investigations
    similar = st.session_state.memory.get_similar_investigations(query, limit=3)
    if similar:
        with st.expander("💡 Similar Past Investigations Found", expanded=False):
            for inv in similar:
                st.markdown(f"**{inv['query']}**")
                st.caption(f"📅 {inv['timestamp'][:10]} | 📊 {inv['filtered_count']} results")
                if inv['summary_file']:
                    st.caption(f"📄 {inv['summary_file']}")
                st.markdown("---")

    # Progress bar
    progress_bar = st.progress(0)
    progress_text = st.empty()

    # Stage 1 - Load LLM (0-15%)
    progress_text.text("🤖 Stage 1/5: Loading AI Model...")
    progress_bar.progress(5)
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            llm = get_llm(
                model,
                mcp_client=st.session_state.mcp_client if mcp_enabled else None,
                enable_mcp=mcp_enabled
            )
    progress_bar.progress(15)

    # Stage 2 - Refine query (15-25%)
    progress_text.text("🔍 Stage 2/5: Refining Search Query...")
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            st.session_state.refined = refine_query(llm, query)
    progress_bar.progress(25)
    p1.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>✨ Refined Query</p><p style='font-size:16px;font-weight:600;color:#1f77b4;'>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 3 - Search dark web (25-50%)
    progress_text.text(f"🌐 Stage 3/5: Searching 21 Dark Web Engines...")
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            st.session_state.results = cached_search_results(
                st.session_state.refined, threads
            )
    progress_bar.progress(50)
    p2.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>📊 Total Results Found</p><p style='font-size:32px;font-weight:bold;color:#2ca02c;'>{len(st.session_state.results)}</p><p style='font-size:12px;color:#666;'>from {len(st.session_state.results)} unique sources</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 4 - Filter results (50-65%)
    progress_text.text(f"🎯 Stage 4/5: AI Filtering Top {min(20, len(st.session_state.results))} Relevant Results...")
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            st.session_state.filtered = filter_results(
                llm, st.session_state.refined, st.session_state.results
            )
    progress_bar.progress(65)
    p3.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>🎯 Filtered Results</p><p style='font-size:32px;font-weight:bold;color:#ff7f0e;'>{len(st.session_state.filtered)}</p><p style='font-size:12px;color:#666;'>most relevant pages</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 5 - Scrape content (65-75%)
    progress_text.text(f"📡 Stage 5/6: Scraping {len(st.session_state.filtered)} Pages via Tor...")
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            st.session_state.scraped = cached_scrape_multiple(
                st.session_state.filtered, threads
            )
    progress_bar.progress(75)

    # Stage 5.5 - Capture Screenshots (75-85%) [Optional]
    screenshot_metadata = None
    if screenshots > 0:
        progress_text.text(f"📸 Bonus Stage: Capturing {screenshots} Screenshots...")
        with status_slot.container():
            with st.spinner(f"📸 Capturing {screenshots} screenshots..."):
                screenshot_results = capture_screenshots_batch(
                    st.session_state.filtered, max_screenshots=screenshots
                )
                screenshot_metadata = get_screenshot_metadata(screenshot_results)
                st.session_state.screenshots = screenshot_metadata
        progress_bar.progress(85)

        # Show screenshot results
        if screenshot_metadata['successful'] > 0:
            st.success(f"✅ Captured {screenshot_metadata['successful']}/{screenshot_metadata['total']} screenshots")

    # Stage 6 - Summarize (85-100%)
    progress_text.text("📝 Generating Intelligence Summary...")
    # 6a) Prepare session state for streaming text
    st.session_state.streamed_summary = ""

    # 6c) UI callback for each chunk
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    with summary_container_placeholder.container():
        hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
        with hdr_col:
            st.subheader("🔍 Investigation Summary", anchor=None, divider="red")
        summary_slot = st.empty()

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped)

    progress_bar.progress(100)
    progress_text.text("✅ Investigation Complete!")

    # Append screenshot info to summary if available
    if screenshot_metadata and screenshot_metadata['successful'] > 0:
        screenshot_section = "\n\n---\n\n## 📸 Screenshots Captured\n\n"
        screenshot_section += f"Successfully captured {screenshot_metadata['successful']} screenshots:\n\n"
        for url, result in screenshot_metadata['results'].items():
            if result['success']:
                screenshot_section += f"- **{result['title'] or 'Untitled'}**\n"
                screenshot_section += f"  - URL: `{url}`\n"
                screenshot_section += f"  - Screenshot: `{result['path']}`\n\n"
        st.session_state.streamed_summary += screenshot_section
        summary_slot.markdown(st.session_state.streamed_summary)

    with btn_col:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"robin_report_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)

    # Save investigation to memory
    duration = int(time.time() - investigation_start_time)
    investigation_id = st.session_state.memory.save_investigation(
        query=query,
        refined_query=st.session_state.refined,
        model=model,
        summary=st.session_state.streamed_summary,
        result_count=len(st.session_state.results),
        filtered_count=len(st.session_state.filtered),
        screenshot_count=screenshot_metadata['successful'] if screenshot_metadata else 0,
        duration_seconds=duration,
        summary_file=fname,
        session_id=st.session_state.session_id
    )

    # Save search results
    filtered_urls = [r['link'] for r in st.session_state.filtered]
    st.session_state.memory.save_search_results(investigation_id, st.session_state.results, filtered_urls)

    # Extract and save entities
    st.session_state.memory.extract_and_save_entities(investigation_id, st.session_state.streamed_summary)

    status_msg = f"✅ Investigation completed! Analyzed {len(st.session_state.results)} results from 21 search engines, filtered to {len(st.session_state.filtered)} most relevant pages."
    if screenshot_metadata and screenshot_metadata['successful'] > 0:
        status_msg += f" Captured {screenshot_metadata['successful']} screenshots."

    # Add memory stats to status message
    updated_stats = st.session_state.memory.get_statistics()
    status_msg += f" 💾 Saved to memory ({updated_stats['total_investigations']} total investigations tracked)."
    status_slot.success(status_msg)

    # Display screenshots section
    if screenshot_metadata and screenshot_metadata['successful'] > 0:
        st.markdown("---")
        st.subheader("📸 Captured Screenshots")
        st.caption(f"Showing {screenshot_metadata['successful']} .onion page screenshots")

        # Display screenshots in a grid
        screenshot_cols = st.columns(3)
        col_idx = 0
        for url, result in screenshot_metadata['results'].items():
            if result['success']:
                with screenshot_cols[col_idx % 3]:
                    st.markdown(f"**{result['title'][:50]}...**" if len(result['title'] or '') > 50 else f"**{result['title'] or 'Untitled'}**")
                    try:
                        screenshot_path = Path(result['path'])
                        if screenshot_path.exists():
                            st.image(str(screenshot_path), use_container_width=True)
                            st.caption(f"🔗 {url[:40]}...")
                    except Exception as e:
                        st.error(f"Error loading screenshot: {e}")
                    col_idx += 1
