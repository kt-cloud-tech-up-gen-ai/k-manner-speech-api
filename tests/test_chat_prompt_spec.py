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


if __name__ == "__main__":
    unittest.main()
