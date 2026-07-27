import threading
import time
import logging
import re
import queue
from typing import Optional

from core.memory import Memory
from core.llm import LLMEngine, LLMUnavailableError
from core.ui import BaseUI, ConsoleUI, TkinterUI
from core.skills import SkillManager, SkillContext
from core.voice import VoiceManager
from core.tts import TTSManager

class JarvisEngine:
    def __init__(
        self,
        memory: Optional[Memory] = None,
        llm: Optional[LLMEngine] = None,
        ui: Optional[BaseUI] = None,
        tts: Optional[TTSManager] = None,
        enable_voice: bool = True,
        prefer_gui: bool = True,
    ):
        self.memory = memory or Memory()
        self.llm = llm or LLMEngine()
        self.running = True
        self._shutdown_lock = threading.Lock()
        self._llm_queue = queue.Queue()
        self._llm_worker_thread = threading.Thread(
            target=self._llm_worker,
            daemon=True,
            name="jarvis-llm",
        )
        self._llm_worker_thread.start()

        if ui is not None:
            self.ui = ui
        elif prefer_gui:
            try:
                self.ui = TkinterUI(self.handle_input)
            except Exception as exc:
                logging.warning(
                    "Tkinter UI failed to initialize; falling back to console: %s", exc
                )
                self.ui = ConsoleUI()
        else:
            self.ui = ConsoleUI()

        self.context = SkillContext(self)
        self.skill_manager = SkillManager(self.context)

        self.tts = tts or TTSManager()
        self.voice_manager = VoiceManager(self) if enable_voice else None
        if hasattr(self.tts, "set_callbacks"):
            self.tts.set_callbacks(self._on_speech_start, self._on_speech_end)

    def _on_speech_start(self):
        if self.voice_manager:
            self.voice_manager.pause()

    def _on_speech_end(self):
        if self.running and self.voice_manager:
            self.voice_manager.resume()

    def start(self):
        logging.info("Jarvis Engine Starting...")
        self.skill_manager.load_skills()
        count = len(self.skill_manager.skills)
        self.ui.display_message(f"System online. {count} skills loaded.", "SYSTEM")
        self.ui.display_message(
            f"Language model: {getattr(self.llm, 'model_name', 'local model')} "
            f"via {getattr(self.llm, 'backend', 'configured backend')}.",
            "SYSTEM",
        )
        if self.skill_manager.load_errors:
            self.ui.display_message(
                f"{len(self.skill_manager.load_errors)} optional skills could not be loaded. "
                "See jarvis_system.log for details.",
                "SYSTEM",
            )
        self.speak("System Online.")
        
        if self.voice_manager:
            self.voice_manager.start_listening()

        if isinstance(self.ui, ConsoleUI):
            while self.running:
                user_text = self.ui.get_input()
                if user_text:
                    self.handle_input(user_text)
        else:
            self.ui.start()

    def handle_input(self, text: str):
        if not isinstance(text, str) or not text.strip() or not self.running:
            return

        text = text.strip()
        if text.lower() in ("exit", "quit", "shutdown", "shutdown jarvis"):
            self.shutdown()
            return

        self.ui.display_message(text, "You")

        if text.lower() in {"help", "show commands", "list skills"}:
            response = "Available skills:\n" + self.skill_manager.help_text()
            self._deliver_response(response, text)
            return

        routed_text = text
        try:
            learned_action = self.memory.resolve_learned_command(text)
            if learned_action:
                routed_text = learned_action
                self.ui.display_message(
                    f"Executing learned action: {learned_action}", "SYSTEM"
                )
        except ValueError as exc:
            response = f"I could not run that learned command: {exc}"
            self._deliver_response(response, text)
            return

        if self.skill_manager.process(routed_text):
            return

        self.ui.set_status("Thinking...")
        history = self.memory.get_recent_history()
        extras = "\n".join(self.memory.get_system_prompt_extras())
        model_name = getattr(self.llm, "model_name", "a local language model")
        system_prompt = (
            "You are J.A.R.V.I.S, a capable local desktop personal assistant. "
            f"Your language model is {model_name}; state this accurately if asked. "
            "Be helpful, precise, concise, and honest about capabilities. "
            "Do not describe yourself as a home automation system. "
            "Do not claim an action was completed unless a skill actually completed it."
        )
        if extras:
            system_prompt += f"\nAdditional user instructions:\n{extras}"

        prompt_lines = [
            f"<|im_start|>system\n{system_prompt}\n<|im_end|>"
        ]
        for item in history:
            role = item.get("role", "assistant")
            if role not in {"system", "user", "assistant"}:
                role = "assistant"
            prompt_lines.append(f"<|im_start|>{role}\n{item['content']}\n<|im_end|>")
        
        prompt_lines.append(
            f"<|im_start|>user\n{routed_text}\n<|im_end|>\n<|im_start|>assistant\n"
        )
        full_prompt = "\n".join(prompt_lines)

        self._llm_queue.put((full_prompt, text))

    def _llm_worker(self):
        while True:
            task = self._llm_queue.get()
            try:
                if task is None:
                    return
                self._run_llm(*task)
            except Exception as exc:
                logging.exception("Unhandled LLM worker error: %s", exc)
            finally:
                self._llm_queue.task_done()

    def _run_llm(self, prompt, original_user_text):
        lower_text = original_user_text.lower()
        response = None

        name_match = re.search(r"\bmy name is\s+(.+?)[.!?]*$", original_user_text, re.I)
        if name_match:
            name = name_match.group(1).strip()
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
                response = "I don't know your identity yet."
            else:
                response = " ".join(parts)

        elif "remember that" in lower_text:
            fact = original_user_text[
                original_user_text.lower().find("remember that") + len("remember that"):
            ].strip()
            if fact:
                self.memory.set_preference(f"fact_{int(time.time())}", fact)
                response = f"I have noted that: {fact}"
        
        if response:
            self._deliver_response(response, original_user_text)
            return

        try:
            response = self.llm.generate(prompt)
        except LLMUnavailableError as exc:
            logging.error("LLM unavailable: %s", exc)
            if "who are you" in lower_text:
                response = "I am JARVIS, your local personal assistant."
            elif "time" in lower_text:
                response = f"The current time is {time.strftime('%I:%M %p')}."
            elif "date" in lower_text:
                response = f"Today's date is {time.strftime('%B %d, %Y')}."
            else:
                if getattr(self.llm, "backend", "ollama") == "llama_cpp":
                    response = (
                        "The configured GGUF language model is unavailable, but built-in "
                        "skills still work. Check MISTRAL_MODEL_PATH and the system log."
                    )
                else:
                    model = getattr(self.llm, "ollama_model", "qwen3.5:4b")
                    response = (
                        f"The local Qwen model '{model}' is unavailable, but built-in "
                        "skills still work. Start Ollama and make sure the model is installed."
                    )
        except Exception as exc:
            logging.exception("Unexpected language-model failure: %s", exc)
            response = (
                "I could not complete that language-model request. "
                "Built-in commands are still available; check jarvis_system.log for details."
            )

        self._deliver_response(response, original_user_text)

    def _deliver_response(self, response: str, user_text: Optional[str] = None):
        if not self.running:
            return
        self.ui.set_status("")
        self.ui.display_message(response, "JARVIS")
        self.speak(response)
        if user_text:
            self.memory.add_exchange(user_text, response)

    def speak(self, text: str):
        if not text: 
            return
        
        # Remove markdown/code blocks for speech
        clean_text = text
        if "```" in clean_text:
            clean_text = "I have generated the code for you."
            
        if self.tts:
            self.tts.speak(clean_text)

    def shutdown(self):
        with self._shutdown_lock:
            if not self.running:
                return
            self.running = False
            if self.voice_manager:
                self.voice_manager.stop_listening()
            try:
                while True:
                    self._llm_queue.get_nowait()
                    self._llm_queue.task_done()
            except queue.Empty:
                pass
            self._llm_queue.put(None)
            self.speak("Shutting down.")
            self.tts.stop(drain=True)
            self.memory.save()
            self.ui.stop()
            logging.info("Jarvis Engine stopped.")
