import unittest

from app.prompt_builder.general_chat import build_chat_prompt
from app.prompt_builder.composer import PromptComposer


class ChatPromptSpecTests(unittest.TestCase):
    def test_build_chat_prompt_includes_persona_and_question(self):
        prompt = build_chat_prompt(
            question="점심 메뉴는 무엇으로 할까요?",
            persona="friendly",
        )

        self.assertIn("친근한 친구처럼 대화한다", prompt)
        self.assertIn("점심 메뉴는 무엇으로 할까요?", prompt)
        self.assertNotIn("대화 이력", prompt)

    def test_compose_bundle_loads_all_prompt_components(self):
        composer = PromptComposer("app/prompts")

        prompt = composer.compose_bundle("base_chat")

        self.assertIn("안전하고 적절한 답변만 제공한다", prompt)
        self.assertIn("답변은 가능한 한 간결하게 작성한다", prompt)


class ChatHistoryTests(unittest.TestCase):
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
