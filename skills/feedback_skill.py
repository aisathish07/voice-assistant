"""
skills/feedback_skill.py
──────────────────────────────────────────────
Feedback Skill for Jarvis
Allows the user to provide feedback on the assistant's performance,
which is logged to the database for later review.
"""

from skills.base_skill import BaseSkill
import re

class Skill(BaseSkill):
    name = "feedback"
    keywords = ["feedback", "suggestion", "report", "comment"]

    async def handle(self, text, jarvis):
        # Extract the feedback content from the user's text
        # It looks for the text following one of the keywords.
        match = re.search(r"(?:feedback|suggestion|report|comment)\s+(.+)", text, re.IGNORECASE)
        
        if not match:
            return "What feedback would you like to provide? Please say something like 'feedback this was a good response.'"

        feedback_text = match.group(1).strip()
        
        if not feedback_text:
            return "It seems you didn't provide any feedback. Please try again."

        try:
            # Access the memory manager from the jarvis instance
            # and save the feedback.
            jarvis.memory.save_feedback(feedback_text)
            return "Thank you! Your feedback has been logged."
        except Exception as e:
            # Log the error if something goes wrong
            # This will appear in the main console log
            jarvis.logger.error(f"Failed to save feedback: {e}")
            return "Sorry, I was unable to save your feedback at this time."
