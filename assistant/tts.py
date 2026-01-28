"""
Text-to-Speech with edge-tts and pyttsx3 fallback
"""
import asyncio
import edge_tts
import pyttsx3
import tempfile
import os
import numpy as np
import sounddevice as sd
from typing import Optional, Generator, AsyncGenerator
import io
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TTS_VOICE, TTS_RATE, TTS_PITCH


class TextToSpeech:
    """TTS with edge-tts (online) and pyttsx3 (offline fallback)"""
    
    def __init__(self):
        self.voice = TTS_VOICE
        self.rate = TTS_RATE
        self.pitch = TTS_PITCH
        self._pyttsx_engine: Optional[pyttsx3.Engine] = None
        self._use_fallback = False
        
    def _init_fallback(self):
        """Initialize pyttsx3 fallback engine"""
        if self._pyttsx_engine is None:
            self._pyttsx_engine = pyttsx3.init()
            # Configure voice properties
            self._pyttsx_engine.setProperty('rate', 175)  # Words per minute
            voices = self._pyttsx_engine.getProperty('voices')
            # Try to find a female voice for consistency
            for voice in voices:
                if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                    self._pyttsx_engine.setProperty('voice', voice.id)
                    break
            print("   ✅ Fallback TTS (pyttsx3) initialized")
    
    async def synthesize(self, text: str) -> Optional[bytes]:
        """
        Synthesize text to audio using edge-tts
        
        Returns:
            Audio bytes (MP3 format) or None if failed
        """
        try:
            communicate = edge_tts.Communicate(
                text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch
            )
            
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            return audio_data if audio_data else None
            
        except Exception as e:
            print(f"   ⚠️ edge-tts failed: {e}, using fallback")
            self._use_fallback = True
            return None
    
    async def synthesize_streaming(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio chunks as they're generated
        
        Yields:
            Audio chunks (MP3 format)
        """
        try:
            communicate = edge_tts.Communicate(
                text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch
            )
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
                    
        except Exception as e:
            print(f"   ⚠️ edge-tts streaming failed: {e}")
            self._use_fallback = True
    
    def speak(self, text: str):
        """
        Speak text - tries edge-tts first, falls back to pyttsx3
        """
        if self._use_fallback:
            self._speak_fallback(text)
            return
        
        try:
            # Try edge-tts
            audio_data = asyncio.run(self.synthesize(text))
            if audio_data:
                self._play_mp3(audio_data)
            else:
                self._speak_fallback(text)
        except Exception as e:
            print(f"   ⚠️ TTS error: {e}, using fallback")
            self._speak_fallback(text)
    
    def _speak_fallback(self, text: str):
        """Speak using pyttsx3 (offline)"""
        self._init_fallback()
        print("   🔊 Using offline TTS...")
        self._pyttsx_engine.say(text)
        self._pyttsx_engine.runAndWait()
    
    def _play_mp3(self, mp3_data: bytes):
        """Play MP3 audio data"""
        try:
            # Save to temp file and play
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3_data)
                temp_path = f.name
            
            # Use ffmpeg/pydub if available, otherwise sounddevice
            try:
                from pydub import AudioSegment
                from pydub.playback import play
                audio = AudioSegment.from_mp3(temp_path)
                play(audio)
            except ImportError:
                # Fallback: use system player
                if sys.platform == "win32":
                    os.system(f'start /min wmplayer "{temp_path}"')
                    import time
                    time.sleep(len(mp3_data) / 16000)  # Rough estimate
                else:
                    os.system(f'mpv --no-video "{temp_path}" 2>/dev/null')
            
            # Cleanup
            try:
                os.unlink(temp_path)
            except:
                pass
                
        except Exception as e:
            print(f"   ⚠️ Audio playback error: {e}")
            self._speak_fallback(text)
    
    async def speak_streaming(self, text: str):
        """
        Speak with streaming - starts playback immediately as audio is generated.
        Pipes audio data directly to a media player process (mpv).
        """
        try:
            import subprocess
            import shutil
            
            # Check for mpv or ffplay
            player = shutil.which("mpv")
            args = ["mpv", "--no-video", "--no-terminal", "-"]
            
            if not player:
                player = shutil.which("ffplay") 
                args = ["ffplay", "-nodisp", "-autoexit", "-"]
                
            if not player:
                print("   ⚠️ No streaming player (mpv/ffplay) found, buffering...")
                # Fallback to buffering
                audio_chunks = []
                async for chunk in self.synthesize_streaming(text):
                     audio_chunks.append(chunk)
                if audio_chunks:
                    self._play_mp3(b"".join(audio_chunks))
                return

            # Start player process reading from stdin
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Pipe chunks to player
            try:
                async for chunk in self.synthesize_streaming(text):
                    if chunk:
                        process.stdin.write(chunk)
                        process.stdin.flush()
            except BrokenPipeError:
                pass # Player closed
            finally:
                if process.stdin:
                    process.stdin.close()
                process.wait()
                
        except Exception as e:
            print(f"   ⚠️ Streaming TTS error: {e}")
            self._speak_fallback(text)


def test_tts():
    """Test TTS"""
    tts = TextToSpeech()
    
    print("\n🔊 Testing edge-tts (online)...")
    tts.speak("Hello! I'm Buddy, your friendly voice assistant. How can I help you today?")
    
    print("\n🔊 Testing fallback (offline)...")
    tts._use_fallback = True
    tts.speak("This is the offline fallback voice.")
    
    print("\n✅ TTS test complete!")


if __name__ == "__main__":
    test_tts()
