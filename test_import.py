import sys
import os

print(f"Python Executable: {sys.executable}")
try:
    import llama_cpp
    print("IMPORT SUCCESS: llama_cpp")
    print(f"Version: {llama_cpp.__version__}")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
except OSError as e:
    print(f"OS ERROR (DLL missing?): {e}")
except Exception as e:
    print(f"GENERAL ERROR: {e}")
