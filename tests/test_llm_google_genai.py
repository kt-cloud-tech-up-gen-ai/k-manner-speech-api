import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.core.config import CHAT_MODEL
from app.services.llm_google_genai import (
    ChatGeneration,
    invoke_llm,
    invoke_structured_llm,
)


class _CapturingModels:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _client_with(response):
    models = _CapturingModels(response)
    return SimpleNamespace(models=models), models


class GoogleGenAIChatProviderTests(unittest.TestCase):
    @patch("app.services.llm_google_genai.get_api_key", return_value="test-key")
    @patch("app.services.llm_google_genai.get_chat_client")
    def test_plain_chat_returns_google_response_text(self, mock_client, _mock_key):
        client, models = _client_with(SimpleNamespace(text="안녕하세요"))
        mock_client.return_value = client

        answer = invoke_llm("완성된 프롬프트", temperature=0.4)

        self.assertEqual(answer, "안녕하세요")
        self.assertEqual(models.kwargs["model"], CHAT_MODEL)
        self.assertEqual(models.kwargs["contents"], "완성된 프롬프트")
        self.assertEqual(models.kwargs["config"].temperature, 0.4)

    @patch("app.services.llm_google_genai.get_api_key", return_value="test-key")
    @patch("app.services.llm_google_genai.get_chat_client")
    def test_structured_chat_validates_parsed_response(self, mock_client, _mock_key):
        client, models = _client_with(
            SimpleNamespace(
                parsed={
                    "answer": "반가워요!",
                    "response_style": "밝고 친근한 말투",
                }
            )
        )
        mock_client.return_value = client

        result = invoke_structured_llm("완성된 프롬프트")

        self.assertEqual(
            result,
            ChatGeneration(answer="반가워요!", response_style="밝고 친근한 말투"),
        )
        self.assertIs(models.kwargs["config"].response_schema, ChatGeneration)
        self.assertEqual(models.kwargs["config"].response_mime_type, "application/json")
        self.assertEqual(mock_client.call_count, 1)

    @patch("app.services.llm_google_genai.get_api_key", return_value="test-key")
    @patch("app.services.llm_google_genai.get_chat_client")
    def test_missing_parsed_response_is_bad_gateway(self, mock_client, _mock_key):
        client, _models = _client_with(SimpleNamespace(parsed=None))
        mock_client.return_value = client

        with self.assertRaises(HTTPException) as raised:
            invoke_structured_llm("완성된 프롬프트")

        self.assertEqual(raised.exception.status_code, 502)

    @patch("app.services.llm_google_genai.get_api_key", return_value=None)
    @patch("app.services.llm_google_genai.get_chat_client")
    def test_missing_key_is_service_unavailable_without_client(self, mock_client, _mock_key):
        with self.assertRaises(HTTPException) as raised:
            invoke_llm("프롬프트")

        self.assertEqual(raised.exception.status_code, 503)
        mock_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
