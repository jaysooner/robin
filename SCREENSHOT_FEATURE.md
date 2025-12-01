# 📸 Screenshot Feature Documentation

## Overview

Robin now includes **Playwright-based screenshot capture** for .onion sites! This powerful feature captures full-page screenshots of dark web pages via Tor, providing visual evidence for your OSINT investigations.

## Features

✅ **Full-Page Screenshots** - Captures entire page, not just viewport
✅ **Tor Integration** - Works seamlessly through Tor SOCKS proxy
✅ **Batch Processing** - Capture multiple screenshots efficiently
✅ **Automatic Storage** - Screenshots saved in organized directory
✅ **UI Integration** - View screenshots directly in web interface
✅ **Report Integration** - Screenshot references added to intelligence reports
✅ **Configurable** - Choose how many screenshots to capture (0-10)

## Installation

### 1. Install Playwright (Already Done!)
```bash
pip install playwright
```

### 2. Install Browser Dependencies
**REQUIRED:** Run this command to install system dependencies:

```bash
sudo apt-get install libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxdamage1 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0
```

### 3. Verify Tor is Running
```bash
# Check Tor status
nc -z 127.0.0.1 9050 && echo "Tor is ready" || echo "Start Tor first"
```

## Usage

### CLI Mode

**Basic Usage:**
```bash
# Capture 3 screenshots
python3 main.py cli -m grok-4.1-fast-free -q "dark web markets" -s 3

# Capture 5 screenshots with custom output
python3 main.py cli -m deepseek-r1-free -q "ransomware groups" -s 5 -o my_investigation

# Maximum screenshots (10)
python3 main.py cli -m llama-3.3-70b-free -q "threat intelligence" -s 10 -t 12
```

**Command Options:**
- `-s` or `--screenshots` : Number of screenshots to capture (0-10)
- Default: 0 (disabled)
- Recommended: 3-5 for balance between coverage and speed

### Web UI Mode

1. **Access UI:** http://localhost:8501

2. **Configure Screenshots:**
   - Look for the **📸 Screenshots** slider in the sidebar
   - Adjust from 0 to 10
   - See warning when enabled

3. **Run Investigation:**
   - Enter your query
   - Click "Run"
   - Watch the "Bonus Stage" for screenshot capture

4. **View Results:**
   - Screenshots appear in a grid below the summary
   - Click to expand
   - Referenced in the downloadable report

## Screenshot Storage

### Directory Structure
```
robin/
├── screenshots/
│   ├── onion_abc123_20251130_143022.png
│   ├── onion_def456_20251130_143045.png
│   └── ...
```

### File Naming Convention
- Format: `onion_{hash}_{timestamp}.png`
- Hash: MD5 of URL (12 chars)
- Timestamp: `YYYYMMDD_HHMMSS`

### Cleanup
```python
from screenshot import cleanup_old_screenshots

# Remove screenshots older than 7 days (default)
cleanup_old_screenshots()

# Custom retention period
cleanup_old_screenshots(days_old=30)
```

## Technical Details

### How It Works

1. **Browser Launch**
   - Chromium (headless mode)
   - Configured with Tor SOCKS5 proxy (127.0.0.1:9050)
   - Anti-detection headers

2. **Page Navigation**
   - Navigates to .onion URL
   - Waits for networkidle
   - Additional 2s wait for JavaScript

3. **Screenshot Capture**
   - Full-page screenshot (1920x1080 viewport)
   - PNG format
   - Saved to screenshots/

4. **Metadata Collection**
   - URL
   - Page title
   - Screenshot path
   - Success/failure status

### Configuration Options

```python
# In screenshot.py

# Screenshot settings
VIEWPORT = {'width': 1920, 'height': 1080}
TIMEOUT = 45000  # 45 seconds for Tor latency
FULL_PAGE = True

# Browser arguments
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--disable-setuid-sandbox',
]
```

## Performance Considerations

### Speed Impact
- **Without Screenshots:** ~30-60 seconds per investigation
- **With 3 Screenshots:** +60-90 seconds
- **With 10 Screenshots:** +3-5 minutes

### Resource Usage
- CPU: Moderate (browser rendering)
- Memory: ~200-300MB per browser instance
- Disk: ~50-200KB per screenshot
- Network: Tor bandwidth (slow!)

### Optimization Tips
1. **Limit Screenshots:** Use 3-5 for most investigations
2. **Adjust Threads:** Lower threads if system is slow
3. **Monitor Disk:** Clean up old screenshots regularly
4. **Tor Circuit:** May need to restart Tor if many failures

## Troubleshooting

### Common Issues

**1. "Playwright dependencies missing"**
```bash
# Solution: Install system dependencies
sudo apt-get install libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxdamage1 libgbm1 libpango-1.0-0 \
    libcairo2 libatspi2.0-0
```

**2. "Timeout errors"**
- Tor is slow! Timeouts are normal for some sites
- Check Tor is running: `nc -z 127.0.0.1 9050`
- Restart Tor: `sudo service tor restart`

**3. "Screenshots are blank/black"**
- Site may require JavaScript
- Site may have anti-bot protection
- Try reducing number of screenshots

**4. "Permission denied" errors**
- Check screenshots/ directory permissions
- Run with proper user permissions

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Example Output

### CLI Output
```
[INFO] Capturing 5 screenshots...
✔ Taking screenshots...
[INFO] Screenshots: 4/5 successful
[INFO] Screenshots saved in: screenshots/

[OUTPUT] Final intelligence summary saved to summary_2025-11-30_14-30-22.md
[OUTPUT] 4 screenshots saved to screenshots/
```

### Report Integration
Screenshots are automatically added to reports:

```markdown
## 📸 Screenshots Captured

Successfully captured 4 screenshots:

- **Example Market - Tor Hidden Service**
  - URL: `http://example.onion/market`
  - Screenshot: `screenshots/onion_abc123_20251130_143022.png`

- **Forum Discussion Thread**
  - URL: `http://forum.onion/thread/123`
  - Screenshot: `screenshots/onion_def456_20251130_143045.png`
```

## Advanced Usage

### Programmatic Access

```python
from screenshot import capture_screenshots_batch, get_screenshot_metadata

# Your filtered results
urls_data = [
    {"link": "http://example.onion", "title": "Example Site"},
    {"link": "http://test.onion", "title": "Test Page"}
]

# Capture screenshots
results = capture_screenshots_batch(urls_data, max_screenshots=5)

# Get metadata
metadata = get_screenshot_metadata(results)
print(f"Successful: {metadata['successful']}/{metadata['total']}")
```

### Custom Screenshot Function

```python
from screenshot import capture_screenshot_playwright
from pathlib import Path

url = "http://example.onion"
output_path = Path("my_screenshot.png")

result = capture_screenshot_playwright(url, output_path, timeout=60000)

if result['success']:
    print(f"Screenshot saved: {result['path']}")
    print(f"Page title: {result['title']}")
else:
    print(f"Error: {result['error']}")
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Anonymity:** Screenshots are captured through Tor for anonymity
2. **Metadata:** Screenshots contain no EXIF data
3. **Storage:** Screenshots are stored locally - secure your system
4. **Sharing:** Be careful sharing screenshots - they may reveal investigation context
5. **Legal:** Ensure you have authorization for your investigations

## Future Enhancements

Planned features:
- [ ] Video recording capability
- [ ] Interactive element capture
- [ ] Screenshot comparison/diff
- [ ] OCR text extraction
- [ ] Automatic annotation
- [ ] Batch export to ZIP
- [ ] Screenshot gallery view
- [ ] Cloud storage integration

## Support

For issues or questions:
1. Check this documentation
2. Review Robin logs
3. Test Tor connectivity
4. Open GitHub issue with screenshots disabled first
5. Include error messages and logs

## Examples

### Research Scenario
```bash
# Investigating ransomware payment sites
python3 main.py cli -m grok-4.1-fast-free \
    -q "ransomware bitcoin payment" \
    -s 5 \
    -t 10 \
    -o ransomware_investigation
```

### Marketplace Monitoring
```bash
# Monitoring dark web marketplaces
python3 main.py cli -m deepseek-r1-free \
    -q "dark web marketplace drugs" \
    -s 8 \
    -t 12 \
    -o marketplace_monitoring
```

### Threat Intel Collection
```bash
# Collecting threat intelligence
python3 main.py cli -m llama-3.3-70b-free \
    -q "zero day exploits sale" \
    -s 3 \
    -t 8 \
    -o threat_intel_$(date +%Y%m%d)
```

---

**📸 Happy Screenshot Hunting!**

*Remember: With great OSINT power comes great responsibility. Use ethically and legally.*
