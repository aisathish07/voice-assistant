"""
Vision Skill - Screenshot capture and AI analysis using Gemini Vision
"""
import logging
import io
import base64
from typing import Dict, Any
from PIL import ImageGrab
from google import genai

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class VisionSkill:
    """
    Captures screenshots and analyzes them using Gemini Vision API.
    Enables commands like "What's on my screen?"
    """
    
    def __init__(self):
        self.keywords = ["screen", "see", "look", "what's on", "screenshot", "vision", "display"]
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        """Initialize Gemini client"""
        if not GEMINI_API_KEY:
            logger.warning("No Gemini API key - Vision skill disabled")
            return
            
        try:
            self._client = genai.Client(api_key=GEMINI_API_KEY)
            self._available = True
            logger.info("✅ Vision skill ready (Gemini)")
        except Exception as e:
            logger.error(f"Failed to init Gemini client: {e}")

    async def handle(self, text: str, context: Dict[str, Any]) -> str:
        """Handle vision commands"""
        text = text.lower()
        
        if not self._available:
            return "Vision is not available. Please set GEMINI_API_KEY in your .env file."

        # Capture screenshot
        try:
            screenshot = ImageGrab.grab()
            
            # Convert to bytes
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()
            
            # Encode to base64
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return "I couldn't capture the screen."

        # Analyze with Gemini Vision
        try:
            # Build prompt based on user question
            if "read" in text or "text" in text:
                prompt = "Read and transcribe all visible text on this screen. Be thorough."
            elif "describe" in text:
                prompt = "Describe what you see on this screen in detail."
            elif "help" in text or "how" in text:
                prompt = "Look at this screen and help the user with what they're working on. Provide guidance."
            elif "code" in text or "error" in text:
                prompt = "Analyze this screen for any code or error messages. Explain what you see and suggest fixes if applicable."
            else:
                # Default: general description
                prompt = "Briefly describe what's on this screen. Focus on the main content and any important details."

            # Call Gemini Vision
            response = self._client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                ]
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"I captured the screen but couldn't analyze it: {e}"
