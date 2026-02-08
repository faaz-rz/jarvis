import sys
import logging
import time
import numpy as np
import sounddevice as sd

# Configure logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("1. Checking Dependencies...")
try:
    import sounddevice as sd
    print(f"   - sounddevice: {sd.__version__}")
except ImportError:
    print("   - sounddevice: MISSING")

try:
    import speech_recognition as sr
    print(f"   - speech_recognition: {sr.__version__}")
except ImportError:
    print("   - speech_recognition: MISSING")

print("\n2. Testing Audio Input (5 seconds)...")
def callback(indata, frames, time, status):
    if status:
        print(status)
    energy = np.max(np.abs(indata))
    print(f"Energy: {energy:5d} | Threshold: 700 | {'SPEAKING' if energy > 700 else '.......'}")

try:
    with sd.InputStream(callback=callback, channels=1, dtype='int16'):
        time.sleep(5)
    print("\n\nAudio Input Test Complete.")
except Exception as e:
    print(f"\nError: {e}")

print("\n3. Testing VoiceManager Integration...")
try:
    # Hack to mock engine
    class MockEngine:
        def speak(self, text):
            print(f"\n[JARVIS SPEAK]: {text}")
        def handle_input(self, text):
            print(f"\n[JARVIS ACTION]: {text}")

    sys.path.append('d:\\J.A.R.V.I.S')
    from core.voice import VoiceManager
    
    vm = VoiceManager(MockEngine())
    vm.start_listening()
    print("VoiceManager started. Say 'Jarvis'...")
    time.sleep(10)
    vm.stop_listening()
    print("Test Complete.")
    
except Exception as e:
    print(f"VoiceManager Error: {e}")
