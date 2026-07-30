import json
import tempfile
import unittest
from pathlib import Path

from core.tools import RiskLevel, ToolCall, ToolRegistry, ToolSpec


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.temp_dir.name) / "audit.jsonl"
        self.calls = []
        self.registry = ToolRegistry(audit_path=self.audit_path)
        self.registry.register(
            ToolSpec(
                name="write_note",
                description="Write a test note.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "maxLength": 20},
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
                handler=lambda text: self.calls.append(text) or f"Wrote {text}",
                risk=RiskLevel.WRITE,
                confirmation="Write the note '{text}'?",
            )
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_risky_tool_requires_confirmation_and_is_audited(self):
        call = ToolCall("write_note", {"text": "hello"})
        denied = self.registry.execute(call)
        self.assertFalse(denied.success)
        self.assertEqual(self.calls, [])

        result = self.registry.execute(call, confirmed=True)
        self.assertTrue(result.success)
        self.assertEqual(self.calls, ["hello"])
        records = [
            json.loads(line)
            for line in self.audit_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(records), 2)
        self.assertFalse(records[0]["success"])
        self.assertEqual(records[1]["tool"], "write_note")
        self.assertEqual(records[1]["risk"], "write")
        self.assertTrue(records[1]["success"])

    def test_schema_validation_rejects_bad_arguments(self):
        call = ToolCall("write_note", {"text": "hello", "unexpected": True})
        result = self.registry.execute(call, confirmed=True)
        self.assertFalse(result.success)
        self.assertIn("Unknown arguments", result.content)
        self.assertEqual(self.calls, [])

    def test_ollama_schema_and_confirmation_are_stable(self):
        schema = self.registry.schemas()[0]
        self.assertEqual(schema["function"]["name"], "write_note")
        self.assertEqual(
            self.registry.confirmation_text(
                ToolCall("write_note", {"text": "hello"})
            ),
            "Write the note 'hello'?",
        )
        self.assertEqual(
            self.registry.confirmation_text(ToolCall("write_note", None)),
            "Write the note '{text}'?",
        )


if __name__ == "__main__":
    unittest.main()
