import tempfile
import unittest
from pathlib import Path

from core.missions import MissionStore


def sample_plan(requires_tool=False):
    return {
        "title": "Reliable result",
        "summary": "Produce and verify one useful outcome.",
        "steps": [
            {
                "title": "Complete work",
                "instruction": "Produce the requested result.",
                "success_criteria": "A concrete result is available.",
                "requires_tool": requires_tool,
            }
        ],
    }


class MissionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "missions.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mission_round_trip_tracks_tool_requirement_and_result(self):
        store = MissionStore(path=self.path)
        mission = store.create("Complete a safe task", sample_plan(True))

        self.assertEqual(mission["status"], "running")
        self.assertTrue(mission["steps"][0]["requires_tool"])
        updated = store.set_step_status(
            mission["id"],
            0,
            "completed",
            "Verified output",
        )
        self.assertEqual(updated["steps"][0]["result"], "Verified output")
        self.assertEqual(store.latest()["id"], mission["id"])

    def test_interrupted_mission_recovers_as_paused_with_pending_step(self):
        store = MissionStore(path=self.path)
        mission = store.create("Recover safely", sample_plan())
        store.set_step_status(mission["id"], 0, "running")

        recovered = MissionStore(path=self.path).active()

        self.assertEqual(recovered["status"], "paused")
        self.assertEqual(recovered["steps"][0]["status"], "pending")

    def test_interrupted_planning_is_saved_and_recovers_paused(self):
        store = MissionStore(path=self.path)
        mission = store.create_planning("Plan after restart")

        recovered = MissionStore(path=self.path).active()

        self.assertEqual(recovered["id"], mission["id"])
        self.assertEqual(recovered["status"], "paused")
        self.assertEqual(recovered["goal"], "Plan after restart")
        self.assertEqual(recovered["steps"], [])

    def test_plan_validation_rejects_missing_verification_fields(self):
        with self.assertRaises(ValueError):
            MissionStore.validate_plan(
                {
                    "title": "Incomplete",
                    "summary": "Missing fields.",
                    "steps": [{"title": "Only a title"}],
                }
            )


if __name__ == "__main__":
    unittest.main()
