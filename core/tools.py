"""Typed tool registry, argument validation, permissions, and audit logging."""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from core.config import PROJECT_ROOT


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    ACTION = "action"
    SENSITIVE = "sensitive"
    WRITE = "write"
    EXECUTE = "execute"
    DESTRUCTIVE = "destructive"


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    risk: RiskLevel = RiskLevel.READ_ONLY
    confirmation: Optional[str] = None

    def ollama_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def confirmation_text(self, arguments: Dict[str, Any]) -> str:
        if self.confirmation:
            try:
                safe_arguments = arguments if isinstance(arguments, dict) else {}
                return self.confirmation.format(**safe_arguments)
            except (KeyError, TypeError, ValueError):
                return self.confirmation
        return f"Allow the {self.name} action with {arguments}?"


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    name: str
    success: bool
    content: str


class PermissionPolicy:
    CONFIRMATION_RISKS = {
        RiskLevel.SENSITIVE,
        RiskLevel.WRITE,
        RiskLevel.EXECUTE,
        RiskLevel.DESTRUCTIVE,
    }

    def requires_confirmation(self, tool: ToolSpec) -> bool:
        return tool.risk in self.CONFIRMATION_RISKS


class ToolRegistry:
    def __init__(self, audit_path=None, permission_policy=None):
        self._tools: Dict[str, ToolSpec] = {}
        self.permission_policy = permission_policy or PermissionPolicy()
        configured_audit = os.environ.get("JARVIS_AUDIT_PATH")
        self.audit_path = Path(
            audit_path or configured_audit or PROJECT_ROOT / "jarvis_audit.jsonl"
        )
        self._audit_lock = threading.Lock()

    def register(self, tool: ToolSpec):
        if not tool.name or not tool.name.replace("_", "").isalnum():
            raise ValueError(f"Invalid tool name: {tool.name!r}")
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def register_many(self, tools: Iterable[ToolSpec]):
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def schemas(self) -> List[Dict[str, Any]]:
        return [self._tools[name].ollama_schema() for name in sorted(self._tools)]

    def names(self) -> List[str]:
        return sorted(self._tools)

    def needs_confirmation(self, call: ToolCall) -> bool:
        tool = self.get(call.name)
        return bool(tool and self.permission_policy.requires_confirmation(tool))

    def confirmation_text(self, call: ToolCall) -> str:
        tool = self.get(call.name)
        if not tool:
            return f"Unknown tool requested: {call.name}"
        return tool.confirmation_text(call.arguments)

    def execute(self, call: ToolCall, confirmed: bool = False) -> ToolResult:
        tool = self.get(call.name)
        if not tool:
            return ToolResult(call.name, False, f"Unknown tool: {call.name}")
        if self.permission_policy.requires_confirmation(tool) and not confirmed:
            result = ToolResult(
                call.name, False, "Permission confirmation is required."
            )
            self._audit(tool, call.arguments, result)
            return result

        try:
            arguments = self.validate_arguments(tool, call.arguments)
        except ValueError as exc:
            logging.warning("Rejected arguments for tool %s: %s", call.name, exc)
            result = ToolResult(call.name, False, f"ValueError: {exc}")
            self._audit(tool, call.arguments, result)
            return result

        try:
            output = tool.handler(**arguments)
            content = str(output) if output is not None else "Done."
            result = ToolResult(call.name, True, content)
        except Exception as exc:
            logging.exception("Tool %s failed: %s", call.name, exc)
            result = ToolResult(call.name, False, f"{type(exc).__name__}: {exc}")
        self._audit(tool, call.arguments, result)
        return result

    def audit_denial(self, call: ToolCall, reason="Permission denied by user."):
        """Record a user-denied model tool proposal without executing it."""
        tool = self.get(call.name)
        if not tool:
            return
        self._audit(tool, call.arguments, ToolResult(call.name, False, reason))

    def validate_arguments(
        self, tool: ToolSpec, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        schema = tool.parameters or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_allowed = schema.get("additionalProperties", False)

        missing = [name for name in required if name not in arguments]
        if missing:
            raise ValueError(f"Missing required arguments: {', '.join(missing)}")
        if not additional_allowed:
            unknown = set(arguments) - set(properties)
            if unknown:
                raise ValueError(f"Unknown arguments: {', '.join(sorted(unknown))}")

        validated = {}
        for name, value in arguments.items():
            rule = properties.get(name, {})
            expected = rule.get("type")
            type_map = {
                "string": str,
                "integer": int,
                "number": (int, float),
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            python_type = type_map.get(expected)
            if python_type and (
                not isinstance(value, python_type)
                or expected in {"integer", "number"} and isinstance(value, bool)
            ):
                raise ValueError(f"Argument '{name}' must be {expected}.")
            if isinstance(value, str):
                max_length = rule.get("maxLength", 1000)
                if len(value) > max_length:
                    raise ValueError(
                        f"Argument '{name}' exceeds {max_length} characters."
                    )
            if "enum" in rule and value not in rule["enum"]:
                raise ValueError(
                    f"Argument '{name}' must be one of {rule['enum']}."
                )
            validated[name] = value
        return validated

    def _audit(
        self, tool: ToolSpec, arguments: Dict[str, Any], result: ToolResult
    ):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool.name,
            "risk": tool.risk.value,
            "arguments": arguments,
            "success": result.success,
            "result": result.content[:500],
        }
        try:
            with self._audit_lock:
                self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self.audit_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False, default=str))
                    handle.write("\n")
        except OSError as exc:
            logging.warning("Could not write tool audit log: %s", exc)
