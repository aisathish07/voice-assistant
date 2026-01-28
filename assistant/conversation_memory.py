"""
Conversation Memory - Persistent conversation history with SQLite backend
"""
import sqlite3
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

class ConversationMemory:
    """
    Persistent conversation memory that saves to SQLite database.
    Robust, thread-safe, and scalable.
    """
    
    def __init__(self, storage_path: Optional[Path] = None, max_messages: int = 100):
        """
        Initialize persistent memory.
        
        Args:
            storage_path: Path to DB file. Defaults to cache/conversation.db
            max_messages: Limit for retrieval (DB stores everything effectively)
        """
        if storage_path is None:
            base_dir = Path(__file__).parent.parent
            storage_path = base_dir / "cache" / "conversation.db"
        
        self.db_path = Path(storage_path)
        self.max_messages = max_messages
        self._lock = threading.Lock()
        
        # Ensure directory exists
        if not self.db_path.parent.exists():
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"   ⚠️ Could not create cache directory: {e}")
                
        self._init_db()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-safe DB connection"""
        return sqlite3.connect(
            str(self.db_path), 
            check_same_thread=False,
            timeout=10.0
        )

    def _init_db(self):
        """Initialize database schema"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            metadata TEXT
                        )
                    """)
                    
                    # Create index for faster retrieval
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
                    
                    conn.commit()
            except Exception as e:
                print(f"   ⚠️ Memory DB Init Error: {e}")

    def add(self, role: str, content: str, metadata: Dict[str, Any] = None) -> None:
        """Add a message to history"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        "INSERT INTO messages (role, content, timestamp, metadata) VALUES (?, ?, ?, ?)",
                        (
                            role, 
                            content, 
                            datetime.now(), 
                            json.dumps(metadata) if metadata else None
                        )
                    )
                    conn.commit()
            except Exception as e:
                print(f"   ⚠️ Failed to save message: {e}")

    def add_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Add user/assistant pair"""
        self.add("user", user_msg)
        self.add("assistant", assistant_msg)

    def get_recent(self, n: int = None) -> List[Dict[str, str]]:
        """Get N most recent messages, ordered chronologically"""
        limit = n if n else self.max_messages
        
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get last N messages (need subquery to get correct order)
                query = f"""
                    SELECT role, content 
                    FROM (
                        SELECT role, content, timestamp 
                        FROM messages 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ) 
                    ORDER BY timestamp ASC
                """
                
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
                
                return [
                    {"role": row["role"], "content": row["content"]} 
                    for row in rows
                ]
        except Exception as e:
            print(f"   ⚠️ Failed to retrieve memory: {e}")
            return []

    def clear(self):
        """Clear all history"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM messages")
                    conn.commit()
                print("   🗑️ Conversation memory cleared (SQLite)")
            except Exception as e:
                print(f"   ⚠️ Failed to clear memory: {e}")
                
    def __len__(self) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages")
                return cursor.fetchone()[0]
        except:
            return 0
