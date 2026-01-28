"""
Base Skill class for Buddy Voice Assistant
All skills inherit from this class.
"""
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod

# Import SkillResponse for type hints
from assistant.skill_response import SkillResponse


class BaseSkill(ABC):
    """Base class for all skills"""
    
    # Skill metadata - override in subclass
    name: str = "base"
    description: str = "Base skill"
    keywords: List[str] = []
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
    
    def configure(self, config: Dict[str, Any]):
        """Set skill configuration"""
        self.config = config
    
    @abstractmethod
    async def handle(self, text: str, context: Dict[str, Any]) -> Union[str, SkillResponse]:
        """
        Handle user input and return response.
        
        Args:
            text: User's spoken text
            context: Dict containing 'llm' (LLMRouter) and other helpers
            
        Returns:
            Response string or SkillResponse object with conversation control
        """
        pass
    
    def matches(self, text: str) -> bool:
        """
        Quick keyword check for routing.
        Returns True if any keyword is found in text.
        """
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.keywords)


# Alias for backward compatibility
Skill = BaseSkill
