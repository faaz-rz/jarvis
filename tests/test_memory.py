import json
import tempfile
import threading
import unittest
from pathlib import Path

from core.memory import Memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "memory.json"
        self.memory = Memory(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preferences_and_learned_commands_persist(self):
        self.memory.set_preference("name", "Faaz")
        self.memory.learn_command("Open editor", "open notepad")

        reloaded = Memory(self.path)
        self.assertEqual(reloaded.get_preference("name"), "Faaz")
        self.assertEqual(
            reloaded.get_learned_command("OPEN EDITOR"), "open notepad"
        )

    def test_learned_command_chains_resolve_and_cycles_are_rejected(self):
        self.memory.learn_command("work", "editor")
        self.memory.learn_command("editor", "open notepad")
        self.assertEqual(
            self.memory.resolve_learned_command("work"), "open notepad"
        )

        self.memory.learn_command("a", "b")
        self.memory.learn_command("b", "a")
        with self.assertRaises(ValueError):
            self.memory.resolve_learned_command("a")

    def test_history_is_limited_and_exchange_is_atomic(self):
        for index in range(55):
            self.memory.add_history_item("user", str(index))
        self.assertEqual(len(self.memory.get_recent_history(100)), 50)
        self.assertEqual(self.memory.get_recent_history(10)[0]["content"], "45")

        self.memory.add_exchange("question", "answer")
        recent = self.memory.get_recent_history(2)
        self.assertEqual([item["role"] for item in recent], ["user", "assistant"])

        # A successful atomic save always leaves valid JSON.
        with self.path.open(encoding="utf-8") as handle:
            json.load(handle)

    def test_concurrent_writes_leave_valid_memory(self):
        threads = [
            threading.Thread(
                target=self.memory.set_preference, args=(f"key_{index}", index)
            )
            for index in range(12)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        reloaded = Memory(self.path)
        for index in range(12):
            self.assertEqual(reloaded.get_preference(f"key_{index}"), index)


if __name__ == "__main__":
    unittest.main()
