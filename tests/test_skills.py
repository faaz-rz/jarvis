import tempfile
import unittest
from pathlib import Path

from core.memory import Memory
from core.skills import SkillContext, SkillManager


class FakeUI:
    def __init__(self):
        self.messages = []

    def display_message(self, text, sender="JARVIS"):
        self.messages.append((sender, text))

    def get_input(self):
        return ""


class FakeLLM:
    current_model_path = None
    default_model_path = None

    def generate(self, prompt):
        return "generated response"


class FakeEngine:
    def __init__(self, memory):
        self.memory = memory
        self.llm = FakeLLM()
        self.ui = FakeUI()
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory = Memory(Path(self.temp_dir.name) / "memory.json")
        self.engine = FakeEngine(self.memory)
        self.context = SkillContext(self.engine)
        self.manager = SkillManager(self.context)
        self.manager.load_skills()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_every_skill_loads_and_priority_is_deterministic(self):
        self.assertEqual(self.manager.load_errors, {})
        self.assertEqual(len(self.manager.skills), 9)
        priorities = [skill.priority for skill in self.manager.skills]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_learning_skill_parses_and_saves_command(self):
        handled = self.manager.process(
            "Learn: when I say focus mode do open notepad"
        )
        self.assertTrue(handled)
        self.assertEqual(
            self.memory.get_learned_command("FOCUS MODE"), "open notepad"
        )

    def test_power_action_requires_confirmation_and_can_cancel(self):
        system_skill = next(
            skill for skill in self.manager.skills if skill.name == "SystemControl"
        )
        self.assertTrue(system_skill.handle("shutdown pc"))
        self.assertEqual(system_skill.pending_power_action, "shutdown")
        self.assertTrue(system_skill.handle("no"))
        self.assertIsNone(system_skill.pending_power_action)

    def test_unsafe_automation_path_is_rejected(self):
        automation = next(
            skill for skill in self.manager.skills if skill.name == "Automation"
        )
        automation.automation_root = Path(self.temp_dir.name).resolve()
        self.assertTrue(automation.handle("create file ../../outside.txt"))
        self.assertIsNone(automation.pending_action)
        self.assertIn("For safety", self.engine.spoken[-1])

    def test_file_automation_requires_confirmation_then_creates_file(self):
        automation = next(
            skill for skill in self.manager.skills if skill.name == "Automation"
        )
        automation.automation_root = Path(self.temp_dir.name).resolve()
        target = automation.automation_root / "notes" / "todo.txt"

        self.assertTrue(automation.handle("create file notes/todo.txt"))
        self.assertFalse(target.exists())
        self.assertTrue(automation.handle("yes"))
        self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
