"""
System Tray Icon - Background management
"""
import threading
import pystray
from PIL import Image, ImageDraw
import sys
import os

class SystemTrayApp:
    def __init__(self, on_exit=None, on_show=None):
        self.on_exit = on_exit
        self.on_show = on_show
        self.icon = None
        
    def create_icon(self):
        # Generate a simple icon programmatically (blue circle)
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0, 0, width, height), fill=(255, 255, 255))
        dc.ellipse((8, 8, width-8, height-8), fill=(0, 120, 255))
        
        return image

    def setup(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show Assistant", self._show_action),
            pystray.MenuItem("Restart", self._restart_action),
            pystray.MenuItem("Exit", self._exit_action)
        )
        
        self.icon = pystray.Icon(
            "Buddy", 
            self.create_icon(), 
            "Buddy Assistant", 
            menu
        )

    def _show_action(self, icon, item):
        if self.on_show:
            self.on_show()

    def _restart_action(self, icon, item):
        # Trigger python restart
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _exit_action(self, icon, item):
        icon.stop()
        if self.on_exit:
            self.on_exit()

    def run(self):
        self.setup()
        self.icon.run()

    def stop(self):
        if self.icon:
            self.icon.stop()
