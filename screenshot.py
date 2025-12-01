import os
import hashlib
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_screenshot_dir():
    """Get or create screenshots directory"""
    screenshot_dir = Path("screenshots")
    screenshot_dir.mkdir(exist_ok=True)
    return screenshot_dir


def sanitize_filename(url):
    """Create a safe filename from URL"""
    # Use hash of URL for consistent, safe filenames
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"onion_{url_hash}_{timestamp}.png"


def capture_screenshot_playwright(url, output_path, timeout=45000):
    """
    Capture screenshot of a .onion URL using Playwright with Tor proxy

    Args:
        url: The .onion URL to capture
        output_path: Path to save the screenshot
        timeout: Timeout in milliseconds (default: 45s for Tor latency)

    Returns:
        dict: Result with success status, path, and any error message
    """
    try:
        with sync_playwright() as p:
            # Launch browser with Tor proxy configuration
            browser = p.chromium.launch(
                headless=True,
                proxy={
                    "server": "socks5://127.0.0.1:9050"
                },
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )

            # Create context with appropriate settings
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
            )

            page = context.new_page()

            # Navigate to the page
            logger.info(f"Navigating to {url}")
            page.goto(url, timeout=timeout, wait_until='networkidle')

            # Wait a bit for any JavaScript to load
            page.wait_for_timeout(2000)

            # Take screenshot
            logger.info(f"Capturing screenshot: {output_path}")
            page.screenshot(path=str(output_path), full_page=True)

            # Get page title for metadata
            title = page.title()

            # Cleanup
            context.close()
            browser.close()

            return {
                "success": True,
                "path": str(output_path),
                "url": url,
                "title": title,
                "error": None
            }

    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout capturing {url}: {e}")
        return {
            "success": False,
            "path": None,
            "url": url,
            "title": None,
            "error": f"Timeout: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error capturing {url}: {e}")
        return {
            "success": False,
            "path": None,
            "url": url,
            "title": None,
            "error": str(e)
        }


def capture_screenshots_batch(urls_data, max_screenshots=10):
    """
    Capture screenshots for multiple URLs

    Args:
        urls_data: List of dicts with 'link' and 'title' keys
        max_screenshots: Maximum number of screenshots to take

    Returns:
        dict: Mapping of URL to screenshot result
    """
    screenshot_dir = get_screenshot_dir()
    results = {}

    # Limit the number of screenshots
    urls_to_capture = urls_data[:max_screenshots]

    logger.info(f"Capturing screenshots for {len(urls_to_capture)} URLs")

    for url_data in urls_to_capture:
        url = url_data['link']

        # Skip if not .onion URL
        if '.onion' not in url:
            logger.warning(f"Skipping non-onion URL: {url}")
            continue

        filename = sanitize_filename(url)
        output_path = screenshot_dir / filename

        result = capture_screenshot_playwright(url, output_path)
        results[url] = result

        if result['success']:
            logger.info(f"✓ Screenshot saved: {output_path}")
        else:
            logger.warning(f"✗ Failed to capture {url}: {result['error']}")

    return results


def get_screenshot_metadata(screenshot_results):
    """
    Generate metadata summary for screenshots

    Args:
        screenshot_results: Dict of URL to screenshot result

    Returns:
        dict: Summary statistics
    """
    total = len(screenshot_results)
    successful = sum(1 for r in screenshot_results.values() if r['success'])
    failed = total - successful

    successful_paths = [
        r['path'] for r in screenshot_results.values() if r['success']
    ]

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "paths": successful_paths,
        "results": screenshot_results
    }


def cleanup_old_screenshots(days_old=7):
    """
    Clean up screenshots older than specified days

    Args:
        days_old: Number of days to keep screenshots
    """
    screenshot_dir = get_screenshot_dir()
    if not screenshot_dir.exists():
        return

    import time
    current_time = time.time()
    days_in_seconds = days_old * 86400

    deleted_count = 0
    for screenshot_file in screenshot_dir.glob("*.png"):
        file_age = current_time - screenshot_file.stat().st_mtime
        if file_age > days_in_seconds:
            screenshot_file.unlink()
            deleted_count += 1
            logger.info(f"Deleted old screenshot: {screenshot_file.name}")

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old screenshots")
