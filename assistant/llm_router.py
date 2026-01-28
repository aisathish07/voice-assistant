"""
LLM Router - Handles local (Ollama) and online (Groq, Nvidia, OpenRouter, Gemini) models
"""
import ollama
from google import genai
from groq import Groq
from openai import OpenAI
from typing import Optional, Generator, List, Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    OLLAMA_MODEL, GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY,
    OPENROUTER_API_KEY, OPENROUTER_MODEL,
    NVIDIA_API_KEY, NVIDIA_MODEL,
    LMSTUDIO_HOST, LMSTUDIO_MODEL
)
from assistant.personality import SYSTEM_PROMPT
from assistant.conversation_memory import ConversationMemory


class LLMRouter:
    """Routes between multiple LLM providers with fallback logic"""
    
    def __init__(self, prefer_local: bool = True):
        self.prefer_local = prefer_local
        self.max_history = 10
        self.memory = ConversationMemory(max_messages=self.max_history * 2) # Keep slightly more in history
        self._ollama_available: Optional[bool] = None
        self._ollama_model_name = OLLAMA_MODEL
        
        # Clients
        self._gemini_client: Optional[genai.Client] = None
        self._groq_client: Optional[Groq] = None
        self._openrouter_client: Optional[OpenAI] = None
        self._nvidia_client: Optional[OpenAI] = None
        self._lmstudio_client: Optional[OpenAI] = None
        self._lmstudio_available: Optional[bool] = None
        
    def _check_ollama(self) -> bool:
        """Check if Ollama is available and find best model"""
        if self._ollama_available is not None:
            return self._ollama_available
        
        try:
            response = ollama.list()
            available_models = []
            
            # Helper to get name
            def get_name(m):
                if isinstance(m, dict):
                    return m.get('name') or m.get('model')
                return getattr(m, 'model', None) or getattr(m, 'name', None)

            models_list = getattr(response, 'models', []) or response
            for m in models_list:
                name = get_name(m)
                if name:
                    available_models.append(name)
            
            print(f"   ✅ Ollama available. Models: {available_models}")
            
            if any(self._ollama_model_name in m for m in available_models):
                # Ensure we use the exact model name found (e.g., 'llama3.2:3b' instead of 'llama3.2')
                match = next((m for m in available_models if self._ollama_model_name in m), self._ollama_model_name)
                self._ollama_model_name = match
                self._ollama_available = True
                return True
            
            fallbacks = ["phi3", "mistral", "llama3", "gemma", "qwen", "tinyllama"]
            for fallback in fallbacks:
                match = next((m for m in available_models if fallback in m), None)
                if match:
                    print(f"   ⚠️ '{self._ollama_model_name}' not found, switching to '{match}'")
                    self._ollama_model_name = match
                    self._ollama_available = True
                    return True
            
            if available_models:
                 self._ollama_model_name = available_models[0]
                 self._ollama_available = True
                 return True

            self._ollama_available = False
            return False
            
        except Exception as e:
            print(f"   ⚠️ Ollama check failed: {e}")
            self._ollama_available = False
            return False

    def _check_lmstudio(self) -> bool:
        """Check if LM Studio is available"""
        if self._lmstudio_available is not None:
            return self._lmstudio_available
        
        try:
            # Initialize LM Studio client
            self._lmstudio_client = OpenAI(
                base_url=LMSTUDIO_HOST,
                api_key="lm-studio"  # LM Studio doesn't require a real key
            )
            # Test connection by listing models
            models = self._lmstudio_client.models.list()
            if models.data:
                model_names = [m.id for m in models.data]
                print(f"   ✅ LM Studio available. Models: {model_names}")
                self._lmstudio_available = True
                return True
            self._lmstudio_available = False
            return False
        except Exception as e:
            print(f"   ⚠️ LM Studio not available: {e}")
            self._lmstudio_available = False
            return False
            
    def _configure_online(self):
        """Lazy load online clients"""
        if not self._groq_client and GROQ_API_KEY:
            try:
                self._groq_client = Groq(api_key=GROQ_API_KEY)
            except Exception as e: print(f"⚠️ Groq Init: {e}")

        if not self._nvidia_client and NVIDIA_API_KEY:
            try:
                self._nvidia_client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=NVIDIA_API_KEY
                )
            except Exception as e: print(f"⚠️ Nvidia Init: {e}")

        if not self._openrouter_client and OPENROUTER_API_KEY:
            try:
                self._openrouter_client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=OPENROUTER_API_KEY
                )
            except Exception as e: print(f"⚠️ OpenRouter Init: {e}")

        if not self._gemini_client and GEMINI_API_KEY:
            try:
                self._gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception as e: print(f"⚠️ Gemini Init: {e}")

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """Build message list with conversation history"""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Load history from memory
        for msg in self.memory.get_recent(self.max_history):
            messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def chat(self, user_message: str) -> str:
        """Route message through available providers"""
        response = None
        self._configure_online()
        
        # 1. Ollama (Local - Speed/Primary)
        if self.prefer_local and self._check_ollama():
            response = self._chat_ollama(user_message)
        
        # 2. LM Studio (Local - Reasoning/Fallback)
        if response is None and self.prefer_local and self._check_lmstudio():
            response = self._chat_lmstudio(user_message)
        
        # 2. Groq (Speed)
        if response is None:
            response = self._chat_groq(user_message)

        # 3. Nvidia (Power)
        if response is None:
            response = self._chat_nvidia(user_message)

        # 4. OpenRouter (Flexibility)
        if response is None:
            response = self._chat_openrouter(user_message)

        # 5. Gemini (Context/Safety)
        if response is None:
            response = self._chat_gemini(user_message)
        
        # Final Failure
        if response is None:
            return "All my brain connections are down. Please check your internet and API keys."
        
        # Update history (Persisted)
        self.memory.add_exchange(user_message, response)
        return response
    
    def _chat_lmstudio(self, user_message: str) -> Optional[str]:
        """Chat with LM Studio (OpenAI-compatible API)"""
        if not self._lmstudio_client:
            return None
        try:
            messages = self._build_messages(user_message)
            completion = self._lmstudio_client.chat.completions.create(
                model=LMSTUDIO_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"   ⚠️ LM Studio: {e}")
            self._lmstudio_available = False
            return None
    
    def _chat_ollama(self, user_message: str) -> Optional[str]:
        try:
            messages = self._build_messages(user_message)
            response = ollama.chat(model=self._ollama_model_name, messages=messages)
            return response['message']['content']
        except Exception as e:
            print(f"   ⚠️ Ollama: {e}")
            self._ollama_available = False
            return None

    def _chat_groq(self, user_message: str) -> Optional[str]:
        if not self._groq_client: return None
        try:
            messages = self._build_messages(user_message)
            completion = self._groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages, temperature=0.7, max_tokens=1024
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"   ⚠️ Groq: {e}")
            return None

    def _chat_nvidia(self, user_message: str) -> Optional[str]:
        if not self._nvidia_client: return None
        try:
            messages = self._build_messages(user_message)
            completion = self._nvidia_client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=messages, temperature=0.7, max_tokens=1024
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"   ⚠️ Nvidia: {e}")
            return None

    def _chat_openrouter(self, user_message: str) -> Optional[str]:
        if not self._openrouter_client: return None
        try:
            messages = self._build_messages(user_message)
            completion = self._openrouter_client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                extra_headers={"HTTP-Referer": "https://github.com/buddy-assistant"},
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"   ⚠️ OpenRouter: {e}")
            return None

    def _chat_gemini(self, user_message: str) -> Optional[str]:
        if not self._gemini_client: return None
        try:
            # Reconstruct history from memory for Gemini
            history_text = self.memory.get_summary_context()
            
            full_prompt = f"{SYSTEM_PROMPT}\n\nPrevious conversation:\n{history_text}\n\nUser: {user_message}\nAssistant:"
            response = self._gemini_client.models.generate_content(
                model=GEMINI_MODEL, contents=full_prompt
            )
            return response.text
        except Exception as e:
            print(f"   ⚠️ Gemini: {e}")
            return None
    
    def clear_history(self):
        self.memory.clear()
