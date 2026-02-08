"""
J.A.R.V.I.S - Advanced AI Assistant
Refactored Enterprise-Grade Edition
"""
import sys
import os
import logging

import logging
import subprocess

# DEBUG: Check environment
print(f"DEBUG: Executable: {sys.executable}")
print(f"DEBUG: Python Version: {sys.version}")

# [CRITICAL] Python 3.14 Compatibility Fix
# Python 3.13+ removed 'aifc', breaking speech_recognition. 
# Also, binary wheels for 3.14 don't exist yet for sounddevice/cffi.
if sys.version_info >= (3, 13):
    print("\n[CRITICAL WARNING] You are running Python 3.13+ (Incompatible with Audio Libraries)")
    print("Attempting to auto-switch to .venv (Python 3.11)...")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    
    if os.path.exists(venv_python):
        print(f"Re-launching with: {venv_python}")
        # Pass all arguments to the new process
        subprocess.call([venv_python] + sys.argv)
        sys.exit(0)
    else:
        print(f"[ERROR] Could not find venv at {venv_python}")
        print("Please install Python 3.11 and create a venv, or run this script with a compatible Python version.")
        sys.exit(1)

# Ensure we can import from local modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# [FIX] Force load venv site-packages if missing (System Environment Issue)
venv_site = os.path.join(BASE_DIR, '.venv', 'Lib', 'site-packages')
if os.path.exists(venv_site) and venv_site not in sys.path:
    print(f"DEBUG: Manually adding venv site-packages: {venv_site}")
    sys.path.append(venv_site)
    import site
    site.addsitedir(venv_site)

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
