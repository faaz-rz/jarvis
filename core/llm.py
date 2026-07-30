"""Local language-model backends for JARVIS."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

from core.config import (
    default_model_path,
    default_ollama_model,
    env_bool,
    env_float,
    env_int,
    ollama_host,
)


HAS_LLAMA = False
LLAMA_IMPORT_ERROR = None
try:
    from llama_cpp import Llama

    HAS_LLAMA = True
except Exception as exc:
    Llama = None
    LLAMA_IMPORT_ERROR = exc


class LLMUnavailableError(RuntimeError):
    """Raised when local inference cannot be used."""


class LLMEngine:
    CHATML_PATTERN = re.compile(
        r"<\|im_start\|>(system|user|assistant)\n(.*?)\n<\|im_end\|>",
        re.DOTALL,
    )

    def __init__(self, model_path=None, backend=None, ollama_model=None):
        selected_path = (
            Path(model_path).expanduser().resolve()
            if model_path
            else default_model_path()
        )
        configured_backend = (
            backend or os.environ.get("JARVIS_LLM_BACKEND", "auto")
        ).strip().lower()
        if configured_backend == "auto":
            configured_backend = (
                "llama_cpp"
                if selected_path and selected_path.is_file()
                else "ollama"
            )
        if configured_backend not in {"ollama", "llama_cpp"}:
            raise ValueError(
                "JARVIS_LLM_BACKEND must be auto, ollama, or llama_cpp."
            )

        self.backend = configured_backend
        self.default_backend = configured_backend
        self.model_path = str(selected_path) if selected_path else None
        self.default_model_path = self.model_path
        self.current_model_path = self.model_path
        self.ollama_model = ollama_model or default_ollama_model()
        self.default_ollama_model = self.ollama_model
        self.ollama_host = ollama_host()
        self.model = None
        self.loaded = False
        self.last_error = None
        self.lock = threading.RLock()
        logging.info(
            "LLM configured: backend=%s model=%s",
            self.backend,
            self.ollama_model if self.backend == "ollama" else self.model_path,
        )

    @property
    def model_name(self) -> str:
        if self.backend == "ollama":
            return self.ollama_model
        return self.model_path or "unconfigured GGUF model"

    def unload_model(self):
        with self.lock:
            if self.model:
                del self.model
                self.model = None
            self.loaded = False
            if self.backend == "llama_cpp":
                import gc

                gc.collect()
            logging.info("Model backend unloaded.")

    def reload_model(self, new_path=None):
        target_path = (
            str(Path(new_path).expanduser().resolve())
            if new_path
            else self.current_model_path
        )
        previous = (
            self.backend,
            self.current_model_path,
            self.model_path,
            self.ollama_model,
        )
        self.unload_model()
        if new_path:
            self.backend = "llama_cpp"
        self.model_path = target_path
        self.current_model_path = target_path
        if self.load_model():
            return True

        (
            self.backend,
            self.current_model_path,
            self.model_path,
            self.ollama_model,
        ) = previous
        return False

    def reload_default_model(self):
        self.unload_model()
        self.backend = self.default_backend
        self.model_path = self.default_model_path
        self.current_model_path = self.default_model_path
        self.ollama_model = self.default_ollama_model
        return self.load_model()

    def load_model(self):
        if self.loaded:
            return True
        if self.backend == "ollama":
            return self._check_ollama()

        if not HAS_LLAMA:
            self.last_error = "llama-cpp-python is not installed or could not load"
            if LLAMA_IMPORT_ERROR:
                self.last_error += f": {LLAMA_IMPORT_ERROR}"
            logging.error(self.last_error)
            return False

        if not self.model_path:
            self.last_error = (
                "No GGUF model is configured. Set JARVIS_GGUF_MODEL_PATH "
                "or use Ollama."
            )
            logging.error(self.last_error)
            return False
        if not os.path.isfile(self.model_path):
            self.last_error = f"Model file was not found: {self.model_path}"
            logging.error(self.last_error)
            return False

        try:
            logging.info("Loading llama.cpp model from %s", self.model_path)
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=env_int("LLM_N_CTX", 4096),
                n_threads=env_int("LLM_N_THREADS", 6),
                n_batch=env_int("LLM_N_BATCH", 512),
                n_gpu_layers=env_int("LLM_N_GPU_LAYERS", 20),
                verbose=env_bool("LLM_VERBOSE", False),
            )
            self.loaded = True
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"Failed to load GGUF model: {exc}"
            logging.error(self.last_error)
            return False

    def _check_ollama(self):
        try:
            result = self._ollama_request("/api/tags", timeout=5)
            names = {
                model.get("name") or model.get("model")
                for model in result.get("models", [])
            }
            if self.ollama_model not in names:
                self.last_error = (
                    f"Ollama model '{self.ollama_model}' is not installed. "
                    f"Run: ollama pull {self.ollama_model}"
                )
                logging.error(self.last_error)
                return False
            self.loaded = True
            self.last_error = None
            return True
        except LLMUnavailableError as exc:
            self.last_error = str(exc)
            logging.error(self.last_error)
            return False

    def generate(self, prompt: str, stop=None, max_tokens=1024) -> str:
        """Generate a response using Ollama or llama.cpp."""
        if self.backend == "ollama":
            messages = [
                {"role": role, "content": content.strip()}
                for role, content in self.CHATML_PATTERN.findall(prompt)
            ]
            if not messages:
                messages = [{"role": "user", "content": prompt.strip()}]
            result = self.chat(messages, max_tokens=max_tokens)
            content = result.get("message", {}).get("content", "").strip()
            if not content:
                raise LLMUnavailableError(
                    f"Ollama model '{self.ollama_model}' returned an empty response."
                )
            return content

        if not self.loaded and not self.load_model():
            raise LLMUnavailableError(
                self.last_error or "The local model is unavailable."
            )

        with self.lock:
            try:
                output = self.model(
                    prompt,
                    max_tokens=max_tokens,
                    stop=stop or ["<|im_end|>", "User:", "[INST]"],
                    echo=False,
                )
                return output["choices"][0]["text"].strip()
            except Exception as exc:
                self.last_error = f"Generation failed: {exc}"
                logging.error(self.last_error)
                raise LLMUnavailableError(self.last_error) from exc

    def chat(
        self,
        messages,
        tools=None,
        max_tokens=1024,
        stream_callback=None,
        cancel_event=None,
        format_schema=None,
    ):
        """Return a normalized chat response with optional tools and streaming."""
        if not self.loaded and not self.load_model():
            raise LLMUnavailableError(
                self.last_error or "The local model is unavailable."
            )
        if self.backend != "ollama":
            prompt = self._messages_to_chatml(messages)
            content = self.generate(prompt, max_tokens=max_tokens)
            if stream_callback:
                stream_callback(content)
            return {"message": {"role": "assistant", "content": content}}

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": bool(stream_callback),
            "think": env_bool("OLLAMA_THINK", False),
            "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
            "options": {
                "num_predict": max_tokens,
                "num_ctx": env_int("OLLAMA_NUM_CTX", 8192),
                "temperature": env_float("OLLAMA_TEMPERATURE", 0.4),
            },
        }
        if tools:
            payload["tools"] = tools
        if format_schema:
            payload["format"] = format_schema

        timeout = env_int("OLLAMA_TIMEOUT_SECONDS", 300)
        with self.lock:
            if stream_callback:
                return self._ollama_stream_request(
                    "/api/chat",
                    payload,
                    stream_callback,
                    cancel_event,
                    timeout,
                )
            return self._ollama_request("/api/chat", payload, timeout=timeout)

    def embed(self, texts, model=None):
        """Create normalized embeddings through the local Ollama server."""
        single = isinstance(texts, str)
        inputs = [texts] if single else list(texts)
        if not inputs:
            return [] if not single else None
        result = self._ollama_request(
            "/api/embed",
            {
                "model": model or os.environ.get(
                    "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"
                ),
                "input": inputs,
                "truncate": True,
                "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
            },
            timeout=env_int("OLLAMA_TIMEOUT_SECONDS", 300),
        )
        embeddings = result.get("embeddings", [])
        if len(embeddings) != len(inputs):
            raise LLMUnavailableError("Ollama returned an unexpected embedding result.")
        return embeddings[0] if single else embeddings

    def analyze_image(self, image_bytes: bytes, prompt: str) -> str:
        """Analyze an image with an Ollama vision-capable model."""
        if self.backend != "ollama":
            raise LLMUnavailableError("Direct image analysis requires the Ollama backend.")
        import base64

        result = self.chat(
            [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                }
            ],
            max_tokens=800,
        )
        content = result.get("message", {}).get("content", "").strip()
        if not content:
            raise LLMUnavailableError("The vision model returned an empty response.")
        return content

    @staticmethod
    def _messages_to_chatml(messages):
        parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            parts.append(f"<|im_start|>{role}\n{content}\n<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    def _ollama_stream_request(
        self, endpoint, payload, stream_callback, cancel_event, timeout
    ):
        data = json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(
            f"{self.ollama_host}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        content_parts = []
        thinking_parts = []
        tool_calls = []
        cancelled = False
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                for raw_line in response:
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        break
                    if not raw_line.strip():
                        continue
                    chunk = json.loads(raw_line.decode("utf-8"))
                    message = chunk.get("message", {})
                    content = message.get("content", "")
                    thinking = message.get("thinking", "")
                    if content:
                        content_parts.append(content)
                        stream_callback(content)
                    if thinking:
                        thinking_parts.append(thinking)
                    if message.get("tool_calls"):
                        tool_calls.extend(message["tool_calls"])
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMUnavailableError(
                f"Ollama request failed with HTTP {exc.code}: {detail[:300]}"
            ) from exc
        except (urllib_error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise LLMUnavailableError(
                f"Could not stream from Ollama at {self.ollama_host}: {exc}"
            ) from exc

        message = {
            "role": "assistant",
            "content": "".join(content_parts),
        }
        if thinking_parts:
            message["thinking"] = "".join(thinking_parts)
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {"message": message, "cancelled": cancelled}

    def _ollama_request(self, endpoint, payload=None, timeout=30):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib_request.Request(
            f"{self.ollama_host}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMUnavailableError(
                f"Ollama request failed with HTTP {exc.code}: {detail[:300]}"
            ) from exc
        except (urllib_error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise LLMUnavailableError(
                f"Could not reach Ollama at {self.ollama_host}: {exc}"
            ) from exc
