from core.llm import LLMEngine

class MockLLMEngine(LLMEngine):
    def __init__(self, response=None):
        self.response = response or (
            "I am running without a local language model. Start Ollama with "
            "qwen3.5:4b to enable open-ended AI responses."
        )
        self.current_model_path = None
        self.default_model_path = None

    def load_model(self):
        return True
        
    def generate(self, prompt: str, stop=None, max_tokens=1024) -> str:
        return self.response
