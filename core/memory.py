import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, Any, List

from core.config import default_memory_path


class Memory:
    def __init__(self, filepath=None):
        self.filepath = Path(filepath) if filepath else default_memory_path()
        self._lock = threading.RLock()
        self.data: Dict[str, Any] = {
            "user_preferences": {},
            "learned_commands": {},  # Format: {"trigger_phrase": "action_description"}
            "history": [],
            "system_prompt_extras": []
        }
        self.load()

    def load(self):
        if self.filepath.exists():
            try:
                with self._lock, self.filepath.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        for key, default in self.data.items():
                            value = loaded.get(key, default)
                            if isinstance(value, type(default)):
                                self.data[key] = value
                logging.info(f"Memory loaded from {self.filepath}")
            except (OSError, ValueError, TypeError) as e:
                logging.error(f"Failed to load memory: {e}")

    def save(self):
        """Persist memory atomically so an interrupted write cannot corrupt it."""
        try:
            with self._lock:
                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary_path = tempfile.mkstemp(
                    prefix=f".{self.filepath.name}.",
                    suffix=".tmp",
                    dir=str(self.filepath.parent),
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(self.data, f, indent=4, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temporary_path, self.filepath)
                except Exception:
                    try:
                        os.unlink(temporary_path)
                    except OSError:
                        pass
                    raise
        except (OSError, TypeError, ValueError) as e:
            logging.error(f"Failed to save memory: {e}")

    def get_preference(self, key: str, default=None):
        with self._lock:
            return self.data["user_preferences"].get(key, default)

    def set_preference(self, key: str, value: Any):
        with self._lock:
            self.data["user_preferences"][key] = value
            self.save()

    def learn_command(self, trigger: str, action: str):
        """Maps a user phrase to a specific action."""
        normalized_trigger = trigger.strip().lower()
        normalized_action = action.strip()
        if not normalized_trigger or not normalized_action:
            raise ValueError("Trigger and action must not be empty.")
        if normalized_trigger == normalized_action.lower():
            raise ValueError("A command cannot map to itself.")
        with self._lock:
            self.data["learned_commands"][normalized_trigger] = normalized_action
            self.save()

    def get_learned_command(self, text: str):
        """Checks if the text matches a learned command."""
        with self._lock:
            return self.data["learned_commands"].get(text.strip().lower())

    def resolve_learned_command(self, text: str, max_depth: int = 10):
        """Resolve chained learned commands and reject cycles."""
        current = text.strip()
        visited = set()
        for _ in range(max_depth):
            normalized = current.lower()
            if normalized in visited:
                raise ValueError("A cycle was detected in learned commands.")
            visited.add(normalized)
            action = self.get_learned_command(current)
            if not action:
                return current if len(visited) > 1 else None
            current = action
        raise ValueError("The learned command chain is too deep.")

    def add_history_item(self, role: str, content: str):
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported history role: {role}")
        with self._lock:
            self.data["history"].append({"role": role, "content": str(content)})
            if len(self.data["history"]) > 50:
                self.data["history"] = self.data["history"][-50:]
            self.save()

    def add_exchange(self, user_text: str, assistant_text: str):
        with self._lock:
            self.data["history"].extend(
                [
                    {"role": "user", "content": str(user_text)},
                    {"role": "assistant", "content": str(assistant_text)},
                ]
            )
            if len(self.data["history"]) > 50:
                self.data["history"] = self.data["history"][-50:]
            self.save()

    def get_recent_history(self, limit=10):
        with self._lock:
            return [item.copy() for item in self.data["history"][-limit:]]

    def get_system_prompt_extras(self) -> List[str]:
        with self._lock:
            return list(self.data["system_prompt_extras"])
