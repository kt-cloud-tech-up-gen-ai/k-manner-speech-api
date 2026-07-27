from app.prompts.personas.persona001 import persona


general_chat_prompt = "당신은 한국어를 배우려는 외국인과 대화하는 학습친구입니다."


def build_chat_prompt(question: str) -> str:
    return f"{general_chat_prompt}\n{persona}\n\n사용자 질문: {question}"