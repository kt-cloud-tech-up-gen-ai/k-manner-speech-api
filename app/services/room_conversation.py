"""Room 문맥을 Conversation과 Feedback 서비스에 동시에 전달한다."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from app.schemas.conversation import (
    ConversationResponse,
    TextConversationRequest,
    VoiceConversationRequest,
)
from app.schemas.room_conversation import (
    RoomConversationContext,
    RoomConversationResult,
    TextRoomTurnRequest,
    VoiceRoomTurnRequest,
)
from app.services.feedback import FeedbackResult


class ConversationProcessor(Protocol):
    def process_text(self, request, *, history=None, scenario=None): ...
    def process_voice(self, request, *, history=None, scenario=None): ...
    def replace_answer(
        self, response: ConversationResponse, answer: str
    ) -> ConversationResponse: ...


FeedbackGenerator = Callable[..., FeedbackResult]


class RoomConversationService:
    """Conversation 결과와 사용자 표현 피드백을 한 Room 턴으로 결합한다."""

    def __init__(
        self,
        conversation: ConversationProcessor,
        feedback_generator: FeedbackGenerator,
    ) -> None:
        self.conversation = conversation
        self.feedback_generator = feedback_generator

    def process_text(
        self, request: TextRoomTurnRequest, context: RoomConversationContext
    ) -> RoomConversationResult:
        conversation_request = TextConversationRequest(
            text=request.text, persona=context.persona_id
        )
        return self._process(self.conversation.process_text, conversation_request, context)

    def process_voice(
        self, request: VoiceRoomTurnRequest, context: RoomConversationContext
    ) -> RoomConversationResult:
        conversation_request = VoiceConversationRequest(
            transcript=request.transcript,
            persona=context.persona_id,
            audio_base64=request.audio_base64,
            audio_mime_type=request.audio_mime_type,
            duration_seconds=request.duration_seconds,
        )
        return self._process(self.conversation.process_voice, conversation_request, context)

    def replace_answer(self, result: RoomConversationResult, answer: str) -> RoomConversationResult:
        conversation = self.conversation.replace_answer(result.conversation, answer)
        return result.model_copy(update={"conversation": conversation})

    def _process(
        self, conversation_method, conversation_request, context: RoomConversationContext
    ) -> RoomConversationResult:
        with ThreadPoolExecutor(max_workers=2) as executor:
            conversation_future = executor.submit(
                conversation_method,
                conversation_request,
                history=context.history,
                scenario=context.scenario_context,
            )
            feedback_future = executor.submit(
                self.feedback_generator,
                context.feedback_messages,
                persona=context.persona_description,
                scenario=context.scenario_description,
                communication_goal=context.communication_goal,
                user_id=context.user_id,
            )
            conversation = conversation_future.result()
            feedback = feedback_future.result()
        return RoomConversationResult(conversation=conversation, feedback=feedback)
