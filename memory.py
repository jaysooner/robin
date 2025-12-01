import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib


class RobinMemory:
    """Persistent memory and context management for Robin investigations"""

    def __init__(self, db_path: str = "robin_memory.db"):
        self.db_path = Path(db_path)
        self.conn = None
        self.initialize_database()

    def initialize_database(self):
        """Create database and tables if they don't exist"""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()

        # Investigations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                refined_query TEXT,
                model TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                summary TEXT,
                screenshot_count INTEGER DEFAULT 0,
                result_count INTEGER DEFAULT 0,
                filtered_count INTEGER DEFAULT 0,
                duration_seconds INTEGER,
                search_engines INTEGER DEFAULT 21,
                summary_file TEXT,
                session_id TEXT
            )
        """)

        # Search results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id INTEGER,
                url TEXT NOT NULL,
                title TEXT,
                was_filtered BOOLEAN DEFAULT 0,
                was_scraped BOOLEAN DEFAULT 0,
                relevance_score FLOAT,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id)
            )
        """)

        # Entities table (artifacts: domains, emails, crypto addresses, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                value TEXT NOT NULL,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                frequency INTEGER DEFAULT 1,
                UNIQUE(entity_type, value)
            )
        """)

        # Investigation-Entity relationship
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investigation_entities (
                investigation_id INTEGER,
                entity_id INTEGER,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id),
                FOREIGN KEY (entity_id) REFERENCES entities(id),
                PRIMARY KEY (investigation_id, entity_id)
            )
        """)

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ended_at DATETIME,
                investigation_count INTEGER DEFAULT 0
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_investigations_timestamp ON investigations(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_frequency ON entities(frequency)")

        self.conn.commit()

    def start_session(self) -> str:
        """Start a new investigation session"""
        session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:16]
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
        self.conn.commit()
        return session_id

    def end_session(self, session_id: str):
        """End an investigation session"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET ended_at = CURRENT_TIMESTAMP,
                investigation_count = (
                    SELECT COUNT(*) FROM investigations WHERE session_id = ?
                )
            WHERE id = ?
        """, (session_id, session_id))
        self.conn.commit()

    def save_investigation(
        self,
        query: str,
        refined_query: str,
        model: str,
        summary: str,
        result_count: int = 0,
        filtered_count: int = 0,
        screenshot_count: int = 0,
        duration_seconds: int = 0,
        summary_file: str = None,
        session_id: str = None
    ) -> int:
        """Save an investigation to memory"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO investigations (
                query, refined_query, model, summary, result_count,
                filtered_count, screenshot_count, duration_seconds,
                summary_file, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            query, refined_query, model, summary, result_count,
            filtered_count, screenshot_count, duration_seconds,
            summary_file, session_id
        ))
        self.conn.commit()
        return cursor.lastrowid

    def save_search_results(self, investigation_id: int, results: List[Dict], filtered_urls: List[str] = None):
        """Save search results for an investigation"""
        cursor = self.conn.cursor()
        filtered_urls_set = set(filtered_urls or [])

        for result in results:
            url = result.get('link', '')
            was_filtered = url in filtered_urls_set
            cursor.execute("""
                INSERT INTO search_results (investigation_id, url, title, was_filtered)
                VALUES (?, ?, ?, ?)
            """, (investigation_id, url, result.get('title', ''), was_filtered))

        self.conn.commit()

    def extract_and_save_entities(self, investigation_id: int, text: str):
        """Extract entities from text and save them"""
        entities = self._extract_entities(text)
        cursor = self.conn.cursor()

        for entity_type, values in entities.items():
            for value in values:
                # Insert or update entity
                cursor.execute("""
                    INSERT INTO entities (entity_type, value, frequency)
                    VALUES (?, ?, 1)
                    ON CONFLICT(entity_type, value)
                    DO UPDATE SET
                        frequency = frequency + 1,
                        last_seen = CURRENT_TIMESTAMP
                """, (entity_type, value))

                # Get entity ID
                cursor.execute("""
                    SELECT id FROM entities WHERE entity_type = ? AND value = ?
                """, (entity_type, value))
                entity_id = cursor.fetchone()[0]

                # Link to investigation
                cursor.execute("""
                    INSERT OR IGNORE INTO investigation_entities (investigation_id, entity_id)
                    VALUES (?, ?)
                """, (investigation_id, entity_id))

        self.conn.commit()

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract various entities from text"""
        entities = {
            'onion_domain': [],
            'email': [],
            'bitcoin': [],
            'ethereum': [],
            'ipv4': [],
            'cve': [],
            'hash_md5': [],
            'hash_sha256': [],
        }

        # Onion domains
        entities['onion_domain'] = list(set(re.findall(r'[a-z2-7]{16,56}\.onion', text.lower())))

        # Email addresses
        entities['email'] = list(set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)))

        # Bitcoin addresses
        entities['bitcoin'] = list(set(re.findall(r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b', text)))
        entities['bitcoin'].extend(list(set(re.findall(r'\bbc1[a-z0-9]{39,59}\b', text))))

        # Ethereum addresses
        entities['ethereum'] = list(set(re.findall(r'\b0x[a-fA-F0-9]{40}\b', text)))

        # IPv4 addresses
        entities['ipv4'] = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))

        # CVE identifiers
        entities['cve'] = list(set(re.findall(r'\bCVE-\d{4}-\d{4,7}\b', text, re.IGNORECASE)))

        # MD5 hashes
        entities['hash_md5'] = list(set(re.findall(r'\b[a-fA-F0-9]{32}\b', text)))

        # SHA256 hashes
        entities['hash_sha256'] = list(set(re.findall(r'\b[a-fA-F0-9]{64}\b', text)))

        # Remove empty lists
        return {k: v for k, v in entities.items() if v}

    def get_investigation_history(self, limit: int = 50) -> List[Dict]:
        """Get recent investigation history"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                id, query, refined_query, model, timestamp,
                result_count, filtered_count, screenshot_count,
                duration_seconds, summary_file
            FROM investigations
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_similar_investigations(self, query: str, limit: int = 5) -> List[Dict]:
        """Find similar past investigations"""
        cursor = self.conn.cursor()
        # Simple similarity based on keyword matching
        words = set(query.lower().split())

        cursor.execute("""
            SELECT
                id, query, refined_query, timestamp,
                result_count, filtered_count, summary_file
            FROM investigations
            ORDER BY timestamp DESC
            LIMIT 100
        """)

        all_investigations = cursor.fetchall()
        scored_investigations = []

        for inv in all_investigations:
            inv_words = set(inv['query'].lower().split())
            common_words = words.intersection(inv_words)
            score = len(common_words)

            if score > 0:
                scored_investigations.append((score, dict(inv)))

        # Sort by score and return top matches
        scored_investigations.sort(key=lambda x: x[0], reverse=True)
        return [inv for score, inv in scored_investigations[:limit]]

    def get_entity_statistics(self) -> Dict:
        """Get statistics about tracked entities"""
        cursor = self.conn.cursor()

        stats = {}
        cursor.execute("SELECT entity_type, COUNT(*) as count FROM entities GROUP BY entity_type")

        for row in cursor.fetchall():
            stats[row['entity_type']] = row['count']

        return stats

    def get_top_entities(self, entity_type: str = None, limit: int = 20) -> List[Dict]:
        """Get most frequent entities"""
        cursor = self.conn.cursor()

        if entity_type:
            cursor.execute("""
                SELECT entity_type, value, frequency, first_seen, last_seen
                FROM entities
                WHERE entity_type = ?
                ORDER BY frequency DESC
                LIMIT ?
            """, (entity_type, limit))
        else:
            cursor.execute("""
                SELECT entity_type, value, frequency, first_seen, last_seen
                FROM entities
                ORDER BY frequency DESC
                LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def search_entities(self, entity_value: str) -> List[Dict]:
        """Search for specific entity and find related investigations"""
        cursor = self.conn.cursor()

        # Find the entity
        cursor.execute("""
            SELECT id, entity_type, value, frequency, first_seen, last_seen
            FROM entities
            WHERE value LIKE ?
        """, (f'%{entity_value}%',))

        entity = cursor.fetchone()
        if not entity:
            return []

        # Find related investigations
        cursor.execute("""
            SELECT i.id, i.query, i.timestamp, i.summary_file
            FROM investigations i
            JOIN investigation_entities ie ON i.id = ie.investigation_id
            WHERE ie.entity_id = ?
            ORDER BY i.timestamp DESC
        """, (entity['id'],))

        investigations = cursor.fetchall()

        return {
            'entity': dict(entity),
            'investigations': [dict(inv) for inv in investigations]
        }

    def get_context_for_query(self, query: str) -> Dict:
        """Build context for a new query based on history"""
        context = {
            'similar_investigations': self.get_similar_investigations(query),
            'related_entities': [],
            'suggested_refinements': []
        }

        # Extract potential entities from query
        entities = self._extract_entities(query)

        # Find known entities from query
        for entity_type, values in entities.items():
            for value in values:
                result = self.search_entities(value)
                if result:
                    context['related_entities'].append(result)

        return context

    def export_database(self, output_file: str):
        """Export database to JSON"""
        export_data = {
            'investigations': self.get_investigation_history(limit=10000),
            'entities': self.get_top_entities(limit=10000),
            'entity_stats': self.get_entity_statistics(),
            'exported_at': datetime.now().isoformat()
        }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        cursor = self.conn.cursor()

        stats = {}

        # Total investigations
        cursor.execute("SELECT COUNT(*) as count FROM investigations")
        stats['total_investigations'] = cursor.fetchone()['count']

        # Total entities
        cursor.execute("SELECT COUNT(*) as count FROM entities")
        stats['total_entities'] = cursor.fetchone()['count']

        # Entity breakdown
        stats['entity_breakdown'] = self.get_entity_statistics()

        # Most used models
        cursor.execute("""
            SELECT model, COUNT(*) as count
            FROM investigations
            GROUP BY model
            ORDER BY count DESC
            LIMIT 5
        """)
        stats['top_models'] = [dict(row) for row in cursor.fetchall()]

        # Total screenshots
        cursor.execute("SELECT SUM(screenshot_count) as total FROM investigations")
        stats['total_screenshots'] = cursor.fetchone()['total'] or 0

        # Average results per investigation
        cursor.execute("SELECT AVG(result_count) as avg FROM investigations WHERE result_count > 0")
        stats['avg_results'] = round(cursor.fetchone()['avg'] or 0, 1)

        return stats

    def cleanup_old_data(self, days_old: int = 90):
        """Remove investigations older than specified days"""
        cursor = self.conn.cursor()

        cursor.execute("""
            DELETE FROM investigations
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days_old,))

        deleted = cursor.rowcount
        self.conn.commit()

        return deleted

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# Singleton instance
_memory_instance = None


def get_memory() -> RobinMemory:
    """Get or create memory instance"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = RobinMemory()
    return _memory_instance
