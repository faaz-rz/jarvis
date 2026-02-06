from core.llm import LLMEngine

class MockLLMEngine(LLMEngine):
    def load_model(self):
        return True
        
    def generate(self, prompt: str, stop=None, max_tokens=1024) -> str:
        return "I am in Mock Mode because the local model failed to load. Please check your CUDA installation or switching to a CPU-only llama-cpp-python."
