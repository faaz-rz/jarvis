# utils.py
import random
import logging

def speak(text, engine, gui=None):
    try:
        prefixes = ["Alright.", "Here's what I found:", "Sure thing.", "Got it."]
        pre = random.choice(prefixes) if random.random() < 0.3 else ""
        full_text = f"{pre} {text}"
        logging.info(f"Jarvis says: {full_text}")
        engine.say(full_text)
        engine.runAndWait()
        if gui:
            gui.display_message(full_text)
    except Exception as e:
        logging.error(f"Failed to speak: {e}")
        print(f"[Jarvis Voice Error]: {e}")