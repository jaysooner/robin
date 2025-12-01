# 💾 Persistent Memory & Context Feature Documentation

## Overview

Robin now includes **persistent memory and context management** using a SQLite database! This powerful feature tracks all your investigations, extracts entities/artifacts, and provides context-aware insights for future investigations.

## Features

✅ **Investigation History** - Track all past investigations with full metadata
✅ **Entity Extraction** - Automatically extract IOCs (domains, emails, crypto, IPs, CVEs, hashes)
✅ **Context-Aware Suggestions** - Find similar past investigations when entering queries
✅ **Session Tracking** - Group investigations by session with timing data
✅ **Statistics Dashboard** - View aggregate stats across all investigations
✅ **Export/Import** - Export database to JSON for backup or sharing
✅ **Data Cleanup** - Remove old investigations to manage database size
✅ **Entity Search** - Find all investigations related to specific entities

## Database Schema

Robin uses SQLite with the following tables:

### 1. `investigations`
Stores investigation metadata:
- `id`, `query`, `refined_query`, `model`
- `timestamp`, `summary`, `summary_file`
- `result_count`, `filtered_count`, `screenshot_count`
- `duration_seconds`, `session_id`

### 2. `search_results`
Tracks all URLs found:
- `investigation_id` (foreign key)
- `url`, `title`
- `was_filtered`, `was_scraped`, `relevance_score`

### 3. `entities`
Stores extracted artifacts:
- `entity_type`, `value`
- `first_seen`, `last_seen`, `frequency`
- Types: onion_domain, email, bitcoin, ethereum, ipv4, cve, hash_md5, hash_sha256

### 4. `investigation_entities`
Many-to-many relationship between investigations and entities

### 5. `sessions`
Tracks investigation sessions:
- `id`, `started_at`, `ended_at`, `investigation_count`

## Usage

### CLI Mode

Memory is **automatically enabled** in CLI mode. Every investigation is tracked:

```bash
# Run investigation - memory tracking happens automatically
python3 main.py cli -m grok-4.1-fast-free -q "ransomware payments"

# Output shows similar past investigations:
💡 [MEMORY] Found similar past investigations:
   - 'ransomware bitcoin payment' (2025-11-29)
   - 'crypto payment tracking' (2025-11-28)

# After completion, see memory stats:
📊 [MEMORY] Investigation saved! Total: 15 investigations, 142 entities tracked
```

### Web UI Mode

Memory is **automatically enabled** in the web UI with rich visualizations:

#### Sidebar - System Info
- **Total Investigations**: Count of all investigations
- **Entities Tracked**: Total unique entities across all investigations

#### Sidebar - Investigation History
Expander showing last 10 investigations:
- Query (truncated to 50 chars)
- Model used, timestamp, result count
- Summary file name

#### Sidebar - Entity Breakdown
Shows count by entity type:
- Onion Domain: 42
- Email: 15
- Bitcoin: 8
- Ethereum: 3
- IPv4: 12
- CVE: 5
- Hash MD5: 7
- Hash SHA256: 6

#### Sidebar - Memory Management
- **Export Memory to JSON**: Download full database as JSON
- **Delete Old Investigations**: Cleanup data older than X days

#### Similar Investigations Display
When you enter a query, Robin checks for similar past investigations and displays them in an expander:
```
💡 Similar Past Investigations Found
  - ransomware bitcoin payment
    📅 2025-11-29 | 📊 18 results
    📄 summary_2025-11-29_14-30-22.md
```

## Entity Extraction

Robin automatically extracts these entity types from investigation summaries:

### 1. Onion Domains
**Pattern**: `[a-z2-7]{16,56}\.onion`
**Example**: `example3yxv7qazqedkvpqlqyfzqx6hj5ixqgdnhqnzcfqjw4bxq.onion`

### 2. Email Addresses
**Pattern**: Standard email regex
**Example**: `contact@example.com`

### 3. Bitcoin Addresses
**Patterns**:
- Legacy: `[13][a-km-zA-HJ-NP-Z1-9]{25,34}`
- SegWit: `bc1[a-z0-9]{39,59}`

**Examples**:
- `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`
- `bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`

### 4. Ethereum Addresses
**Pattern**: `0x[a-fA-F0-9]{40}`
**Example**: `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4`

### 5. IPv4 Addresses
**Pattern**: `(?:\d{1,3}\.){3}\d{1,3}`
**Example**: `192.168.1.1`

### 6. CVE Identifiers
**Pattern**: `CVE-\d{4}-\d{4,7}` (case-insensitive)
**Example**: `CVE-2024-1234`

### 7. MD5 Hashes
**Pattern**: `[a-fA-F0-9]{32}`
**Example**: `5d41402abc4b2a76b9719d911017c592`

### 8. SHA256 Hashes
**Pattern**: `[a-fA-F0-9]{64}`
**Example**: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

## Database Location

**Default**: `robin_memory.db` in the project root

The database is created automatically on first run. No setup required!

```
robin/
├── robin_memory.db          # SQLite database
├── memory.py                # Memory module
├── main.py                  # CLI with memory integration
└── ui.py                    # Web UI with memory integration
```

## API Reference

### Core Methods

```python
from memory import get_memory

# Get singleton memory instance
memory = get_memory()

# Start a session
session_id = memory.start_session()

# Save an investigation
investigation_id = memory.save_investigation(
    query="ransomware payments",
    refined_query="ransomware cryptocurrency payment methods",
    model="grok-4.1-fast-free",
    summary="...",
    result_count=145,
    filtered_count=20,
    screenshot_count=5,
    duration_seconds=87,
    summary_file="summary_2025-11-30.md",
    session_id=session_id
)

# Save search results
memory.save_search_results(
    investigation_id,
    search_results,
    filtered_urls
)

# Extract and save entities
memory.extract_and_save_entities(
    investigation_id,
    summary_text
)

# End session
memory.end_session(session_id)
```

### Query Methods

```python
# Get investigation history
history = memory.get_investigation_history(limit=50)
# Returns: [{"id": 1, "query": "...", "model": "...", ...}, ...]

# Find similar investigations
similar = memory.get_similar_investigations("ransomware", limit=5)
# Returns: [{"id": 1, "query": "...", "score": 3, ...}, ...]

# Get statistics
stats = memory.get_statistics()
# Returns: {
#   "total_investigations": 15,
#   "total_entities": 142,
#   "entity_breakdown": {"bitcoin": 8, "onion_domain": 42, ...},
#   "top_models": [{"model": "grok-4.1-fast-free", "count": 10}, ...],
#   "total_screenshots": 45,
#   "avg_results": 123.4
# }

# Get entity statistics
entity_stats = memory.get_entity_statistics()
# Returns: {"onion_domain": 42, "email": 15, "bitcoin": 8, ...}

# Get top entities
top_entities = memory.get_top_entities(entity_type="bitcoin", limit=20)
# Returns: [{"entity_type": "bitcoin", "value": "1A1z...", "frequency": 5, ...}, ...]

# Search for specific entity
entity_info = memory.search_entities("example.onion")
# Returns: {
#   "entity": {"id": 1, "entity_type": "onion_domain", "value": "...", ...},
#   "investigations": [{"id": 1, "query": "...", ...}, ...]
# }

# Get context for new query
context = memory.get_context_for_query("ransomware payment")
# Returns: {
#   "similar_investigations": [...],
#   "related_entities": [...],
#   "suggested_refinements": [...]
# }
```

### Management Methods

```python
# Export database to JSON
memory.export_database("backup_20251130.json")

# Cleanup old data
deleted_count = memory.cleanup_old_data(days_old=90)

# Close connection
memory.close()
```

## Export Format

When you export the database, you get a JSON file with this structure:

```json
{
  "investigations": [
    {
      "id": 1,
      "query": "ransomware payments",
      "refined_query": "ransomware cryptocurrency payment methods",
      "model": "grok-4.1-fast-free",
      "timestamp": "2025-11-30 14:30:22",
      "summary": "...",
      "result_count": 145,
      "filtered_count": 20,
      "screenshot_count": 5,
      "duration_seconds": 87,
      "summary_file": "summary_2025-11-30_14-30-22.md"
    }
  ],
  "entities": [
    {
      "entity_type": "bitcoin",
      "value": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
      "frequency": 3,
      "first_seen": "2025-11-29 10:15:30",
      "last_seen": "2025-11-30 14:30:22"
    }
  ],
  "entity_stats": {
    "onion_domain": 42,
    "email": 15,
    "bitcoin": 8
  },
  "exported_at": "2025-11-30T15:45:00"
}
```

## Use Cases

### 1. Track Investigation Campaign
Monitor a specific threat actor over time:
```bash
# Investigation 1
python3 main.py cli -m grok-4.1-fast-free -q "APT28 activity"

# Investigation 2 (weeks later)
python3 main.py cli -m grok-4.1-fast-free -q "APT28 malware"

# Robin automatically shows: "Found similar past investigations"
```

### 2. Entity Relationship Mapping
Track how entities appear across investigations:
```python
# Find all investigations mentioning a Bitcoin address
entity_info = memory.search_entities("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

for inv in entity_info['investigations']:
    print(f"Investigation: {inv['query']} on {inv['timestamp']}")
```

### 3. Threat Intelligence Collection
Build a knowledge base over time:
- Track emerging threats
- Monitor cryptocurrency addresses
- Follow onion domain evolution
- Correlate CVEs with dark web discussions

### 4. Investigation Analytics
Understand your research patterns:
```python
stats = memory.get_statistics()
print(f"Total investigations: {stats['total_investigations']}")
print(f"Most used model: {stats['top_models'][0]['model']}")
print(f"Average results per investigation: {stats['avg_results']}")
```

## Performance Considerations

### Database Size
- ~10 KB per investigation (without summary text)
- ~50 KB per investigation (with full summary)
- 100 investigations ≈ 5 MB
- 1,000 investigations ≈ 50 MB

**Recommendation**: Cleanup old data every 90 days

### Query Performance
- All queries use indexed columns
- Sub-millisecond lookups for history/entities
- Similar investigation matching: O(n) but limited to last 100

### Memory Usage
- Database connection: ~1 MB RAM
- Minimal overhead per query
- Singleton pattern ensures one connection

## Troubleshooting

### Database Locked Error
**Cause**: Multiple processes accessing database
**Solution**: Only run one instance of Robin at a time

### Memory Fills Up
**Cause**: Too many investigations stored
**Solution**: Use cleanup feature in UI or run:
```python
memory.cleanup_old_data(days_old=30)
```

### Entity Extraction Misses Data
**Cause**: Non-standard format or encoding
**Solution**: Entities use regex patterns - some edge cases may be missed. This is expected.

### Export File Too Large
**Cause**: Large number of investigations with full summaries
**Solution**: Clean up old data before exporting, or export in chunks

## Security Considerations

⚠️ **Important Security Notes:**

1. **Database Encryption**: SQLite database is **not encrypted** by default
   - Sensitive data (onion URLs, crypto addresses, summaries) stored in plaintext
   - Secure your system and database file
   - Consider full-disk encryption

2. **Sensitive Information**: Database contains:
   - Investigation queries (may reveal research targets)
   - Onion URLs (dark web sites visited)
   - Extracted entities (IOCs, addresses, emails)
   - Full intelligence summaries

3. **Sharing**: Be careful sharing exports
   - Remove sensitive investigations before exporting
   - Sanitize entity data if needed
   - Use cleanup feature to remove old/sensitive data

4. **Access Control**: Protect the database file
   - Set appropriate file permissions
   - Limit user access on multi-user systems
   - Back up to secure locations only

## Advanced Usage

### Custom Entity Extraction

Extend the entity extraction in `memory.py`:

```python
def _extract_entities(self, text: str) -> Dict[str, List[str]]:
    entities = {
        'onion_domain': [],
        'email': [],
        # ... existing types ...
        'custom_pattern': [],  # Add your custom type
    }

    # Add custom regex
    entities['custom_pattern'] = list(set(re.findall(r'YOUR_REGEX_HERE', text)))

    return {k: v for k, v in entities.items() if v}
```

### Programmatic Analysis

Build custom analytics:

```python
from memory import get_memory
import pandas as pd

memory = get_memory()

# Get all investigations
history = memory.get_investigation_history(limit=10000)

# Convert to DataFrame for analysis
df = pd.DataFrame(history)

# Analyze by model
model_stats = df.groupby('model').agg({
    'id': 'count',
    'duration_seconds': 'mean',
    'filtered_count': 'mean'
})

print(model_stats)
```

### Entity Timeline

Track entity first/last seen dates:

```python
# Get top bitcoin addresses
btc_addresses = memory.get_top_entities(entity_type='bitcoin', limit=50)

for entity in btc_addresses:
    print(f"{entity['value']}")
    print(f"  First seen: {entity['first_seen']}")
    print(f"  Last seen: {entity['last_seen']}")
    print(f"  Frequency: {entity['frequency']} investigations")
```

## Future Enhancements

Planned features:
- [ ] Graph visualization of entity relationships
- [ ] Automated threat actor tracking
- [ ] Machine learning-based query suggestions
- [ ] Cross-investigation entity correlation
- [ ] Investigation templates based on history
- [ ] API endpoint for external integrations
- [ ] Advanced search with filters
- [ ] Investigation tagging/categorization
- [ ] Collaborative investigation sharing

## Integration Examples

### Investigation Workflow

```python
from memory import get_memory
from llm import get_llm, refine_query, generate_summary
from search import get_search_results
from scrape import scrape_multiple

# Initialize memory
memory = get_memory()
session_id = memory.start_session()

# Your query
query = "ransomware payment methods"

# Check for similar investigations
similar = memory.get_similar_investigations(query)
if similar:
    print("Found similar past investigations:")
    for inv in similar:
        print(f"  - {inv['query']}")

# Run investigation
llm = get_llm("grok-4.1-fast-free")
refined = refine_query(llm, query)
results = get_search_results(refined)
# ... continue pipeline ...

# Save to memory
investigation_id = memory.save_investigation(
    query=query,
    refined_query=refined,
    # ... other params ...
)

memory.end_session(session_id)
```

### Entity Monitoring

```python
# Monitor a specific Bitcoin address
target_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

# Search for it
entity_info = memory.search_entities(target_address)

if entity_info:
    print(f"Entity found: {entity_info['entity']['value']}")
    print(f"Frequency: {entity_info['entity']['frequency']}")
    print(f"Related investigations:")
    for inv in entity_info['investigations']:
        print(f"  - {inv['query']} ({inv['timestamp']})")
else:
    print("Entity not found in database")
```

## Support

For issues or questions:
1. Check this documentation
2. Review `memory.py` source code
3. Check database with SQLite browser: `sqlite3 robin_memory.db`
4. Open GitHub issue with relevant details

## Examples

### Research Campaign

```bash
# Day 1: Initial investigation
python3 main.py cli -m grok-4.1-fast-free -q "darknet markets 2025"

# Day 7: Follow-up
python3 main.py cli -m grok-4.1-fast-free -q "darknet marketplace trends"
# Robin shows: "Found similar past investigations"

# Day 30: Analysis
python3 main.py cli -m grok-4.1-fast-free -q "dark web market shutdown"
# Robin shows: Previous 2 investigations with related queries
```

### Entity Tracking

```bash
# Investigation mentions Bitcoin address
python3 main.py cli -m grok-4.1-fast-free -q "ransomware payment analysis"

# Later: Search for that address in UI
# 🔍 Entity Breakdown expander shows bitcoin addresses tracked
# Click to see all investigations where it appeared
```

---

**💾 Happy Investigating with Persistent Memory!**

*Remember: With great memory comes great responsibility. Secure your database and handle sensitive data appropriately.*
