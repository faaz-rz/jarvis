import os
try:
    from llama_cpp import Llama
    print("SUCCESS: llama_cpp imported.")
except ImportError:
    print("FAILURE: llama_cpp could not be imported.")
    exit(1)

# Path to the model - using the one found in checking
model_path = r"D:\models\capybara\capybarahermes-2.5-mistral-7b.Q5_0.gguf"

if not os.path.exists(model_path):
    print(f"WARNING: Default model path not found: {model_path}")
    print("Attempting to verify just module build info...")
else:
    print(f"Loading model from {model_path}...")
    try:
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1, # Force all layers to GPU
            n_ctx=2048,
            verbose=True
        )
        print("Model loaded.")
        
        # internal metadata check if possible (some versions expose it)
        # But verbose output above should show "BLAS = 1" and "CUDA = 1"
        
        output = llm("Hello, verify GPU.", max_tokens=10)
        print("Generation output:", output)
        print("VERIFICATION COMPLETE. Check logs above for 'BLAS = 1'.")
    except Exception as e:
        print(f"Error loading model: {e}")
