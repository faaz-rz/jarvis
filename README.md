# JARVIS

JARVIS is a modular local personal assistant written in Python. It combines typed
and spoken interaction, deterministic desktop skills, persistent memory, and the
local `qwen3.5:4b` model served by Ollama.

The assistant remains usable in text mode when audio, OCR, web research, or the
local model is unavailable. Optional capabilities report their own setup problem
instead of preventing the application from starting.

## Features

- Tkinter chat interface with an automatic console fallback
- Text-to-speech through `pyttsx3`
- Wake-word voice commands with one-step and two-step interaction
- Offline speech recognition through the bundled Vosk English model
- Optional Google speech-recognition fallback
- Local Qwen inference through Ollama, with optional direct-GGUF support
- JSON memory with atomic, thread-safe persistence
- Dynamically discovered skills with deterministic priorities
- Application launch, system status, screenshots, search, research, and OCR
- Custom learned commands
- Confirmations and safety limits for power and automation actions

## Architecture

```text
Microphone ──> VAD ──> Vosk/Google ─┐
                                    ├─> JarvisEngine
Text UI ─────────────────────────────┘        │
                                             ├─> learned command lookup
                                             ├─> prioritized skills
                                             ├─> memory heuristics
                                             └─> local LLM fallback
                                                      │
                                      UI <── response ─┴─> TTS
                                                      │
                                                 JSON memory
```

The important modules are:

- `jarvis.py`: command-line entry point and Windows CUDA path setup
- `core/engine.py`: request routing and application lifecycle
- `core/llm.py`: Qwen/Ollama and optional llama.cpp inference
- `core/memory.py`: preferences, learned commands, and conversation history
- `core/skills.py`: skill interface, discovery, ordering, and isolation
- `core/voice.py`: audio capture, VAD, transcription, and wake-word state
- `core/tts.py`: queued text-to-speech worker
- `core/ui.py`: console and Tkinter interfaces
- `skills/`: independently loadable assistant capabilities

## Requirements

Python 3.11 or 3.12 is recommended. Python 3.9+ supports text mode, but binary
audio and model packages may not publish wheels for every Python version.

External programs used by optional features:

- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for screen reading
- [Ollama](https://ollama.com/) with `qwen3.5:4b` for language responses

This machine already has `qwen3.5:4b`, `qwen3:8b`, and `qwen3:14b` installed.

## Installation

### Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Make sure Ollama is running, then start JARVIS with `python jarvis.py`.

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python jarvis.py
```

Some systems require PortAudio before `sounddevice` can be installed. Tkinter may
also be a separate operating-system package on Linux.

## Running without optional features

The built-in skills and console interface do not require a language model:

```bash
python jarvis.py --console --no-voice
```

Useful options:

```text
--console          use the terminal instead of Tkinter
--no-voice         disable microphone input
--backend NAME     auto, ollama, or llama_cpp
--ollama-model ID  select an installed Ollama model
--model PATH       use a direct GGUF model with llama.cpp
--memory PATH      use this JSON memory file
--log-level LEVEL  DEBUG, INFO, WARNING, or ERROR
```

Run `python jarvis.py --help` for the authoritative list.

## Configuration

`config.example.env` documents all supported environment variables. The most
important ones are:

| Variable | Purpose |
|---|---|
| `JARVIS_LLM_BACKEND` | `ollama` by default; optional `llama_cpp` |
| `OLLAMA_MODEL` | Ollama model; defaults to `qwen3.5:4b` |
| `OLLAMA_HOST` | Ollama API address |
| `MISTRAL_MODEL_PATH` | Optional direct-GGUF model |
| `CODE_MODEL_PATH` | Optional GGUF coding model |
| `JARVIS_MEMORY_PATH` | Memory JSON location |
| `JARVIS_SPEECH_BACKEND` | `auto`, `vosk`, `offline`, or `google` |
| `VOSK_MODEL_PATH` | Offline speech model; defaults to `Vm` |
| `JARVIS_AUTOMATION_ROOT` | Directory automation is allowed to modify |
| `TESSERACT_PATH` | Tesseract executable when it is not on `PATH` |
| `LLM_N_GPU_LAYERS` | Model layers offloaded to the GPU |

Environment variables are read directly by the application. The example file is
documentation; it is not automatically loaded.

## Voice interaction

Both forms are supported:

```text
"Jarvis, open calculator"
```

or:

```text
User:   "Jarvis"
JARVIS: "Yes?"
User:   "Open calculator"
```

In `auto` mode, JARVIS prefers the bundled Vosk model when the `vosk` package is
installed. It otherwise uses Google through `SpeechRecognition`, which requires
an internet connection.

## Example commands

```text
open calculator
what is my battery level
take a screenshot
search for Python dataclasses
research retrieval augmented generation
read my screen
my name is Ada
what is my name
remember that my meeting is at four
Learn: when I say focus mode do open notepad
create folder demo
shutdown pc
```

File creation and power actions require confirmation. Automated files are
restricted to `JARVIS_AUTOMATION_ROOT`. PowerShell accepts only a small allowlist
and rejects command chaining and destructive verbs.

## Adding a skill

Create a module in `skills/` with a subclass of `BaseSkill`:

```python
from core.skills import BaseSkill


class WeatherSkill(BaseSkill):
    name = "Weather"
    description = "Reports local weather."
    priority = 50

    def handle(self, text: str) -> bool:
        if "weather" not in text.lower():
            return False
        self.context.speak("Weather integration is ready.")
        return True
```

Higher-priority skills run first. A skill returns `True` only when it has handled
the request. Import and runtime failures are logged without crashing other skills.

## Tests

The test suite covers memory persistence and concurrency, skill discovery and
ordering, confirmation behavior, wake-word routing, engine fallbacks, and clean
shutdown:

```bash
python -m unittest discover -v
```

## Privacy and security

- Qwen through Ollama and Vosk speech recognition run locally.
- Google speech recognition is online; select `offline` to forbid that fallback.
- Screen OCR and conversation history can contain sensitive data.
- `jarvis_memory.json` is plain JSON. Protect or relocate it on shared machines.
- Generated code is executed only after the explicit `run code` request, but it
  should still be reviewed before use.

The legacy `jarvis_learning.pkl` files are retained only for compatibility with
older experiments. They are not trained models and are not used by the current
application.

## Troubleshooting

Logs are written to `jarvis_system.log`.

- If Qwen does not respond, run `ollama list`, start Ollama, and verify
  `qwen3.5:4b` is installed.
- For direct GGUF inference, install `requirements-llama.txt`, set
  `JARVIS_LLM_BACKEND=llama_cpp`, and configure `MISTRAL_MODEL_PATH`.
- If CUDA DLL loading fails on Windows, use `repair_jarvis.bat` to reinstall the
  CPU version of `llama-cpp-python`.
- If voice is unavailable, run `python debug_voice.py` and check microphone
  permission and PortAudio installation.
- If OCR fails, install Tesseract and set `TESSERACT_PATH`.
