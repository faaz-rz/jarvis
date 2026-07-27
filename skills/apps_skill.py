import os
import platform
import shlex
import shutil
import subprocess
import logging
from core.skills import BaseSkill


class AppControlSkill(BaseSkill):
    name = "AppControl"
    description = "Opens common applications."
    priority = 60
    
    def __init__(self, context):
        super().__init__(context)
        system = platform.system()
        if system == "Windows":
            self.common_apps = {
                "notepad": ["notepad.exe"],
                "calculator": ["calc.exe"],
                "cmd": ["cmd.exe"],
                "explorer": ["explorer.exe"],
                "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
                "spotify": [os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")],
            }
        elif system == "Darwin":
            self.common_apps = {
                "textedit": ["open", "-a", "TextEdit"],
                "calculator": ["open", "-a", "Calculator"],
                "terminal": ["open", "-a", "Terminal"],
                "finder": ["open", "."],
                "chrome": ["open", "-a", "Google Chrome"],
                "spotify": ["open", "-a", "Spotify"],
            }
        else:
            self.common_apps = {
                "calculator": ["gnome-calculator"],
                "terminal": ["x-terminal-emulator"],
                "files": ["xdg-open", "."],
                "chrome": ["google-chrome"],
                "spotify": ["spotify"],
            }

    def handle(self, text: str) -> bool:
        lower = text.lower()
        if "open" in lower:
            for app, command in self.common_apps.items():
                if app in lower:
                    self.open_app(app, command)
                    return True
            parts = lower.split("open ", 1)
            if len(parts) > 1:
                target = parts[1].strip()
                self.open_generic(target)
                return True
        return False

    def open_app(self, name, command):
        self.context.speak(f"Opening {name}")
        try:
            executable = command[0]
            if os.path.isabs(executable) and not os.path.exists(executable):
                raise FileNotFoundError(executable)
            if not os.path.isabs(executable) and not shutil.which(executable):
                raise FileNotFoundError(executable)
            subprocess.Popen(command)
        except (OSError, ValueError) as e:
            logging.error("Failed to open %s: %s", name, e)
            self.context.speak(f"Failed to open {name}. {e}")

    def open_generic(self, target):
        self.context.speak(f"Attempting to launch {target}")
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(target)
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", target])
            else:
                executable = shutil.which(shlex.split(target)[0])
                if not executable:
                    raise FileNotFoundError(target)
                subprocess.Popen([executable, *shlex.split(target)[1:]])
        except (OSError, ValueError):
            self.context.speak(f"Could not find or launch {target}")
