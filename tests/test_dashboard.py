import json
import time
import unittest
from urllib import error as urllib_error
from urllib import request as urllib_request

from core.dashboard import DashboardUI


class DashboardUITests(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.dashboard = DashboardUI(
            callback_handler=self.commands.append,
            port=0,
            open_browser=False,
        )
        self.dashboard.configure_system(
            model="qwen-test:4b",
            backend="ollama",
            skills=["Vision", "Automation"],
            tools=["analyze_screen", "create_file"],
            voice_enabled=False,
            memory_enabled=True,
        )
        self.dashboard.display_message("System online.", "SYSTEM")
        self.dashboard.start_background()

    def tearDown(self):
        self.dashboard.stop()

    def test_dashboard_serves_state_and_assets_with_security_headers(self):
        with urllib_request.urlopen(
            f"{self.dashboard.url}/api/state",
            timeout=3,
        ) as response:
            state = json.loads(response.read().decode("utf-8"))
            self.assertEqual(state["model"], "qwen-test:4b")
            self.assertEqual(state["tools"], ["analyze_screen", "create_file"])
            self.assertEqual(state["messages"][0]["text"], "System online.")
            self.assertTrue(state["session_token"])
            self.assertEqual(
                response.headers["X-Frame-Options"],
                "DENY",
            )

        with urllib_request.urlopen(self.dashboard.url, timeout=3) as response:
            html = response.read().decode("utf-8")
            self.assertIn("One brain. Many abilities.", html)
            self.assertIn("Content-Security-Policy", response.headers)

    def test_message_api_requires_token_and_dispatches_asynchronously(self):
        payload = json.dumps({"text": "hello jarvis"}).encode("utf-8")
        request = urllib_request.Request(
            f"{self.dashboard.url}/api/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib_error.HTTPError) as denied:
            urllib_request.urlopen(request, timeout=3)
        self.assertEqual(denied.exception.code, 403)

        request.add_header("X-Jarvis-Token", self.dashboard.session_token)
        with urllib_request.urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode("utf-8"))
            self.assertTrue(result["accepted"])

        deadline = time.monotonic() + 2
        while not self.commands and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.commands, ["hello jarvis"])

    def test_action_api_maps_controls_and_rejects_foreign_origins(self):
        payload = json.dumps({"action": "allow"}).encode("utf-8")
        foreign_request = urllib_request.Request(
            f"{self.dashboard.url}/api/action",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Jarvis-Token": self.dashboard.session_token,
                "Origin": "https://malicious.example",
            },
            method="POST",
        )
        with self.assertRaises(urllib_error.HTTPError) as denied:
            urllib_request.urlopen(foreign_request, timeout=3)
        self.assertEqual(denied.exception.code, 403)

        local_request = urllib_request.Request(
            f"{self.dashboard.url}/api/action",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Jarvis-Token": self.dashboard.session_token,
                "Origin": self.dashboard.url,
            },
            method="POST",
        )
        with urllib_request.urlopen(local_request, timeout=3) as response:
            self.assertEqual(response.status, 202)

        deadline = time.monotonic() + 2
        while not self.commands and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.commands, ["yes"])

    def test_mission_api_and_controls_dispatch_safe_commands(self):
        mission_request = urllib_request.Request(
            f"{self.dashboard.url}/api/mission",
            data=json.dumps({"goal": "Produce a verified report"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Jarvis-Token": self.dashboard.session_token,
                "Origin": self.dashboard.url,
            },
            method="POST",
        )
        with urllib_request.urlopen(mission_request, timeout=3) as response:
            self.assertEqual(response.status, 202)

        pause_request = urllib_request.Request(
            f"{self.dashboard.url}/api/action",
            data=json.dumps({"action": "mission_pause"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Jarvis-Token": self.dashboard.session_token,
            },
            method="POST",
        )
        with urllib_request.urlopen(pause_request, timeout=3) as response:
            self.assertEqual(response.status, 202)

        deadline = time.monotonic() + 2
        while len(self.commands) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(
            self.commands,
            ["Super Mission: Produce a verified report", "pause mission"],
        )

    def test_mission_state_is_retained_for_new_dashboard_connections(self):
        mission = {
            "id": "mission-1",
            "title": "Test mission",
            "status": "paused",
            "steps": [],
        }
        self.dashboard.emit_event("mission_updated", {"mission": mission})
        self.assertEqual(
            self.dashboard.state_snapshot()["mission"]["id"],
            "mission-1",
        )

    def test_ui_methods_publish_stream_and_brain_events(self):
        self.dashboard.set_status("Thinking...")
        self.dashboard.begin_stream()
        self.dashboard.append_stream("Hello")
        self.dashboard.end_stream()
        snapshot = self.dashboard.state_snapshot()
        event_types = [event["type"] for event in snapshot["events"]]
        self.assertIn("brain_state", event_types)
        self.assertIn("stream_chunk", event_types)
        self.assertEqual(snapshot["messages"][-1]["text"], "Hello")


if __name__ == "__main__":
    unittest.main()
