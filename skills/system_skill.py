import ctypes
import logging
import os
import platform
import subprocess
import time
from pathlib import Path

from core.skills import BaseSkill
from core.tools import RiskLevel, ToolSpec

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
except Exception:
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
                self.context.speak(self.set_volume("up"))
                return True
            if "down" in lower or "decrease" in lower:
                self.context.speak(self.set_volume("down"))
                return True
            if "mute" in lower:
                self.context.speak(self.set_volume("mute"))
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
            self.context.speak(self.take_screenshot())
            return True

        if "battery" in lower:
            self.context.speak(self.get_battery_status())
            return True

        return False

    def tools(self):
        return [
            ToolSpec(
                name="get_battery_status",
                description="Report the computer's battery percentage and charging state.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                handler=self.get_battery_status,
                risk=RiskLevel.READ_ONLY,
            ),
            ToolSpec(
                name="set_volume",
                description="Increase, decrease, or toggle mute for system audio.",
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["up", "down", "mute"],
                        }
                    },
                    "required": ["action"],
                    "additionalProperties": False,
                },
                handler=self.set_volume,
                risk=RiskLevel.ACTION,
            ),
            ToolSpec(
                name="take_screenshot",
                description="Capture the current screen and save it in Pictures.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                handler=self.take_screenshot,
                risk=RiskLevel.WRITE,
                confirmation="Capture and save a screenshot of the current screen?",
            ),
            ToolSpec(
                name="control_computer_power",
                description="Schedule a Windows computer shutdown or restart.",
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["shutdown", "restart"],
                        }
                    },
                    "required": ["action"],
                    "additionalProperties": False,
                },
                handler=self.execute_power_action,
                risk=RiskLevel.DESTRUCTIVE,
                confirmation="This will {action} the computer. Allow it?",
            ),
        ]

    def _execute_power_action(self, action):
        self.context.speak(self.execute_power_action(action))

    def execute_power_action(self, action):
        if platform.system() != "Windows":
            return "Automatic power control is currently supported only on Windows."
        command = ["shutdown", "/s" if action == "shutdown" else "/r", "/t", "10"]
        try:
            subprocess.run(command, check=True, timeout=5)
            return f"{action.title()} scheduled in 10 seconds."
        except (OSError, subprocess.SubprocessError) as exc:
            logging.error("Power action failed: %s", exc)
            return f"Could not {action} the computer."

    def set_volume(self, action):
        if action == "mute":
            return self._mute()
        direction = 1 if action == "up" else -1
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
            result = "Increased" if direction > 0 else "Decreased"
            return f"{result} volume."
        except (OSError, subprocess.SubprocessError, AttributeError) as exc:
            logging.error("Volume control failed: %s", exc)
            return "Volume control is unavailable on this system."

    def _mute(self):
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
            return "Toggled mute."
        except (OSError, subprocess.SubprocessError, AttributeError) as exc:
            logging.error("Mute failed: %s", exc)
            return "Mute control is unavailable on this system."

    # Compatibility helpers for older integrations.
    def change_volume(self, direction):
        return self.set_volume("up" if direction > 0 else "down")

    def mute(self):
        return self.set_volume("mute")

    def take_screenshot(self):
        if pyautogui is None:
            return "Screenshot support requires the pyautogui package."
        try:
            pictures = Path.home() / "Pictures"
            pictures.mkdir(parents=True, exist_ok=True)
            path = pictures / f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot(str(path))
            return f"Screenshot saved to {path}."
        except Exception as exc:
            logging.error("Screenshot failed: %s", exc)
            return f"Failed to take a screenshot: {exc}"

    def get_battery_status(self):
        if psutil is None:
            return "Battery reporting requires the psutil package."
        battery = psutil.sensors_battery()
        if not battery:
            return "No battery was detected."
        state = "plugged in" if battery.power_plugged else "on battery"
        return f"Battery is at {int(battery.percent)} percent and {state}."

    def report_battery(self):
        return self.get_battery_status()
