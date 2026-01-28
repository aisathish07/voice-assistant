"""
Calendar Skill - Google Calendar integration
"""
import logging
import os.path
import datetime
from typing import Dict, Any, List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")

class CalendarSkill:
    """
    Reads and creates Google Calendar events.
    """
    
    def __init__(self):
        self.keywords = ["calendar", "schedule", "events", "meeting", "appointment"]
        self.creds = None
        self.service = None
        self._auth_completed = False
        
        # Try to authenticate on startup
        try:
            self._authenticate(interactive=False)
        except Exception as e:
            logger.warning(f"Calendar auth failed (expected for first run): {e}")

    def _authenticate(self, interactive=True):
        """Authenticate with Google Calendar API"""
        token_path = os.path.join(CACHE_DIR, 'token.json')
        creds_path = 'credentials.json' # User must provide this
        
        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not interactive:
                    raise Exception("Auth required")
                    
                if not os.path.exists(creds_path):
                    raise FileNotFoundError("credentials.json not found. Please download it from Google Cloud Console.")
                    
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
                
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())
                
        self.service = build('calendar', 'v3', credentials=self.creds)
        self._auth_completed = True
        logger.info("✅ Google Calendar connected")

    async def handle(self, text: str, context: Dict[str, Any]) -> str:
        """Handle calendar commands"""
        if not self._auth_completed:
            # Check if we have credentials.json
            if not os.path.exists('credentials.json'):
                return "I need a 'credentials.json' file to access your calendar. Please download it from Google Cloud Console."
            
            try:
                self._authenticate(interactive=True)
            except Exception as e:
                return f"Authentication failed: {e}"

        text = text.lower()
        
        # List events
        if "what" in text or "list" in text or "show" in text:
            return self._list_events()
            
        # Create event (simple parsing)
        if "create" in text or "add" in text or "schedule" in text:
            # Very basic parsing: "schedule meeting [summary] at [time]"
            return "I can't create events yet via voice, but I can read your schedule!"
            
        return "I can list your upcoming events. Just say 'What's on my calendar?'"

    def _list_events(self) -> str:
        """List next 5 upcoming events"""
        try:
            now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
            events_result = self.service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=5, singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if not events:
                return 'No upcoming events found.'

            response = "Here are your next 5 events: "
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Parse date to readable format
                try:
                    dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    time_str = dt.strftime("%A at %I:%M %p")
                except:
                    time_str = start
                    
                response += f"{event['summary']} on {time_str}. "
                
            return response
            
        except Exception as e:
            logger.error(f"Calendar error: {e}")
            return "I had trouble checking your calendar."
