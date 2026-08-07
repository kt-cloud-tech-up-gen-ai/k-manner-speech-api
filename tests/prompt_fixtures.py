"""프롬프트 테스트용 최소 프롬프트 셋.

app/prompts/의 실제 파일에 의존하지 않기 위해, 테스트가 쓸 프롬프트를 여기에
하드코딩하고 임시 디렉터리에 풀어 쓴다.

이렇게 하는 이유:

1. 프로덕션 프롬프트 문구를 다듬을 때마다 테스트가 깨지지 않는다. 프롬프트는
   자주 손보는 콘텐츠인데, 그때마다 assertIn 문자열을 따라 고치게 되면 테스트가
   회귀 방지가 아니라 유지보수 비용이 된다.
2. 반대로 테스트가 특정 persona가 존재하기를 요구하지도 않는다. 실제로
   test_build_chat_prompt_includes_persona_and_question은 한 번도 만들어진 적 없는
   'friendly' persona 번들을 요구해 계속 실패하고 있었다.
3. 검증에 쓰는 문자열과 그 출처가 한 파일 안에 있어, 테스트를 읽을 때
   app/prompts/를 뒤질 필요가 없다.

프롬프트 조합 로직(우선순위 정렬, 번들 전개) 자체를 검증하는 것이 목적이므로
내용은 최소한으로만 둔다.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from app.prompt_builder.composer import PromptComposer

# 테스트가 프롬프트에서 찾을 문구. 조합 순서 검증에도 쓴다.
SAFETY_TEXT = "테스트용 안전 규칙이다."
CONCISE_TEXT = "테스트용 간결 문체다."
IDENTITY_TEXT = "테스트용 정체성이다."
PERSONALITY_TEXT = "테스트용 성격이다."

BUNDLE_NAME = "base_chat"
PERSONA_ID = "testpersona"

# priority가 높을수록 앞에 온다. 프로덕션과 같은 대소 관계를 유지해
# 조합 순서 검증이 실제 동작을 반영하게 한다.
_PROMPTS = {
    "rules/safety": {"priority": 100, "prompt": SAFETY_TEXT},
    "identities/friend": {"priority": 85, "prompt": IDENTITY_TEXT},
    "personalities/friendly": {"priority": 65, "prompt": PERSONALITY_TEXT},
    "styles/concise": {"priority": 40, "prompt": CONCISE_TEXT},
}

_BUNDLES = {
    BUNDLE_NAME: [("rules", "safety"), ("styles", "concise")],
    f"personas/{PERSONA_ID}": [
        ("identities", "friend"),
        ("personalities", "friendly"),
    ],
}


def _write_prompt_tree(root: Path) -> None:
    for key, body in _PROMPTS.items():
        path = root / f"{key}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump({"id": path.stem, "version": 1, **body}, allow_unicode=True),
            encoding="utf-8",
        )

    for name, items in _BUNDLES.items():
        path = root / "bundles" / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "id": path.stem,
                    "version": 1,
                    "prompts": [{"category": c, "name": n} for c, n in items],
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )


def use_fixture_prompts(test_case) -> PromptComposer:
    """이 테스트 동안 프롬프트 조합이 픽스처 셋만 보게 만든다.

    build_chat_prompt이 모듈 전역 composer를 쓰므로 그것까지 함께 바꿔치기한다.
    임시 디렉터리 정리와 patch 해제는 addCleanup으로 등록한다.
    """
    tmp = tempfile.TemporaryDirectory()
    test_case.addCleanup(tmp.cleanup)

    root = Path(tmp.name)
    _write_prompt_tree(root)

    composer = PromptComposer(root)
    patcher = patch("app.prompt_builder.general_chat.composer", composer)
    patcher.start()
    test_case.addCleanup(patcher.stop)

    return composer
