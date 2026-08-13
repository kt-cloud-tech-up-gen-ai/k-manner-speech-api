import unittest
from pathlib import Path
from unittest.mock import Mock

from app.schemas.conversation import ConversationResponse
from app.schemas.emotion_group import Emotion
from app.schemas.emotion_tts import EmotionTtsResponse
from app.schemas.user_input import UserInputAnalysis
from app.services.feedback import CategoryScores, FeedbackMessage, FeedbackResult


class RoomConversationTests(unittest.TestCase):
    @staticmethod
    def _conversation() -> ConversationResponse:
        return ConversationResponse(
            input_type="text",
            source_text="안녕하세요",
            persona="doyun",
            analysis=UserInputAnalysis(
                user_text="안녕하세요",
                user_emotion=Emotion.NORMAL,
                user_speaking_style=None,
                inferred_style="정중한 말투",
                user_intent="인사",
            ),
            answer="반가워요!",
            response_style="밝은 말투",
            audio=EmotionTtsResponse(
                text="반가워요!",
                speaking_style="밝은 말투",
                audio_path=str(Path("app/outputs/result.wav").resolve()),
                metadata_path=str(Path("app/outputs/result.json").resolve()),
                tts_provider="gemini",
                tts_model="gemini-3.1-flash-tts-preview",
                voice_name="Kore",
            ),
            processing_time_ms=100,
        )

    @staticmethod
    def _feedback() -> FeedbackResult:
        return FeedbackResult(
            score=90,
            category_scores=CategoryScores(
                honorifics=22, politeness=23, context_fit=22, naturalness=23
            ),
            summary="자연스럽고 예의 바른 인사입니다.",
            strengths=["존댓말이 자연스럽습니다."],
            improvements=[],
            issues=[],
        )

    def test_text_turn_combines_conversation_and_feedback_with_room_context(self):
        from app.schemas.room_conversation import RoomConversationContext, TextRoomTurnRequest
        from app.services.room_conversation import RoomConversationService

        conversation = Mock()
        conversation.process_text.return_value = self._conversation()
        feedback = Mock(return_value=self._feedback())
        service = RoomConversationService(conversation, feedback)
        context = RoomConversationContext(
            room_id="room-1",
            user_id="user-1",
            persona_id="doyun",
            persona_description="도윤 / 처음 만난 또래",
            scenario_description="캠퍼스 길 묻기",
            communication_goal="자연스럽게 길 묻기",
            scenario_context={
                "id": "ask-directions",
                "description": "캠퍼스 길 묻기",
                "communication_goal": "자연스럽게 길 묻기",
            },
            history=[{"role": "assistant", "content": "무엇을 도와드릴까요?"}],
            feedback_messages=[FeedbackMessage(id="m1", role="user", content="안녕하세요")],
        )

        result = service.process_text(TextRoomTurnRequest(text="안녕하세요"), context)

        self.assertEqual(result.conversation.answer, "반가워요!")
        self.assertEqual(result.feedback.score, 90)
        conversation_request = conversation.process_text.call_args.args[0]
        self.assertEqual(conversation_request.persona, "doyun")
        self.assertEqual(conversation.process_text.call_args.kwargs["history"], context.history)
        self.assertEqual(
            conversation.process_text.call_args.kwargs["scenario"],
            context.scenario_context,
        )
        self.assertEqual(feedback.call_args.kwargs["user_id"], "user-1")
        self.assertEqual(feedback.call_args.kwargs["communication_goal"], "자연스럽게 길 묻기")

    def test_replace_answer_preserves_feedback_and_regenerates_conversation(self):
        from app.schemas.room_conversation import RoomConversationResult
        from app.services.room_conversation import RoomConversationService

        conversation = Mock()
        original = self._conversation()
        replacement = original.model_copy(
            update={
                "answer": "수업 시간이 다 돼서 가봐야 해.",
                "audio": original.audio.model_copy(
                    update={"text": "수업 시간이 다 돼서 가봐야 해."}
                ),
            }
        )
        conversation.replace_answer.return_value = replacement
        service = RoomConversationService(conversation, Mock())
        result = RoomConversationResult(
            conversation=original,
            feedback=self._feedback(),
        )

        replaced = service.replace_answer(result, replacement.answer)

        conversation.replace_answer.assert_called_once_with(original, replacement.answer)
        self.assertEqual(replaced.conversation.answer, replacement.answer)
        self.assertEqual(replaced.conversation.audio.text, replacement.answer)
        self.assertEqual(replaced.feedback, result.feedback)

    def test_openapi_uses_room_turn_routes_only(self):
        import app.main

        paths = app.main.app.openapi()["paths"]
        self.assertIn("/rooms/{room_id}/turns/text", paths)
        self.assertIn("/rooms/{room_id}/turns/voice", paths)
        self.assertIn("/voice/emotion-analysis", paths)
        self.assertNotIn("/api/v1/conversation/text", paths)
        self.assertNotIn("/api/v1/conversation/voice", paths)


if __name__ == "__main__":
    unittest.main()
