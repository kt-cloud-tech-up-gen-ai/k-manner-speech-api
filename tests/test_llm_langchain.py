import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.llm import ChatGeneration, invoke_llm, invoke_structured_llm


class LangChainChatProviderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
