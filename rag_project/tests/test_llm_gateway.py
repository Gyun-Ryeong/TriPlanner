"""학교 LLM 게이트웨이(Bedrock, OpenAI 호환) 호출 — 실제 네트워크 없이 가짜 응답으로 확인"""
import unittest
from unittest.mock import MagicMock, patch

import config
from llm import ollama_client as oc


def fake_response(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.text = str(body)
    return r


class GatewayTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("LLM_PROVIDER", "gateway"), ("LLM_BASE_URL", "https://gw.example/v1"),
                            ("LLM_API_KEY", "test-key"), ("LLM_MODEL", "bedrock-haiku"), ("LLM_JSON_MODE", False)):
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_sends_openai_format_and_parses_json(self):
        body = {"choices": [{"message": {"content": '```json\n{"days": []}\n```'}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30}}
        with patch.object(oc.requests, "post", return_value=fake_response(200, body)) as post:
            parsed, raw = oc.chat_json_messages([{"role": "user", "content": "부산"}])
        self.assertEqual(parsed, {"days": []})
        url, kwargs = post.call_args[0][0], post.call_args[1]
        self.assertEqual(url, "https://gw.example/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "bedrock-haiku")
        self.assertNotIn("response_format", kwargs["json"])  # 기본은 끔 (게이트웨이가 지원하지 않을 수 있음)
        self.assertEqual(oc.LAST_STATS["prompt_tokens"], 120)

    def test_errors_become_connection_error(self):
        with patch.object(oc.requests, "post", return_value=fake_response(401, {"error": {"message": "bad key"}})):
            with self.assertRaises(oc.OllamaConnectionError) as e:
                oc.chat_json("sys", "hi")
        self.assertIn("401", str(e.exception))
        self.assertIn("키를 확인", str(e.exception))
        with patch.object(oc.requests, "post", side_effect=oc.requests.exceptions.Timeout()):
            with self.assertRaises(oc.OllamaConnectionError):
                oc.chat_json("sys", "hi")

    def test_missing_key_is_explained(self):
        with patch.object(config, "LLM_API_KEY", ""):
            with self.assertRaises(oc.OllamaConnectionError) as e:
                oc.chat_json("sys", "hi")
        self.assertIn("LLM_API_KEY", str(e.exception))

    def test_ollama_is_default(self):
        with patch.object(config, "LLM_PROVIDER", "ollama"), \
             patch.object(oc, "_post_chat_model", return_value='{"ok": 1}') as m:
            self.assertEqual(oc.chat_json("sys", "hi")[0], {"ok": 1})
        m.assert_called_once()


if __name__ == "__main__":
    unittest.main()
