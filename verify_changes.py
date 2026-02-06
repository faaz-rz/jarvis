import os
import sys
import site

# DLL Fix for llama-cpp-python
# [FIX] CUDA DLL Injection for RTX 3050 (llama-cpp-python)
import site
import os

# Clear conflicting env vars that might point to missing/corrupt CUDA installs
os.environ.pop('CUDA_PATH', None)
os.environ.pop('CUDA_HOME', None)

try:
    # Try finding Nvidia Runtime/cuBLAS in site-packages
    site_dirs = site.getsitepackages()
    programs = [
        ('nvidia', 'cuda_runtime', 'bin'),
        ('nvidia', 'cublas', 'bin')
    ]
    for base, sub, folder in programs:
        for d in site_dirs:
            candidate = os.path.join(d, base, sub, folder)
            if os.path.exists(candidate):
                os.add_dll_directory(candidate)
                os.environ['PATH'] = candidate + os.pathsep + os.environ['PATH']
                print(f"Injected DLL Path: {candidate}")
                # Don't break immediately, we need BOTH runtime and cublas if possible
                # Actually earlier I broke, but usually correct to add all found.
                # But for simplicity let's follow the jarvis logic (which broke?)
                # Wait, jarvis logic broke after first find?
                # "break" is inside the inner loop (site_dirs).
                # So it finds "cuda_runtime" in one site-dir, breaks, then finds "cublas" in one site-dir.
                # Yes, that is correct.
                pass
except Exception as e:
    print(f"DLL Injection failed: {e}")
except ImportError:
    print("nvidia.cuda_runtime not found.")

try:
    from core.llm import LLMEngine, HAS_LLAMA
    from core.engine import JarvisEngine
    
    if not HAS_LLAMA:
        print("HAS_LLAMA is False. Attempting direct import to show trace:")
        from llama_cpp import Llama
        
    print("Imports successful. HAS_LLAMA = True.")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}")
