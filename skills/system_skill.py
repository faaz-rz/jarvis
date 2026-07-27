import ctypes
import logging
import os
import platform
import subprocess
import time
from pathlib import Path

from core.skills import BaseSkill

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
except ImportError:
    pyautogui = None


class SystemSkill(BaseSkill):
    name = "SystemControl"
    description = "Controls volume, screenshots, battery status, and system power."
    priority = 90

    def __init__(self, context):
        super().__init__(context)
        self.pending_power_action = None

    def handle(self, text: str) -> bool:
        lower = text.lower().strip()

        if self.pending_power_action:
            if lower in {"yes", "confirm", "proceed", "do it"}:
                action = self.pending_power_action
                self.pending_power_action = None
                self._execute_power_action(action)
                return True
            if lower in {"no", "cancel", "stop", "don't"}:
                self.pending_power_action = None
                self.context.speak("Power command cancelled.")
                return True
            self.context.speak("Please say yes to confirm or no to cancel.")
            return True

        if lower in {"start listening", "resume listening", "enable voice"}:
            voice = getattr(self.context.engine, "voice_manager", None)
            if voice and voice.start_listening():
                self.context.speak("Voice listening is active.")
            else:
                self.context.speak("Voice input is not available.")
            return True

        if lower in {"stop listening", "pause listening", "disable voice"}:
            voice = getattr(self.context.engine, "voice_manager", None)
            if voice:
                voice.stop_listening()
                self.context.speak("Voice listening is paused.")
            else:
                self.context.speak("Voice input is not enabled.")
            return True

        if "volume" in lower:
            if "up" in lower or "increase" in lower:
                self.change_volume(1)
                return True
            if "down" in lower or "decrease" in lower:
                self.change_volume(-1)
                return True
            if "mute" in lower:
                self.mute()
                return True

        if "shutdown pc" in lower or "turn off computer" in lower:
            self.pending_power_action = "shutdown"
            self.context.speak(
                "This will shut down the computer. Say yes to confirm or no to cancel."
            )
            return True

        if "restart pc" in lower or "restart computer" in lower:
            self.pending_power_action = "restart"
            self.context.speak(
                "This will restart the computer. Say yes to confirm or no to cancel."
            )
            return True

        if "screenshot" in lower:
            self.take_screenshot()
            return True

        if "battery" in lower:
            self.report_battery()
            return True

        return False

    def _execute_power_action(self, action):
        if platform.system() != "Windows":
            self.context.speak(
                "Automatic power control is currently supported only on Windows."
            )
            return
        command = ["shutdown", "/s" if action == "shutdown" else "/r", "/t", "10"]
        try:
            subprocess.run(command, check=True, timeout=5)
            self.context.speak(f"{action.title()} scheduled in 10 seconds.")
        except (OSError, subprocess.SubprocessError) as exc:
            logging.error("Power action failed: %s", exc)
            self.context.speak(f"Could not {action} the computer.")

    def change_volume(self, direction):
        system = platform.system()
        try:
            if system == "Windows":
                key = 0xAF if direction > 0 else 0xAE
                for _ in range(5):
                    ctypes.windll.user32.keybd_event(key, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(key, 0, 2, 0)
            elif system == "Darwin":
                delta = "+5" if direction > 0 else "-5"
                script = (
                    "set volume output volume "
                    f"((output volume of (get volume settings)) {delta})"
                )
                subprocess.run(["osascript", "-e", script], check=True, timeout=5)
            else:
                change = "+5%" if direction > 0 else "-5%"
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", change],
                    check=True,
                    timeout=5,
                )
            action = "Increased" if direction > 0 else "Decreased"
            self.context.speak(f"{action} volume.")
        except (OSError, subprocess.SubprocessError, AttributeError) as exc:
            logging.error("Volume control failed: %s", exc)
            self.context.speak("Volume control is unavailable on this system.")

    def mute(self):
        system = platform.system()
        try:
            if system == "Windows":
                ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
            elif system == "Darwin":
                subprocess.run(
                    ["osascript", "-e", "set volume with output muted"],
                    check=True,
                    timeout=5,
                )
            else:
                subprocess.run(
                    ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
                    check=True,
                    timeout=5,
                )
            self.context.speak("Toggled mute.")
        except (OSError, subprocess.SubprocessError, AttributeError) as exc:
            logging.error("Mute failed: %s", exc)
            self.context.speak("Mute control is unavailable on this system.")

    def take_screenshot(self):
        if pyautogui is None:
            self.context.speak("Screenshot support requires the pyautogui package.")
            return
        try:
            pictures = Path.home() / "Pictures"
            pictures.mkdir(parents=True, exist_ok=True)
            path = pictures / f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot(str(path))
            self.context.speak(f"Screenshot saved as {path.name} in Pictures.")
        except Exception as exc:
            logging.error("Screenshot failed: %s", exc)
            self.context.speak("Failed to take a screenshot.")

    def report_battery(self):
        if psutil is None:
            self.context.speak("Battery reporting requires the psutil package.")
            return
        battery = psutil.sensors_battery()
        if not battery:
            self.context.speak("No battery was detected.")
            return
        state = "plugged in" if battery.power_plugged else "on battery"
        self.context.speak(f"Battery is at {int(battery.percent)} percent and {state}.")
