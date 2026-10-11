import os
import unittest
from unittest.mock import Mock, patch

from llm_gateway import LLMGateway


class AnthropicGatewayTests(unittest.TestCase):
    @patch("llm_gateway.httpx.post")
    def test_uses_anthropic_messages_api_and_extracts_text(self, mock_post):
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {"content": [{"type": "text", "text": '{"ok": true}'}]}
        mock_post.return_value = response
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "anthropic",
                "ANTHROPIC_BASE_URL": "https://example.test/v1",
                "ANTHROPIC_AUTH_TOKEN": "test-token",
                "ANTHROPIC_MODEL": "test-model",
            },
            clear=False,
        ):
            result = LLMGateway().generate("generator", "Return JSON", expect_json=True)

        request = mock_post.call_args.kwargs
        self.assertEqual(mock_post.call_args.args[0], "https://example.test/v1/messages")
        self.assertEqual(request["headers"]["x-api-key"], "test-token")
        self.assertEqual(request["json"]["model"], "test-model")
        self.assertIn("ONLY valid JSON", request["json"]["messages"][0]["content"])
        self.assertEqual(result, '{"ok": true}')

    def test_anthropic_requires_token(self):
        with patch.dict(
            os.environ,
            {"AI_PROVIDER": "anthropic", "ANTHROPIC_AUTH_TOKEN": ""},
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_AUTH_TOKEN"):
                LLMGateway()

    def test_default_provider_is_anthropic(self):
        with patch.dict(
            os.environ,
            {"ANTHROPIC_AUTH_TOKEN": "test-token"},
            clear=True,
        ):
            gateway = LLMGateway()
        self.assertEqual(gateway.provider, "anthropic")

    @patch("llm_gateway.httpx.post")
    def test_nvidia_chat_completions_remains_supported(self, mock_post):
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        mock_post.return_value = response
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "nvidia",
                "NVIDIA_API_KEY": "test-key",
                "NVIDIA_MODEL": "test-model",
            },
            clear=False,
        ):
            result = LLMGateway().generate("generator", "Return JSON", expect_json=True)

        self.assertEqual(mock_post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(result, '{"ok": true}')


if __name__ == "__main__":
    unittest.main()
