import os
import sys
import site
import logging
import io
import contextlib

# Setup logging
logging.basicConfig(level=logging.INFO)

print("--- Step 1: Injecting DLLs ---")
try:
    site_dirs = site.getsitepackages()
    programs = [
        ('nvidia', 'cuda_runtime', 'bin'),
        ('nvidia', 'cublas', 'bin'), 
        ('nvidia', 'cudart', 'bin') # Add cudart just in case
    ]
    injected = 0
    for base, sub, folder in programs:
        for d in site_dirs:
            candidate = os.path.join(d, base, sub, folder)
            if os.path.exists(candidate):
                print(f"Found DLL path: {candidate}")
                try:
                    os.add_dll_directory(candidate)
                    os.environ['PATH'] = candidate + os.pathsep + os.environ['PATH']
                    injected += 1
                    print("  -> Injected successfully.")
                except Exception as e:
                    print(f"  -> Injection failed: {e}")
                break
    if injected == 0:
        print("WARNING: No NVIDIA DLL paths found in site-packages!")
except Exception as e:
    print(f"DLL Injection block failed: {e}")

print("\n--- Step 2: Importing Llama ---")
try:
    from llama_cpp import Llama
    print("Success: llama_cpp imported.")
except ImportError:
    print("Failure: llama_cpp import failed.")
    sys.exit(1)
except Exception as e:
    print(f"Failure: {e}")
    sys.exit(1)

model_path = r"D:\models\capybara\capybarahermes-2.5-mistral-7b.Q5_0.gguf"
if not os.path.exists(model_path):
    print("Model not found, skipping load.")
    sys.exit(0)

print(f"\n--- Step 3: Loading Model from {model_path} ---")
# Capture stderr to see internal logs
f = io.StringIO()
try:
    with contextlib.redirect_stderr(sys.stdout): # Redirect stderr to stdout to capture llama.cpp logs
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1, # Try full offload
            verbose=True
        )
    print("\nModel Initialized.")
    
    # Check simple generation
    print("Generating...")
    output = llm("Hello", max_tokens=5)
    print("Output:", output)

except Exception as e:
    print(f"\nCRITICAL ERROR during model load: {e}")
    import traceback
    traceback.print_exc()
