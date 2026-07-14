import sys
import types
import unittest
from unittest.mock import patch

from src.model_client import ModelClient, parse_json_object


class ModelJsonTests(unittest.TestCase):
    def test_parses_plain_json(self):
        self.assertEqual(
            parse_json_object('{"items": ["Python"]}'),
            {"items": ["Python"]},
        )

    def test_parses_markdown_fenced_nested_json(self):
        content = (
            "说明\n```json\n"
            '{"star": {"action": "测试"}, "warnings": []}'
            "\n```"
        )
        self.assertEqual(parse_json_object(content)["star"]["action"], "测试")

    def test_rejects_non_object_json(self):
        with self.assertRaises(ValueError):
            parse_json_object('["not", "object"]')

    def test_rejects_empty_content(self):
        with self.assertRaises(ValueError):
            parse_json_object("  ")


class FakeCompletions:
    def create(self, **kwargs):
        message = type("Message", (), {"content": '{"ok": true}'})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeOpenAIClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


class ModelClientTests(unittest.TestCase):
    def test_injected_transport_does_not_require_optional_packages(self):
        client = ModelClient(client=FakeOpenAIClient(), model="local-test")
        self.assertEqual(client.chat_json("return json"), {"ok": True})

    def test_lazy_transport_receives_finite_timeout(self):
        captured = {}
        fake_module = types.ModuleType("openai")

        def fake_openai(**kwargs):
            captured.update(kwargs)
            return FakeOpenAIClient()

        fake_module.OpenAI = fake_openai
        with patch.dict(sys.modules, {"openai": fake_module}):
            client = ModelClient(
                model="local-test",
                base_url="http://127.0.0.1:11434/v1",
                api_key="test",
                timeout=12.0,
            )
            client._get_client()
        self.assertEqual(captured["timeout"], 12.0)


if __name__ == "__main__":
    unittest.main()
