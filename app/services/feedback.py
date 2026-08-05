"""사용자 발화의 예절/매너를 LLM으로 평가한다."""

import json
import logging
import re

from app.services.llm import invoke_llm

logger = logging.getLogger(__name__)

# TODO(KAN-63): 평가 결과를 저장하지 않아 호출할 때마다 LLM을 다시 부른다.
#   피드백 이력이 필요하면 chat_feedbacks 테이블을 추가할 것. → app/models/chat.py
# TODO(KAN-63): 평가 기준(점수 배점, 항목)이 프롬프트에만 있고 기획 확정본이 아니다.
#   기준이 확정되면 FEEDBACK_PROMPT를 갱신할 것.

FEEDBACK_PROMPT = """\
# Task

너는 한국어 존댓말과 예절 표현을 가르치는 코치다.
아래 대화에서 **사용자(user)의 발화만** 평가한다. 상대(assistant)의 발화는 맥락 참고용이다.

평가 기준
- 존댓말/높임 표현의 적절성
- 상황과 상대에 맞는 예의 수준
- 무례하거나 오해를 살 수 있는 표현
- 더 자연스러운 대안 표현

반드시 아래 JSON 형식만 출력한다. 다른 텍스트는 절대 붙이지 않는다.

{{"score": 0-100 정수, "summary": "한두 문장 총평", "improvements": ["개선점1", "개선점2"]}}

# 대화

{transcript}
"""


def build_transcript(messages: list[tuple[str, str]]) -> str:
    return "\n".join(f"- {role}: {content}" for role, content in messages)


def parse_feedback(raw: str) -> dict:
    """LLM 응답에서 JSON 객체를 추출한다. 실패 시 원문을 총평으로 사용한다."""
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            score = data.get("score")
            improvements = data.get("improvements")
            return {
                "score": int(score) if isinstance(score, (int, float)) else None,
                "summary": str(data.get("summary") or ""),
                "improvements": [
                    str(item) for item in improvements if isinstance(improvements, list)
                ]
                if isinstance(improvements, list)
                else [],
            }

    logger.warning("Feedback response was not valid JSON; falling back to raw text")
    return {"score": None, "summary": text, "improvements": []}


def generate_feedback(messages: list[tuple[str, str]]) -> dict:
    prompt = FEEDBACK_PROMPT.format(transcript=build_transcript(messages))
    return parse_feedback(invoke_llm(prompt, temperature=0.2))
