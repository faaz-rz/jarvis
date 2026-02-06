
import os
try:
    from llama_cpp import Llama
    print("llama-cpp-python imported successfully.")
    # Attempt to load a dummy model or just check build info if available
    # usually verifying headers is hard without loading, so let's try to see if we can force a load that fails or check logs
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # We can check if the DLL is loaded.
    # On windows, we look for cublas64 or similar in the process
    import ctypes
    import sys
    
    print(f"Python Version: {sys.version}")
    
except ImportError:
    print("llama-cpp-python NOT installed.")

# Check for CUDA compiler variable usage
if os.environ.get('CMAKE_ARGS'):
    print(f"CMAKE_ARGS: {os.environ.get('CMAKE_ARGS')}")
else:
    print("CMAKE_ARGS not set in current env.")

# We will try to run a dummy load with n_gpu_layers
print("To verify, we need to reinstall with proper flags if the output showed 'BLAS = 0'.")
