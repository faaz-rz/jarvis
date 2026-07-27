"""Interactive microphone diagnostic for JARVIS."""
import logging
import sys
import time


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def optional_imports():
    missing = []
    try:
        import numpy as np
    except Exception as exc:
        np = None
        missing.append(f"numpy: {exc}")
    try:
        import sounddevice as sd
    except Exception as exc:
        sd = None
        missing.append(f"sounddevice: {exc}")
    try:
        import speech_recognition as sr
    except Exception as exc:
        sr = None
        missing.append(f"SpeechRecognition: {exc}")
    try:
        import vosk
    except Exception as exc:
        vosk = None
        missing.append(f"vosk: {exc}")
    return np, sd, sr, vosk, missing


def main():
    np, sd, sr, vosk, missing = optional_imports()
    print("Voice dependency check")
    print(f"- numpy: {getattr(np, '__version__', 'missing')}")
    print(f"- sounddevice: {getattr(sd, '__version__', 'missing')}")
    print(f"- SpeechRecognition: {getattr(sr, '__version__', 'missing')}")
    print(f"- vosk: {'installed' if vosk else 'missing'}")

    if not np or not sd:
        print("\nMicrophone test cannot run:")
        for item in missing:
            print(f"- {item}")
        print("\nInstall dependencies with: pip install -r requirements.txt")
        return 1

    print("\nTesting audio input for five seconds...")

    def callback(indata, frames, callback_time, status):
        if status:
            print(status)
        energy = int(np.max(np.abs(indata.astype(np.int32))))
        state = "SPEAKING" if energy > 700 else "quiet"
        print(f"Energy: {energy:5d} | Threshold: 700 | {state}")

    try:
        with sd.InputStream(callback=callback, channels=1, dtype="int16"):
            time.sleep(5)
    except Exception as exc:
        print(f"Audio input failed: {exc}")
        return 1

    print("\nTesting VoiceManager startup for ten seconds...")

    class MockUI:
        def display_message(self, text, sender="SYSTEM"):
            print(f"[{sender}] {text}")

        def set_status(self, text):
            print(f"[status] {text}")

    class MockTTS:
        is_speaking = False

    class MockEngine:
        running = True
        ui = MockUI()
        tts = MockTTS()

        def speak(self, text):
            print(f"[JARVIS] {text}")

        def handle_input(self, text):
            print(f"[COMMAND] {text}")

    from core.voice import VoiceManager

    manager = VoiceManager(MockEngine())
    if not manager.start_listening():
        print("VoiceManager could not start. Review the messages above.")
        return 1
    print("Say 'Jarvis' followed by a command.")
    time.sleep(10)
    manager.stop_listening()
    print("Voice diagnostic complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
