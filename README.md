# JARVIS

JARVIS is a modular local personal assistant written in Python. It combines typed
and spoken interaction, deterministic desktop skills, persistent memory, and the
local `qwen3.5:4b` model served by Ollama.

The assistant remains usable in text mode when audio, OCR, web research, or the
local model is unavailable. Optional capabilities report their own setup problem
instead of preventing the application from starting.

## Features

- Local one-brain dashboard with a live capability graph and activity trace
- Persistent Super Missions that plan, execute, verify, pause, and resume
- Real-time chat, streaming, STOP, voice, and permission controls in the browser
- Tkinter chat interface with an automatic console fallback
- Text-to-speech through `pyttsx3`
- Wake-word voice commands with one-step and two-step interaction
- Offline speech recognition through the bundled Vosk English model
- Optional Google speech-recognition fallback
- Local Qwen inference through Ollama with streaming and cancellation
- Native Qwen tool calling with JSON-schema argument validation
- Central permission checks for sensitive, write, execute, and destructive tools
- Per-action JSONL audit logging
- SQLite long-term memory with local semantic embeddings and lexical fallback
- JSON preferences and short conversation history with atomic persistence
- Dynamically discovered skills with deterministic priorities
- Qwen screen vision with an OCR fallback
- Application launch, system status, screenshots, search, and sourced research
- Custom learned commands
- Optional direct-GGUF support; Qwen also handles code generation by default

## Architecture

```text
Microphone -> VAD -> Vosk/Google --+
                                   +-> JarvisEngine
Dashboard / text / Tkinter UI -----+       |
                                           +-> learned commands / deterministic skills
                                           |
                                           +-> Qwen agent loop
                                               |       |
                                    relevant memory    +-> typed tool registry
                                               |              |
                                               |       permission policy
                                               |              |
                                               +<-- audited skill result
                                               |
                                      streamed UI response -> TTS
                                               |
                                      JSON + SQLite memory

Super Mission goal -> Qwen structured plan -> saved mission steps
                                             -> execute one step at a time
                                             -> tool evidence / permission
                                             -> verify, continue, or pause
```

The default interface is now a local browser dashboard bound only to
`127.0.0.1`. It visualizes one central JARVIS/Qwen brain and activates nearby
capability nodes only when real engine events occur. It does not expose or
pretend to display private model chain-of-thought.

The hybrid router intentionally keeps predictable commands such as `open
calculator` fast and deterministic. Requests that need reasoning go to Qwen,
which can call registered tools, receive their real results, and continue until
it has a final answer. The loop is capped at five model turns.

The important modules are:

- `jarvis.py`: command-line entry point and Windows CUDA path setup
- `core/engine.py`: request routing and application lifecycle
- `core/llm.py`: Qwen chat, streaming, tools, embeddings, vision, and llama.cpp
- `core/memory.py`: preferences, learned commands, and conversation history
- `core/long_term_memory.py`: SQLite storage and semantic retrieval
- `core/tools.py`: schemas, validation, risk policy, execution, and audit logs
- `core/skills.py`: skill discovery, ordering, isolation, and tool registration
- `core/voice.py`: audio capture, VAD, transcription, and wake-word state
- `core/tts.py`: queued text-to-speech worker
- `core/ui.py`: console and Tkinter interfaces
- `core/dashboard.py`: secure local HTTP, live events, and browser control bridge
- `core/missions.py`: durable Super Mission plans, steps, state, and recovery
- `dashboard/`: the one-brain interface, capability graph, chat, and activity UI
- `skills/`: independently loadable assistant capabilities

## Requirements

Python 3.11 or 3.12 is recommended. Python 3.9+ supports text mode, but binary
audio and model packages may not publish wheels for every Python version.

External programs used by optional features:

- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for screen reading
- [Ollama](https://ollama.com/) with `qwen3.5:4b` for language responses

Install the local chat/vision model and embedding model once:

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

## Installation

### Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Make sure Ollama is running, then start JARVIS with `python jarvis.py`. The local
brain dashboard opens automatically.

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
--console          use the terminal instead of the brain dashboard
--tk               use the legacy Tkinter window
--no-voice         disable microphone input
--no-long-term-memory  disable SQLite memory for this run
--dashboard-port N choose the preferred local dashboard port
--no-browser        start the dashboard without opening it automatically
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
| `OLLAMA_EMBEDDING_MODEL` | Local embedding model; defaults to `nomic-embed-text:latest` |
| `JARVIS_GGUF_MODEL_PATH` | Optional direct-GGUF model |
| `CODE_MODEL_PATH` | Optional GGUF coding model |
| `JARVIS_MEMORY_PATH` | Memory JSON location |
| `JARVIS_DB_PATH` | SQLite long-term memory location |
| `JARVIS_MISSIONS_PATH` | SQLite Super Mission state; defaults beside the JSON memory file |
| `JARVIS_MEMORY_SIMILARITY` | Semantic retrieval threshold |
| `JARVIS_AUDIT_PATH` | Executed tool-call audit log |
| `JARVIS_DASHBOARD_PORT` | Preferred local dashboard port; defaults to `8765` |
| `JARVIS_NO_BROWSER` | Start the dashboard without opening a browser |
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
compare my saved astronomy preference with what is on my screen
my name is Ada
what is my name
remember that my meeting is at four
Learn: when I say focus mode do open notepad
create folder demo
shutdown pc
```

## Super Mission mode

Use the **Super Mission** button in the dashboard for a larger goal, or type:

```text
Super Mission: review this project, fix its highest-impact reliability issue,
and verify the result
```

Qwen first returns a schema-validated plan of one to six steps. JARVIS saves the
plan in SQLite, executes only one step at a time, records tool evidence, and
continues only when that step has a grounded result. A step marked as requiring
a real capability cannot succeed without a successful tool result. Sensitive
tools still stop at the normal human permission checkpoint.

Mission controls are available in the dashboard and as text commands:

```text
mission status
pause mission
resume mission
cancel mission
```

If the application closes during a mission, in-progress work is recovered as
paused on the next launch. Resume it explicitly after reviewing the saved steps.
This feature uses Qwen prompting and structured output; it does not modify or
fine-tune Qwen's model weights.

File creation and power actions require confirmation. Automated files are
restricted to `JARVIS_AUTOMATION_ROOT`. PowerShell accepts only a small allowlist
and rejects command chaining and destructive verbs.

When Qwen chooses a sensitive, write, execute, or destructive tool, JARVIS pauses
the agent loop and asks for `yes` or `no`. Nothing is executed before approval.
The dashboard and Tkinter `STOP` buttons—or `stop generating` in text
mode—cancel an active stream.

## Adding a skill

Create a module in `skills/` with a subclass of `BaseSkill`:

```python
from core.skills import BaseSkill
from core.tools import RiskLevel, ToolSpec


class WeatherSkill(BaseSkill):
    name = "Weather"
    description = "Reports local weather."
    priority = 50

    def handle(self, text: str) -> bool:
        if "weather" not in text.lower():
            return False
        self.context.speak("Weather integration is ready.")
        return True

    def get_weather(self, city):
        return f"Weather provider result for {city}"

    def tools(self):
        return [
            ToolSpec(
                name="get_weather",
                description="Get the current weather for a city.",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                    "additionalProperties": False,
                },
                handler=self.get_weather,
                risk=RiskLevel.READ_ONLY,
            )
        ]
```

Higher-priority skills run first. A skill returns `True` only when it has handled
the request. Tools use explicit schemas and risk levels; do not expose arbitrary
shell execution. Import and runtime failures are logged without crashing other
skills.

## Tests

The test suite covers mission persistence and recovery, memory persistence and
concurrency, semantic retrieval,
tool schemas and audits, central confirmation behavior, streamed native tool
calls, skill routing, voice routing, model fallbacks, and clean shutdown:

```bash
python -m unittest discover -v
```

## Privacy and security

- Qwen through Ollama and Vosk speech recognition run locally.
- The dashboard binds to `127.0.0.1`, rejects cross-origin control requests,
  requires a random session token for actions, and sends a restrictive browser
  security policy.
- Google speech recognition is online; select `offline` to forbid that fallback.
- Screen capture always requires confirmation when Qwen requests it as a tool.
- Memory and audit files are plain text/SQLite. Protect or relocate them on
  shared machines, or run with `--no-long-term-memory`.
- Retrieved memory and visible screen text are labeled untrusted so they cannot
  silently become system instructions.
- Generated code is executed only after the explicit `run code` request, but it
  should still be reviewed before use.

The legacy `jarvis_learning.pkl` files are retained only for compatibility with
older experiments. They are not trained models and are not used by the current
application.

## Troubleshooting

Logs are written to `jarvis_system.log`.

- If Qwen does not respond, run `ollama list`, start Ollama, and verify
  `qwen3.5:4b` is installed.
- If semantic memory is unavailable, verify `nomic-embed-text:latest` is listed
  by Ollama. Lexical memory search remains available.
- For direct GGUF inference, install `requirements-llama.txt`, set
  `JARVIS_LLM_BACKEND=llama_cpp`, and configure `JARVIS_GGUF_MODEL_PATH`.
- If CUDA DLL loading fails on Windows, use `repair_jarvis.bat` to reinstall the
  CPU version of `llama-cpp-python`.
- If voice is unavailable, run `python debug_voice.py` and check microphone
  permission and PortAudio installation.
- If OCR fails, install Tesseract and set `TESSERACT_PATH`.
