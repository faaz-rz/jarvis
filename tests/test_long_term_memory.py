import tempfile
import unittest
from pathlib import Path

from core.long_term_memory import LongTermMemory


class FakeEmbeddingLLM:
    @staticmethod
    def _vector(text):
        lower = text.lower()
        return [1.0, 0.0] if any(
            word in lower for word in ("star", "space", "telescope", "astronomy")
        ) else [0.0, 1.0]

    def embed(self, texts):
        if isinstance(texts, str):
            return self._vector(texts)
        return [self._vector(text) for text in texts]


class LongTermMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory = LongTermMemory(
            FakeEmbeddingLLM(),
            Path(self.temp_dir.name) / "memory.db",
        )

    def tearDown(self):
        self.memory.close()
        self.temp_dir.cleanup()

    def test_semantic_search_and_clear(self):
        self.memory.add("user", "Astronomy uses powerful telescopes.")
        self.memory.add("user", "My preferred pasta sauce contains basil.")
        self.memory.wait_for_embeddings()

        results = self.memory.search("Tell me something about distant stars")
        self.assertTrue(results)
        self.assertIn("Astronomy", results[0]["content"])

        self.assertIn("cleared", self.memory.clear().lower())
        self.assertEqual(self.memory.recent(), [])

    def test_json_history_is_imported_only_once(self):
        history = [
            {"role": "user", "content": "I enjoy space documentaries."},
            {"role": "assistant", "content": "I will remember that."},
        ]
        self.memory.import_history_once(history)
        self.memory.import_history_once(history)
        self.assertEqual(len(self.memory.recent()), 2)


if __name__ == "__main__":
    unittest.main()
