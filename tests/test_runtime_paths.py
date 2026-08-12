import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.core.config import ROOT, get_tts_settings


class RuntimePathTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_tts_settings.cache_clear()

    def test_prompt_loading_is_independent_of_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from app.prompt_builder.general_chat import build_chat_prompt; "
                        "print(build_chat_prompt('안녕하세요', persona='doyun'))"
                    ),
                ],
                cwd=outside,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, "AC-PROMPTS-REPO-ROOT-ANCHORED")
        self.assertIn("안녕하세요", completed.stdout)

    def test_tts_output_path_resolution_contract(self) -> None:
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "test-key", "TTS_OUTPUT_DIR": "var/audio"},
        ):
            get_tts_settings.cache_clear()
            relative = get_tts_settings().output_dir

        absolute_input = (ROOT.parent / "absolute-audio").resolve()
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "test-key", "TTS_OUTPUT_DIR": str(absolute_input)},
        ):
            get_tts_settings.cache_clear()
            absolute = get_tts_settings().output_dir

        self.assertEqual(relative, ROOT / "var/audio", "AC-TTS-OUTPUT-REPO-ROOT-ANCHORED")
        self.assertEqual(absolute, absolute_input)
