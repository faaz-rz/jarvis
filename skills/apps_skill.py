import os
import subprocess
import logging
from core.skills import BaseSkill

class AppControlSkill(BaseSkill):
    name = "AppControl"
    description = "Opens and closes applications."
    
    def __init__(self, context):
        super().__init__(context)
        self.common_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "explorer": "explorer.exe",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
        }

    def handle(self, text: str) -> bool:
        lower = text.lower()
        if "open" in lower:
            for app, path in self.common_apps.items():
                if app in lower:
                    self.open_app(app, path)
                    return True
            # Try generic launch
            parts = lower.split("open ", 1)
            if len(parts) > 1:
                target = parts[1].strip()
                self.open_generic(target)
                return True
        return False

    def open_app(self, name, path):
        self.context.speak(f"Opening {name}")
        try:
            subprocess.Popen(path)
        except Exception as e:
            self.context.speak(f"Failed to open {name}. {e}")

    def open_generic(self, target):
        self.context.speak(f"Attempting to launch {target}")
        try:
            # os.startfile is Windows only
            os.startfile(target)
        except Exception:
            try:
                subprocess.Popen(target)
            except Exception:
                self.context.speak(f"Could not find or launch {target}")
