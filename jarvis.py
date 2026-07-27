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
    parser.add_argument(
        "--console",
        action="store_true",
        help="Use the terminal interface instead of Tkinter.",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable microphone input while keeping typed input and TTS.",
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
