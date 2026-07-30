import unittest
import json
import threading
from unittest.mock import patch

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

    def test_streaming_collects_content_and_native_tool_calls(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __iter__(self):
                chunks = [
                    {"message": {"content": "Working "}, "done": False},
                    {
                        "message": {
                            "content": "now.",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "get_status",
                                        "arguments": {},
                                    }
                                }
                            ],
                        },
                        "done": True,
                    },
                ]
                return iter(
                    (json.dumps(chunk) + "\n").encode("utf-8")
                    for chunk in chunks
                )

        llm = LLMEngine(backend="ollama", ollama_model="qwen-test:4b")
        llm.loaded = True
        streamed = []
        with patch("core.llm.urllib_request.urlopen", return_value=FakeResponse()):
            result = llm.chat(
                [{"role": "user", "content": "Check status"}],
                tools=[],
                stream_callback=streamed.append,
                cancel_event=threading.Event(),
            )

        self.assertEqual("".join(streamed), "Working now.")
        self.assertEqual(result["message"]["content"], "Working now.")
        self.assertEqual(
            result["message"]["tool_calls"][0]["function"]["name"],
            "get_status",
        )


if __name__ == "__main__":
    unittest.main()
