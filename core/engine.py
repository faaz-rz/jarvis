import threading
import time
import logging
from typing import Optional

from core.memory import Memory
from core.llm import LLMEngine
from core.ui import BaseUI, ConsoleUI, TkinterUI
from core.skills import SkillManager, SkillContext

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

class JarvisEngine:
    def __init__(self):
        self.memory = Memory()
        self.llm = LLMEngine()
        
        # Initialize UI - prefers Tkinter, falls back to Console
        # We need a callback for when the user hits 'Send'
        try:
            self.ui = TkinterUI(self.handle_input)
        except Exception:
            logging.warning("Tkinter UI failed to initialize, falling back to Console")
            self.ui = ConsoleUI()

        self.context = SkillContext(self)
        self.skill_manager = SkillManager(self.context)
        
        self.tts_engine = None
        self._setup_tts()
        
        self.running = True

    def _setup_tts(self):
        if pyttsx3:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 160)
                # Run TTS in a separate thread loop is tricky with pyttsx3
                # We'll just call it blocking for now or use a queue if needed
            except Exception as e:
                logging.error(f"TTS Init failed: {e}")

    def start(self):
        logging.info("Jarvis Engine Starting...")
        self.skill_manager.load_skills()
        self.ui.display_message("System Online. skills loaded.", "SYSTEM")
        self.speak("System Online.")
        
        # Start the UI (blocking for Tkinter)
        # For Console, we need a loop
        if isinstance(self.ui, ConsoleUI):
            while self.running:
                user_text = self.ui.get_input()
                if user_text:
                    self.handle_input(user_text)
        else:
            self.ui.start()

    def handle_input(self, text: str):
        if text.lower() in ("exit", "quit", "shutdown"):
            self.shutdown()
            return

        self.ui.display_message(text, "You")
        
        # 1. Check learned commands
        learned_action = self.memory.get_learned_command(text)
        if learned_action:
            self.ui.display_message(f"(Executing learned action: {learned_action})", "SYSTEM")
            # Recursively handle the learned action text
            # CAUTION: prevent infinite loops
            if learned_action != text:
                self.handle_input(learned_action)
            return

        # 2. Check Skills
        print(f"DEBUG: Checking skills for: '{text}'")
        if self.skill_manager.process(text):
            return

        # 3. Fallback to LLM
        self.ui.set_status("Thinking...")
        
        # Construct prompt with history
        history = self.memory.get_recent_history()
        prompt_lines = [
            f"<|im_start|>system\nYou are J.A.R.V.I.S, an advanced enterprise-grade AI assistant. You can see the screen, browse the internet, and control the system. You are helpful, precise, witty, and highly capable. You answer directly and efficiently.\n<|im_end|>"
        ]
        for item in history:
            role = "user" if item['role'] == "user" else "assistant"
            prompt_lines.append(f"<|im_start|>{role}\n{item['content']}\n<|im_end|>")
        
        prompt_lines.append(f"<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n")
        full_prompt = "\n".join(prompt_lines)

        # Run LLM in separate thread to not block UI
        threading.Thread(target=self._run_llm, args=(full_prompt, text)).start()

    def _run_llm(self, prompt, original_user_text):
        # 4. Smart Regex/Heuristics (Run BEFORE or INSTEAD of broken LLM)
        #    This ensures Jarvis works even if the model is missing.
        lower_text = original_user_text.lower()
        response = None

        if "my name is" in lower_text:
            name = original_user_text.split("is")[-1].strip()
            self.memory.set_preference("user_name", name)
            response = f"Nice to meet you, {name}. I've saved that to memory."
        
        elif "i am your boss" in lower_text or "i'm your boss" in lower_text:
            self.memory.set_preference("user_role", "Boss")
            response = "Understood, Boss. I am at your service."

        elif "what is my name" in lower_text:
            name = self.memory.get_preference("user_name")
            if name:
                response = f"Your name is {name}."
            else:
                response = "I don't know your name yet. Please tell me 'My name is...'."

        elif "who am i" in lower_text:
            role = self.memory.get_preference("user_role")
            name = self.memory.get_preference("user_name")
            parts = []
            if name: parts.append(f"You are {name}.")
            if role: parts.append(f"You are the {role}.")
            if not parts:
                response = "I'm not sure related to your identity yet."
            else:
                response = " ".join(parts)

        elif "remember that" in lower_text:
             fact = original_user_text[original_user_text.lower().find("remember that")+13:].strip()
             self.memory.set_preference(f"fact_{int(time.time())}", fact)
             response = f"I have noted that: {fact}"
        
        # If we caught it with regex, we can skip LLM or combine. 
        # For now, if we have a regex response, return it immediately (faster/safer).
        if response:
            self.ui.set_status("")
            self.ui.display_message(response, "JARVIS")
            self.speak(response)
            self.memory.add_history_item("user", original_user_text)
            self.memory.add_history_item("assistant", response)
            return

        # 5. LLM Attempt
        response = self.llm.generate(prompt)
        
        # Check for error message from LLM engine
        if "System Error:" in response or "Error:" in response:
            logging.error(f"LLM FAILURE RESPONSE: {response}")
            # Fallback chat logic if LLM is broken
            if "hello" in lower_text or "hi" in lower_text:
                fallback = "Hello! My AI core is currently offline (" + response + "), but my command modules are fully operational."
            elif "who are you" in lower_text:
                fallback = "I am JARVIS. (System Error: " + response + ")"
            elif "time" in lower_text:
                fallback = f"The current time is {time.strftime('%I:%M %p')}."
            elif "date" in lower_text:
                fallback = f"Today's date is {time.strftime('%B %d, %Y')}."
            else:
                fallback = f"My AI system reported: {response}. I can still run commands."
            
            response = fallback

        self.ui.set_status("")
        self.ui.display_message(response, "JARVIS")
        self.speak(response)
        
        # Save history
        self.memory.add_history_item("user", original_user_text)
        self.memory.add_history_item("assistant", response)

    def speak(self, text: str):
        if not text: 
            return
        
        # Remove markdown/code blocks for speech
        clean_text = text
        if "```" in clean_text:
            clean_text = "I have generated the code for you."
            
        if self.tts_engine:
            try:
                # pyttsx3 runAndWait is blocking, so we might want to thread this
                # or just accept the pause. Threading pyttsx3 is notoriously unstable.
                # A simple daemon thread for saying one thing:
                def _say():
                    try:
                        # Re-init in thread if needed or use properly
                        # Usually best to have one specialized TTS thread with a queue
                        # For simplicity here:
                        engine = pyttsx3.init()
                        engine.say(clean_text)
                        engine.runAndWait()
                    except:
                        pass
                threading.Thread(target=_say, daemon=True).start()
            except Exception:
                pass

    def shutdown(self):
        self.running = False
        self.speak("Shutting down.")
        self.memory.save()
        if isinstance(self.ui, TkinterUI):
            self.ui.root.quit()
        exit(0)
