from core.skills import BaseSkill
import ctypes
import os
import time
# psutil and pyautogui are assumed installed from previous context or standard env
try:
    import psutil
    import pyautogui
except ImportError:
    pass


class SystemSkill(BaseSkill):
    name = "SystemControl"
    description = "Controls Volume, Brightness, and System Power."

    def mute(self):
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
        self.context.speak("Muted volume.")
        
    def handle(self, text: str) -> bool:
        lower = text.lower()
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
            self.context.speak("Shutting down the computer.")
            os.system("shutdown /s /t 10")
            return True
            
        if "restart pc" in lower:
            self.context.speak("Restarting the computer.")
            os.system("shutdown /r /t 10")
            return True
            
        if "screenshot" in lower:
            import pyautogui
            self.context.speak("Taking screenshot...")
            try:
                # Save to user's pictures or current dir
                path = os.path.join(os.environ['USERPROFILE'], 'Pictures', f'screenshot_{int(time.time())}.png')
                pyautogui.screenshot(path)
                self.context.speak(f"Screenshot saved to Pictures.")
            except Exception as e:
                self.context.speak(f"Failed to take screenshot: {e}")
            return True
            
        if "battery" in lower:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                pct = int(battery.percent)
                plugged = "PLUGGED IN" if battery.power_plugged else "ON BATTERY"
                self.context.speak(f"Battery is at {pct}% and {plugged}.")
            else:
                self.context.speak("No battery detected.")
            return True

        return False

    def change_volume(self, direction):
        # direction: 1 for up, -1 for down
        # 0xAF = Volume Up, 0xAE = Volume Down
        key = 0xAF if direction > 0 else 0xAE
        # Send 5 key presses for noticeable change
        for _ in range(5):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)
        
        action = "Increased" if direction > 0 else "Decreased"
        self.context.speak(f"{action} volume.")

    def mute(self):
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
        self.context.speak("Muted volume.")
