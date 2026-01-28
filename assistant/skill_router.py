"""
Skill Router - Hybrid keyword + LLM intent classification
"""
import os
import sys
import importlib.util
import asyncio
from typing import Dict, Any, List, Optional, Union
import ollama

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OLLAMA_HOST
from skills.base_skill import BaseSkill
from assistant.skill_response import SkillResponse


class SkillRouter:
    """
    Routes user input to appropriate skills using hybrid approach:
    1. Fast keyword matching (~1ms)
    2. LLM classification for ambiguous queries (~150ms)
    """
    
    def __init__(self, llm_router=None, tts=None, skills_dir: str = None):
        self.skills: Dict[str, BaseSkill] = {}
        self.skills_dir = skills_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "skills"
        )
        self.llm = llm_router
        self.tts = tts
        self._classifier_model = "gemma:2b"  # Fast, small model for classification
        
    def load_skills(self):
        """Dynamically load all skills from skills directory"""
        print("📦 Loading skills...")
        
        for filename in os.listdir(self.skills_dir):
            if not filename.endswith("_skill.py"):
                continue
            if filename == "base_skill.py":
                continue
                
            skill_path = os.path.join(self.skills_dir, filename)
            skill_name = filename[:-3]  # Remove .py
            
            try:
                spec = importlib.util.spec_from_file_location(skill_name, skill_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for Skill class or any class inheriting BaseSkill
                # Also explicitly check for our new skills
                skill_class = None
                
                # Explicit checks for new skills
                if skill_name == "reminder_skill":
                    skill_class = getattr(module, "ReminderSkill", None)
                elif skill_name == "clipboard_skill":
                    skill_class = getattr(module, "ClipboardSkill", None)
                elif skill_name == "calendar_skill":
                    skill_class = getattr(module, "CalendarSkill", None)
                elif skill_name == "vision_skill":
                    skill_class = getattr(module, "VisionSkill", None)
                elif skill_name == "mcp_skill":
                    skill_class = getattr(module, "MCPSkill", None)
                    
                # Standard check
                if not skill_class:
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, BaseSkill) and 
                            attr is not BaseSkill):
                            skill_class = attr
                            break
                    
                # Fallback for simpler non-BaseSkill classes (duck typing)
                if not skill_class:
                     for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and attr_name.endswith("Skill"):
                             skill_class = attr
                             break

                if skill_class:
                    skill_instance = skill_class()
                    
                    # Inject dependencies if needed
                    # ReminderSkill needs TTS callback
                    if skill_name == "reminder_skill" and hasattr(skill_instance, "set_tts_callback") and getattr(self, "tts", None):
                        skill_instance.set_tts_callback(self.tts)
                        
                    # Use name attribute or class name
                    name = getattr(skill_instance, "name", skill_name.replace("_skill", ""))
                    self.skills[name] = skill_instance
                    print(f"   ✅ Loaded: {name}")
                    
            except Exception as e:
                print(f"   ⚠️ Failed to load {filename}: {e}")
        
        print(f"   Total skills: {len(self.skills)}")
    
    async def route(self, text: str, context: Dict[str, Any]) -> Optional[Union[str, SkillResponse]]:
        """
        Route user input to appropriate skill.
        
        Returns:
            Response string or SkillResponse if skill handled, None if should use LLM
        """
        # Phase 1: Fast keyword matching
        matched_skill = self._keyword_match(text)
        
        if matched_skill:
            print(f"   🎯 Keyword match: {matched_skill.name}")
            try:
                return await matched_skill.handle(text, context)
            except Exception as e:
                print(f"   ⚠️ Skill error: {e}")
                return None
        
        # Phase 2: LLM classification for ambiguous queries
        classified_skill = await self._llm_classify(text)
        
        if classified_skill and classified_skill in self.skills:
            print(f"   🧠 LLM classified: {classified_skill}")
            try:
                return await self.skills[classified_skill].handle(text, context)
            except Exception as e:
                print(f"   ⚠️ Skill error: {e}")
                return None
        
        # No skill matched - let main LLM handle it
        return None
    
    def _keyword_match(self, text: str) -> Optional[BaseSkill]:
        """Fast keyword-based skill matching"""
        for skill in self.skills.values():
            if skill.matches(text):
                return skill
        return None
    
    async def _llm_classify(self, text: str) -> Optional[str]:
        """Use small LLM to classify intent"""
        if not self.skills:
            return None
            
        skill_list = ", ".join([
            f"{name}: {skill.description}" 
            for name, skill in self.skills.items()
        ])
        
        prompt = f"""Classify this user request into one of these skills, or respond "general" if none match.
Skills: {skill_list}

User: "{text}"
Respond with ONLY the skill name or "general". Nothing else."""
        
        try:
            response = ollama.chat(
                model=self._classifier_model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": 20}  # Very short response
            )
            result = response['message']['content'].strip().lower()
            
            # Clean up response
            result = result.replace('"', '').replace("'", "").strip()
            
            if result == "general":
                return None
            return result if result in self.skills else None
            
        except Exception as e:
            print(f"   ⚠️ Classification failed: {e}")
            return None
    
    def get_skill_names(self) -> List[str]:
        """Get list of loaded skill names"""
        return list(self.skills.keys())
