import threading
import queue
import logging
import time

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import pythoncom
except ImportError:
    pythoncom = None


class TTSManager:
    def __init__(self, on_start=None, on_end=None):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.running = True
        self.engine = None
        self.is_speaking = False
        self.on_start = on_start
        self.on_end = on_end
        
        if pyttsx3:
            self.thread.start()
        else:
            logging.warning("TTSManager: pyttsx3 not installed. Speech disabled.")

    def speak(self, text):
        if not text or not self.running or not pyttsx3:
            return
        self.queue.put(str(text))

    def set_callbacks(self, on_start=None, on_end=None):
        self.on_start = on_start
        self.on_end = on_end

    def _worker(self):
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
            self.running = False
            return

        logging.info("TTSManager: Worker started.")
        
        while True:
            try:
                text = self.queue.get()
                if text is None:
                    self.queue.task_done()
                    break

                logging.info(f"TTSManager Speaking: {text[:50]}...")
                self.is_speaking = True
                if self.on_start:
                    self.on_start()
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                logging.error(f"TTSManager Error: {e}")
                time.sleep(1)
            finally:
                if "text" in locals() and text is not None:
                    self.is_speaking = False
                    if self.on_end:
                        try:
                            self.on_end()
                        except Exception as e:
                            logging.debug(f"TTS end callback failed: {e}")
                    self.queue.task_done()

        self.is_speaking = False
        if pythoncom:
            pythoncom.CoUninitialize()

    def stop(self, drain=True):
        if not self.running:
            return
        self.running = False
        if not pyttsx3:
            return

        if not drain:
            try:
                while True:
                    self.queue.get_nowait()
                    self.queue.task_done()
            except queue.Empty:
                pass
        self.queue.put(None)
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=5.0)
