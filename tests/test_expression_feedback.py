import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import EXPRESSION_FEEDBACK_MODEL
from app.main import app
from app.schemas.expression_feedback import (
    ExpressionFeedbackRequest,
    ExpressionFeedbackResponse,
    ExpressionIssue,
    ExpressionIssueType,
)
from app.services.expression_feedback import (
    ExpressionFeedbackConfigurationError,
    ExpressionFeedbackGenerationError,
    generate_expression_feedback,
)


def make_feedback() -> ExpressionFeedbackResponse:
    return ExpressionFeedbackResponse(
        feedback=(
            "지난주에 완료한 업무를 보고하는 상황이므로 "
            "과거형을 사용하는 것이 자연스럽습니다."
        ),
        suggested_text="저는 지난주에 고객 미팅을 진행했습니다.",
        issues=[
            ExpressionIssue(
                type=ExpressionIssueType.TENSE,
                expression="진행해요",
                suggestion="진행했습니다",
                reason="지난주에 완료된 업무를 나타내기 때문입니다.",
            )
        ],
    )


def make_request() -> ExpressionFeedbackRequest:
    return ExpressionFeedbackRequest.model_validate(
        {
            "text": "저는 지난주에 고객 미팅을 진행해요.",
            "context": {
                "previous_utterances": [
                    {
                        "speaker": "listener",
                        "text": "지난주에는 어떤 업무를 했어요?",
                    }
                ],
                "situation": "지난주 업무 보고",
                "relationship": "coworker",
                "relative_status": "peer",
                "formality": "polite",
                "communication_type": "spoken",
            },
        }
    )


class FakeResponses:
    def __init__(self, output: ExpressionFeedbackResponse | None) -> None:
        self.output = output
        self.request: dict | None = None

    async def parse(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.output)


class FakeOpenAIClient:
    def __init__(self, output: ExpressionFeedbackResponse | None) -> None:
        self.responses = FakeResponses(output)


def test_generate_expression_feedback_calls_terra_with_context_and_schema():
    expected = make_feedback()
    request = make_request()
    client = FakeOpenAIClient(expected)

    feedback = asyncio.run(generate_expression_feedback(request, client=client))

    assert feedback == expected
    assert client.responses.request["model"] == EXPRESSION_FEEDBACK_MODEL
    assert client.responses.request["text_format"] is ExpressionFeedbackResponse
    assert client.responses.request["reasoning"] == {"effort": "low"}
    assert client.responses.request["text"] == {"verbosity": "low"}
    assert "verbosity" not in client.responses.request
    assert client.responses.request["store"] is False

    model_input = json.loads(client.responses.request["input"])
    assert model_input["text"] == request.text
    assert model_input["context"]["previous_utterances"][0] == {
        "speaker": "listener",
        "text": "지난주에는 어떤 업무를 했어요?",
    }


def test_generate_expression_feedback_rejects_missing_parsed_output():
    client = FakeOpenAIClient(None)

    with pytest.raises(ExpressionFeedbackGenerationError):
        asyncio.run(generate_expression_feedback(make_request(), client=client))


def test_expression_feedback_endpoint_uses_context(monkeypatch):
    expected = make_feedback()

    async def fake_generate(request: ExpressionFeedbackRequest):
        assert request.text == "저는 지난주에 고객 미팅을 진행해요."
        assert request.context is not None
        assert request.context.formality.value == "polite"
        assert request.context.previous_utterances[0].speaker == "listener"
        return expected

    monkeypatch.setattr(
        "app.routers.routers.generate_expression_feedback",
        fake_generate,
    )

    response = TestClient(app).post(
        "/expression-feedback",
        json=make_request().model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_expression_feedback_endpoint_allows_omitting_context(monkeypatch):
    expected = ExpressionFeedbackResponse(
        feedback="자연스럽고 정중한 표현입니다.",
        suggested_text="자료를 보내 주실 수 있을까요?",
        issues=[],
    )

    async def fake_generate(request: ExpressionFeedbackRequest):
        assert request.context is None
        return expected

    monkeypatch.setattr(
        "app.routers.routers.generate_expression_feedback",
        fake_generate,
    )

    response = TestClient(app).post(
        "/expression-feedback",
        json={"text": "  자료를 보내 주실 수 있을까요?  "},
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_expression_feedback_endpoint_rejects_blank_text():
    response = TestClient(app).post(
        "/expression-feedback",
        json={"text": "   "},
    )

    assert response.status_code == 422


def test_expression_feedback_endpoint_rejects_invalid_context_enum():
    response = TestClient(app).post(
        "/expression-feedback",
        json={
            "text": "안녕하세요.",
            "context": {"formality": "very_polite"},
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ExpressionFeedbackConfigurationError("설정 오류"), 503),
        (ExpressionFeedbackGenerationError("호출 오류"), 502),
    ],
)
def test_expression_feedback_endpoint_maps_service_errors(
    monkeypatch,
    error: RuntimeError,
    expected_status: int,
):
    async def fake_generate(_: ExpressionFeedbackRequest):
        raise error

    monkeypatch.setattr(
        "app.routers.routers.generate_expression_feedback",
        fake_generate,
    )

    response = TestClient(app).post(
        "/expression-feedback",
        json={"text": "안녕하세요."},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}
