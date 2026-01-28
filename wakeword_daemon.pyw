"""
Wake Word Daemon - Lightweight always-on listener
Runs silently in background, launches assistant when wake word detected.
"""
import sys
import os
import subprocess
import threading
import time
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pyaudio
import pystray
from PIL import Image, ImageDraw

# Import only what's needed
from config import (
    PICOVOICE_ACCESS_KEY, PORCUPINE_KEYWORD_PATH,
    SAMPLE_RATE, CHUNK_SIZE
)

class WakeWordDaemon:
    """Lightweight wake word listener with tray icon"""
    
    def __init__(self):
        self.running = True
        self.listening = True
        self.porcupine = None
        self.audio = None
        self.stream = None
        self.tray_icon = None
        
    def setup_porcupine(self):
        """Initialize Porcupine wake word engine"""
        import pvporcupine
        
        keyword_path = PORCUPINE_KEYWORD_PATH if os.path.exists(PORCUPINE_KEYWORD_PATH) else None
        
        try:
            if keyword_path:
                self.porcupine = pvporcupine.create(
                    access_key=PICOVOICE_ACCESS_KEY,
                    keyword_paths=[keyword_path]
                )
            else:
                # Use built-in keywords
                self.porcupine = pvporcupine.create(
                    access_key=PICOVOICE_ACCESS_KEY,
                    keywords=["jarvis", "computer"]
                )
            print("✅ Wake word engine ready")
        except Exception as e:
            print(f"❌ Porcupine init failed: {e}")
            raise
            
    def setup_audio(self):
        """Initialize audio stream"""
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length
        )
        print("🎤 Audio stream ready")
        
    def create_icon_image(self, color=(0, 120, 255)):
        """Generate tray icon"""
        size = 64
        image = Image.new('RGB', (size, size), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.ellipse((8, 8, size-8, size-8), fill=color)
        return image
        
    def setup_tray(self):
        """Setup system tray icon"""
        menu = pystray.Menu(
            pystray.MenuItem("Buddy Daemon", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Listening", 
                self.toggle_listening,
                checked=lambda item: self.listening
            ),
            pystray.MenuItem("Test Wake", self.test_wake),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.exit_daemon)
        )
        
        self.tray_icon = pystray.Icon(
            "BuddyDaemon",
            self.create_icon_image(),
            "Buddy Wake Daemon (Listening)",
            menu
        )
        
    def toggle_listening(self, icon, item):
        """Toggle wake word listening"""
        self.listening = not self.listening
        if self.listening:
            icon.icon = self.create_icon_image((0, 120, 255))  # Blue
            icon.title = "Buddy Wake Daemon (Listening)"
        else:
            icon.icon = self.create_icon_image((128, 128, 128))  # Gray
            icon.title = "Buddy Wake Daemon (Paused)"
            
    def test_wake(self, icon, item):
        """Manually trigger wake (for testing)"""
        self.launch_assistant()
        
    def exit_daemon(self, icon, item):
        """Clean exit"""
        self.running = False
        icon.stop()
        
    def launch_assistant(self):
        """Launch the full assistant"""
        print("🚀 Launching assistant...")
        
        # Path to main.py
        main_script = Path(__file__).parent / "main.py"
        python_exe = sys.executable
        
        # Launch as separate process (non-blocking)
        subprocess.Popen(
            [python_exe, str(main_script)],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
    def listen_loop(self):
        """Main wake word detection loop"""
        print("👂 Listening for wake word...")
        
        while self.running:
            if not self.listening:
                time.sleep(0.1)
                continue
                
            try:
                # Read audio frame
                pcm = self.stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = np.frombuffer(pcm, dtype=np.int16)
                
                # Check for wake word
                result = self.porcupine.process(pcm)
                
                if result >= 0:
                    print("🎯 Wake word detected!")
                    self.launch_assistant()
                    
                    # Brief cooldown to prevent double-trigger
                    time.sleep(2.0)
                    
            except Exception as e:
                print(f"⚠️ Listen error: {e}")
                time.sleep(0.5)
                
    def cleanup(self):
        """Cleanup resources"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.porcupine:
            self.porcupine.delete()
        print("🛑 Daemon stopped")
        
    def run(self):
        """Main entry point"""
        try:
            self.setup_porcupine()
            self.setup_audio()
            self.setup_tray()
            
            # Start listening in background thread
            listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
            listen_thread.start()
            
            print("\n✅ Buddy Daemon Running!")
            print("   Check System Tray for icon")
            print("   Say 'Hey Jarvis' or 'Computer' to activate\n")
            
            # Run tray icon (blocks)
            self.tray_icon.run()
            
        except Exception as e:
            print(f"❌ Daemon failed: {e}")
        finally:
            self.cleanup()


def main():
    daemon = WakeWordDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
