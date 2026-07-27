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
                "No GGUF model is configured. Set MISTRAL_MODEL_PATH or use Ollama."
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
        if not self.loaded and not self.load_model():
            raise LLMUnavailableError(
                self.last_error or "The local model is unavailable."
            )

        with self.lock:
            if self.backend == "ollama":
                return self._generate_ollama(prompt, max_tokens=max_tokens)
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

    def _generate_ollama(self, prompt: str, max_tokens: int) -> str:
        messages = [
            {"role": role, "content": content.strip()}
            for role, content in self.CHATML_PATTERN.findall(prompt)
        ]
        if not messages:
            messages = [{"role": "user", "content": prompt.strip()}]

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "think": env_bool("OLLAMA_THINK", False),
            "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
            "options": {
                "num_predict": max_tokens,
                "num_ctx": env_int("OLLAMA_NUM_CTX", 8192),
                "temperature": env_float("OLLAMA_TEMPERATURE", 0.4),
            },
        }
        result = self._ollama_request(
            "/api/chat",
            payload,
            timeout=env_int("OLLAMA_TIMEOUT_SECONDS", 300),
        )
        content = result.get("message", {}).get("content", "").strip()
        if not content:
            raise LLMUnavailableError(
                f"Ollama model '{self.ollama_model}' returned an empty response."
            )
        return content

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
