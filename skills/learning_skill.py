import re

from core.skills import BaseSkill


class LearningSkill(BaseSkill):
    name = "SelfLearning"
    description = "Allows the user to teach Jarvis custom commands."
    priority = 100

    def handle(self, text: str) -> bool:
        if text.lower().startswith("learn:"):
            try:
                match = re.fullmatch(
                    r"learn:\s*when\s+i\s+say\s+(.+?)\s+do\s+(.+)",
                    text.strip(),
                    flags=re.IGNORECASE,
                )
                if not match:
                    self.context.speak(
                        "Use: Learn: when I say <phrase> do <action>."
                    )
                    return True
                trigger_phrase, action = (value.strip() for value in match.groups())
                self.context.memory.learn_command(trigger_phrase, action)
                self.context.speak(
                    f"Understood. When you say '{trigger_phrase}', I will '{action}'."
                )
                return True
            except (ValueError, OSError) as e:
                self.context.speak(f"I couldn't learn that. Error: {e}")
                return True
        return False
