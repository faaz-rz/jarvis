import os
import platform
import re
import subprocess
from pathlib import Path

from core.config import PROJECT_ROOT
from core.skills import BaseSkill


class AutomationSkill(BaseSkill):
    name = "Automation"
    description = "Creates files or folders and runs approved read-only PowerShell commands."
    priority = 10

    BLOCKED_POWERSHELL = re.compile(
        r"(?i)(remove-item|clear-disk|format-volume|stop-computer|restart-computer|"
        r"invoke-expression|\biex\b|encodedcommand|downloadstring|set-executionpolicy|"
        r"\bdel\b|\berase\b|\brmdir\b|shutdown)"
    )
    SHELL_METACHARACTERS = re.compile(r"""[;&|><`$(){}\[\]]""")
    ALLOWED_POWERSHELL = (
        re.compile(
            r"(?i)get-(?:process|service|date|computerinfo)"
            r"(?:\s+[a-z0-9_.*?\\:/-]+)?"
        ),
        re.compile(r"""(?i)write-output\s+["'][^"']{0,200}["']"""),
    )

    def __init__(self, context):
        super().__init__(context)
        root = os.environ.get("JARVIS_AUTOMATION_ROOT")
        self.automation_root = Path(root).expanduser().resolve() if root else PROJECT_ROOT
        self.pending_action = None

    def handle(self, text: str) -> bool:
        stripped = text.strip()
        lower = stripped.lower()

        if self.pending_action:
            if lower in {"yes", "confirm", "proceed", "do it", "sure"}:
                self.execute_pending()
                return True
            if lower in {"no", "cancel", "stop", "don't"}:
                self.context.speak("Command cancelled.")
                self.pending_action = None
                return True
            self.context.speak("Please say yes to execute or no to cancel.")
            return True

        folder_match = re.fullmatch(
            r"(?:create|make)\s+(?:a\s+)?folder\s+(.+)", stripped, re.IGNORECASE
        )
        if folder_match:
            return self._propose_path_action("folder", folder_match.group(1))

        file_match = re.fullmatch(
            r"create\s+(?:a\s+)?file\s+(.+)", stripped, re.IGNORECASE
        )
        if file_match:
            return self._propose_path_action("file", file_match.group(1))

        for prefix in ("run powershell ", "run command "):
            if lower.startswith(prefix):
                command = stripped[len(prefix):].strip()
                self._propose_powershell(command)
                return True

        return False

    def _safe_target(self, value: str):
        cleaned = value.strip().strip("\"'")
        candidate = (self.automation_root / cleaned).resolve()
        try:
            candidate.relative_to(self.automation_root)
        except ValueError:
            return None
        return candidate

    def _propose_path_action(self, kind: str, value: str):
        target = self._safe_target(value)
        if target is None:
            self.context.speak(
                f"For safety, automated files must stay inside {self.automation_root}."
            )
            return True
        self.pending_action = {"kind": kind, "target": target}
        self.context.speak(
            f"Create {kind} at {target}? Say yes to confirm or no to cancel."
        )
        return True

    def _propose_powershell(self, command: str):
        if platform.system() != "Windows":
            self.context.speak("PowerShell automation is available only on Windows.")
            return
        if (
            self.BLOCKED_POWERSHELL.search(command)
            or self.SHELL_METACHARACTERS.search(command)
            or not any(
                pattern.fullmatch(command.strip())
                for pattern in self.ALLOWED_POWERSHELL
            )
        ):
            self.context.speak(
                "That command is outside the safe PowerShell allowlist and was rejected."
            )
            return
        self.pending_action = {"kind": "powershell", "command": command}
        self.context.speak(
            f"I am ready to execute: {command}. Say yes to confirm or no to cancel."
        )

    def execute_pending(self):
        action, self.pending_action = self.pending_action, None
        if not action:
            return

        try:
            if action["kind"] == "folder":
                action["target"].mkdir(parents=True, exist_ok=False)
                self.context.speak("Folder created.")
                return
            if action["kind"] == "file":
                action["target"].parent.mkdir(parents=True, exist_ok=True)
                action["target"].touch(exist_ok=False)
                self.context.speak("File created.")
                return

            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    action["command"],
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                output = result.stdout.strip() or "Done."
                self.context.speak(f"Success. {output[:300]}")
            else:
                self.context.speak(f"Command failed: {result.stderr[:300]}")
        except FileExistsError:
            self.context.speak("That file or folder already exists; nothing was overwritten.")
        except (OSError, subprocess.SubprocessError) as exc:
            self.context.speak(f"Automation failed: {exc}")
