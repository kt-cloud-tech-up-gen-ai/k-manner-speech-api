import os
import shutil
import tempfile
import unittest

from app.prompt_builder.general_chat import build_chat_prompt
from app.prompt_builder.composer import PromptComposer


class ChatPromptSpecTests(unittest.TestCase):
    def test_build_chat_prompt_includes_persona_and_history(self):
        original_cwd = os.getcwd()
        tempdir = tempfile.mkdtemp()
        try:
            os.chdir(tempdir)
            prompt = build_chat_prompt(
                question="점심 메뉴는 무엇으로 할까요?",
                persona="friendly",
                history=[{"role": "user", "content": "안녕"}, {"role": "assistant", "content": "안녕!"}],
            )
            self.assertIn("친근한 친구처럼 대화한다", prompt)
            self.assertIn("점심 메뉴는 무엇으로 할까요?", prompt)
            self.assertIn("안녕", prompt)
            self.assertIn("대화 이력", prompt)
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(tempdir, ignore_errors=True)

    def test_compose_bundle_loads_all_prompt_components(self):
        composer = PromptComposer("app/prompts")

        prompt = composer.compose_bundle("base_chat")

        self.assertIn("안전하고 적절한 답변만 제공한다", prompt)
        self.assertIn("답변은 가능한 한 간결하게 작성한다", prompt)


if __name__ == "__main__":
    unittest.main()
