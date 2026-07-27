"""Audio capture, speech detection, transcription, and wake-word handling."""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from collections import deque

from core.config import vosk_model_path

try:
    import numpy as np
except Exception as exc:
    np = None
    NP_ERROR = exc
else:
    NP_ERROR = None

try:
    import sounddevice as sd
except Exception as exc:
    sd = None
    SD_ERROR = exc
else:
    SD_ERROR = None

try:
    import speech_recognition as sr
except Exception as exc:
    sr = None
    SR_ERROR = exc
else:
    SR_ERROR = None

try:
    from vosk import KaldiRecognizer, Model as VoskModel
except Exception:
    KaldiRecognizer = None
    VoskModel = None


class VoiceManager:
    def __init__(self, engine):
        self.engine = engine
        self.SAMPLE_RATE = 16000
        self.BLOCK_SIZE = 4096
        self.CHANNELS = 1
        self.DTYPE = "int16"
        self.SILENCE_THRESHOLD = int(os.environ.get("VOICE_THRESHOLD", "700"))
        self.SILENCE_DURATION = float(os.environ.get("VOICE_SILENCE_SECONDS", "1.5"))
        self.COMMAND_TIMEOUT = float(os.environ.get("VOICE_COMMAND_TIMEOUT", "8"))
        self.wake_word = os.environ.get("JARVIS_WAKE_WORD", "jarvis").strip().lower()

        self.is_listening = False
        self.user_enabled = True
        self.stop_event = threading.Event()
        self.audio_queue = queue.Queue()
        self.stream = None
        self.thread = None
        self._state_lock = threading.RLock()
        self._awaiting_command_until = 0.0

        self.recognizer = sr.Recognizer() if sr else None
        self.vosk_model = None
        self.speech_backend = "none"
        self._configure_transcription()

        missing = []
        if not np:
            missing.append(f"numpy ({NP_ERROR})")
        if not sd:
            missing.append(f"sounddevice ({SD_ERROR})")
        if self.speech_backend == "none":
            missing.append(
                "a speech backend (install vosk for offline use or SpeechRecognition for Google)"
            )
        if missing:
            message = "Voice disabled; missing " + ", ".join(missing)
            logging.warning(message)
            if hasattr(self.engine, "ui"):
                self.engine.ui.display_message(message, "SYSTEM")

    @property
    def available(self) -> bool:
        return bool(np is not None and sd is not None and self.speech_backend != "none")

    def _configure_transcription(self):
        requested = os.environ.get("JARVIS_SPEECH_BACKEND", "auto").strip().lower()
        model_path = vosk_model_path()

        if requested in {"auto", "vosk", "offline"} and VoskModel and model_path:
            try:
                self.vosk_model = VoskModel(str(model_path))
                self.speech_backend = "vosk"
                logging.info("Voice transcription backend: Vosk (%s)", model_path)
                return
            except Exception as exc:
                logging.warning("Could not load Vosk model at %s: %s", model_path, exc)

        if requested not in {"vosk", "offline"} and self.recognizer:
            self.speech_backend = "google"
            logging.info("Voice transcription backend: Google Speech Recognition")

    def start_listening(self):
        self.user_enabled = True
        if not self.available:
            return False

        with self._state_lock:
            if self.is_listening:
                return True
            self._drain_audio_queue()
            self.stop_event = threading.Event()
            self.is_listening = True
            self.thread = threading.Thread(
                target=self._vad_loop,
                args=(self.stop_event,),
                daemon=True,
                name="jarvis-vad",
            )
            self.thread.start()

            try:
                self.stream = sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    blocksize=self.BLOCK_SIZE,
                    channels=self.CHANNELS,
                    dtype=self.DTYPE,
                    callback=self._audio_callback,
                )
                self.stream.start()
            except Exception as exc:
                logging.error("Failed to start audio stream: %s", exc)
                self.is_listening = False
                self.stop_event.set()
                self._close_stream()
                return False

        logging.info("VoiceManager started listening")
        if hasattr(self.engine, "ui"):
            self.engine.ui.set_status("Voice active")
            self.engine.ui.display_message(
                f"Voice online. Say '{self.wake_word}'.", "SYSTEM"
            )
        return True

    def pause(self):
        with self._state_lock:
            if not self.is_listening:
                return
            self.is_listening = False
            self.stop_event.set()
            self._close_stream()
            self._drain_audio_queue()
        logging.debug("VoiceManager paused")

    def resume(self):
        if self.user_enabled and getattr(self.engine, "running", True):
            self.start_listening()

    def stop_listening(self):
        self.user_enabled = False
        self.pause()
        self._awaiting_command_until = 0.0
        logging.info("VoiceManager stopped listening")

    def _close_stream(self):
        stream, self.stream = self.stream, None
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    def _drain_audio_queue(self):
        try:
            while True:
                self.audio_queue.get_nowait()
        except queue.Empty:
            pass

    def _audio_callback(self, indata, frames, callback_time, status):
        if status:
            logging.warning("VoiceManager audio status: %s", status)
        if self.is_listening:
            self.audio_queue.put(indata.copy())

    def _vad_loop(self, stop_event):
        logging.debug("VoiceManager VAD loop started")
        buffer = []
        pre_roll = deque(maxlen=2)
        is_speaking = False
        silence_chunks = 0
        chunks_per_second = self.SAMPLE_RATE / self.BLOCK_SIZE
        silence_limit = max(1, int(self.SILENCE_DURATION * chunks_per_second))

        while not stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if getattr(getattr(self.engine, "tts", None), "is_speaking", False):
                buffer = []
                pre_roll.clear()
                is_speaking = False
                silence_chunks = 0
                continue

            energy = int(np.max(np.abs(chunk.astype(np.int32))))
            if energy > self.SILENCE_THRESHOLD:
                if not is_speaking:
                    buffer = list(pre_roll)
                    pre_roll.clear()
                is_speaking = True
                silence_chunks = 0
                buffer.append(chunk)
            elif is_speaking:
                silence_chunks += 1
                buffer.append(chunk)
                if silence_chunks >= silence_limit:
                    full_audio = np.concatenate(buffer)
                    threading.Thread(
                        target=self._recognize_audio,
                        args=(full_audio,),
                        daemon=True,
                        name="jarvis-transcription",
                    ).start()
                    buffer = []
                    is_speaking = False
                    silence_chunks = 0
            else:
                pre_roll.append(chunk)

    def _recognize_audio(self, audio_data):
        try:
            text = self._transcribe(audio_data)
            if text:
                logging.info("VoiceManager heard: %r", text)
                self._handle_transcript(text)
        except Exception as exc:
            if sr and isinstance(exc, getattr(sr, "UnknownValueError", ())):
                logging.debug("VoiceManager heard only noise")
            else:
                logging.error("Voice transcription failed: %s", exc)

    def _transcribe(self, audio_data) -> str:
        audio_bytes = audio_data.tobytes()
        if self.speech_backend == "vosk" and self.vosk_model:
            recognizer = KaldiRecognizer(self.vosk_model, self.SAMPLE_RATE)
            recognizer.AcceptWaveform(audio_bytes)
            return json.loads(recognizer.FinalResult()).get("text", "").strip().lower()

        if self.speech_backend == "google" and self.recognizer and sr:
            source = sr.AudioData(audio_bytes, self.SAMPLE_RATE, 2)
            return self.recognizer.recognize_google(source).strip().lower()
        return ""

    def _handle_transcript(self, text: str):
        """Route a transcript. Kept separate so wake-word behavior is testable."""
        text = text.strip().lower()
        now = time.monotonic()

        if "stop listening" in text:
            self.engine.speak("Pausing voice.")
            self.stop_listening()
            return

        wake_index = text.find(self.wake_word)
        if wake_index >= 0:
            command = text[wake_index + len(self.wake_word):].strip(" ,.!?")
            if command:
                self._awaiting_command_until = 0.0
                self.engine.handle_input(command)
                return

            self._awaiting_command_until = now + self.COMMAND_TIMEOUT
            self.engine.speak("Yes?")
            if hasattr(self.engine, "ui"):
                self.engine.ui.display_message("Yes? I'm listening...", "JARVIS")
                self.engine.ui.set_status("Listening for command")
            return

        if now <= self._awaiting_command_until:
            self._awaiting_command_until = 0.0
            self.engine.handle_input(text)
