import os
import aiohttp
from skills.base_skill import BaseSkill

class GoogleSearchSkill(BaseSkill):
    name = "google_search"
    description = "Searches the web using Google Custom Search API"
    keywords = ["search for", "google", "find info on", "look up", "who is", "what is"]

    async def handle(self, query: str, context: dict) -> str:
        api_key = os.getenv("GOOGLE_CLIENT_ID") # Using Client ID as API Key for simplicity if enabled, or specific API Key
        # Note: Usually Custom Search needs a specific API Key, not OAuth Client ID. 
        # If user has a specific "API Key" for Custom Search, it should be used.
        # For now, we'll try to use the GOOGLE_CLIENT_ID if it works as a key (unlikely) or ask user for a specific key.
        # BETTER: Let's assume the user might need a specific API Key for this.
        # I will check if there is a specific GOOGLE_API_KEY env var, if not, I'll try to use the one we have.
        
        # Actually, Custom Search needs a standard API Key (AIza...), not Client ID.
        # The user provided a key earlier for YouTube.
        # That SAME key usually works for Custom Search if the API is enabled!
        
        api_key = os.getenv("YOUTUBE_API_KEY") # Re-using the YouTube Key which is a standard Google API Key
        cx = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

        if not api_key or not cx:
            return "I need both a Google API Key and a Search Engine ID to search the web."

        # Extract search term
        search_term = query
        for kw in self.keywords:
            if query.lower().startswith(kw):
                search_term = query[len(kw):].strip()
                break
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": search_term,
            "num": 3 # Top 3 results
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("items", [])
                        if not items:
                            return f"I couldn't find anything for '{search_term}'."
                        
                        result_text = f"Here's what I found for '{search_term}':\n\n"
                        for item in items:
                            title = item.get("title")
                            snippet = item.get("snippet")
                            link = item.get("link")
                            result_text += f"🔹 **{title}**\n{snippet}\n🔗 {link}\n\n"
                        
                        return result_text
                    else:
                        return f"Error searching Google: {response.status}"
        except Exception as e:
            return f"Failed to perform search: {str(e)}"
