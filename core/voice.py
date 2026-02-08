import threading
import time
import logging
import queue
import numpy as np


sr_error = None
try:
    import speech_recognition as sr
except ImportError as e:
    sr = None
    sr_error = e

sd_error = None
try:
    import sounddevice as sd
except ImportError as e:
    sd = None
    sd_error = e

class VoiceManager:
    def __init__(self, engine):
        self.engine = engine
        self.recognizer = sr.Recognizer() if sr else None
        
        # Audio Configuration
        self.SAMPLE_RATE = 16000
        self.BLOCK_SIZE = 4096 
        self.CHANNELS = 1
        self.DTYPE = 'int16'
        
        # VAD Configuration
        self.SILENCE_THRESHOLD = 700  # Raised to avoid noise-floor triggering (was 200)
        self.SILENCE_DURATION = 1.5   # Seconds of silence to consider command end
        
        self.is_listening = False
        self.stop_event = threading.Event()
        self.audio_queue = queue.Queue()
        
        self.wake_word = "jarvis"

        if not sd or not sr:
            msg = "Missing: "
            if not sd: msg += f"sounddevice ({sd_error}), "
            if not sr: msg += f"speech_recognition ({sr_error})"
            logging.warning(f"VoiceManager: {msg}")
            
            if hasattr(self.engine, 'ui'):
                self.engine.ui.display_message(f"Voice Init Failed: {msg}", "SYSTEM")

    def start_listening(self):
        if not sd or not sr:
            return
        
        if self.is_listening:
            return

        self.is_listening = True
        self.stop_event.clear()
        
        # Start processing thread
        self.thread = threading.Thread(target=self._vad_loop, daemon=True)
        self.thread.start()
        
        # Start Stream
        try:
             self.stream = sd.InputStream(samplerate=self.SAMPLE_RATE, blocksize=self.BLOCK_SIZE,
                                    channels=self.CHANNELS, dtype=self.DTYPE,
                                    callback=self._audio_callback)
             self.stream.start()
             logging.info("VoiceManager (SoundDevice): Started listening...")
             if hasattr(self.engine, 'ui'):
                 self.engine.ui.set_status("Voice Active (Listening...)")
                 self.engine.ui.display_message("Voice System Online. Say 'Jarvis'...", "SYSTEM")
        except Exception as e:
            logging.error(f"Failed to start stream: {e}")
            self.is_listening = False

    def pause(self):
        """Temporarily pause listening without closing stream completely if possible, 
           or just set a flag to ignore input."""
        if self.is_listening:
            logging.info("VoiceManager: Pausing...")
            self.stop_event.set() # Stops the VAD loop
            # We don't necessarily close the stream to keep it fast, 
            # but for safety let's stop it.
            if hasattr(self, 'stream'):
                self.stream.stop()
            self.is_listening = False

    def resume(self):
        """Resume listening."""
        logging.info("VoiceManager: Resuming...")
        self.start_listening()


    def stop_listening(self):
        self.is_listening = False
        self.stop_event.set()
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        logging.info("VoiceManager: Stopped listening.")

    def _audio_callback(self, indata, frames, time, status):
        if status:
            logging.warning(f"VoiceManager Audio Status: {status}")
        self.audio_queue.put(indata.copy())

    def _vad_loop(self):
        logging.info("VoiceManager: VAD Loop Started")
        
        buffer = []
        is_speaking = False
        silence_chunks = 0
        
        # Calculate chunks for silence duration
        chunks_per_sec = self.SAMPLE_RATE / self.BLOCK_SIZE
        silence_limit = int(self.SILENCE_DURATION * chunks_per_sec)
        
        while not self.stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            # Check if TTS is speaking
            if hasattr(self.engine, 'tts') and self.engine.tts.is_speaking:
                # Clear buffer to avoid processing system speech
                buffer = []
                is_speaking = False
                silence_chunks = 0
                continue
            
            # Energy Calculation
            # Amplitude max is simple and fast
            energy = np.max(np.abs(chunk))
            
            # Dynamic Threshold (very simple: if quiet, lower it slightly, if loud, raise it?)
            # For now, keeping static is safer to avoid drift loops
            
            if energy > self.SILENCE_THRESHOLD:
                is_speaking = True
                silence_chunks = 0
                buffer.append(chunk)
            else:
                if is_speaking:
                    silence_chunks += 1
                    buffer.append(chunk)
                    
                    if silence_chunks > silence_limit:
                        # End of utterance
                        logging.info("VoiceManager: End of speech detected. Processing...")
                        # Spawn thread to recognize so we don't block VAD
                        full_audio = np.concatenate(buffer)
                        threading.Thread(target=self._recognize_audio, args=(full_audio,), daemon=True).start()
                        
                        # Reset
                        buffer = []
                        is_speaking = False
                        silence_chunks = 0
                else:
                    # Pre-roll buffer could go here
                    pass

    def _recognize_audio(self, audio_data):
        try:
            # Create AudioData
            audio_bytes = audio_data.tobytes()
            source = sr.AudioData(audio_bytes, self.SAMPLE_RATE, 2)
            
            # Google SR
            text = self.recognizer.recognize_google(source).lower()
            logging.info(f"VoiceManager Heard: '{text}'")
            
            if self.wake_word in text:
                logging.info("VoiceManager: Wake Word Detected")
                self.engine.speak("Yes?")
                if hasattr(self.engine, 'ui'):
                    self.engine.ui.display_message("Yes? I'm listening...", "JARVIS")
                    self.engine.ui.set_status("Listening for command...")
                
                # Extract command
                parts = text.split(self.wake_word, 1)
                if len(parts) > 1 and parts[1].strip():
                    command = parts[1].strip()
                    self.engine.handle_input(command)
                    if hasattr(self.engine, 'ui'):
                        self.engine.ui.set_status("Processing Command...")
                    
            elif "stop" in text and "listening" in text:
                 self.engine.speak("Pausing voice.")
                 self.stop_listening()

        except sr.UnknownValueError:
            logging.debug("VoiceManager: Only noise.")
        except sr.RequestError as e:
            logging.error(f"VoiceManager API Error: {e}")
        except Exception as e:
            logging.error(f"VoiceManager Unexpected Error: {e}")
