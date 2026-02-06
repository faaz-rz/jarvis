import os
import json
import logging
import pickle
from typing import Dict, Any, List

class Memory:
    def __init__(self, filepath="jarvis_memory.json"):
        self.filepath = filepath
        self.data: Dict[str, Any] = {
            "user_preferences": {},
            "learned_commands": {},  # Format: {"trigger_phrase": "action_description"}
            "history": [],
            "system_prompt_extras": []
        }
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                logging.info(f"Memory loaded from {self.filepath}")
            except Exception as e:
                logging.error(f"Failed to load memory: {e}")

    def save(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save memory: {e}")

    def get_preference(self, key: str, default=None):
        return self.data["user_preferences"].get(key, default)

    def set_preference(self, key: str, value: Any):
        self.data["user_preferences"][key] = value
        self.save()

    def learn_command(self, trigger: str, action: str):
        """Maps a user phrase to a specific action."""
        self.data["learned_commands"][trigger.lower()] = action
        self.save()

    def get_learned_command(self, text: str) -> str:
        """Checks if the text matches a learned command."""
        return self.data["learned_commands"].get(text.lower())

    def add_history_item(self, role: str, content: str):
        self.data["history"].append({"role": role, "content": content})
        # Keep last 50 messages strictly for saving, runtime might use fewer
        if len(self.data["history"]) > 50:
            self.data["history"] = self.data["history"][-50:]
        self.save()

    def get_recent_history(self, limit=10):
        return self.data["history"][-limit:]
