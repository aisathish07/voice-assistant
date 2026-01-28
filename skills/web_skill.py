import os
from skills.base_skill import BaseSkill
from assistant.web_agent import WebAgent
from typing import Any, Optional

agent = WebAgent()

class Skill(BaseSkill):
    name = "web"
    keywords = ["google", "search", "browse", "look up"]

    async def handle(self, text: str, context: Any) -> Optional[str]:
        if os.getenv("WEB_AGENT_ENABLED", "").lower() != "true":
            return "Web search is disabled (set WEB_AGENT_ENABLED=true)."

        # Extract query by removing a keyword
        query = text.lower()
        for kw in self.keywords:
            if query.startswith(kw):
                query = query[len(kw):].strip()
                break
        
        if not query:
            return "What would you like me to search for?"

        results = await agent.search(query)
        if not results:
            return f"No results for '{query}'."
        
        titles = [r["title"] for r in results[:3]]
        return "Top results: " + " | ".join(titles)