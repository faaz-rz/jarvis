"""Persistent mission plans for JARVIS Super Mode."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import default_missions_path


MISSION_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A concise mission title.",
        },
        "summary": {
            "type": "string",
            "description": "A one-sentence description of the approach.",
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "A short observable step name.",
                    },
                    "instruction": {
                        "type": "string",
                        "description": "The exact work JARVIS should perform.",
                    },
                    "success_criteria": {
                        "type": "string",
                        "description": "How the step result can be verified.",
                    },
                    "requires_tool": {
                        "type": "boolean",
                        "description": (
                            "True when completion requires a real tool result; "
                            "false for reasoning or writing-only output."
                        ),
                    },
                },
                "required": [
                    "title",
                    "instruction",
                    "success_criteria",
                    "requires_tool",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "steps"],
    "additionalProperties": False,
}


class MissionStore:
    ACTIVE_STATUSES = {
        "planning",
        "running",
        "waiting_permission",
        "paused",
    }

    def __init__(self, path=None, memory_path=None):
        self.path = Path(path or default_missions_path(memory_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()
        self._recover_interrupted()

    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mission_steps (
                    mission_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    success_criteria TEXT NOT NULL,
                    requires_tool INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    result TEXT,
                    PRIMARY KEY (mission_id, position),
                    FOREIGN KEY (mission_id) REFERENCES missions(id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_missions_updated "
                "ON missions(updated_at DESC)"
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(mission_steps)"
                ).fetchall()
            }
            if "requires_tool" not in columns:
                connection.execute(
                    """
                    ALTER TABLE mission_steps
                    ADD COLUMN requires_tool INTEGER NOT NULL DEFAULT 0
                    """
                )

    def _recover_interrupted(self):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE mission_steps
                SET status = 'pending'
                WHERE status IN ('running', 'waiting_permission')
                """
            )
            connection.execute(
                """
                UPDATE missions
                SET status = 'paused', updated_at = ?
                WHERE status IN ('planning', 'running', 'waiting_permission')
                """,
                (self._timestamp(),),
            )

    def create(self, goal, plan):
        mission = self.create_planning(goal)
        return self.apply_plan(mission["id"], plan)

    def create_planning(self, goal):
        goal = str(goal).strip()
        if not goal:
            raise ValueError("Mission goal cannot be empty.")
        mission_id = uuid.uuid4().hex
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO missions(
                    id, title, goal, summary, status, current_step,
                    created_at, updated_at
                ) VALUES (?, 'Planning mission', ?, ?, 'planning', NULL, ?, ?)
                """,
                (
                    mission_id,
                    goal,
                    "Qwen is creating a grounded, verifiable plan.",
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(mission_id)

    def apply_plan(self, mission_id, plan):
        normalized = self.validate_plan(plan)
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE missions
                SET title = ?, summary = ?, status = 'running',
                    current_step = 0, updated_at = ?
                WHERE id = ? AND status = 'planning'
                """,
                (
                    normalized["title"],
                    normalized["summary"],
                    timestamp,
                    mission_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Mission is no longer in planning state.")
            connection.execute(
                "DELETE FROM mission_steps WHERE mission_id = ?",
                (mission_id,),
            )
            connection.executemany(
                """
                INSERT INTO mission_steps(
                    mission_id, position, title, instruction,
                    success_criteria, requires_tool, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                [
                    (
                        mission_id,
                        position,
                        step["title"],
                        step["instruction"],
                        step["success_criteria"],
                        int(step["requires_tool"]),
                    )
                    for position, step in enumerate(normalized["steps"])
                ],
            )
        return self.get(mission_id)

    def get(self, mission_id):
        with self._connect() as connection:
            mission = connection.execute(
                "SELECT * FROM missions WHERE id = ?",
                (mission_id,),
            ).fetchone()
            if not mission:
                return None
            steps = connection.execute(
                """
                SELECT position, title, instruction, success_criteria,
                       requires_tool, status, result
                FROM mission_steps
                WHERE mission_id = ?
                ORDER BY position
                """,
                (mission_id,),
            ).fetchall()
        snapshot = dict(mission)
        snapshot["steps"] = [dict(step) for step in steps]
        for step in snapshot["steps"]:
            step["requires_tool"] = bool(step["requires_tool"])
        return snapshot

    def active(self):
        placeholders = ",".join("?" for _ in self.ACTIVE_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT id FROM missions
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC LIMIT 1
                """,
                tuple(self.ACTIVE_STATUSES),
            ).fetchone()
        return self.get(row["id"]) if row else None

    def latest(self):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM missions ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return self.get(row["id"]) if row else None

    def next_pending_step(self, mission_id):
        mission = self.get(mission_id)
        if not mission:
            return None
        return next(
            (
                step
                for step in mission["steps"]
                if step["status"] == "pending"
            ),
            None,
        )

    def set_status(self, mission_id, status, current_step=None):
        timestamp = self._timestamp()
        with self._lock, self._connect() as connection:
            if current_step is None:
                connection.execute(
                    "UPDATE missions SET status = ?, updated_at = ? WHERE id = ?",
                    (status, timestamp, mission_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE missions
                    SET status = ?, current_step = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, int(current_step), timestamp, mission_id),
                )
        return self.get(mission_id)

    def set_step_status(self, mission_id, position, status, result=None):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE mission_steps
                SET status = ?, result = COALESCE(?, result)
                WHERE mission_id = ? AND position = ?
                """,
                (status, result, mission_id, int(position)),
            )
            connection.execute(
                """
                UPDATE missions
                SET current_step = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(position), self._timestamp(), mission_id),
            )
        return self.get(mission_id)

    def pause(self, mission_id, reason=None):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE mission_steps
                SET status = 'pending', result = COALESCE(?, result)
                WHERE mission_id = ?
                  AND status IN ('running', 'waiting_permission')
                """,
                (reason, mission_id),
            )
            connection.execute(
                """
                UPDATE missions
                SET status = 'paused', updated_at = ?
                WHERE id = ?
                  AND status IN (
                      'planning', 'running', 'waiting_permission', 'paused'
                  )
                """,
                (self._timestamp(), mission_id),
            )
        return self.get(mission_id)

    def fail_planning(self, mission_id):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE missions
                SET status = 'failed', updated_at = ?
                WHERE id = ? AND status = 'planning'
                """,
                (self._timestamp(), mission_id),
            )
        return self.get(mission_id)

    def complete(self, mission_id):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE missions
                SET status = 'completed', updated_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (self._timestamp(), mission_id),
            )
        return self.get(mission_id)

    def cancel(self, mission_id):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE mission_steps SET status = 'cancelled'
                WHERE mission_id = ? AND status != 'completed'
                """,
                (mission_id,),
            )
            connection.execute(
                """
                UPDATE missions
                SET status = 'cancelled', updated_at = ?
                WHERE id = ?
                """,
                (self._timestamp(), mission_id),
            )
        return self.get(mission_id)

    @staticmethod
    def validate_plan(plan):
        if not isinstance(plan, dict):
            raise ValueError("Mission plan must be a JSON object.")
        title = str(plan.get("title", "")).strip()[:120]
        summary = str(plan.get("summary", "")).strip()[:500]
        raw_steps = plan.get("steps")
        if not title or not summary or not isinstance(raw_steps, list):
            raise ValueError("Mission plan is missing a title, summary, or steps.")
        if not 1 <= len(raw_steps) <= 6:
            raise ValueError("Mission plans require between one and six steps.")

        steps = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                raise ValueError("Each mission step must be an object.")
            step = {
                "title": str(raw_step.get("title", "")).strip()[:120],
                "instruction": str(raw_step.get("instruction", "")).strip()[:1000],
                "success_criteria": str(
                    raw_step.get("success_criteria", "")
                ).strip()[:500],
                "requires_tool": raw_step.get("requires_tool"),
            }
            if (
                not step["title"]
                or not step["instruction"]
                or not step["success_criteria"]
                or not isinstance(step["requires_tool"], bool)
            ):
                raise ValueError("Every mission step requires complete fields.")
            steps.append(step)
        return {"title": title, "summary": summary, "steps": steps}

    @staticmethod
    def parse_plan_response(content):
        if isinstance(content, dict):
            return MissionStore.validate_plan(content)
        try:
            parsed = json.loads(str(content))
        except (TypeError, ValueError) as exc:
            raise ValueError("Qwen returned an invalid mission plan.") from exc
        return MissionStore.validate_plan(parsed)

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()
