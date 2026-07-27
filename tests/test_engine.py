import tempfile
import unittest
from pathlib import Path

from core.engine import JarvisEngine
from core.llm import LLMUnavailableError
from core.memory import Memory


class FakeUI:
    def __init__(self):
        self.messages = []
        self.statuses = []

    def display_message(self, text, sender="JARVIS"):
        self.messages.append((sender, text))

    def set_status(self, text):
        self.statuses.append(text)

    def get_input(self):
        return ""

    def start(self):
        pass

    def stop(self):
        pass


class FakeTTS:
    def __init__(self):
        self.spoken = []
        self.is_speaking = False
        self.stopped = False

    def set_callbacks(self, on_start=None, on_end=None):
        self.on_start = on_start
        self.on_end = on_end

    def speak(self, text):
        self.spoken.append(text)

    def stop(self, drain=True):
        self.stopped = True


class FakeLLM:
    current_model_path = None
    default_model_path = None

    def __init__(self, response="model answer", unavailable=False):
        self.response = response
        self.unavailable = unavailable

    def generate(self, prompt):
        if self.unavailable:
            raise LLMUnavailableError("not configured")
        return self.response


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory = Memory(Path(self.temp_dir.name) / "memory.json")
        self.ui = FakeUI()
        self.tts = FakeTTS()

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_engine(self, llm=None):
        return JarvisEngine(
            memory=self.memory,
            llm=llm or FakeLLM(),
            ui=self.ui,
            tts=self.tts,
            enable_voice=False,
        )

    def test_memory_heuristic_saves_name(self):
        engine = self.make_engine()
        engine._run_llm("unused", "My name is Ada.")
        self.assertEqual(self.memory.get_preference("user_name"), "Ada")
        self.assertIn(("JARVIS", "Nice to meet you, Ada. I've saved that to memory."), self.ui.messages)

    def test_llm_unavailable_has_clean_fallback(self):
        engine = self.make_engine(FakeLLM(unavailable=True))
        engine._run_llm("prompt", "explain qubits")
        response = self.ui.messages[-1][1]
        self.assertIn("Qwen", response)
        self.assertNotIn("Traceback", response)

    def test_shutdown_stops_services_without_exiting_process(self):
        engine = self.make_engine()
        engine.shutdown()
        self.assertFalse(engine.running)
        self.assertTrue(self.tts.stopped)


if __name__ == "__main__":
    unittest.main()
