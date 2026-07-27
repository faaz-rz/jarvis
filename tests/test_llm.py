import unittest

from core.llm import LLMEngine


class OllamaLLMTests(unittest.TestCase):
    def test_ollama_model_check_and_chat_generation(self):
        llm = LLMEngine(backend="ollama", ollama_model="qwen-test:4b")
        calls = []

        def fake_request(endpoint, payload=None, timeout=30):
            calls.append((endpoint, payload))
            if endpoint == "/api/tags":
                return {"models": [{"name": "qwen-test:4b"}]}
            return {"message": {"role": "assistant", "content": "Qwen response"}}

        llm._ollama_request = fake_request
        self.assertTrue(llm.load_model())

        prompt = (
            "<|im_start|>system\nBe concise.\n<|im_end|>\n"
            "<|im_start|>user\nHello\n<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        self.assertEqual(llm.generate(prompt), "Qwen response")
        chat_payload = calls[-1][1]
        self.assertEqual(chat_payload["model"], "qwen-test:4b")
        self.assertEqual(
            [message["role"] for message in chat_payload["messages"]],
            ["system", "user"],
        )

    def test_missing_ollama_model_has_actionable_error(self):
        llm = LLMEngine(backend="ollama", ollama_model="missing:4b")
        llm._ollama_request = lambda *args, **kwargs: {"models": []}
        self.assertFalse(llm.load_model())
        self.assertIn("ollama pull missing:4b", llm.last_error)


if __name__ == "__main__":
    unittest.main()
