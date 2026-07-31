# JARVIS Interview Guide

## 30-second explanation

JARVIS is a local-first desktop assistant built in Python. It uses a hybrid
architecture: deterministic skills handle predictable commands quickly, while
Qwen 3.5 runs an agent loop for requests that need reasoning. Qwen can select
typed tools, but a central policy validates every argument and pauses for
permission before sensitive or state-changing actions. Results are returned to
Qwen so its final answer reflects what actually happened. The system also
supports streaming, cancellation, local voice input, Qwen vision, and semantic
long-term memory.

For larger objectives, Super Mission mode asks Qwen for a schema-validated plan,
persists it in SQLite, runs one step at a time, and requires observable evidence
before advancing. The same central permission policy remains in control.

The primary interface presents Qwen as one central brain rather than separate
departments. Voice, vision, memory, research, applications, files, system
control, and code appear as abilities around the core and illuminate only when
real engine events activate them.

## Request flow

1. Text or voice reaches `JarvisEngine`.
2. Learned commands and high-priority deterministic skills get the first chance
   to handle simple requests.
3. For other requests, the engine retrieves relevant long-term memories and
   sends the conversation, tool schemas, and untrusted memory context to Qwen.
4. If Qwen returns tool calls, the registry validates names, required fields,
   types, enums, lengths, and unexpected arguments.
5. The permission policy pauses sensitive, write, execute, or destructive calls.
6. Approved tools execute and write a JSONL audit record.
7. Tool results go back to Qwen. It can call another tool or stream a final
   response. The loop stops after five iterations.
8. The final exchange is saved in JSON history and SQLite long-term memory.

For a Super Mission, a separate planning turn produces one to six structured
steps. The engine persists the plan, executes the current step through the same
agent loop, records successful tool results as evidence, and either advances,
pauses, or waits for permission. It never launches a collection of independent
department agents.

## Why the architecture is hybrid

Pure keyword routing is fast and reliable but cannot plan or combine tools. A
pure agent is flexible but slower and less predictable. The hybrid approach
keeps common commands deterministic while allowing natural multi-step requests.
It also gives graceful degradation: skills still work when Ollama is stopped.

## Important design decisions

### Native tool calling instead of parsing model text

Each skill exposes `ToolSpec` objects with JSON schemas. Ollama sends these
schemas to Qwen and returns structured `tool_calls`. This avoids regex-parsing
sentences such as “I will call open_application,” which is brittle and unsafe.

### Permission is enforced outside the model

Qwen may propose an action, but it cannot approve its own action. The
`PermissionPolicy` classifies tools by risk. The engine stores the pending calls
and resumes only after the user says yes. This is a security boundary, not merely
a prompt instruction.

### Results are grounded

JARVIS never treats the model's intention as success. The actual Python handler
runs, its success or error is appended as a `tool` message, and only then does
Qwen produce the final response.

### Two levels of memory

The JSON store keeps preferences, learned commands, and a short history with
atomic writes. SQLite keeps longer conversational memory. A background worker
creates local embeddings through `nomic-embed-text`; semantic cosine search is
used when embeddings are available, with lexical retrieval as a fallback.
Retrieved text is explicitly marked as untrusted context to reduce prompt
injection risk.

### Concurrency and responsiveness

The UI thread does not perform model inference. A single LLM worker serializes
agent requests, Ollama output streams back to the UI, and a cancellation event
can stop generation. TTS and memory embedding have separate background workers.
Tkinter updates are passed through a queue because Tk widgets are not
thread-safe.

### Live brain dashboard

The default browser interface is served only on the loopback address. Engine
events drive the graph, task lifecycle, transcript, activity trace, streaming
response, cancellation, and approval dialog. Browser actions require a random
session token and same-origin checks. The interface shows operational states,
not hidden model chain-of-thought.

### Durable Super Missions

Mission state and step results live in a dedicated SQLite database. If the
process exits while planning, running, or waiting for permission, startup
recovery marks the mission paused and resets the interrupted step to pending.
The user must explicitly resume it. A step declared `requires_tool` cannot be
marked complete unless at least one real tool succeeded.

## Safety controls to mention

- Tool allowlist: Qwen can call only registered functions.
- Strict argument validation: unknown or malformed fields are rejected.
- Central approval for sensitive or state-changing actions.
- Automation paths are resolved and must remain inside
  `JARVIS_AUTOMATION_ROOT`.
- Files are created with no-overwrite behavior.
- PowerShell uses a small read-only allowlist and rejects metacharacters.
- Executed and failed tool actions are written to an audit log.
- Screen and recalled memory content are treated as data, not instructions.
- Tool loops have a fixed upper bound and model requests can be cancelled.
- Super Missions run sequentially, survive restarts, and pause when required
  evidence is missing.
- The dashboard cannot be framed by another site and rejects cross-origin
  control requests.

## Failure handling

- If Ollama or Qwen is unavailable, deterministic skills continue to work and
  the user receives an actionable error.
- If the embedding model is unavailable, memory search falls back to lexical
  matching.
- If Qwen vision is unavailable, screen reading falls back to Tesseract OCR.
- Missing optional voice, OCR, research, or desktop dependencies do not prevent
  startup.
- Skill import and runtime errors are isolated and logged.

## Evidence and testing

The automated suite verifies mission persistence, crash recovery, required-tool
evidence, tool schemas, validation, audit records, permission gating, the
agent's write-confirmation cycle, streamed native tool calls, semantic and
lexical memory behavior, concurrent JSON persistence, skill priority,
wake-word states, model failure fallback, and clean shutdown.

Live validation on this machine demonstrated:

- `qwen3.5:4b` emitted a structured tool call.
- The tool result was fed back and Qwen streamed a grounded answer.
- A file did not exist before approval and was created only after approval.
- The action produced an audit entry.
- `nomic-embed-text` produced a 768-dimensional embedding.
- Qwen vision correctly identified a red test image.

## Common interview questions

**Why not let Qwen directly execute Python functions?**

Because model output is untrusted. A registry creates a narrow interface where
the application owns validation, permissions, execution, and auditing.

**How do you prevent hallucinated success?**

The model sees the real tool result. Its final response is generated only after
the handler returns success or an error.

**How does cancellation work?**

The active request owns a `threading.Event`. The STOP action sets it; the
streaming Ollama reader checks the event between chunks, closes the response,
clears the active state, and preserves any partial answer.

**Is Super Mission mode a multi-agent system?**

No. It is one Qwen-driven brain using a durable state machine. Qwen plans the
goal, the engine executes one saved step through the existing tool registry, and
the verifier checks real evidence before proceeding.

**Did you train or fine-tune Qwen?**

No model weights are changed. The behavior comes from structured prompts, a
strict JSON plan schema, persistent mission state, tool-grounded execution, and
deterministic safety checks outside the model.

**How would you scale it?**

Separate model, tool, and memory services; add per-user authorization and
encrypted storage; use a durable task queue; add tool timeouts and sandboxing;
and instrument latency, tool success, retrieval quality, and permission-denial
rates.

**What would you improve next?**

The highest-value next steps are sandboxed generated-code execution, encrypted
memory and audit logs, retrieval-quality evaluation, per-tool rate limits,
stronger end-to-end GUI/voice tests, and packaging with signed releases.

## Short demo script

1. Run `python jarvis.py --console --no-voice`.
2. Ask a normal question to show streamed Qwen output.
3. Ask: “Use your create file tool to prepare demo.txt.”
4. Show that JARVIS asks for permission and the file does not yet exist.
5. Say `yes`, then show the grounded completion and audit record.
6. Say `remember that I prefer concise answers`, then ask about the preference
   in a later conversation.
7. In the dashboard, start a Super Mission and show its saved steps, pause,
   resume, and per-step verification.
