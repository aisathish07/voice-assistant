"""
Buddy Voice Assistant - Main Application (Desktop Mode)
"""
import sys
import os
import time
import threading
from enum import Enum, auto
from pathlib import Path
import tkinter as tk

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import ASSISTANT_NAME, SOUNDS_DIR
from assistant.audio import AudioRecorder
from assistant.wake_word import WakeWordDetector
from assistant.stt import SpeechToText
from assistant.tts import TextToSpeech
from assistant.llm_router import LLMRouter, SkillResponse
from assistant.skill_router import SkillRouter
from assistant.health_monitor import get_monitor

# GUI Imports
from gui.overlay import AssistantOverlay
from gui.tray import SystemTrayApp

class AssistantState(Enum):
    """Voice assistant states"""
    IDLE = auto()       # Waiting for wake word
    WAKE = auto()       # Wake word detected, play ding
    LISTENING = auto()  # Recording user speech (VAD active)
    PROCESSING = auto() # Transcribing and generating response
    SPEAKING = auto()   # Playing TTS response


class VoiceAssistant:
    """Main voice assistant application"""
    
    FOLLOWUP_PHRASES = [
        "what would you like", "what should i", "would you like me to",
        "anything else", "what else", "tell me more",
        "which one", "please specify", "can you clarify"
    ]
    
    def __init__(self):
        self.state = AssistantState.IDLE
        self._running = False
        self._wake_triggered = False
        self._followup_timeout = 0
        self.monitor = get_monitor()
        self.ui_callback = None
        
        print("\n" + "="*50)
        print(f"  🤖 {ASSISTANT_NAME} Voice Assistant (Desktop Mode)")
        print("="*50 + "\n")
        
    def set_ui_callback(self, callback):
        self.ui_callback = callback
        
    def initialize(self):
        """Initialize all components"""
        print("\n📦 Loading components...")
        self.audio = AudioRecorder()
        self.audio.start_stream()
        
        self.wake_detector = WakeWordDetector()
        self.wake_detector.load_model()
        
        self.stt = SpeechToText()
        self.stt.load_models()
        self.llm = LLMRouter()
        self.tts = TextToSpeech()
        
        self.skill_router = SkillRouter(
            llm_router=self.llm,
            tts=self.tts
        )
        self.skill_router.load_skills()
        
        print("\n✅ All components loaded!\n")
        self.monitor.start()

    def _transition(self, new_state: AssistantState):
        """Transition state and notify UI"""
        print(f"   [{self.state.name}] → [{new_state.name}]")
        self.state = new_state
        if self.ui_callback:
            self.ui_callback(new_state.name)

    def trigger_wake(self):
        """External wake trigger (e.g. from Tray)"""
        self._wake_triggered = True

    def run(self):
        """Main event loop (runs in thread)"""
        self._running = True
        self.state = AssistantState.IDLE
        
        try:
            while self._running:
                try:
                    self.monitor.heartbeat()
                    self._process_state()
                except Exception as e:
                    self.monitor.log_crash(e)
                    print("   🔄 Auto-recovering...")
                    self._transition(AssistantState.IDLE)
        except Exception as e:
            print(f"Critical Error: {e}")
        finally:
            self.shutdown()

    def _process_state(self):
        if self.state == AssistantState.IDLE:
            chunk = self.audio.get_audio_chunk()
            if chunk:
                detected = self.wake_detector.process_audio(chunk)
                if detected or self._wake_triggered:
                    self._wake_triggered = False
                    self._transition(AssistantState.WAKE)
        
        elif self.state == AssistantState.WAKE:
            self._play_ding()
            self._transition(AssistantState.LISTENING)
        
        elif self.state == AssistantState.LISTENING:
            audio_bytes = self.stt.listen_with_vad(self.audio, max_duration=15.0)
            if audio_bytes:
                self._transition(AssistantState.PROCESSING)
                self._process_speech(audio_bytes)
            else:
                self._transition(AssistantState.IDLE)
                
    def _play_ding(self):
        ding_path = SOUNDS_DIR / "ding.wav"
        if ding_path.exists():
            self.audio.play_file(str(ding_path))

    def _process_speech(self, audio_bytes):
        text, confidence = self.stt.transcribe(audio_bytes)
        print(f"   🗣️ User: {text} ({confidence:.2f})")
        
        if not text or confidence < 0.4:
            self._transition(AssistantState.IDLE)
            return

        if self.ui_callback:
            self.ui_callback("PROCESSING", text=f"Processing: {text[:30]}...")

        # Skill Routing
        skill_response = None
        # async handling wrapper would be needed here for true async skills
        # for now, we assume synchronous execution or wrapped async
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Check specific skills first
        response_text = loop.run_until_complete(
            self.skill_router.route(text, {"confidence": confidence})
        )

        if not response_text:
            # LLM Chat
            response_text = self.llm.chat(text)

        # Handle struct response
        should_continue = False
        final_text = str(response_text)
        
        if isinstance(response_text, SkillResponse):
            final_text = response_text.text
            should_continue = response_text.continue_listening

        # heuristics
        if not should_continue:
             should_continue = self._should_continue_listening(final_text)

        self._transition(AssistantState.SPEAKING)
        
        # Text to Speech
        if self.ui_callback:
             self.ui_callback("SPEAKING", text=final_text[:50]+"...")
             
        # Streaming TTS
        loop.run_until_complete(self.tts.speak_streaming(final_text))
        
        if should_continue:
             print("   👂 Listening for follow-up...")
             self._transition(AssistantState.LISTENING)
        else:
             self._transition(AssistantState.IDLE)
             
        loop.close()

    def _should_continue_listening(self, text):
        if text.endswith("?"): return True
        return any(p in text.lower() for p in self.FOLLOWUP_PHRASES)

    def shutdown(self):
        print("\n🛑 Shutting down...")
        self._running = False
        if hasattr(self, 'audio'): self.audio.stop_recording(); self.audio.stop_stream()

def main():
    """Desktop App Entry Point"""
    
    # 1. Setup UI (Main Thread)
    root = tk.Tk()
    overlay = AssistantOverlay(root)
    
    # 2. Setup Assistant (Background Thread)
    assistant = VoiceAssistant()
    
    # UI Callback: Update overlay when state changes
    def update_ui(state_name, text=None):
        # Schedule update on UI thread
        root.after(0, lambda: overlay.set_state(state_name, text))
        
    assistant.set_ui_callback(update_ui)
    
    # init logic
    try:
        assistant.initialize()
    except Exception as e:
        print(f"Init failed: {e}")
        return

    # 3. Setup Tray
    def on_show():
        assistant.trigger_wake()
        
    def on_exit():
        assistant.shutdown()
        root.quit()
        os._exit(0)

    tray = SystemTrayApp(on_exit=on_exit, on_show=on_show)
    threading.Thread(target=tray.run, daemon=True).start()
    
    # 4. Start Assistant Thread
    threading.Thread(target=assistant.run, daemon=True).start()
    
    print("\n🚀 Buddy Desktop App Running!")
    print("   Check System Tray (bottom right)")
    
    # 5. Start UI Loop (Blocking)
    root.mainloop()

if __name__ == "__main__":
    main()
