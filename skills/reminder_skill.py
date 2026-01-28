"""
Reminder Skill - Sets alarms and reminders
"""
import threading
import time
import re
import sqlite3
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assistant.skill_router import SkillResponse
from config import SOUNDS_DIR

logger = logging.getLogger(__name__)

class ReminderSkill:
    """
    Sets reminders/alarms and triggers them in the background.
    """
    
    def __init__(self):
        self.keywords = ["remind", "alarm", "timer", "alert"]
        self.db_path = Path(__file__).parent.parent / "cache" / "reminders.db"
        self._running = False
        self._thread = None
        self._tts_callback = None
        
        # Ensure DB exists
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
        self._init_db()
        self.start_worker()

    def set_tts_callback(self, tts):
        """Set TTS callback for announcing reminders"""
        self._tts_callback = tts

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _init_db(self):
        """Initialize database"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id TEXT PRIMARY KEY,
                        message TEXT NOT NULL,
                        trigger_time DATETIME NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending'
                    )
                """)
        except Exception as e:
            logger.error(f"Failed to init reminder DB: {e}")

    def start_worker(self):
        """Start background worker thread"""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("   ⏰ Reminder worker started")

    def _worker_loop(self):
        """Check for triggered reminders every second"""
        while self._running:
            try:
                now = datetime.now()
                triggered = []
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, message FROM reminders 
                        WHERE status = 'pending' AND trigger_time <= ?
                    """, (now,))
                    triggered = cursor.fetchall()
                    
                    if triggered:
                        # Mark as completed
                        ids = [t[0] for t in triggered]
                        cursor.execute(f"""
                            UPDATE reminders SET status = 'completed' 
                            WHERE id IN ({','.join(['?']*len(ids))})
                        """, ids)
                        conn.commit()
                
                # Trigger alerts
                for _, message in triggered:
                    self._trigger_alert(message)
                    
            except Exception as e:
                logger.error(f"Reminder worker error: {e}")
                
            time.sleep(1.0)

    def _trigger_alert(self, message: str):
        """Play sound and speak message"""
        print(f"\n⏰ ALERT: {message}\n")
        
        # Play alarm sound if exists
        # TODO: Play sound via audio manager
        
        # Speak
        if self._tts_callback:
            # We need to run sync TTS from this thread, but TTS might expect main thread
            # Simply calling speak() usually works if thread-safe or fire-and-forget
            try:
                self._tts_callback.speak(f"Reminder: {message}")
            except Exception as e:
                print(f"Failed to speak reminder: {e}")

    async def handle(self, text: str, context: Dict[str, Any]) -> str:
        """Handle reminder requests"""
        text = text.lower()
        
        # Parse "remind me in X minutes to Y"
        # or "set alarm for 5 minutes"
        
        duration = 0
        unit = "seconds"
        message = "Time's up!"
        
        # Extract duration
        m_min = re.search(r"(\d+)\s*(?:min|minute)", text)
        m_sec = re.search(r"(\d+)\s*(?:sec|second)", text)
        m_hour = re.search(r"(\d+)\s*(?:hour|hr)", text)
        
        if m_hour:
            duration += int(m_hour.group(1)) * 3600
        if m_min:
            duration += int(m_min.group(1)) * 60
        if m_sec:
            duration += int(m_sec.group(1))
            
        if duration == 0:
            return "I didn't catch the time. Try 'Remind me in 5 minutes'."
            
        # Extract message
        # "remind me in 5 mins TO check the oven"
        m_msg = re.search(r"(?:to|that)\s+(.+)$", text)
        if m_msg:
            message = m_msg.group(1).strip()
        elif "alarm" in text or "timer" in text:
            message = "Alarm"
            
        # Set reminder
        trigger_time = datetime.now() + timedelta(seconds=duration)
        cid = str(uuid.uuid4())
        
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO reminders (id, message, trigger_time) VALUES (?, ?, ?)",
                (cid, message, trigger_time)
            )
        
        # Format confirmation
        time_str = trigger_time.strftime("%I:%M %p")
        return f"OK, I've set a reminder for {message} at {time_str}."

    def stop(self):
        self._running = False
