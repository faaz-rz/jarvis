from core.skills import BaseSkill
import random
import time

class SmallTalkSkill(BaseSkill):
    name = "SmallTalk"
    description = "Handles basic conversation when LLM is offline."

    def __init__(self, context):
        super().__init__(context)
        self.responses = {
            "hello": ["Greetings!", "Hello there.", "Systems online and ready.", "Hi!", "I am listening."],
            "hi": ["Hello!", "Hi there.", "At your service.", "Ready for instructions."],
            "hey": ["Hello.", "Yes?", "I'm here."],
            "yo": ["Greetings.", "Online."],
            "how are you": ["I am operating at peak efficiency.", "All systems nominal.", "I am functioning within normal parameters.", "I am ready to assist you."],
            "who are you": ["I am J.A.R.V.I.S, your personal AI assistant.", "I am a sophisticated AI system designed to aid you.", "I am your automated assistant."],
            "what can you do": ["I can open apps, search the web, read your screen, control system settings, and learn new commands.", "Try asking me to 'read screen', 'search for news', or 'open calculator'."],
            "thank you": ["You're welcome.", "My pleasure.", "Anytime.", "Happy to help."],
            "thanks": ["You're welcome.", "Glad to be of service."],
            "good morning": ["Good morning.", "Hope you have a productive day."],
            "good night": ["Good night.", "Sleep well.", "I'll stand guard."],
            "bye": ["Goodbye!", "Signing off.", "See you soon.", "Terminating session."],
            "jarvis": ["Yes?", "At your service.", "Awaiting commands.", "I am here."],
        }

    def handle(self, text: str) -> bool:
        # [FIX] Robust stripping of punctuation and whitespace
        clean_text = text.lower().strip()
        for char in '.?!,':
            clean_text = clean_text.replace(char, '')
        clean_text = clean_text.strip()
        
        # Exact match or simple containment
        for key, replies in self.responses.items():
            # Check for exact match OR (key is prevalent and text is short)
            if clean_text == key:
                response = random.choice(replies)
                self.context.speak(response)
                self.context.memory.add_history_item("user", text)
                self.context.memory.add_history_item("assistant", response)
                return True
            
            # Substring match for longer phrases (avoid matching "hi" in "history")
            if len(key) > 3 and key in clean_text:
                response = random.choice(replies)
                self.context.speak(response)
                # We need to manually add to history since we bypassing engine LLM logic
                self.context.memory.add_history_item("user", text)
                self.context.memory.add_history_item("assistant", response)
                return True
                
        # Time/Date checks (Engine fallback covers this, but Skill is faster)
        if "what time" in clean_text or "current time" in clean_text:
             t = time.strftime('%I:%M %p')
             self.context.speak(f"It is {t}.")
             return True
             
        return False
