import os
import threading
import logging
import time

# Global flag to track if llama_cpp is usable
HAS_LLAMA = False
try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    Llama = None
except OSError:
    # Captures "FileNotFoundError: ... CUDA/.../bin" and other DLL issues
    Llama = None
except Exception:
    Llama = None

class LLMEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(LLMEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_path=None):
        if hasattr(self, 'model'):
            return
        
        # 1. User specified path
        default_path = r"D:\models\capybara\capybarahermes-2.5-mistral-7b.Q5_0.gguf"
        
        self.model_path = os.environ.get('MISTRAL_MODEL_PATH')
        
        # Priority Check
        if not self.model_path:
            self.model_path = default_path
            
        self.default_model_path = default_path 
        self.current_model_path = self.model_path
            
        self.model = None
        self.loaded = False
        self.lock = threading.RLock()
        logging.info(f"LLM Engine Configured. Target Model: {self.model_path}")

    def unload_model(self):
        with self.lock:
            if self.model:
                del self.model
                self.model = None
            self.loaded = False
            import gc
            gc.collect()
            logging.info("Model unloaded.")

    def reload_model(self, new_path=None):
        if new_path:
            self.current_model_path = new_path
        
        self.unload_model()
        # Force re-load next time load_model is called or call it now
        # We'll set the internal path and let load_model handle it
        self.model_path = self.current_model_path
        return self.load_model()

    def load_model(self):
        if self.loaded:
            return True
        
        if not HAS_LLAMA:
            logging.error("llama_cpp module failed to import (Check CUDA/DLLs or install CPU version).")
            return False

        if not os.path.exists(self.model_path):
            logging.error(f"CRITICAL: Model file missing at: {self.model_path}")
            return False

        try:
            logging.info(f"Loading Llama model from {self.model_path}...")
            # Reduced Context for stability on lower-end/CPU
            # Optimized for RTX 3050 4GB: n_batch=512, n_ctx=4096, offload all layers
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=4096,          # Safe limit for 4GB VRAM
                n_threads=6,
                n_batch=512,         # Lower batch size to reduce VRAM spikes
                n_gpu_layers=20,     # Adjusted for 4GB VRAM (prevents overflow to RAM)
                verbose=True
            )
            self.loaded = True
            logging.info("Model loaded successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to load model: {e}")
            return False

    def generate(self, prompt: str, stop=None, max_tokens=1024) -> str:
        """Thread-safe generation."""
        if not HAS_LLAMA:
            return "System Error: llama-cpp-python is missing or broken (check CUDA/DLLs). Falling back to mock response."

        if not self.loaded:
            if not self.load_model():
                return "Error: Model could not be loaded. Please check logs."

        with self.lock:
            try:
                output = self.model(
                    prompt,
                    max_tokens=max_tokens,
                    stop=stop or ["<|im_end|>", "User:", "[INST]"],
                    echo=False
                )
                return output['choices'][0]['text'].strip()
            except Exception as e:
                logging.error(f"Generation error: {e}")
                return f"Error regenerating response: {e}"
