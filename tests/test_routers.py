import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.routers import AskGeminiRequest, GenerationConfig, ask_gemini


class AskGeminiTests(unittest.TestCase):
    def test_generation_config_is_optional(self):
        request = AskGeminiRequest(systemInstruction="system", contents="hello")
        self.assertIsNone(request.generationConfig)

    def test_unknown_generation_config_field_is_rejected_locally(self):
        with self.assertRaises(ValidationError):
            GenerationConfig(additionalProp1={})

    @patch("app.routers.routers.get_api_key", return_value="test-key")
    @patch("app.routers.routers.urlopen")
    def test_omitted_generation_config_is_not_sent_upstream(self, mock_urlopen, _mock_key):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"candidates":[{"content":{"parts":[{"text":"answer"}]}}]}'
        )

        response = ask_gemini(
            AskGeminiRequest(systemInstruction="system", contents="hello")
        )

        sent_request = mock_urlopen.call_args.args[0]
        self.assertNotIn("generationConfig", sent_request.data.decode("utf-8"))
        self.assertEqual(response.answer, "answer")

    @patch("app.routers.routers.get_api_key", return_value="test-key")
    @patch("app.routers.routers.urlopen")
    def test_upstream_400_is_exposed_as_client_error(self, mock_urlopen, _mock_key):
        mock_urlopen.side_effect = HTTPError(
            url="https://example.test",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"Unknown name additionalProp1"}}'),
        )

        with self.assertLogs("app.routers.routers", level="WARNING") as logs:
            with self.assertRaises(HTTPException) as raised:
                ask_gemini(AskGeminiRequest(systemInstruction="system", contents="hello"))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertNotIn("additionalProp1", raised.exception.detail)
        self.assertIn("additionalProp1", " ".join(logs.output))

    @patch("app.routers.routers.get_api_key", return_value="test-key")
    @patch("app.routers.routers.urlopen", side_effect=TimeoutError())
    def test_timeout_is_gateway_timeout(self, _mock_urlopen, _mock_key):
        with self.assertRaises(HTTPException) as raised:
            ask_gemini(AskGeminiRequest(systemInstruction="system", contents="hello"))
        self.assertEqual(raised.exception.status_code, 504)

    @patch("app.routers.routers.get_api_key", return_value="test-key")
    @patch("app.routers.routers.urlopen", side_effect=URLError("offline"))
    def test_connection_failure_is_bad_gateway(self, _mock_urlopen, _mock_key):
        with self.assertRaises(HTTPException) as raised:
            ask_gemini(AskGeminiRequest(systemInstruction="system", contents="hello"))
        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
