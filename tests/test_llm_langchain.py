import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.llm import ChatGeneration, invoke_llm, invoke_structured_llm


class LangChainChatProviderTests(unittest.TestCase):
    @patch("app.services.llm.CHAT_MODEL", "gemini-3.1-flash-lite")
    @patch("app.services.llm.get_api_key", return_value="test-key")
    @patch("app.services.llm.get_chat_model")
    def test_plain_chat_uses_langchain_model(self, mock_model_factory, _mock_key):
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="안녕하세요")
        mock_model_factory.return_value = model

        answer = invoke_llm("프롬프트", temperature=0.4)

        self.assertEqual(answer, "안녕하세요")
        mock_model_factory.assert_called_once_with("test-key", 0.4)
        model.invoke.assert_called_once()

    @patch("app.services.llm.CHAT_MODEL", "gemini-3.1-flash-lite")
    @patch("app.services.llm.get_api_key", return_value="test-key")
    @patch("app.services.llm.get_chat_model")
    def test_structured_chat_uses_pydantic_schema(self, mock_model_factory, _mock_key):
        structured_model = Mock()
        structured_model.invoke.return_value = ChatGeneration(
            answer="반가워요!", response_style="밝고 친근한 말투"
        )
        model = Mock()
        model.with_structured_output.return_value = structured_model
        mock_model_factory.return_value = model

        result = invoke_structured_llm("프롬프트")

        self.assertEqual(result.answer, "반가워요!")
        self.assertEqual(result.response_style, "밝고 친근한 말투")
        model.with_structured_output.assert_called_once_with(ChatGeneration)


class OpenAIChatProviderTests(unittest.TestCase):
    @patch("app.services.llm.CHAT_MODEL", "gpt-5.6-luna")
    @patch("app.services.llm.get_openai_client")
    def test_plain_chat_uses_responses_api(self, mock_client):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(output_text="안녕하세요")
        mock_client.return_value = client

        answer = invoke_llm("프롬프트")

        self.assertEqual(answer, "안녕하세요")
        client.responses.create.assert_called_once_with(
            model="gpt-5.6-luna",
            reasoning={"effort": "low"},
            input="프롬프트",
            store=False,
        )

    @patch("app.services.llm.CHAT_MODEL", "gpt-5.6-luna")
    @patch("app.services.llm.get_openai_client")
    def test_structured_chat_uses_responses_parse(self, mock_client):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=ChatGeneration(
                answer="본관 1층이에요.", response_style="친절한 존댓말"
            )
        )
        mock_client.return_value = client

        result = invoke_structured_llm("프롬프트")

        self.assertEqual(result.answer, "본관 1층이에요.")
        self.assertIs(
            client.responses.parse.call_args.kwargs["text_format"], ChatGeneration
        )


if __name__ == "__main__":
    unittest.main()
