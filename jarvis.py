"""
J.A.R.V.I.S - Advanced AI Assistant
Refactored Enterprise-Grade Edition
"""
import sys
import os
import logging

# Ensure we can import from local modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Setup logging
logging.basicConfig(
    filename='jarvis_system.log', 
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s: %(message)s'
)

# [FIX] CUDA DLL Injection for RTX 3050 (llama-cpp-python)
import site
import os

# Clear conflicting env vars that might point to incompatible System CUDA (e.g. v13.1)
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
                logging.info(f"Injected DLL Path: {candidate}")
                break
except Exception as e:
    logging.warning(f"DLL Injection failed: {e}")

try:
    from core.engine import JarvisEngine
except ImportError as e:
    print(f"CRITICAL: Failed to import core modules. {e}")
    print("Ensure you are running 'python jarvis.py' from the D:\\J.A.R.V.I.S directory.")
    sys.exit(1)

def main():
    try:
        app = JarvisEngine()
        app.start()
    except KeyboardInterrupt:
        print("\nForce Quit.")
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
