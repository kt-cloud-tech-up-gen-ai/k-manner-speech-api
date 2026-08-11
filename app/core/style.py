"""프로젝트 감정 라벨을 Gemini TTS용 연기 지시로 변환합니다."""

from app.schemas.emotion_group import Emotion

# Gemini TTS가 자연어 지시로 감정, 속도, 높낮이를 제어하도록 베이스라인을 정의합니다.
EMOTION_STYLES = {
    Emotion.ANGRY: "한국어 원어민처럼 말한다. 화가 난 감정을 분명히 표현하고 낮고 단호하게 말하되 원문을 바꾸지 않는다.",
    Emotion.HAPPY: "한국어 원어민처럼 말한다. 밝고 생기 있는 목소리로 평소보다 약간 빠르고 경쾌하게 말한다.",
    Emotion.EMBARRASSED: "한국어 원어민처럼 말한다. 당황한 감정을 표현하고 첫 부분은 놀란 듯 약간 머뭇거리며 말한다.",
    Emotion.CURIOUS: "한국어 원어민처럼 말한다. 호기심이 느껴지게 질문 끝을 자연스럽게 올려 말한다.",
    Emotion.SAD: "한국어 원어민처럼 말한다. 낮고 힘없는 목소리로 천천히 슬픔을 표현한다.",
    Emotion.NORMAL: "한국어 원어민처럼 감정을 과장하지 않고 일상적인 속도와 안정적인 높낮이로 말한다.",
}


def get_emotion_style(emotion: Emotion) -> str:
    """검증된 감정 Enum을 Gemini TTS에 전달할 한국어 연기 지시로 변환합니다."""

    return EMOTION_STYLES[emotion]
