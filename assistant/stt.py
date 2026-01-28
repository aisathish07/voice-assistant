"""
Speech-to-Text using faster-whisper with Silero VAD
"""
import numpy as np
from faster_whisper import WhisperModel
import torch
from typing import Optional, Tuple, List
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    SAMPLE_RATE, VAD_THRESHOLD, SILENCE_DURATION_MS, MIN_SPEECH_DURATION_MS
)


class SpeechToText:
    """Speech-to-Text with VAD-based endpoint detection"""
    
    def __init__(self):
        self.whisper_model: Optional[WhisperModel] = None
        self.vad_model = None
        self.vad_utils = None
        self._audio_buffer: List[bytes] = []
        
    def load_models(self):
        """Load Whisper and VAD models"""
        print("🔄 Loading STT models...")
        
        # Load faster-whisper
        self.whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE
        )
        print(f"   ✅ Whisper model: {WHISPER_MODEL} ({WHISPER_DEVICE.upper()})")
        
        # Load Silero VAD
        self.vad_model, self.vad_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=True
        )
        print("   ✅ Silero VAD loaded")
        
    def _check_speech(self, audio_chunk: bytes) -> float:
        """
        Check if audio chunk contains speech
        
        Returns:
            Speech probability (0.0 - 1.0)
        """
        if self.vad_model is None:
            return 1.0  # Assume speech if no VAD
        
        # Convert to float tensor
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_float)
        
        # Get speech probability
        speech_prob = self.vad_model(audio_tensor, SAMPLE_RATE).item()
        return speech_prob
    
    def listen_with_vad(self, audio_manager, max_duration: float = 15.0) -> Optional[bytes]:
        """
        Listen for speech using VAD to detect when user stops speaking
        
        Args:
            audio_manager: AudioManager instance (already recording)
            max_duration: Maximum listening time in seconds
            
        Returns:
            Complete audio bytes or None if no speech detected
        """
        if self.vad_model is None:
            self.load_models()
        
        self._audio_buffer = []
        silence_samples = 0
        speech_samples = 0
        samples_per_chunk = 512  # ~32ms at 16kHz
        silence_threshold = int(SILENCE_DURATION_MS * SAMPLE_RATE / 1000 / samples_per_chunk)
        min_speech_threshold = int(MIN_SPEECH_DURATION_MS * SAMPLE_RATE / 1000 / samples_per_chunk)
        
        start_time = time.time()
        has_speech = False
        
        print("👂 Listening... (speak now)")
        
        while time.time() - start_time < max_duration:
            chunk = audio_manager.get_audio_chunk(timeout=0.1)
            if chunk is None:
                continue
            
            self._audio_buffer.append(chunk)
            speech_prob = self._check_speech(chunk)
            
            if speech_prob > VAD_THRESHOLD:
                speech_samples += 1
                silence_samples = 0
                if speech_samples >= min_speech_threshold:
                    has_speech = True
            else:
                if has_speech:
                    silence_samples += 1
                    # Check if we've had enough silence to stop
                    if silence_samples >= silence_threshold:
                        print("   🔇 Silence detected, processing...")
                        break
        
        if not has_speech:
            print("   ⚠️ No speech detected")
            return None
        
        # Combine all audio chunks
        return b''.join(self._audio_buffer)
    
    def transcribe(self, audio_bytes: bytes) -> Tuple[str, float]:
        """
        Transcribe audio bytes to text
        
        Args:
            audio_bytes: Raw audio bytes (int16, 16kHz)
            
        Returns:
            Tuple of (transcription, confidence)
        """
        if self.whisper_model is None:
            self.load_models()
        
        # Convert to numpy float32
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        
        # Transcribe
        segments, info = self.whisper_model.transcribe(
            audio_float,
            language=None, # Auto-detect language
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200
            ) 
        )
        
        # Log detected language
        if info.language != "en":
              print(f"   🌍 Detected language: {info.language} ({info.language_probability:.0%})")
        
        # Collect transcription
        text_parts = []
        total_prob = 0.0
        count = 0
        
        for segment in segments:
            text_parts.append(segment.text)
            total_prob += segment.avg_logprob
            count += 1
        
        text = " ".join(text_parts).strip()
        avg_confidence = (total_prob / count) if count > 0 else -1.0
        # Convert log prob to probability (exp of log prob)
        # Typical values: -0.3 = ~74%, -0.5 = ~60%, -0.7 = ~50%, -1.0 = ~37%
        confidence = min(1.0, max(0.0, np.exp(avg_confidence)))
        
        return text, confidence


def test_stt():
    """Test STT with VAD"""
    from .audio_manager import AudioManager
    
    stt = SpeechToText()
    stt.load_models()
    
    audio = AudioManager()
    audio.start_stream()
    audio.start_recording()
    
    print("\n🎤 Speak something (I'll detect when you stop)...\n")
    
    audio_bytes = stt.listen_with_vad(audio, max_duration=10.0)
    
    audio.stop_recording()
    audio.stop_stream()
    
    if audio_bytes:
        print("📝 Transcribing...")
        text, confidence = stt.transcribe(audio_bytes)
        print(f"\n✅ Transcription: '{text}'")
        print(f"   Confidence: {confidence:.2%}")
    else:
        print("❌ No audio captured")


if __name__ == "__main__":
    test_stt()
