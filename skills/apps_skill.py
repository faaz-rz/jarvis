import os
import platform
import shlex
import shutil
import subprocess
import logging
from core.skills import BaseSkill
from core.tools import RiskLevel, ToolSpec


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
            for app in self.common_apps:
                if app in lower:
                    self.context.speak(self.launch_application(app))
                    return True
            parts = lower.split("open ", 1)
            if len(parts) > 1:
                target = parts[1].strip()
                self.context.speak(self.launch_application(target))
                return True
        return False

    def tools(self):
        return [
            ToolSpec(
                name="open_application",
                description=(
                    "Open a desktop application. Use only when the user asks to "
                    "launch or open an application."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "application": {
                            "type": "string",
                            "maxLength": 100,
                            "description": "Application name, such as calculator or chrome.",
                        }
                    },
                    "required": ["application"],
                    "additionalProperties": False,
                },
                handler=self.launch_application,
                risk=RiskLevel.ACTION,
            )
        ]

    def launch_application(self, application):
        name = application.strip().lower()
        command = self.common_apps.get(name)
        if command:
            return self._open_known_app(name, command)
        return self._open_generic(name)

    def _open_known_app(self, name, command):
        try:
            executable = command[0]
            if os.path.isabs(executable) and not os.path.exists(executable):
                raise FileNotFoundError(executable)
            if not os.path.isabs(executable) and not shutil.which(executable):
                raise FileNotFoundError(executable)
            subprocess.Popen(command)
            return f"Opened {name}."
        except (OSError, ValueError) as e:
            logging.error("Failed to open %s: %s", name, e)
            return f"Failed to open {name}: {e}"

    def _open_generic(self, target):
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
            return f"Opened {target}."
        except (OSError, ValueError) as exc:
            return f"Could not find or launch {target}: {exc}"
