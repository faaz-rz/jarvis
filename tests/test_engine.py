import tempfile
import unittest
import json
from pathlib import Path

from core.engine import JarvisEngine
from core.llm import LLMUnavailableError
from core.memory import Memory


class FakeUI:
    def __init__(self):
        self.messages = []
        self.statuses = []
        self.events = []

    def display_message(self, text, sender="JARVIS"):
        self.messages.append((sender, text))

    def set_status(self, text):
        self.statuses.append(text)

    def emit_event(self, event_type, data=None):
        self.events.append((event_type, data or {}))

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
    backend = "ollama"
    model_name = "qwen-test:4b"
    ollama_model = "qwen-test:4b"

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
            enable_long_term_memory=False,
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

    def test_qwen_tool_write_waits_for_central_permission(self):
        class ToolCallingLLM(FakeLLM):
            def chat(
                self,
                messages,
                tools=None,
                stream_callback=None,
                cancel_event=None,
            ):
                if any(message.get("role") == "tool" for message in messages):
                    return {
                        "message": {
                            "role": "assistant",
                            "content": "The requested file was created.",
                        },
                        "cancelled": False,
                    }
                return {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "create_file",
                                    "arguments": {"path": "agent-proof.txt"},
                                }
                            }
                        ],
                    },
                    "cancelled": False,
                }

        engine = self.make_engine(ToolCallingLLM())
        engine.skill_manager.load_skills()
        automation = next(
            skill
            for skill in engine.skill_manager.skills
            if skill.name == "Automation"
        )
        automation.automation_root = Path(self.temp_dir.name).resolve()
        engine.skill_manager.tool_registry.audit_path = (
            Path(self.temp_dir.name) / "audit.jsonl"
        )
        target = automation.automation_root / "agent-proof.txt"

        engine.handle_input(
            "Please prepare an empty artifact called agent-proof.txt."
        )
        engine._llm_queue.join()
        self.assertFalse(target.exists())
        self.assertIsNotNone(engine._pending_tool_request)
        self.assertIn("Permission required", self.ui.messages[-1][1])
        self.assertIn(
            "permission_required",
            [event_type for event_type, _ in self.ui.events],
        )

        engine.handle_input("yes")
        engine._llm_queue.join()
        self.assertTrue(target.exists())
        self.assertIsNone(engine._pending_tool_request)
        self.assertIn(
            ("JARVIS", "The requested file was created."),
            self.ui.messages,
        )
        event_types = [event_type for event_type, _ in self.ui.events]
        self.assertIn("tool_started", event_types)
        self.assertIn("tool_finished", event_types)
        self.assertIn("task_completed", event_types)
        engine.shutdown()

    def test_agent_turn_limit_survives_permission_pauses(self):
        class RepeatingToolLLM(FakeLLM):
            def __init__(self):
                super().__init__()
                self.chat_calls = 0

            def chat(
                self,
                messages,
                tools=None,
                stream_callback=None,
                cancel_event=None,
            ):
                self.chat_calls += 1
                return {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "create_file",
                                    "arguments": {
                                        "path": f"loop-{self.chat_calls}.txt"
                                    },
                                }
                            }
                        ],
                    },
                    "cancelled": False,
                }

        llm = RepeatingToolLLM()
        engine = self.make_engine(llm)
        engine.skill_manager.load_skills()
        automation = next(
            skill
            for skill in engine.skill_manager.skills
            if skill.name == "Automation"
        )
        automation.automation_root = Path(self.temp_dir.name).resolve()
        engine.skill_manager.tool_registry.audit_path = (
            Path(self.temp_dir.name) / "loop-audit.jsonl"
        )

        engine.handle_input("Keep preparing numbered empty artifacts.")
        engine._llm_queue.join()
        for _ in range(10):
            if not engine._pending_tool_request:
                break
            engine.handle_input("yes")
            engine._llm_queue.join()

        self.assertEqual(llm.chat_calls, 5)
        self.assertIsNone(engine._pending_tool_request)
        self.assertIn(
            ("JARVIS", "I stopped because the tool-call limit was reached."),
            self.ui.messages,
        )
        engine.shutdown()

    def test_qwen_is_instructed_as_one_unified_brain(self):
        class CapturingLLM(FakeLLM):
            def __init__(self):
                super().__init__()
                self.messages = None

            def chat(
                self,
                messages,
                tools=None,
                stream_callback=None,
                cancel_event=None,
            ):
                self.messages = messages
                return {
                    "message": {
                        "role": "assistant",
                        "content": "Unified response.",
                    },
                    "cancelled": False,
                }

        llm = CapturingLLM()
        engine = self.make_engine(llm)
        engine.skill_manager.load_skills()
        engine.handle_input("Explain distributed consensus tradeoffs.")
        engine._llm_queue.join()

        system_prompt = llm.messages[0]["content"]
        self.assertIn("one unified intelligence", system_prompt)
        self.assertIn("not separate agents or departments", system_prompt)
        self.assertIn("never reveal private chain-of-thought", system_prompt)
        engine.shutdown()

    def test_super_mission_plans_executes_and_persists_verified_steps(self):
        class MissionLLM(FakeLLM):
            def __init__(self):
                super().__init__()
                self.chat_calls = 0

            def chat(
                self,
                messages,
                tools=None,
                stream_callback=None,
                cancel_event=None,
                max_tokens=None,
                format_schema=None,
            ):
                self.chat_calls += 1
                if format_schema is not None:
                    return {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "title": "Two-part result",
                                    "summary": "Complete two verifiable text steps.",
                                    "steps": [
                                        {
                                            "title": "Draft",
                                            "instruction": "Draft part one.",
                                            "success_criteria": "Part one is returned.",
                                            "requires_tool": False,
                                        },
                                        {
                                            "title": "Review",
                                            "instruction": "Review part one.",
                                            "success_criteria": "A review is returned.",
                                            "requires_tool": False,
                                        },
                                    ],
                                }
                            ),
                        },
                        "cancelled": False,
                    }
                return {
                    "message": {
                        "role": "assistant",
                        "content": f"Verified text result {self.chat_calls}.",
                    },
                    "cancelled": False,
                }

        llm = MissionLLM()
        engine = self.make_engine(llm)
        engine.skill_manager.load_skills()

        engine.handle_input("Super Mission: produce two reviewed parts")
        engine._llm_queue.join()

        mission = engine.missions.latest()
        self.assertEqual(mission["status"], "completed")
        self.assertTrue(
            all(step["status"] == "completed" for step in mission["steps"])
        )
        self.assertEqual(llm.chat_calls, 3)
        event_types = [event_type for event_type, _ in self.ui.events]
        self.assertIn("mission_created", event_types)
        self.assertIn("mission_step_completed", event_types)
        self.assertIn("mission_completed", event_types)
        engine.shutdown()

    def test_super_mission_pauses_when_required_tool_has_no_evidence(self):
        class MissionLLM(FakeLLM):
            def chat(
                self,
                messages,
                tools=None,
                stream_callback=None,
                cancel_event=None,
                max_tokens=None,
                format_schema=None,
            ):
                if format_schema is not None:
                    return {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "title": "Tool-backed task",
                                    "summary": "Perform a real action.",
                                    "steps": [
                                        {
                                            "title": "Act",
                                            "instruction": "Perform the action.",
                                            "success_criteria": "A tool confirms success.",
                                            "requires_tool": True,
                                        }
                                    ],
                                }
                            ),
                        },
                        "cancelled": False,
                    }
                return {
                    "message": {
                        "role": "assistant",
                        "content": "I completed it without a tool.",
                    },
                    "cancelled": False,
                }

        engine = self.make_engine(MissionLLM())
        engine.skill_manager.load_skills()
        engine.handle_input("Super Mission: perform a tool-backed task")
        engine._llm_queue.join()

        mission = engine.missions.latest()
        self.assertEqual(mission["status"], "paused")
        self.assertEqual(mission["steps"][0]["status"], "pending")
        self.assertIn(
            "no tool completed successfully",
            mission["steps"][0]["result"],
        )
        engine.shutdown()

    def test_super_mission_waits_for_permission_then_records_tool_evidence(self):
        class MissionToolLLM(FakeLLM):
            def chat(
                self,
                messages,
                tools=None,
                stream_callback=None,
                cancel_event=None,
                max_tokens=None,
                format_schema=None,
            ):
                if format_schema is not None:
                    return {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "title": "Create artifact",
                                    "summary": "Create and verify one file.",
                                    "steps": [
                                        {
                                            "title": "Create file",
                                            "instruction": "Create mission-proof.txt.",
                                            "success_criteria": "The file tool succeeds.",
                                            "requires_tool": True,
                                        }
                                    ],
                                }
                            ),
                        },
                        "cancelled": False,
                    }
                if any(message.get("role") == "tool" for message in messages):
                    return {
                        "message": {
                            "role": "assistant",
                            "content": "The artifact was created and verified.",
                        },
                        "cancelled": False,
                    }
                return {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "create_file",
                                    "arguments": {"path": "mission-proof.txt"},
                                }
                            }
                        ],
                    },
                    "cancelled": False,
                }

        engine = self.make_engine(MissionToolLLM())
        engine.skill_manager.load_skills()
        automation = next(
            skill
            for skill in engine.skill_manager.skills
            if skill.name == "Automation"
        )
        automation.automation_root = Path(self.temp_dir.name).resolve()
        engine.skill_manager.tool_registry.audit_path = (
            Path(self.temp_dir.name) / "mission-audit.jsonl"
        )
        target = automation.automation_root / "mission-proof.txt"

        engine.handle_input("Super Mission: create a verified proof artifact")
        engine._llm_queue.join()
        self.assertFalse(target.exists())
        self.assertEqual(engine.missions.latest()["status"], "waiting_permission")

        engine.handle_input("yes")
        engine._llm_queue.join()

        mission = engine.missions.latest()
        self.assertTrue(target.exists())
        self.assertEqual(mission["status"], "completed")
        self.assertIn(
            "Verified tool results: create_file",
            mission["steps"][0]["result"],
        )
        engine.shutdown()


if __name__ == "__main__":
    unittest.main()
