# AGENTS.md

이 파일은 Codex CLI가 이 저장소에서 세션을 시작할 때 자동으로 읽는 프로젝트 지침이다.
Claude Code 사용자는 `CLAUDE.md`가 아니라 이 파일과 `README.md`를 함께 참고한다.

## 프로젝트

FastAPI 기반 한국어 존댓말 스피킹 연습 API. 구조·환경변수·API 명세·마이그레이션 절차는
`README.md`에 있다. 코드를 건드리기 전에 `README.md`의 "프로젝트 구조"와 "의존 방향"을 먼저 읽는다.

## 공유 스킬

이 저장소는 팀 공용 스킬을 `.agents/skills/`에 담고 있다. Codex는 이 경로를 자동으로 스캔하므로
별도 설치가 필요 없다. 사용법과 각 스킬의 역할은 `README.md`의 "팀 공용 스킬" 절에 있다.
Codex에서 명시 호출할 때는 `$plan-acc`, `$sc-tdd-backend`처럼 `$<skill-name>`을 쓴다.
Claude Code의 `/plan-acc` 같은 슬래시 호출과 혼동하지 않는다. 자연어 요청이 `description`과
일치하면 Codex가 자동으로 선택할 수도 있다.

| 스킬 | 언제 쓰나 |
|------|-----------|
| `plan-acc` | 가정 없이 기획할 때. 모든 모호함을 질문으로 해소하고 breaker로 검증 가능한 AC를 강제한다. |
| `sc-test-design` | 테스트를 짜기 **전에** 테스트 케이스 명세를 설계할 때. 실행 코드가 아니라 리뷰 가능한 문서를 만든다. |
| `sc-tdd-backend` | 서버 사이드 TDD. API·서비스·마이그레이션 등 이 저장소 작업의 기본 경로. |
| `sc-tdd` | 백엔드/UI 구분이 모호할 때 도메인을 분류해 위 두 파이프라인으로 라우팅한다. |
| `sc-tdd-uiux` | 프론트엔드 TDD. `sc-tdd`가 라우팅하는 대상이라 함께 두며, 이 저장소에서 직접 쓸 일은 없다. |

## 이 저장소에서 지킬 것

- **테스트 먼저.** 새 동작을 추가할 때는 `sc-tdd-backend`를 따른다. 실패하는 테스트를 먼저 확인한 뒤 구현한다.
- **마이그레이션은 순서가 있다.** `migrations/versions/`를 수정하기 전에 `README.md`의 "적용 순서 주의"를 읽는다.
- **의존 버전은 고정되어 있다.** `requirements.txt`를 올리기 전에 `README.md`의 "의존성 버전 정책"에 근거를 적는다.
- **DB는 팀 공용이다.** Supabase `public` 스키마에 팀원 테이블이 함께 있다. 일괄 DROP·TRUNCATE 금지.
- **비밀값 금지.** `.env`는 커밋하지 않는다. 새 환경변수는 `.env.example`과 `README.md`에 함께 추가한다.

## 산출물 경로

`plan-acc`와 `sc-test-design`은 결과 문서를 `.claude/` 아래에 쓴다
(`.claude/plan-acc/`, `.claude/test-design/`, `.claude/test-roles.md`).
이 경로는 `.gitignore`에서 제외되어 있어 개인 작업물로 남는다 — 공유하려면 명시적으로 커밋한다.
