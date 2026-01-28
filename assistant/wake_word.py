"""
Wake Word Detection using openWakeWord or Porcupine
"""
import numpy as np
from typing import Callable, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    WAKE_WORD_MODEL, WAKE_WORD_THRESHOLD, 
    PICOVOICE_ACCESS_KEY, PORCUPINE_KEYWORD_PATH
)

class WakeWordDetector:
    """Detects wake word using Porcupine (priority) or openWakeWord (fallback)"""
    
    def __init__(self, on_wake: Optional[Callable] = None):
        self.threshold = WAKE_WORD_THRESHOLD
        self.on_wake = on_wake
        self.oww_model = None
        self.porcupine = None
        self.use_porcupine = False
        
    def load_model(self):
        """Load the wake word model"""
        # Try loading Porcupine first if key is present
        if PICOVOICE_ACCESS_KEY:
            try:
                import pvporcupine
                print("🔄 Loading Porcupine wake word model...")
                
                keyword_path = PORCUPINE_KEYWORD_PATH if os.path.exists(PORCUPINE_KEYWORD_PATH) else None
                
                # Load multiple keywords
                # Priority: Custom model -> Built-ins
                keyword_paths = [keyword_path] if keyword_path else []
                keywords = None 
                
                if not keyword_paths:
                    # Fallback to built-in keywords if no custom model
                    # Note: Availability depends on platform/license
                    keywords = ["jarvis", "computer", "alexa", "hey google"]
                
                try:
                    self.porcupine = pvporcupine.create(
                        access_key=PICOVOICE_ACCESS_KEY,
                        keyword_paths=keyword_paths if keyword_paths else None,
                        keywords=keywords
                    )
                except Exception:
                    # Fallback to just "jarvis" or "computer" if some fail
                    self.porcupine = pvporcupine.create(
                        access_key=PICOVOICE_ACCESS_KEY,
                        keywords=["jarvis", "computer"]
                    )
                    
                self.use_porcupine = True
                print(f"✅ Porcupine loaded! Keywords: {keywords or 'Custom Model'}")
                return
            except Exception as e:
                print(f"⚠️ Porcupine failed to load: {e}")
                print("   Falling back to openWakeWord...")
        
        # Fallback to openWakeWord
        print("🔄 Loading openWakeWord model...")
        from openwakeword.model import Model
        self.oww_model = Model(
            wakeword_models=[WAKE_WORD_MODEL],
            inference_framework="onnx"
        )
        print(f"✅ openWakeWord loaded: '{WAKE_WORD_MODEL}'")
    
    def process_audio(self, audio_chunk: bytes) -> bool:
        """Process audio chunk and check for wake word"""
        if self.use_porcupine and self.porcupine:
            return self._process_porcupine(audio_chunk)
        else:
            return self._process_oww(audio_chunk)

    def _process_porcupine(self, audio_chunk: bytes) -> bool:
        """Process using Porcupine"""
        # Porcupine expects int16 array
        pcm = np.frombuffer(audio_chunk, dtype=np.int16)
        
        # Porcupine requires exactly frame_length samples
        # We might need to handle buffering if chunks don't match
        # But for simplicity, we assume chunk size matches or we skip
        # A better implementation would buffer.
        # For now, we'll try to process what fits. 
        # Note: Porcupine frame length is usually 512, which matches our CHUNK_SIZE
        
        try:
            result = self.porcupine.process(pcm)
            if result >= 0:
                print("🎯 Wake word detected (Porcupine)!")
                if self.on_wake:
                    self.on_wake()
                return True
        except Exception:
            pass
            
        return False

    def _process_oww(self, audio_chunk: bytes) -> bool:
        """Process using openWakeWord"""
        if self.oww_model is None:
            self.load_model()
        
        # Convert bytes to numpy array
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        
        # openWakeWord expects float32 normalized audio
        audio_float = audio_data.astype(np.float32) / 32768.0
        
        # Run prediction
        prediction = self.oww_model.predict(audio_float)
        
        # Check all wake word scores
        for model_name, score in self.oww_model.prediction_buffer.items():
            if len(score) > 0 and score[-1] > self.threshold:
                print(f"🎯 Wake word detected! Score: {score[-1]:.3f}")
                self.oww_model.reset()
                if self.on_wake:
                    self.on_wake()
                return True
        
        return False
    
    def reset(self):
        """Reset the wake word buffer"""
        if self.oww_model:
            self.oww_model.reset()


def test_wake_word():
    """Test wake word detection"""
    from .audio_manager import AudioManager
    import time
    
    detected = False
    
    def on_wake():
        nonlocal detected
        detected = True
        print("🎉 WAKE WORD DETECTED!")
    
    detector = WakeWordDetector(on_wake=on_wake)
    detector.load_model()
    
    audio = AudioManager()
    audio.start_stream()
    audio.start_recording()
    
    print("\n👂 Listening for 'Hey Jarvis'... (10 seconds)")
    print("   Say the wake word to test detection.\n")
    
    start = time.time()
    while time.time() - start < 10 and not detected:
        chunk = audio.get_audio_chunk()
        if chunk:
            detector.process_audio(chunk)
    
    audio.stop_recording()
    audio.stop_stream()
    
    if detected:
        print("✅ Test passed!")
    else:
        print("❌ No wake word detected in 10 seconds")


if __name__ == "__main__":
    test_wake_word()
