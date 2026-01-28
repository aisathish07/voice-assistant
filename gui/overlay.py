"""
Floating Overlay - Visual Feedback for the Assistant
"""
import tkinter as tk
from threading import Thread
import time
import math

class AssistantOverlay:
    """
    Transparent floating window that shows assistant state.
    """
    def __init__(self, root):
        self.root = root
        
        # Window setup
        self.root.overrideredirect(True)  # Remove title bar
        self.root.wm_attributes("-topmost", True)  # Always on top
        self.root.wm_attributes("-transparentcolor", "black")  # Transparency key
        
        # Position: Bottom Center
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.width = 400
        self.height = 100
        x = (screen_width - self.width) // 2
        y = screen_height - 150
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        # Canvas for drawing
        self.canvas = tk.Canvas(
            root, 
            width=self.width, 
            height=self.height, 
            bg="black", 
            highlightthickness=0
        )
        self.canvas.pack()
        
        # State
        self.state = "IDLE"
        self.text_var = tk.StringVar()
        self.text_var.set("")
        
        # UI Elements
        self.circle = self.canvas.create_oval(180, 30, 220, 70, fill="#333333", outline="")
        self.label = tk.Label(
            root, 
            textvariable=self.text_var, 
            bg="black", 
            fg="white", 
            font=("Segoe UI", 12)
        )
        self.canvas.create_window(200, 85, window=self.label)
        
        # Animation
        self.glow_idx = 0
        self.animating = True
        self._animate()
        
        # Initial: Hidden
        self.hide()

    def set_state(self, state, text=None):
        """Update visual state"""
        self.state = state
        if text:
            self.text_var.set(text)
            
        self.show()
            
        color = "#333333" # IDLE/Default
        
        if state == "WAKE" or state == "LISTENING":
            color = "#00aaff" # Blue
            self.text_var.set("Listening...")
        elif state == "PROCESSING":
            color = "#aa00ff" # Purple
            self.text_var.set("Thinking...")
        elif state == "SPEAKING":
            color = "#00ffaa" # Cyan/Green
            
        if text: # Override text
            self.text_var.set(text)

        self.canvas.itemconfig(self.circle, fill=color)

        if state == "IDLE":
            self.hide() # Auto-hide on idle (optional)
        else:
            self.show()

    def _animate(self):
        """Pulse animation loop"""
        if self.state in ["LISTENING", "PROCESSING", "SPEAKING"]:
             # Simple pulse size
            scale = math.sin(time.time() * 5) * 5
            base_r = 20
            r = base_r + scale
            self.canvas.coords(self.circle, 200-r, 50-r, 200+r, 50+r)
            
        self.root.after(50, self._animate)

    def show(self):
        self.root.deiconify()

    def hide(self):
        self.root.withdraw()

# For testing independently
if __name__ == "__main__":
    root = tk.Tk()
    app = AssistantOverlay(root)
    app.set_state("LISTENING")
    root.mainloop()
