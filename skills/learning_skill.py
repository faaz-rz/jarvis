import re

from core.skills import BaseSkill
from core.tools import RiskLevel, ToolSpec


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

    def tools(self):
        return [
            ToolSpec(
                name="remember_fact",
                description="Store a user-provided fact in long-term memory.",
                parameters={
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "maxLength": 1000,
                            "description": "The exact fact the user asked JARVIS to remember.",
                        }
                    },
                    "required": ["fact"],
                    "additionalProperties": False,
                },
                handler=self.remember_fact,
                risk=RiskLevel.WRITE,
                confirmation="Save this fact in long-term memory: {fact}?",
            ),
            ToolSpec(
                name="search_memory",
                description="Search JARVIS long-term memory for relevant past information.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "maxLength": 500,
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                handler=self.search_memory,
                risk=RiskLevel.READ_ONLY,
            ),
            ToolSpec(
                name="clear_long_term_memory",
                description="Permanently clear all SQLite long-term conversational memory.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                handler=self.clear_long_term_memory,
                risk=RiskLevel.DESTRUCTIVE,
                confirmation="Permanently clear all long-term conversational memory?",
            ),
        ]

    def remember_fact(self, fact):
        long_term = getattr(self.context.engine, "long_term_memory", None)
        if long_term:
            return long_term.remember_fact(fact)
        self.context.memory.set_preference(f"fact_{hash(fact)}", fact)
        return f"Remembered: {fact}"

    def search_memory(self, query):
        long_term = getattr(self.context.engine, "long_term_memory", None)
        if not long_term:
            return "Long-term memory is disabled."
        results = long_term.search(query, limit=5)
        if not results:
            return "No relevant long-term memories were found."
        return "\n".join(
            f"- [{item['kind']}] {item['content'][:500]}"
            for item in results
        )

    def clear_long_term_memory(self):
        long_term = getattr(self.context.engine, "long_term_memory", None)
        if not long_term:
            return "Long-term memory is disabled."
        return long_term.clear()
