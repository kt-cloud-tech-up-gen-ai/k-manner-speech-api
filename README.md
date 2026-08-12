# K-MANNER SPEECH API

YAML 기반 프롬프트 조합 시스템과 한국어 표현 피드백 기능을 갖춘 FastAPI 채팅 API입니다.
정체성(identity)·성격(personality)·문체(style)·규칙(rule) 등을 YAML 파일로 분리해 두고,
우선순위에 따라 하나의 시스템 프롬프트로 합성한 뒤 Google Gemini에 질의합니다.
대화 종료 후 표현 평가는 Gemini의 구조화 출력으로 생성합니다.

- 버전: `0.0.1`
- 프레임워크: FastAPI + LangChain (`langchain-google-genai`)
- 기본 모델: `gemini-2.5-flash` (`app/core/config.py`의 `CHAT_MODEL`)
- 표현 피드백 모델: `gemini-2.5-flash` (`FEEDBACK_MODEL`로 변경 가능)

---

## 요구사항

- Python 3.10 이상 (`str | Path` 문법 사용). 3.14.3에서 전체 의존성 설치·테스트 검증 완료.
- Google Gemini API 키 (선택 — 미설정 시 LLM 호출 없이 기본 문구를 반환)
- Google Gemini API 키 (`/rooms/{room_id}/messages`, `/rooms/{room_id}/feedback` 사용 시 필요)

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

테스트를 돌리려면 개발용 의존성도 함께 설치합니다.

```bash
pip install -r requirements-dev.txt   # requirements.txt를 포함합니다
pytest
```

## 의존성 버전 정책

`requirements.txt`와 `requirements-dev.txt`는 **모든 패키지를 `==`로 고정**합니다.
고정 시점은 **2026-08-07**이며, 각 패키지의 당시 PyPI 최신 릴리스를 채택했습니다.

### 왜 고정했나

이전 `requirements.txt`는 버전 제약이 전혀 없어(`fastapi`, `langchain`, …) 설치 시점마다
서로 다른 조합이 깔렸습니다. 이 프로젝트에서 이는 이론적인 위험이 아니라 실제 위험입니다.

- **LangChain 생태계가 0.3 → 1.x 메이저 전환을 겪었습니다.** 제약 없는 `langchain`은
  전환 전후 어느 쪽이든 설치될 수 있어, 같은 커밋이 환경에 따라 다르게 동작합니다.
- **`pydantic`은 v1/v2 호환성 경계가 있고**, FastAPI ≥ 0.102.0 + Pydantic v2 조합에서는
  같은 모델이라도 요청/응답 OpenAPI 스키마가 분리 생성됩니다
  ([공식 문서](https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/)).
  버전이 흔들리면 API 문서 계약 자체가 흔들립니다.
- **`SQLAlchemy` 2.x + Alembic**은 마이그레이션 autogenerate 결과가 버전에 민감합니다.

### 검증 방법

고정 세트는 추측이 아니라 실제 설치로 확인했습니다.

1. Python 3.14.3 클린 venv에서 `pip install -r requirements.txt` 의존성 충돌 없이 resolve.
2. `pytest` 실행 결과 **88 passed / 49 subtests passed**.
3. 잔여 실패 1건은 의존성 버전과 무관한 기존 이슈입니다.
   - `test_chat_prompt_spec` — `app/prompts/personas/friendly.yaml` 파일 부재

### 변경 내역과 근거

| 항목 | 조치 | 사유 |
| --- | --- | --- |
| 전체 15개 패키지 | 버전 미지정 → `==` 고정 | 재현 가능한 빌드. 위 "왜 고정했나" 참조 |
| `langchain-core==1.5.3` | **신규 추가** | `app/services/llm.py`, `app/services/gemini.py`가 `langchain_core.messages`를 **직접 import** 하는데 선언이 없었음. `langchain-google-genai`의 전이 의존에 우연히 기대던 상태 — 상위 패키지가 의존성을 바꾸면 즉시 `ImportError` |
| `httpx==0.28.1`, `pytest==9.1.1` | **`requirements-dev.txt` 신규** | `tests/test_new_apis.py`가 `fastapi.testclient.TestClient`를 쓰고 이는 `httpx`를 요구하나 어디에도 선언이 없어, 클린 환경에서 테스트가 실행 불가였음 |
| `langchain`, `langchain-community`, `langchain-huggingface`, `langchain-text-splitters` | 고정하되 **제거 후보로 표시** | `app/`·`tests/` 전체 grep 결과 import 0건. 실제로 쓰이는 것은 `langchain-google-genai`와 `langchain-core` 뿐. 4개를 빼면 설치 패키지가 **84개 → 57개**로 줄어듦(langgraph·numpy·tokenizers·huggingface_hub·aiohttp 등이 딸려옴) |
| `python-multipart` | 고정하되 제거 후보로 표시 | `UploadFile`/`Form`을 쓰는 엔드포인트가 없음 |

> 제거 후보 5개는 **아직 지우지 않았습니다.** 향후 파일 업로드나 RAG(text-splitters,
> huggingface 임베딩) 도입 계획이 있다면 남겨두는 편이 낫고, 없다면 삭제해 설치 표면을
> 줄이는 것을 권합니다. 판단이 필요한 사안이라 이번 변경에서는 사실만 기록했습니다.

### 갱신 방법

```bash
# 최신 버전 확인
curl -s https://pypi.org/pypi/<package>/json | python3 -c "import sys,json;print(json.load(sys.stdin)['info']['version'])"
```

버전을 올린 뒤에는 반드시 **클린 venv 설치 + `pytest`**로 회귀를 확인하고,
이 표의 "고정 시점"을 갱신합니다.

## 환경변수

`.env.example`을 복사해 `.env`를 만들고 키를 채웁니다.

```bash
cp .env.example .env
```

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 선택 | 접속할 DB. 미설정 시 `postgresql+psycopg://postgres:postgres@localhost:5432/k_manner_speech`. **마이그레이션이 적용되는 대상이기도 하므로 값을 확인하고 실행하세요.** |
| `GOOGLE_API_KEY` | 선택 | Gemini API 키. 먼저 확인합니다. |
| `GEMINI_API_KEY` | 선택 | `GOOGLE_API_KEY`가 없을 때 사용하는 대체 키. |
| `FEEDBACK_MODEL` | 선택 | 표현 피드백 Gemini 모델. 기본값은 `gemini-2.5-flash`이며 `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY`를 사용합니다. |
| `SUPABASE_URL` | 인증 사용 시 | Supabase 프로젝트 URL (`https://<project-ref>.supabase.co`). |
| `SUPABASE_ANON_KEY` | 인증 사용 시 | 공개용 클라이언트 키. 대시보드의 **Publishable key**(`sb_publishable_...`) 또는 Legacy API keys 탭의 anon 키(`eyJ...`). `SUPABASE_PUBLISHABLE_KEY`라는 이름으로 넣어도 됩니다. 이 자리에 `service_role`/Secret 키를 넣지 마세요. |
| `SUPABASE_SERVICE_ROLE_KEY` | 회원 탈퇴 사용 시 | `service_role`(Secret) 키. `DELETE /auth/me`의 Supabase 계정 삭제에만 쓰입니다. 서버 환경변수로만 보관하고 클라이언트·로그·커밋에 노출 금지. 미설정 시 탈퇴 API만 503. |

`SUPABASE_*`가 비어 있으면 `/auth/login` 등 인증 엔드포인트가 503을 반환합니다
(나머지 API는 영향 없음). 값은 Supabase Dashboard > Project Settings > API 에서 확인합니다.

두 값 모두 비어 있으면 `/chat`은 LLM을 호출하지 않고
`"질문에 대한 답변을 준비했습니다. {question}"` 형태의 기본 문구를 반환합니다.

## 데이터베이스 마이그레이션

스키마는 Alembic으로 관리합니다. **애플리케이션이 테이블을 만들지 않으므로, 서버를 띄우기
전에 한 번은 적용해야 합니다.** 카탈로그 데이터(persona·시나리오·선택 가능한 조합)도
마이그레이션에 시드로 들어 있어, 어느 환경이든 upgrade만 하면 같은 값이 채워집니다.

```bash
alembic current          # 지금 DB가 어느 리비전인지
alembic upgrade head     # 최신까지 적용
```

- **저장소 루트에서 실행하세요.** `alembic.ini`가 루트에 있습니다.
- 적용 대상은 `DATABASE_URL`이 가리키는 DB입니다. 원격 DB를 가리키고 있지 않은지 먼저
  확인하세요 (`alembic current`가 어디에 붙는지도 같은 값을 따릅니다).
- 되돌릴 때는 `alembic downgrade -1` (한 단계). 모든 리비전에 `downgrade()`가 있습니다.

리비전 목록과 순서는 `alembic history`로 봅니다.

### 적용 순서 주의

`chat_rooms.status`·`turn_count`는 `server_default` 없이 NOT NULL입니다. 즉 **이 컬럼을 모르는
구 버전 코드가 붙어 있는 DB에 적용하면 채팅방 생성이 실패합니다.** 서비스가 떠 있는 DB에
적용할 때는 코드 배포와 함께 진행하거나, 해당 리비전에 `server_default`를 추가하세요.

### DBA에게 SQL만 넘겨야 할 때

```bash
alembic upgrade <현재리비전>:head --sql > migration.sql
```

접속 없이 SQL만 렌더합니다. 단 **SQLite로는 안 됩니다**(batch 연산이 테이블 반영을 요구).
`DATABASE_URL`이 PostgreSQL을 가리킬 때만 동작합니다.

## 실행

### 프런트엔드 로컬 연동

1. 이 저장소에서 `alembic upgrade head` 후 API를 `http://localhost:8000`으로 실행합니다.
2. 형제 `k-manner-speech-front/web` 저장소에서 `npm run api:generate`로 FastAPI OpenAPI 기반 타입을 갱신합니다.
3. 프런트의 `VITE_API_URL=http://localhost:8000`을 설정하고 `npm run dev`를 실행합니다.

인증은 Supabase 이메일/비밀번호 방식이며 access/refresh는 HttpOnly 쿠키, CSRF는
double-submit 쿠키/헤더를 사용합니다. 서버는 localhost:5173의 credential CORS를 허용합니다.
게스트는 서버가 서명한 익명 HttpOnly 쿠키로 방과 메시지를 소유하며, 사용자가 보낸 세 번째
메시지에 AI가 응답한 뒤 방이 완료됩니다. 로그인하면 현재 브라우저의 게스트 기록을 삭제합니다.

대화·피드백 보존 정책은 2년이지만 자동 삭제 작업은 이번 범위에 포함하지 않습니다. 회원
탈퇴 시 이름·이메일 등 개인정보와 프로필·목표·방·메시지·피드백을 즉시 삭제합니다.
staging/prod 배포와 외부 SLA/모니터링은 이번 범위에서 제외하며 로컬 JSON 구조화 로그를
사용합니다. API 테스트는 `python -m unittest discover -s tests -v`로 실행합니다.

```bash
uvicorn app.main:app --reload
```

- 기본 주소: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

> **반드시 저장소 루트에서 실행하세요.** `app/prompt_builder/general_chat.py`가
> `PromptComposer("app/prompts")`처럼 상대 경로를 사용하므로, 다른 디렉터리에서 실행하면
> 프롬프트 YAML을 찾지 못해 `FileNotFoundError`가 발생합니다.

---

## 팀 공용 스킬 (Codex · Claude Code)

이 저장소의 개발 워크플로우를 `.agents/skills/`에 프로젝트 스킬로 함께 둡니다.
별도 설치 없이 Codex CLI·IDE·앱과 Claude Code에서 같은 원본을 사용합니다.

```
.agents/skills/                     ← 스킬 원본 (단일 소스)
├── plan-acc/
│   ├── SKILL.md
│   ├── breaker.py                  ← AC 검증 하네스
│   └── templates/                  ← 아키타입별 질문지 6종
├── sc-test-design/SKILL.md
├── sc-tdd/SKILL.md
├── sc-tdd-backend/SKILL.md
└── sc-tdd-uiux/SKILL.md

.claude/skills -> ../.agents/skills ← Claude Code가 같은 원본을 읽는 심링크
AGENTS.md                            ← Codex용 저장소 지침과 기본 스킬 선택 규칙
```

`SKILL.md` 본문은 특정 모델명이나 Claude Code의 `Task`·`TodoWrite`에 의존하지 않습니다.
Codex는 현재 세션의 파일·셸·계획 도구를 사용하고, Claude Code는 대응하는 자체 도구를 사용합니다.
`.claude/plan-acc/`처럼 이름에 `claude`가 남은 경로는 기존 산출물 호환성을 위한 공유 작업
경로이며 Codex도 그대로 씁니다.

### Codex에서 사용하기

Codex는 실행 위치부터 저장소 루트까지의 `.agents/skills/`를 자동 스캔합니다. 저장소 루트나
그 하위 디렉터리에서 Codex를 열고 다음 중 하나로 사용합니다.

- **명시 호출:** 프롬프트에서 `$`로 스킬을 지목합니다.

  ```text
  $plan-acc /rooms 즐겨찾기 기능을 가정 없이 기획하고 AC까지 작성해줘.
  ```

- **목록에서 선택:** Codex CLI/IDE에서 `/skills`를 실행하거나 `$`를 입력해 스킬을 고릅니다.
- **자동 선택:** `SKILL.md`의 `description`과 요청이 맞으면 Codex가 스킬을 자동으로 선택할 수 있습니다.

  ```text
  /rooms 즐겨찾기 기능을 TDD로 구현해줘. 실패하는 테스트부터 확인해줘.
  ```

Codex는 스킬 변경을 자동 감지합니다. 목록에 갱신 내용이 보이지 않을 때만 Codex를 다시
시작합니다. 같은 이름이 두 번 보이면 개인 경로(`~/.agents/skills`)에도 같은 스킬이 있는
경우입니다. 선택 화면에서 이 저장소의 `.agents/skills/` 경로를 확인하세요.

### Claude Code에서 사용하기

Claude Code는 `.claude/skills` 심링크를 통해 같은 파일을 읽습니다. 스킬 이름을 슬래시
명령으로 호출하거나 자연어 트리거를 사용합니다.

```text
/plan-acc "/rooms 즐겨찾기 기능 추가"
```

Codex의 명시 호출은 `$plan-acc`, Claude Code의 명시 호출은 `/plan-acc`입니다.
예전 개인 설정에서 쓰던 `/sc:tdd-backend` 같은 콜론 명령은 이 저장소에 포함되지 않습니다.

### 스킬별 역할과 호출명

| 스킬 | 하는 일 | Codex | Claude Code |
| --- | --- | --- | --- |
| `plan-acc` | 가정 없이 질문을 먼저 해소하고 Given/When/Then AC와 breaker를 갖춘 계획을 만듭니다. | `$plan-acc` | `/plan-acc` |
| `sc-test-design` | 구현 전에 What/Who/Why·GWT·Negative를 갖춘 테스트 케이스 명세를 설계하고 역할별로 리뷰합니다. | `$sc-test-design` | `/sc-test-design` |
| `sc-tdd-backend` | 서버 사이드 red-green-refactor를 수행합니다. 이 저장소의 기본 구현 경로입니다. | `$sc-tdd-backend` | `/sc-tdd-backend` |
| `sc-tdd` | 요청의 백엔드/UI 범위가 불명확할 때 분류한 뒤 전문 파이프라인으로 연결합니다. | `$sc-tdd` | `/sc-tdd` |
| `sc-tdd-uiux` | 렌더링·인터랙션·접근성을 포함한 프론트엔드 TDD를 수행합니다. 이 백엔드 저장소에서는 보통 직접 쓰지 않습니다. | `$sc-tdd-uiux` | `/sc-tdd-uiux` |

### 전형적인 흐름

```text
1. plan-acc          → 질문 해소 → AC가 포함된 계획서
2. sc-test-design    → AC를 리뷰 가능한 테스트 케이스 명세로 변환
3. sc-tdd-backend    → 실패 테스트 확인 → 최소 구현 → 품질 게이트
```

`sc-tdd-backend`와 `sc-tdd-uiux`는 자체 첫 단계에서 `sc-test-design`을 읽고 따르므로 3번부터
명시 호출해도 테스트 설계 단계가 생략되지 않습니다.

### 산출물 경로

| 스킬 | 산출물 | 기본 커밋 여부 |
| --- | --- | --- |
| `plan-acc` | `.claude/plan-acc/{YYYY-MM-DD-HHmm}_{slug}.md` | 제외 |
| `sc-test-design` | `.claude/test-design/{YYYY-MM-DD-HHmm}_{slug}.md` | 제외 |
| `sc-test-design` | `.claude/test-roles.md` (없으면 기본 역할로 생성) | 제외 |

이 경로들은 `.gitignore` 대상이라 개인 작업물로 남습니다. 팀에 공유해야 할 때만
`git add -f <경로>`로 명시적으로 추가합니다.

### 스킬을 수정하거나 추가할 때

`.agents/skills/<이름>/SKILL.md`를 수정하거나 추가합니다. 두 도구가 다른 사본을 갖지 않도록
`.claude/skills` 아래에는 직접 파일을 만들지 않습니다. Codex에서는 `$skill-creator`로 생성·수정
작업을 요청할 수도 있습니다.

```markdown
---
name: my-skill
description: 무엇을 하는지와 언제 사용해야 하는지를 실제 트리거 문구와 함께 씁니다.
---

# my-skill

(도구에 종속되지 않은 실행 절차)
```

공통 호환성을 위해 frontmatter는 `name`과 `description`만 사용합니다. `description`은 Codex가
자동 선택할 때 보는 정보이므로 주요 용도와 `$my-skill`·`/my-skill` 같은 명시 호출 조건을 앞에
둡니다. 자세한 형식은 [OpenAI의 Build skills 문서](https://learn.chatgpt.com/docs/build-skills)를
참고하세요.

### 알아둘 제약

- Windows에서 Claude Code를 쓰면 `.claude/skills` 심링크가 일반 파일로 체크아웃될 수 있습니다.
  `git config core.symlinks true` 후 다시 체크아웃하거나 `.agents/skills`를 `.claude/skills`로
  복사하세요. Codex는 `.agents/skills/`를 직접 읽으므로 영향받지 않습니다.
- `plan-acc`의 breaker는 저장소 루트에서 실행합니다:
  `python3 .agents/skills/plan-acc/breaker.py <plan.md> --repo .`

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

### 카탈로그 (`/personas`, `/scenarios`)

대화 상대와 상황 목록입니다. 출처는 DB이며 값은 마이그레이션 시드로 들어갑니다
(→ [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)).

**목록과 단건이 담는 값이 다릅니다.** 목록은 *고르기 위한 정보*만, 단건은 *고른 뒤에 필요한
정보*까지 줍니다. 나눈 기준은 분량이 아니라 변경 속도입니다 — `communication_goal`·
`max_turns`처럼 프롬프트 규칙이 바뀔 때 함께 바뀌는 값이 목록에 섞이면, 내부 규칙을 손볼
때마다 목록 화면의 계약이 흔들립니다.

> 아래 예제는 `alembic upgrade head`만 적용한 DB에서 그대로 받은 응답입니다. SQLite로
> 뽑았기 때문에 `version`의 표기가 행마다 다릅니다(`...Z` / 오프셋 없음). SQLite는 컬럼에
> 타임존을 보존하지 않습니다. 운영 DB는 `timestamptz`이므로 모두 오프셋이 붙어 돌아옵니다.

#### `GET /personas`

```bash
curl http://127.0.0.1:8000/personas
```

```json
{
  "personas": [
    {
      "id": "doyun",
      "first_name": "도윤",
      "middle_name": null,
      "last_name": null,
      "age": 22,
      "gender": "male",
      "description": "도윤 / 캠퍼스 훈남 / 처음 만난 또래"
    }
  ]
}
```

`age`와 `gender`는 화면 표시용이 아니라 **말투를 정하는 값**입니다. 사용자와의 나이 차가
존댓말/반말을 가릅니다.

#### `GET /personas/{persona_id}`

상대 단건입니다. **고를 수 있는 시나리오 목록이 함께 실립니다.** 상대를 고른 화면에서 곧바로
상황을 고를 수 있도록 한 번에 내려 줍니다.

```bash
curl http://127.0.0.1:8000/personas/doyun
```

```json
{
  "id": "doyun",
  "first_name": "도윤",
  "middle_name": null,
  "last_name": null,
  "age": 22,
  "gender": "male",
  "description": "도윤 / 캠퍼스 훈남 / 처음 만난 또래",
  "relationship_description": "같은 캠퍼스에서 오늘 처음 만난 또래",
  "voice_id": null,
  "version": "2026-08-07T00:00:00Z",
  "scenarios": [
    {
      "id": "campus_directions",
      "description": "캠퍼스에서 처음 만난 또래에게 교무처 위치를 묻는 대화",
      "time_context": "평일 오후",
      "place_context": "캠퍼스 중앙 광장"
    },
    {
      "id": "interview",
      "description": "면접 상황 대화 연습",
      "time_context": "평일 오전",
      "place_context": "회사 회의실"
    },
    {
      "id": "roleplay",
      "description": "지정한 캐릭터와의 역할극 대화",
      "time_context": null,
      "place_context": null
    }
  ]
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `relationship_description` | string | 사용자와 이 상대의 관계. 호칭과 존대 수준을 정합니다. |
| `voice_id` | string \| null | ElevenLabs 음성 id. `null`이면 `ELEVENLABS_VOICE_ID` 기본 음성을 씁니다. |
| `version` | datetime | 정의가 마지막으로 바뀐 시각. 클라이언트 캐시 무효화에 씁니다. |
| `scenarios` | array | **이 상대로 고를 수 있는 시나리오.** id 오름차순. 원소는 목록과 같은 요약 형태입니다. |

`scenarios`가 빈 배열이면 이 상대로 준비된 상황이 아직 없다는 뜻입니다. 오류가 아닙니다.

**여기 없는 조합으로 `POST /rooms`를 호출하면 400입니다.**

```json
{
  "detail": "고를 수 없는 조합입니다: persona=doyun, scenario=unpaired. GET /personas/doyun 의 scenarios 목록에서 고르세요."
}
```

`scenario_id`를 보내지 않으면 조합 자체가 없으므로 검사하지 않습니다(상대만으로 만드는
방은 그대로 허용).

#### `GET /scenarios`

```bash
curl http://127.0.0.1:8000/scenarios
```

```json
{
  "scenarios": [
    {
      "id": "campus_directions",
      "description": "캠퍼스에서 처음 만난 또래에게 교무처 위치를 묻는 대화",
      "time_context": "평일 오후",
      "place_context": "캠퍼스 중앙 광장"
    },
    {
      "id": "interview",
      "description": "면접 상황 대화 연습",
      "time_context": "평일 오전",
      "place_context": "회사 회의실"
    },
    {
      "id": "roleplay",
      "description": "지정한 캐릭터와의 역할극 대화",
      "time_context": null,
      "place_context": null
    }
  ]
}
```

`time_context`·`place_context`는 배경 묘사라 없을 수 있습니다. `null`이면 화면에 표시하지
않으면 됩니다.

#### `GET /scenarios/{scenario_id}`

시나리오 단건입니다. 대화 진행 규칙과 **이 상황을 연습할 수 있는 상대 목록**이 함께 실립니다.

```bash
curl http://127.0.0.1:8000/scenarios/campus_directions
```

```json
{
  "id": "campus_directions",
  "description": "캠퍼스에서 처음 만난 또래에게 교무처 위치를 묻는 대화",
  "time_context": "평일 오후",
  "place_context": "캠퍼스 중앙 광장",
  "communication_goal": "교무처 위치를 정중하게 묻고 안내를 끝까지 확인한다",
  "end_condition": "교무처 위치를 안내받고 감사 인사를 하면 종료",
  "max_turns": 10,
  "version": "2026-08-08T00:00:00",
  "personas": [
    {
      "id": "doyun",
      "first_name": "도윤",
      "middle_name": null,
      "last_name": null,
      "age": 22,
      "gender": "male",
      "description": "도윤 / 캠퍼스 훈남 / 처음 만난 또래"
    }
  ]
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `communication_goal` | string | 사용자가 달성해야 하는 의사소통 목표. **표현 피드백의 채점 기준이 됩니다.** |
| `end_condition` | string | 대화를 끝내도 되는 조건. 충족하고 끝나면 방 상태가 `completed`입니다. |
| `max_turns` | int | 턴 상한. 왕복 1회를 1턴으로 셉니다. 여기 도달했는데 `end_condition`을 못 채우면 방 상태가 `failed`가 됩니다. |
| `personas` | array | 이 상황을 연습할 수 있는 상대. id 오름차순. |

시나리오가 턴 상한에서 대화를 매듭짓는 대사(`turn_limit_exit_line`)는 **응답에 넣지
않습니다.** 그 말은 대화 메시지로 전달되므로 카탈로그로 미리 내려 줄 이유가 없습니다.

#### 오류

| 상황 | 응답 |
| --- | --- |
| 없는 `persona_id` / `scenario_id` | `404` — `{"detail": "알 수 없는 persona입니다: ghost"}` |

id는 대소문자와 앞뒤 공백을 관대하게 받습니다(`DOYUN`, `  Doyun  ` 모두 같은 상대).

### 채팅방 (`/rooms`)

**이 계열은 전부 로그인이 필요합니다(Bearer).** 방 주인은 토큰이 정합니다 — 요청 본문이나
쿼리 파라미터로 `user_id`를 받지 않습니다. `room_id`로 접근하는 엔드포인트는 **남의 방과
없는 방에 똑같이 404**를 줍니다. 403으로 나누면 응답만으로 그 방이 실재한다는 사실이 새기
때문입니다.

> 아래 예제도 실제 응답입니다. 목록·내역 응답의 `created_at`에 오프셋(`Z`)이 없는 것은
> SQLite로 뽑았기 때문입니다(자세한 이유는 [카탈로그 절](#카탈로그-personas-scenarios)).

#### `POST /rooms`

```bash
curl -X POST http://127.0.0.1:8000/rooms \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"persona_id": "doyun", "scenario_id": "campus_directions", "name": "교무처 찾기"}'
```

```json
{
  "id": "22e707aed0e24e7b84747232a9eb0447",
  "user_id": "8b1f...",
  "persona_id": "doyun",
  "scenario_id": "campus_directions",
  "name": "교무처 찾기",
  "created_at": "2026-08-08T14:04:43.184854Z"
}
```

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `persona_id` | ✅ | 대화 상대. 대소문자·앞뒤 공백은 관대하게 받고 카탈로그의 id로 저장됩니다. |
| `scenario_id` | | **생략하거나 `null`이면 자유 대화방**입니다. 턴 상한도 종료 조건도 없이 계속 대화합니다. |
| `name` | ✅ | 방 이름. |

**`scenario_id`를 보낼 때는 그 상대로 고를 수 있는 조합이어야 합니다.**
`GET /personas/{persona_id}`의 `scenarios` 목록이 그 범위입니다.

```json
{
  "detail": "고를 수 없는 조합입니다: persona=doyun, scenario=cafe_order. GET /personas/doyun 의 scenarios 목록에서 고르세요."
}
```

**자유 대화방은 상대마다 하나**입니다. 상대가 N명이면 최대 N개를 가질 수 있습니다.
이미 있는데 또 만들면 409와 함께 기존 방의 id를 알려 줍니다.

```json
{
  "detail": "이미 이 상대와의 자유 대화방이 있습니다: room_id=93aabd61b85543f19f7aa8322224d6e4. 시나리오 없는 방은 상대마다 하나만 만들 수 있습니다."
}
```

| 상황 | 응답 |
| --- | --- |
| 토큰 없음·만료 | `401` |
| 없는 `persona_id` / `scenario_id` | `400` — `{"detail": "알 수 없는 persona입니다: ghost"}` |
| 고를 수 없는 조합 | `400` |
| 자유 대화방 중복 | `409` |
| `persona_id`·`scenario_id`가 빈 문자열이거나 공백뿐 | `422` |

마지막 줄이 중요합니다. **시나리오를 고르지 않겠다는 뜻은 필드를 생략하거나 `null`을 보내는
것**이며, 빈 문자열은 잘못된 요청으로 거부됩니다.

#### `GET /rooms`

내 방 목록을 최신 생성순으로 반환합니다. 파라미터는 없습니다.

```bash
curl http://127.0.0.1:8000/rooms -H "Authorization: Bearer <token>"
```

```json
{
  "rooms": [
    {
      "id": "93aabd61b85543f19f7aa8322224d6e4",
      "user_id": "8b1f...",
      "persona_id": "doyun",
      "scenario_id": null,
      "name": "도윤과 수다",
      "created_at": "2026-08-08T14:04:43.189749"
    }
  ]
}
```

#### `POST /rooms/{room_id}/messages`

```bash
curl -X POST http://127.0.0.1:8000/rooms/<room_id>/messages \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"question": "교무처가 어디예요?"}'
```

```json
{
  "answer": "교무처는 본관 2층에 있어.",
  "message": {
    "id": "d0559f4176b246d8ad3daee831f41369",
    "role": "assistant",
    "content": "교무처는 본관 2층에 있어.",
    "created_at": "2026-08-08T14:04:43.206867Z"
  }
}
```

사용자 메시지를 저장하고, 방의 persona와 최근 50건 이력으로 답변을 만들어 함께 저장합니다.
응답의 `message`는 **persona 쪽 메시지**입니다.

> **아직 시나리오가 대화에 반영되지 않습니다.** `scenario_id`는 저장만 되고 프롬프트에는
> 들어가지 않아, 시나리오가 있는 방과 자유 대화방의 프롬프트가 현재 동일합니다.
> `max_turns` 같은 값도 아직 대화에 영향을 주지 않습니다
> (`app/routers/rooms.py`의 `TODO(KAN-59/KAN-65)`).
> `communication_goal`은 예외로, 대화 프롬프트가 아니라
> [표현 피드백](#post-roomsroom_idfeedback)의 채점 입력으로만 쓰입니다.

#### `GET /rooms/{room_id}/messages`

오래된 순으로 전체 내역을 반환합니다.

```json
{
  "messages": [
    {
      "id": "af33d8f3f85e474b9140860582544445",
      "role": "user",
      "content": "교무처가 어디예요?",
      "created_at": "2026-08-08T14:04:43.205799"
    },
    {
      "id": "d0559f4176b246d8ad3daee831f41369",
      "role": "assistant",
      "content": "교무처는 본관 2층에 있어.",
      "created_at": "2026-08-08T14:04:43.206867"
    }
  ]
}
```

#### `DELETE /rooms/{room_id}`

```bash
curl -X DELETE http://127.0.0.1:8000/rooms/<room_id> -H "Authorization: Bearer <token>"
```

성공하면 `204`, 본문은 없습니다. **대화 내역과 피드백도 함께 사라지며 되돌릴 수 없습니다**
— 숨김 처리가 아니라 실제 삭제입니다. 자유 대화방을 지우면 그 상대의 자리가 비어 같은
상대로 다시 만들 수 있습니다.

### `POST /rooms/{room_id}/feedback`

채팅방의 최근 대화에서 사용자 발화만 평가합니다. 상대 발화, persona, scenario는
맥락으로 사용하며 높임법·예의·상황 적합성·자연스러움을 각각 25점으로 평가합니다.
시나리오가 있는 방은 그 시나리오의 `communication_goal`을 함께 보내며, 상황 적합성
점수는 이 목표에 맞는 표현인지로 판단합니다(자유 대화방은 목표 없이 평가합니다).

로그인이 필요하며 내 방만 평가합니다(남의 방·없는 방 모두 `404`).

```bash
curl -X POST http://127.0.0.1:8000/rooms/<room_id>/feedback \
  -H "Authorization: Bearer <token>"
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
이 경우 `cached`가 `true`입니다. LLM에 넣는 내용(지시문·입력 값)이 바뀌면 프롬프트 버전을
올리므로, 이전 버전으로 저장된 결과는 재사용되지 않고 다시 채점됩니다
(현재 `expression-feedback-v2`).

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

계층(타입)별로 나눈다. 각 디렉터리가 "무엇인가"가 아니라 "어떤 역할인가"로 묶인다.

```
app/
├── main.py                 # FastAPI 앱 생성 및 라우터 등록
├── core/                   # 앱 전역 인프라 (도메인 로직 없음)
│   ├── config.py           # .env 로딩, 채팅/피드백 모델 정의
│   ├── db.py               # SQLAlchemy 엔진과 세션
│   └── auth.py             # Supabase Auth 연동, 인증 의존성
├── models/                 # SQLAlchemy 엔티티 (= DB 테이블의 모양)
│   ├── user.py             # 사용자 프로필·학습 목적
│   ├── chat.py             # 채팅방·메시지·피드백
│   └── catalog.py          # persona·scenario
├── schemas/                # Pydantic DTO (= API 계약의 모양)
│   ├── auth.py             # 라우터와 1:1 대응
│   ├── chat.py
│   ├── health.py
│   ├── rooms.py
│   ├── catalog.py
│   └── voice.py
├── routers/                # HTTP 엔드포인트만. 로직은 services에 위임
│   ├── health.py           # GET /health
│   ├── chat.py             # POST /chat, /ask_gemini
│   ├── auth.py             # POST /auth/login, GET/PUT /auth/me*
│   ├── rooms.py            # 채팅방·메시지·피드백 API
│   ├── catalog.py          # GET /personas, /scenarios
│   └── voice.py            # POST /tts
├── services/               # 도메인 로직·외부 API 호출
│   ├── llm.py              # LangChain 경유 채팅 (프롬프트 조합 적용)
│   ├── gemini.py           # Gemini REST 직접 호출 (/ask_gemini 전용)
│   ├── feedback.py         # Luna Structured Outputs 표현 평가
│   ├── catalog.py          # persona/scenario YAML 조회
│   └── tts.py              # ElevenLabs 음성 합성
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

### 의존 방향

```
routers  ->  services  ->  core
   |            |
   +----> schemas <-------- models (enum 재사용)
```

**routers는 services를 import하지만 그 반대는 없다.** 이 방향이 뒤집히면
라우터 파일 하나를 고칠 때 서비스 계층이 함께 흔들린다.

### 데이터 모델

테이블은 마이그레이션이 만듭니다(→ [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)).

| 테이블 | 역할 |
| --- | --- |
| `personas` | 대화 상대 카탈로그. id는 `"doyun"`처럼 사람이 읽는 자연키. |
| `scenarios` | 상황 카탈로그. 목표·종료 조건·턴 상한을 갖는다. |
| `persona_scenarios` | **어떤 상대로 어떤 상황을 고를 수 있는지.** N:N 매핑이며 복합 PK `(persona_id, scenario_id)`. 여기 없는 조합으로는 방을 만들 수 없다. |
| `chat_rooms` | 채팅방. 주인(`user_id`)·상대·상황과 진행 상태를 가진다. |
| `chat_messages` | 대화 내역. 방을 지우면 함께 삭제된다. |
| `chat_feedbacks` | 표현 피드백 결과. 방을 지우면 함께 삭제된다. |
| `user_profiles`, `user_learning_goals` | 온보딩 설정. |

`chat_rooms`에는 제약이 둘 있습니다.

- `ck_chat_rooms_status` — 진행 상태는 `in_progress` / `completed` / `failed` / `abandoned`
  넷 중 하나. `failed`는 턴 상한에 도달했는데 종료 조건을 못 채운 경우입니다.
- `uq_chat_rooms_free_talk` — `WHERE scenario_id IS NULL`이 붙은 **부분** 유니크 인덱스로,
  자유 대화방을 사용자-상대 당 하나로 묶습니다. 시나리오가 있는 방은 대상이 아니라
  같은 조합으로 몇 개든 만들 수 있습니다.

`user_id`는 Supabase `auth.users`의 id이며 스키마 소유가 달라 FK를 걸지 않습니다(논리 참조).

### models와 schemas를 왜 나누나

`models/`는 DB 테이블의 모양, `schemas/`는 API 계약의 모양이다. 둘은 서로 다른
속도로 변한다. 컬럼을 추가해도 응답에 노출할지는 별개 결정이고, 반대로 응답 형태를
바꾸는 데 마이그레이션이 필요하지도 않다. 라우터는 `_to_room_response()` 같은
명시적 변환 함수로 둘을 잇는다 — 어떤 필드가 밖으로 나가는지 코드에 그대로 보인다.

### 왜 도메인별(`app/domains/<feature>/`)이 아닌가

도메인 수직 슬라이스를 권하는 [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)의
README 자체가 그 전제를 밝힌다 — 타입별 구조는 "마이크로서비스나 소규모 프로젝트에
잘 맞고, 도메인이 많은 모놀리스에서 깨진다". 이 프로젝트는 약 2,000 LOC에 라우터
6개다. FastAPI 공식 문서의 [Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)와
공식 템플릿([full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template))도
모두 타입별 레이어를 쓴다.

도메인이 늘어 라우터 파일 하나를 고칠 때 다른 도메인 파일을 계속 함께 열게 되면
그때 전환을 검토한다. 전환 임계치를 수치로 제시한 출처는 없다.

### DTO 네이밍 규칙

`app/schemas/__init__.py`의 모듈 docstring에 정리해 두었다. 요약하면
`<리소스><동작?>Request/Response`이며, 리소스 이름은 대응하는 도메인 모델과 맞춘다
(`ChatMessage` → `ChatMessageResponse`).

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
