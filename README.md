# K-MANNER SPEECH API

YAML 기반 프롬프트 조합 시스템과 한국어 표현 피드백 기능을 갖춘 FastAPI 채팅 API입니다.
정체성(identity)·성격(personality)·문체(style)·규칙(rule) 등을 YAML 파일로 분리해 두고,
우선순위에 따라 하나의 시스템 프롬프트로 합성한 뒤 Google Gemini에 질의합니다.
대화 종료 후 표현 평가는 OpenAI GPT-5.6 Luna의 Structured Outputs로 생성합니다.

- 버전: `0.0.1`
- 프레임워크: FastAPI + LangChain (`langchain-google-genai`)
- 기본 모델: `gemini-2.5-flash` (`app/core/config.py`의 `CHAT_MODEL`)
- 표현 피드백 모델: `gpt-5.6-luna` (`FEEDBACK_MODEL`로 변경 가능)

---

## 요구사항

- Python 3.10 이상 (`str | Path` 문법 사용)
- Google Gemini API 키 (선택 — 미설정 시 LLM 호출 없이 기본 문구를 반환)
- OpenAI API 키 (`/rooms/{room_id}/feedback` 사용 시 필요)

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 환경변수

`.env.example`을 복사해 `.env`를 만들고 키를 채웁니다.

```bash
cp .env.example .env
```

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `GOOGLE_API_KEY` | 선택 | Gemini API 키. 먼저 확인합니다. |
| `GEMINI_API_KEY` | 선택 | `GOOGLE_API_KEY`가 없을 때 사용하는 대체 키. |
| `OPENAI_API_KEY` | 표현 피드백 사용 시 | GPT-5.6 Luna Responses API 키. 서버 환경에만 저장합니다. |
| `FEEDBACK_MODEL` | 선택 | 표현 피드백 모델. 기본값은 `gpt-5.6-luna`. |
| `SUPABASE_URL` | 인증 사용 시 | Supabase 프로젝트 URL (`https://<project-ref>.supabase.co`). |
| `SUPABASE_ANON_KEY` | 인증 사용 시 | 공개용 클라이언트 키. 대시보드의 **Publishable key**(`sb_publishable_...`) 또는 Legacy API keys 탭의 anon 키(`eyJ...`). `SUPABASE_PUBLISHABLE_KEY`라는 이름으로 넣어도 됩니다. `service_role`/Secret 키는 사용 금지. |

`SUPABASE_*`가 비어 있으면 `/auth/login` 등 인증 엔드포인트가 503을 반환합니다
(나머지 API는 영향 없음). 값은 Supabase Dashboard > Project Settings > API 에서 확인합니다.

두 값 모두 비어 있으면 `/chat`은 LLM을 호출하지 않고
`"질문에 대한 답변을 준비했습니다. {question}"` 형태의 기본 문구를 반환합니다.

## 실행

```bash
uvicorn app.main:app --reload
```

- 기본 주소: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

> **반드시 저장소 루트에서 실행하세요.** `app/prompt_builder/general_chat.py`가
> `PromptComposer("app/prompts")`처럼 상대 경로를 사용하므로, 다른 디렉터리에서 실행하면
> 프롬프트 YAML을 찾지 못해 `FileNotFoundError`가 발생합니다.

---

## API

### `GET /health`

서버 상태를 점검합니다.

**요청**: 없음

**응답**

```json
{ "status": "ok" }
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | 정상일 때 `"ok"` |

```bash
curl http://127.0.0.1:8000/health
```

### `POST /chat`

사용자 질문에 LLM이 답변합니다.

**요청**

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `persona` | string | ✅ |페르소나 이름|
| `question` | string | ✅ | 사용자 질문 |

**응답**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `answer` | string | LLM의 답변 |

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "점심 메뉴는 무엇으로 할까요?"}'
```

```json
{ "answer": "..." }
```

LLM 호출 중 예외가 발생하면 HTTP 500 대신
`{"answer": "LLM 호출 중 오류가 발생했습니다: ..."}` 형태로 200 응답을 반환합니다.

> 이 엔드포인트는 **무상태(stateless)** 입니다. 대화 이력을 저장하지 않으며,
> 매 요청마다 프롬프트를 새로 합성해 단일 메시지로 전송합니다.

### `POST /rooms/{room_id}/feedback`

채팅방의 최근 대화에서 사용자 발화만 평가합니다. 상대 발화, persona, scenario는
맥락으로 사용하며 높임법·예의·상황 적합성·자연스러움을 각각 25점으로 평가합니다.

```bash
curl -X POST http://127.0.0.1:8000/rooms/<room_id>/feedback
```

```json
{
  "score": 80,
  "category_scores": {
    "honorifics": 18,
    "politeness": 18,
    "context_fit": 20,
    "naturalness": 24
  },
  "summary": "의도는 전달되지만 상대에 맞는 존댓말이 필요합니다.",
  "strengths": ["의도가 분명합니다."],
  "improvements": ["상대에게 맞는 종결 표현을 사용해 보세요."],
  "issues": [
    {
      "message_id": "...",
      "original": "야 뭐해",
      "category": "politeness",
      "explanation": "친하지 않은 상대에게는 지나치게 반말처럼 들릴 수 있습니다.",
      "suggestion": "지금 무엇을 하고 계세요?"
    }
  ],
  "cached": false
}
```

같은 마지막 메시지·모델·프롬프트 버전 조합의 결과는 `chat_feedbacks`에서 재사용하며,
이 경우 `cached`가 `true`입니다.

### `GET /auth/me`

로그인 사용자의 계정 정보와 온보딩 프로필을 함께 반환합니다. `Authorization: Bearer <access_token>` 필수(없으면 401).

> ⚠️ **변경 (breaking)**: 이전에는 계정 정보만 평평하게 반환했으나, 이제 `user` / `profile` 로 감싼 형태입니다.

프로필을 아직 저장하지 않은 사용자는 기본값이 내려오며, 이 조회는 DB에 아무것도 쓰지 않습니다.

```bash
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

```json
{
  "user": { "id": "9f0c...", "email": "me@example.com", "role": "authenticated" },
  "profile": {
    "native_language": "ko",
    "gender": "male",
    "learning_goals": ["travel", "business"],
    "study_frequency": "daily",
    "push_enabled": true,
    "updated_at": "2026-08-06T11:20:31+00:00"
  }
}
```

프로필이 없을 때의 `profile`: 모든 설정값이 `null`, `learning_goals`는 `[]`, `push_enabled`는 `false`, `updated_at`은 `null`.

### `PUT /auth/me/profile`

온보딩 프로필을 **전체 교체**합니다. 프로필이 없으면 새로 만듭니다. 인증 필수(없으면 401).

**요청** — 다섯 필드를 모두 명시해야 하며(누락 시 422), 값으로 `null`은 허용합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `native_language` | `"ko"` \| `"en"` \| null | 모국어 |
| `gender` | `male` \| `female` \| `other` \| `prefer_not_to_say` \| null | 성별 |
| `learning_goals` | 배열 (`daily_conversation`, `business`, `travel`, `exam`, `culture`, `other`) | 주요 학습 목적. 기존 선택을 통째로 대체하며, `[]`이면 모두 해제됩니다. 중복 값은 무시됩니다. |
| `study_frequency` | `daily` \| `five_per_week` \| `three_per_week` \| `twice_per_week` \| `weekly` \| null | 학습 빈도 |
| `push_enabled` | boolean | 푸시 알림 수신 여부 |

**응답** — 갱신된 프로필 객체(위 `GET /auth/me`의 `profile`과 같은 스키마).

```bash
curl -X PUT http://127.0.0.1:8000/auth/me/profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"native_language":"ko","gender":"male","learning_goals":["travel","business"],"study_frequency":"daily","push_enabled":true}'
```

```json
{
  "native_language": "ko",
  "gender": "male",
  "learning_goals": ["travel", "business"],
  "study_frequency": "daily",
  "push_enabled": true,
  "updated_at": "2026-08-06T11:20:31+00:00"
}
```

---

## 프로젝트 구조

```
app/
├── main.py                 # FastAPI 앱 생성 및 라우터 등록
├── core/
│   ├── config.py           # .env 로딩, 채팅/피드백 모델 정의
│   └── db.py               # SQLAlchemy 엔진과 세션
├── models/
│   └── chat.py             # 채팅방·메시지·피드백 모델
├── services/
│   ├── llm.py              # Gemini 채팅 호출
│   ├── openai_client.py    # OpenAI 클라이언트 생성
│   └── feedback.py         # Luna Structured Outputs 표현 평가
├── routers/
│   ├── routers.py          # /health, /chat, /ask_gemini
│   └── rooms.py            # 채팅방·메시지·피드백 API
├── prompt_builder/
│   ├── composer.py         # PromptComposer
│   └── general_chat.py     # 일반 채팅 프롬프트 조합
└── prompts/
    ├── identities/         # 정체성 (assistant, friend, professor)
    ├── personalities/      # 성격 (formal, friendly, humorous, tsundere)
    ├── styles/             # 문체 (concise, detailed, emoji, markdown)
    ├── rules/              # 규칙 (safety, no_hallucination, citation)
    ├── tasks/              # 작업 (explain, summarize, translate)
    └── modes/              # 모드 (interview, roleplay)
```

---

## 프롬프트 조합 시스템

### YAML 스키마

각 프롬프트 파일은 다음 형식을 따릅니다.

```yaml
id: friendly            # 식별자
version: 1              # 버전
description: 친근한 말투  # 설명 (선택)
priority: 65            # 합성 순서 (선택, 기본값 50)
enabled: true           # 사용 여부 (선택, 기본값 true)

prompt: |               # 필수 — 실제 프롬프트 본문
  # Personality

  친근하고 편안한 말투를 사용한다.
```

- `prompt` 필드가 없으면 `PromptComposer`가 `ValueError`를 발생시킵니다.
- `priority`가 **높을수록 앞쪽**에 배치됩니다 (내림차순 정렬).
- `enabled: false`인 프롬프트는 합성에서 제외됩니다.

### 합성 순서

`PromptComposer.compose_by_priority()`가 `priority` 내림차순으로 정렬한 뒤
각 `prompt` 본문을 빈 줄 두 개(`\n\n`)로 이어 붙입니다.
최종적으로 `general_chat.build_chat_prompt()`가 맨 뒤에 `사용자 질문: {question}`을 덧붙입니다.

### 현재 `/chat`에 사용되는 조합

`app/prompts/chat/general_chat.py`에 하드코딩되어 있습니다.

| 순서 | 카테고리 | 이름 | priority |
| --- | --- | --- | --- |
| 1 | rules | `safety` | 100 |
| 2 | rules | `no_hallucination` | 95 |
| 3 | identities | `friend` | 85 |
| 4 | personalities | `friendly` | 65 |
| 5 | styles | `concise` | 40 |

### 사용 가능한 프롬프트 전체 목록

| 카테고리 | 이름 | priority | 설명 |
| --- | --- | --- | --- |
| rules | `safety` | 100 | 안전·사실성·프라이버시·프롬프트 인젝션 방어 규칙 |
| rules | `no_hallucination` | 95 | 존재하지 않는 정보 생성 금지 |
| rules | `citation` | 75 | 신뢰성이 중요한 분야에서 출처 제시 |
| identities | `assistant` | 90 | 범용 AI 비서 |
| identities | `friend` | 85 | 친근한 친구 같은 말투 |
| identities | `professor` | 80 | 개념부터 설명하는 선생님 |
| personalities | `friendly` | 65 | 친근하고 편안한 말투 |
| personalities | `formal` | 60 | 정중하고 차분한 말투 |
| personalities | `humorous` | 55 | 적절한 유머 |
| personalities | `tsundere` | 50 | 츤데레 캐릭터 |
| tasks | `explain` | 80 | 핵심부터 설명하는 답변 방식 |
| tasks | `summarize` | 75 | 입력 내용 요약 |
| tasks | `translate` | 75 | 자연스러운 번역 |
| modes | `interview` | 70 | 한 번에 하나씩 질문하는 인터뷰 진행 |
| modes | `roleplay` | 70 | 역할극 수행 |
| styles | `detailed` | 45 | 배경지식·예시를 포함한 상세 설명 |
| styles | `concise` | 40 | 간결한 답변 |
| styles | `emoji` | 35 | 적절한 이모지 사용 |
| styles | `markdown` | 30 | Markdown 형식 활용 |

### 이름으로 조합하기

`compose_by_name()`을 사용하면 카테고리별 이름 목록만으로 프롬프트를 합성할 수 있습니다.

```python
from app.prompts.composer import PromptComposer

composer = PromptComposer("app/prompts")

prompt = composer.compose_by_name(
    identities=["professor"],
    personalities=["formal"],
    styles=["detailed", "markdown"],
    rules=["safety", "no_hallucination", "citation"],
    tasks=["explain"],
)
```

### 새 프롬프트 추가하기

1. 해당 카테고리 디렉터리에 `<이름>.yaml`을 만듭니다.
   (`app/prompts/personalities/calm.yaml` 등)
2. `id`, `version`, `priority`, `prompt` 필드를 작성합니다.
3. 기존 `priority` 값과 겹치지 않도록 배치 위치를 정합니다.
4. `general_chat.py`의 조합 목록 또는 `compose_by_name()` 호출에 추가합니다.

파일 이름이 곧 조합 시 사용하는 키입니다 (`composer.load("personalities", "calm")`).

---

## 알려진 제약 사항

- **실행 디렉터리 의존**: 프롬프트 경로가 상대 경로라 저장소 루트에서만 정상 동작합니다.
- **`.env` 로딩 경로**: `app/core/config.py`의 `ROOT` 계산이 `data/` 디렉터리를 찾지 못하면
  저장소 **상위** 디렉터리로 폴백합니다. 실제로는 뒤이어 호출되는 인자 없는 `load_dotenv()`가
  현재 작업 디렉터리 기준으로 `.env`를 찾아 로드하므로, 저장소 루트에서 실행하면 문제가 없습니다.
- **프롬프트 조합 고정**: `/chat`은 페르소나·문체를 요청으로 선택할 수 없고
  `general_chat.py`에 정의된 조합만 사용합니다.
- **대화 이력 없음**: 멀티턴 컨텍스트를 유지하지 않습니다 (`app/core/state.py`는 비어 있음).
- **`explain.yaml`의 `id` 불일치**: 파일명은 `explain`이지만 `id` 필드는 `behavior`입니다.
  로더는 파일명을 사용하므로 동작에는 영향이 없습니다.
