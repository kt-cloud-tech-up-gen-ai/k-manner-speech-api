"""프로젝트에서 사용하는 6개 감정 그룹."""

from enum import Enum


class Emotion(str, Enum):
    ANGRY = "화남"
    HAPPY = "기쁨"
    EMBARRASSED = "당황스러움"
    CURIOUS = "궁금"
    SAD = "슬픔"
    NORMAL = "보통"
