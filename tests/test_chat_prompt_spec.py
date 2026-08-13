import unittest

from app.prompt_builder.general_chat import build_chat_prompt
from tests.prompt_fixtures import (
    BUNDLE_NAME,
    CONCISE_TEXT,
    IDENTITY_TEXT,
    PERSONA_ID,
    PERSONALITY_TEXT,
    SAFETY_TEXT,
    use_fixture_prompts,
)


class PromptTestCase(unittest.TestCase):
    """프롬프트 조합 테스트의 공통 준비.

    app/prompts/의 실제 파일 대신 tests/prompt_fixtures.py의 최소 셋을 쓴다.
    이유는 그쪽 모듈 docstring 참고.
    """

    def setUp(self):
        self.composer = use_fixture_prompts(self)


class ChatPromptSpecTests(PromptTestCase):
    def test_build_chat_prompt_includes_persona_and_question(self):
        prompt = build_chat_prompt(
            question="점심 메뉴는 무엇으로 할까요?",
            persona=PERSONA_ID,
        )

        self.assertIn(IDENTITY_TEXT, prompt)
        self.assertIn(PERSONALITY_TEXT, prompt)
        self.assertIn("점심 메뉴는 무엇으로 할까요?", prompt)
        self.assertNotIn("대화 이력", prompt)

    def test_base_bundle_applies_even_without_persona(self):
        prompt = build_chat_prompt(question="안녕")

        self.assertIn(SAFETY_TEXT, prompt)
        self.assertIn(CONCISE_TEXT, prompt)
        self.assertNotIn(IDENTITY_TEXT, prompt)

    def test_prompts_are_ordered_by_priority(self):
        """priority가 높은 프롬프트가 앞에 온다. (safety 100 > 정체성 85 > 문체 40)"""
        prompt = build_chat_prompt(question="안녕", persona=PERSONA_ID)

        self.assertLess(prompt.index(SAFETY_TEXT), prompt.index(IDENTITY_TEXT))
        self.assertLess(prompt.index(IDENTITY_TEXT), prompt.index(CONCISE_TEXT))

    def test_compose_bundle_loads_all_prompt_components(self):
        prompt = self.composer.compose_bundle(BUNDLE_NAME)

        self.assertIn(SAFETY_TEXT, prompt)
        self.assertIn(CONCISE_TEXT, prompt)


class ScenarioChatPromptTests(PromptTestCase):
    def test_scenario_rules_are_rendered_before_the_question(self):
        prompt = build_chat_prompt(
            question="선배님, 교무처가 어디인지 여쭤봐도 될까요?",
            persona=PERSONA_ID,
            scenario={
                "id": "campus_directions_senior",
                "description": "후배가 도윤 선배에게 교무처 위치를 묻는 상황",
                "time_context": "평일 오후, 수업 시작 15분 전",
                "place_context": "캠퍼스 중앙 광장",
                "communication_goal": "존댓말로 위치를 묻고 안내를 확인한다",
                "end_condition": "본관 1층임을 확인하고 감사하면 종료",
                "max_turns": 10,
                "turn_limit_exit_line": "본관 1층 안내 데스크에 물어봐.",
            },
        )

        self.assertIn("## 현재 대화 시나리오", prompt)
        self.assertIn("시나리오의 관계·상황 설정", prompt)
        self.assertIn("페르소나의 일반 배경보다 우선", prompt)
        for expected in (
            "campus_directions_senior",
            "후배가 도윤 선배에게 교무처 위치를 묻는 상황",
            "평일 오후, 수업 시작 15분 전",
            "캠퍼스 중앙 광장",
            "존댓말로 위치를 묻고 안내를 확인한다",
            "본관 1층임을 확인하고 감사하면 종료",
            "10",
            "본관 1층 안내 데스크에 물어봐.",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, prompt)
        self.assertLess(prompt.index("## 현재 대화 시나리오"), prompt.index("사용자 질문:"))

    def test_scenario_omits_missing_optional_context(self):
        prompt = build_chat_prompt(
            question="안녕하세요",
            scenario={
                "id": "minimal",
                "description": "짧은 연습",
                "time_context": None,
                "place_context": None,
                "communication_goal": "정중하게 인사한다",
                "end_condition": "서로 인사하면 종료",
                "max_turns": 3,
                "turn_limit_exit_line": None,
            },
        )

        self.assertIn("정중하게 인사한다", prompt)
        self.assertNotIn("시간: ", prompt)
        self.assertNotIn("장소: ", prompt)
        self.assertNotIn("턴 상한 마무리: ", prompt)
        self.assertNotIn("None", prompt)

    def test_scenario_section_is_omitted_for_free_talk(self):
        prompt = build_chat_prompt(question="안녕하세요", scenario=None)

        self.assertNotIn("현재 대화 시나리오", prompt)
        self.assertNotIn("페르소나의 일반 배경보다 우선", prompt)


class ChatHistoryTests(PromptTestCase):
    """대화 이력을 프롬프트에 싣는 규약. (routers/rooms.py의 send_message가 쓴다)"""

    def test_history_is_rendered_as_labelled_turns_in_order(self):
        prompt = build_chat_prompt(
            question="그럼 언제 만날까요?",
            history=[
                {"role": "user", "content": "안녕하세요"},
                {"role": "assistant", "content": "네 안녕하세요"},
            ],
        )

        self.assertIn("## 대화 이력", prompt)
        self.assertIn("사용자: 안녕하세요", prompt)
        self.assertIn("상대: 네 안녕하세요", prompt)
        # 이력이 이번 질문보다 앞에 와야 한다.
        self.assertLess(prompt.index("사용자: 안녕하세요"), prompt.index("그럼 언제 만날까요?"))
        # 오래된 순서가 유지되어야 한다.
        self.assertLess(prompt.index("사용자: 안녕하세요"), prompt.index("상대: 네 안녕하세요"))

    def test_history_section_is_omitted_when_empty(self):
        for history in (None, [], [{"role": "user", "content": "   "}]):
            with self.subTest(history=history):
                prompt = build_chat_prompt(question="안녕", history=history)
                self.assertNotIn("대화 이력", prompt)

    def test_unknown_roles_are_dropped(self):
        """system 등 표시 규약이 없는 role이 프롬프트에 새어 들어가면 안 된다."""
        prompt = build_chat_prompt(
            question="안녕",
            history=[
                {"role": "system", "content": "내부 지침"},
                {"role": "user", "content": "실제 발화"},
            ],
        )

        self.assertNotIn("내부 지침", prompt)
        self.assertIn("사용자: 실제 발화", prompt)


class EmotionAwareChatPromptTests(PromptTestCase):
    def test_analysis_is_rendered_as_delimited_context(self):
        prompt = build_chat_prompt(
            question="안녕하세요",
            persona=PERSONA_ID,
            analysis={
                "emotion": "보통",
                "inferred_style": "정중하고 격식 있는 문어체",
                "intent": "인사 및 대화 시작",
            },
        )

        self.assertIn("## 현재 사용자 입력 분석", prompt)
        self.assertIn("감정: 보통", prompt)
        self.assertIn("추론 말투: 정중하고 격식 있는 문어체", prompt)
        self.assertIn("의도: 인사 및 대화 시작", prompt)
        self.assertIn("사용자 텍스트: 안녕하세요", prompt)
        self.assertIn(SAFETY_TEXT, prompt)
        self.assertIn(IDENTITY_TEXT, prompt)


if __name__ == "__main__":
    unittest.main()
