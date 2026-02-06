from core.skills import BaseSkill
import pyautogui
import pytesseract
from PIL import Image
import os
import logging

class VisionSkill(BaseSkill):
    name = "VisionSkill"
    description = "Allows Jarvis to see the screen and read text using OCR."

    def __init__(self, context):
        super().__init__(context)
        # Configure Tesseract Path
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        else:
            logging.warning(f"Tesseract not found at {tesseract_path}. Vision skill may fail.")

    def handle(self, text: str) -> bool:
        lower = text.lower()
        triggers = ["read screen", "read my screen", "what is on my screen", "what's on my screen", "scan screen", "scan this"]
        
        if any(t in lower for t in triggers):
            self.read_screen()
            return True
        return False

    def read_screen(self):
        self.context.speak("Scanning screen...")
        try:
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # OCR
            text = pytesseract.image_to_string(screenshot)
            
            if not text.strip():
                self.context.speak("I couldn't detect any clear text on the screen.")
                return

            # Summarize or read it
            if len(text) > 500:
                self.context.speak("I've captured the screen content. It's quite long, so I'll summarize it.")
                prompt = f"The following is text extracted from the user's screen via OCR. Summarize it and capture the key information:\n\n{text[:4000]}"
                summary = self.context.llm_query(prompt)
                self.context.speak(summary)
            else:
                self.context.speak(f"Here is what I see: {text}")
                
            # Store in memory for context
            self.context.memory.add_history_item("system", f"[SCREENSHOT_OCR_CONTEXT]: {text[:1000]}...")
            
        except Exception as e:
            logging.error(f"Vision error: {e}")
            self.context.speak("I encountered an error while trying to read the screen.")
