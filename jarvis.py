"""J.A.R.V.I.S. application entry point."""
from __future__ import annotations

import argparse
import logging
import os
import site
import sys
from pathlib import Path

from core.config import PROJECT_ROOT


def configure_logging(level: str = "INFO"):
    log_path = Path(os.environ.get("JARVIS_LOG_PATH", PROJECT_ROOT / "jarvis_system.log"))
    logging.basicConfig(
        filename=str(log_path),
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def configure_windows_cuda_paths():
    """Expose NVIDIA runtime DLLs installed by Python packages on Windows."""
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    for site_dir in site.getsitepackages():
        for relative in (
            Path("nvidia") / "cuda_runtime" / "bin",
            Path("nvidia") / "cublas" / "bin",
        ):
            candidate = Path(site_dir) / relative
            if candidate.exists():
                os.add_dll_directory(str(candidate))
                os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")
                logging.info("Added CUDA DLL directory: %s", candidate)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the JARVIS personal assistant.")
    interface = parser.add_mutually_exclusive_group()
    interface.add_argument(
        "--console",
        action="store_true",
        help="Use the terminal interface instead of the brain dashboard.",
    )
    interface.add_argument(
        "--tk",
        action="store_true",
        help="Use the legacy Tkinter interface instead of the brain dashboard.",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable microphone input while keeping typed input and TTS.",
    )
    parser.add_argument(
        "--no-long-term-memory",
        action="store_true",
        help="Disable SQLite conversational and semantic memory for this run.",
    )
    parser.add_argument("--model", help="Path to a local GGUF model for llama.cpp.")
    parser.add_argument(
        "--backend",
        choices=("auto", "ollama", "llama_cpp"),
        help="Language-model backend. Auto prefers an existing GGUF, otherwise Ollama.",
    )
    parser.add_argument(
        "--ollama-model",
        help="Ollama model name, for example qwen3.5:4b.",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=None,
        help="Preferred local brain-dashboard port; defaults to 8765.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the dashboard without opening a browser automatically.",
    )
    parser.add_argument("--memory", help="Path to the JSON memory file.")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("JARVIS_LOG_LEVEL", "INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    configure_logging(args.log_level)
    configure_windows_cuda_paths()

    from core.engine import JarvisEngine
    from core.llm import LLMEngine
    from core.memory import Memory

    engine = None
    try:
        engine = JarvisEngine(
            memory=Memory(args.memory) if args.memory else None,
            llm=LLMEngine(
                args.model,
                backend=args.backend,
                ollama_model=args.ollama_model,
            ),
            enable_voice=not args.no_voice,
            prefer_gui=not args.console,
            enable_long_term_memory=not args.no_long_term_memory,
            prefer_dashboard=not args.tk,
            dashboard_port=args.dashboard_port,
            open_dashboard=not args.no_browser,
        )
        engine.start()
        return 0
    except KeyboardInterrupt:
        if engine:
            engine.shutdown()
        return 0
    except Exception as exc:
        logging.exception("Critical startup error: %s", exc)
        print(f"JARVIS could not start: {exc}", file=sys.stderr)
        print("See jarvis_system.log for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
