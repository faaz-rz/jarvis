import threading
import queue
import logging
import time

try:
    import pyttsx3
    import pythoncom
except ImportError:
    pyttsx3 = None
    pythoncom = None

class TTSManager:
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.running = True
        self.engine = None
        self.is_speaking = False
        
        if pyttsx3:
            self.thread.start()
        else:
            logging.warning("TTSManager: pyttsx3 not installed. Speech disabled.")

    def speak(self, text):
        if not text:
            return
        # Clean text (remove code blocks, etc. if needed)
        self.queue.put(text)

    def _worker(self):
        # Initialize engine ONLY in the worker thread
        try:
            if pythoncom:
                pythoncom.CoInitialize()
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 170) # Slightly faster
            # Select a good voice if available (optional)
            voices = self.engine.getProperty('voices')
            for v in voices:
                if "zira" in v.name.lower(): # Zira is a good Windows voice
                    self.engine.setProperty('voice', v.id)
                    break
        except Exception as e:
            logging.error(f"TTSManager Init Error: {e}")
            return

        logging.info("TTSManager: Worker started.")
        
        while self.running:
            try:
                # Get text, wait max 1 sec to check running flag
                text = self.queue.get(timeout=1.0)
                
                logging.info(f"TTSManager Speaking: {text[:50]}...")
                
                self.is_speaking = True
                self.engine.say(text)
                logging.debug("TTSManager: runAndWait starting...")
                self.engine.runAndWait()
                logging.debug("TTSManager: runAndWait finished.")
                self.is_speaking = False
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"TTSManager Error: {e}")
                time.sleep(1)

    def stop(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        # pyttsx3 cleanup if needed (runAndWait handles dispatch)
