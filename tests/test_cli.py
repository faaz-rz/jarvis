import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CLITests(unittest.TestCase):
    def test_help_command(self):
        result = subprocess.run(
            [sys.executable, "jarvis.py", "--help"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--no-voice", result.stdout)
        self.assertIn("--no-long-term-memory", result.stdout)
        self.assertIn("--ollama-model", result.stdout)
        self.assertIn("--dashboard-port", result.stdout)
        self.assertIn("--tk", result.stdout)

    def test_console_mode_starts_handles_input_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            memory_path = Path(temporary) / "memory.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "jarvis.py",
                    "--console",
                    "--no-voice",
                    "--memory",
                    str(memory_path),
                ],
                cwd=str(PROJECT_ROOT),
                input="hi\nexit\n",
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("System online. 9 skills loaded.", result.stdout)
        self.assertIn("[JARVIS]:", result.stdout)


if __name__ == "__main__":
    unittest.main()
