import os
import sys
import glob
import importlib.util

print(f"Python: {sys.version}")
print(f"Platform: {sys.platform}")

try:
    import llama_cpp
    package_dir = os.path.dirname(llama_cpp.__file__)
    print(f"llama-cpp-python pkg dir: {package_dir}")
    
    # List files in package dir to check for DLLs
    files = os.listdir(package_dir)
    print("Files in package directory:")
    for f in files:
        if f.endswith(".dll") or f.endswith(".so"):
            print(f" - {f}")

    # specific check for llama.dll
    lib_path = os.path.join(package_dir, "lib", "llama.dll")
    if not os.path.exists(lib_path):
         # check root
         lib_path = os.path.join(package_dir, "llama.dll")

    if os.path.exists(lib_path):
        print(f"Found library at: {lib_path}")
    else:
        print("WARNING: Could not find llama.dll or similar.")

    print("\n--- Attempting Load ---")
    try:
        from llama_cpp import Llama
        # Don't load full model, just see if it crashs or prints CUDA info
        # We need a dummy model path or it will fail.
        # But we can check internal backend info if exposed.
        print("llama_cpp imported. Trying to initialize backend...")
    except Exception as e:
        print(f"Error importing Llama: {e}")
        import traceback
        traceback.print_exc()

except ImportError:
    print("llama-cpp-python NOT installed or import failed.")
