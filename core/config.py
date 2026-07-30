"""Central configuration helpers for JARVIS.

Configuration is intentionally environment-variable based so the application can
run from any working directory without editing source code.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def configured_path(name: str, default: Optional[Path] = None) -> Optional[Path]:
    value = os.environ.get(name)
    if value:
        return Path(value).expanduser().resolve()
    return default.resolve() if default else None


def default_memory_path() -> Path:
    return configured_path("JARVIS_MEMORY_PATH", PROJECT_ROOT / "jarvis_memory.json")


def default_database_path(memory_path=None) -> Path:
    configured = configured_path("JARVIS_DB_PATH")
    if configured:
        return configured
    if memory_path:
        return Path(memory_path).with_suffix(".db")
    return PROJECT_ROOT / "jarvis_memory.db"


def default_model_path() -> Optional[Path]:
    configured = configured_path("JARVIS_GGUF_MODEL_PATH")
    if configured:
        return configured

    # Backward-compatible alias used by the original project.
    configured = configured_path("MISTRAL_MODEL_PATH")
    if configured:
        return configured

    # Preserve compatibility with the original Windows setup without requiring it.
    legacy = Path(r"D:\models\capybara\capybarahermes-2.5-mistral-7b.Q5_0.gguf")
    return legacy if legacy.exists() else None


def coding_model_path() -> Optional[Path]:
    configured = configured_path("CODE_MODEL_PATH")
    if configured:
        return configured

    legacy = Path(r"D:\models\codellama\codellama-7b-instruct.Q5_K_M.gguf")
    return legacy if legacy.exists() else None


def default_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "qwen3.5:4b").strip()


def ollama_host() -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return host


def vosk_model_path() -> Optional[Path]:
    configured = configured_path("VOSK_MODEL_PATH")
    if configured:
        return configured
    bundled = PROJECT_ROOT / "Vm"
    return bundled if bundled.exists() else None
