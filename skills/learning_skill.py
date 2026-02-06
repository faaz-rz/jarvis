from core.skills import BaseSkill

class LearningSkill(BaseSkill):
    name = "SelfLearning"
    description = "Allows the user to teach Jarvis custom commands."

    def handle(self, text: str) -> bool:
        # Syntax: "Learn: when I say <phrase> do <action>"
        lower = text.lower()
        if lower.startswith("learn:"):
            try:
                # Remove "learn:"
                content = text[6:].strip() 
                # Split by "when i say" and "do"
                # This is a bit naive parsing, but effective for strict commands
                if "when i say" in content.lower() and "do" in content.lower():
                    # normalize casing for parsing logic but keep content
                    # "when I say hello world do open notepad"
                    lower_content = content.lower()
                    start_idx = lower_content.find("when i say") + len("when i say")
                    do_idx = lower_content.find(" do ")
                    
                    trigger_phrase = content[start_idx:do_idx].strip()
                    action = content[do_idx+4:].strip()
                    
                    self.context.memory.learn_command(trigger_phrase, action)
                    self.context.speak(f"Understood. When you say '{trigger_phrase}', I will '{action}'.")
                    return True
            except Exception as e:
                self.context.speak(f"I couldn't learn that. Error: {e}")
                return True
        return False
