---
name: plan-acc
description: Accuracy-first planning that forbids assumptions, asks every clarifying question up front, and produces testable Acceptance Criteria with breaker checks. Use when the user invokes $plan-acc in Codex or /plan-acc in Claude Code, or asks for "정확하게 기획", "가정 없이 계획", "철저하게 기획", "AC 박힌 계획", or an implementation-ready plan with no unresolved questions.
---

# plan-acc — Accuracy-First Planning

**"Acc" = Accuracy.** Refuse to finalize the plan until every material ambiguity is resolved.

## When to use

- User wants a plan with **zero assumptions** and **fully testable AC**
- Explicit invocation: Codex `$plan-acc <goal>`; Claude Code `/plan-acc <goal>`
- Korean phrases: "정확하게 기획", "가정 없이 계획", "철저하게 기획", "AC 박힌 계획", "구현 중 질문 없게"

# Runtime Compatibility

- Use the current runtime's file-reading, shell, and plan-tracking tools. Do not require a provider-specific task API or model name.
- Keep the pipeline in the current agent by default. If the runtime supports delegation and the user or active project instructions permit it, delegate only independent research or review work; otherwise run those steps sequentially.
- Track tasks with the runtime's native plan mechanism when available (for example, Codex plan updates or Claude Code TodoWrite). If none exists, keep the task list in the output document.
- Treat `.claude/plan-acc/` as the project's existing shared artifact path; its name does not require Claude Code and Codex may write there.

# Inviolable Principles

These five rules **override** any instinct to be helpful via guessing. Violating any one means **the planning is incomplete.**

| # | Principle | Operational Test |
|---|-----------|------------------|
| 1 | **NO Assumptions** | If you can't quote the user (or evidence in repo) for a claim, you assumed. Ask instead. |
| 2 | **Ambiguity → Question** | Two valid interpretations = ambiguity = question required. Never pick one silently. |
| 3 | **All Questions Up-Front** | Before Phase 4 output, enumerate every question that could arise during implementation and ask them now. |
| 4 | **No Observation = Not Done** | An AC cannot be marked done while its `Observed:` is still `미관찰`. If you cannot write a Breaker for an AC, delete it or rewrite it — that AC protects nothing. |
| 5 | **Predetermined Templates** | Use one of 6 templates (5 vertical archetypes + small-change horizontal). No ad-hoc structure. If none fits, follow the fallback flow. |

# Pipeline

```
User Goal
   │
   ▼
Phase 0: Working Context Resolution
   │  Extract path/repo signals from goal + attached refs
   │  Compare against cwd's git root
   │  Skip if no signals OR all signals inside cwd
   │  Otherwise: user picks (cd / auto-mv after / accept orphan)
   ▼
Phase 1: Archetype Selection (research-driven)
   │  Match keywords → score 6 templates → confidence check
   │  If confident: pick top template
   │  If ambiguous: inspect repository evidence, then ask the user if still unresolved
   │  Tie-break rule: prefer user's frequency (Web > Game > Design=Tooling=AI/ML)
   ▼
[DYNAMIC TEMPLATE LOAD]
   │  Call your file reading tool on templates/<template-id>.md to read specific Q&A and AC criteria.
   ▼
Phase 2: Template Q&A (AC enforced)
   │  Run template-specific Q&A
   │  Front-load EVERY question (Principle 3)
   ▼
Phase 3: AC Validation + Breaker 검증
   │  Each task has objective, testable AC? GWT scenarios defined?
   │  Each AC has Verify/Breaker/Expect-red per the Universal AC gate?
   │  Run breaker.py, fold Observed back into the plan
   │  Fail → loop to Phase 2 with specific gaps
   ▼
Phase 4: Output
   │  → {resolved_output_repo}/.claude/plan-acc/{YYYY-MM-DD-HHmm}_{slug}.md
   │  → Runtime plan tracker, or document task list when unavailable
```

## Phase 0: Working Context Resolution

세션 출력은 `cwd/.claude/plan-acc/`에 저장됨. cwd가 작업의 evidence(proposal/log/feedback)나 target code 어느 쪽과도 무관하면 출력 파일이 고아가 됨. Phase 0은 archetype 선택 *전에* 이 mismatch를 검출하는 fail-safe.

**Signal extraction** — goal text + 사용자가 첨부한 파일 reference에서 추출:
- 절대 경로 (`/Users/...`, `~/...`), 명시적 repo 이름 멘션
- 이전 세션 로그 reference (`.claude/plan-acc/YYYY-MM-DD-HHmm_*.md` 슬러그)
- Proposal / feedback / log 파일 경로, `@`-prefixed file mentions 형태

**Resolution algorithm:**
```yaml
phase_0:
  step_1_cwd_root: "git rev-parse --show-toplevel"
  step_2_signal_roots: "각 추출 경로의 git root identify"
  step_3_skip_when:
    - "추출된 신호 0개 (goal이 순수 개념적)"
    - "추출된 모든 경로의 git root == cwd git root"
  step_4_mismatch_when:
    - "≥1개 신호 경로의 git root ≠ cwd git root"
  step_5_anchor_priority:
    rule: "여러 candidate repo가 있으면 다음 순서로 권장:"
    order:
      1: "Trigger evidence (proposal/log/feedback)를 담은 repo"
      2: "수정 대상 code가 있는 repo"
      3: "cwd (last resort)"
```

---

## Phase 1: Archetype Selection

**Keyword scoring** (sum matches per template):

| Template ID | Archetype | Trigger Keywords |
|-------------|-----------|------------------|
| **design-system** | Design System | 디자인 시스템, 컴포넌트, 토큰, Storybook, design token, component library, axe, a11y, WCAG, 디자인 라이브러리, 테마, props API |
| **agent-tooling** | Agent Tooling & Plugins | skill, hook, MCP, slash command, agent, automation, Codex, Claude Code, Antigravity, Obsidian, 큐, queue, claude-loop, install.sh, install-antigravity.sh, autonomous, plugin, plugin.json |
| **game-engine** | Game Engine | 게임, 바둑, 사활, canvas, WebGL, rendering, 60fps, 인터랙티브 보드, FPS, 게임 룰, WebWorker |
| **ml-research** | ML Research | 모델, 학습, training, 추론, inference, 벤치마크, dataset, fine-tuning, 데이터셋, 라벨링, annotation, mAP, IoU, recall, precision, object detection, segmentation, classification, computer vision, CV, LLM, embedding, RAG, wandb, hydra, DVC, Roboflow, MPS, CUDA, model checkpoint, hyperparameter, ablation, 재현성, seed |
| **web-application** | Web Application | 웹앱, API, frontend, backend, Firestore, 인증, REST, NestJS, Next.js, SvelteKit, FastAPI, Celery, Redis, 사용자, 로그인, 결제 |
| **small-change** | Small Change | 이동, 재배치, rearrange, restructure, rename, refactor, cleanup, tweak, polish, move, reorganize, fix typo, fix bug, dependency bump, simplify, consolidate, extract, inline, comment, docstring, 정리, 청소, 작은, minor, quick |

**Selection rules:**
```yaml
selection:
  step_1_score: "Match goal text against all 6 keyword sets, count hits per template"
  step_2_confidence:
    high: "Top score ≥ 3 AND top score > 2× second-best → auto-select"
    medium: "Top score 1-2 AND clear leader → confirm with user"
    low: "All scores 0-1 OR multiple tied → inspect repository evidence, then ask user"
  step_3_tie_break:
    rule: "When top 2 are tied or within 1 hit, prefer template with higher user frequency"
    frequency_priority: ["web-application", "game-engine", "design-system", "agent-tooling", "ml-research"]
```

---

## ⚡ DYNAMIC TEMPLATE LOAD RULE (CRITICAL)

**Once the Archetype is decided, you MUST dynamically load the matching template content before proceeding to Phase 2.**

1. Identify the selected `Template ID` (e.g., `web-application`).
2. Call your file reading tool on the template file located in the `templates/` subdirectory:
   - **Path**: `templates/<template-id>.md` (relative to the skill directory, e.g., `.agents/skills/plan-acc/templates/<template-id>.md` when the skill is installed in a repo).
3. Read the loaded template's specific Q&A and Acceptance Criteria list.
4. **DO NOT** assume or guess template questions. Always load the template dynamically using your file reading tool.

---

## Phase 2 & 3: Q&A, AC Validation, Breaker 검증

1. **Template Q&A**: Ask all template-specific questions loaded from `templates/<template-id>.md`.
2. **Validation**: Check user answers for vague words (`어차피`, `알아서`, `whatever`). Reject if vague. Enforce objective Given/When/Then ACs.
3. **Breaker 검증 실행**: AC가 확정되고(구현 완료 후, 또는 실행 가능한 시점에) 다음을 돌려 계획서가 아니라 **실제 저장소**에서 각 AC를 검증한다:
   ```
   python3 .agents/skills/plan-acc/breaker.py <plan.md> --repo <root>
   ```
   - 출력에 찍히는 `Observed:` 붙여넣기 텍스트를 계획서의 해당 AC에 그대로 반영한다. 계획서에 적힌 `Observed` 텍스트 자체는 판정 입력이 아니다 — 하네스가 실행할 때마다 다시 관측한 값만 진실이다.
   - `GUARDED`(또는 `--accept-unguarded`로 승인된 waiver)가 아닌 AC는 Phase 2로 되돌아가 Breaker/Verify/Expect-red를 다시 쓴다.
   - breaker를 댈 수 없는 AC는 Inviolable Principle 4에 따라 삭제하거나 다시 쓴다 — 그 AC는 아무것도 지키지 않는다.
   - 계획 밖에서(구현 중) 새로 추가한 검증도 이 게이트 대상이다. `--require-coverage`로 Base-SHA 이후 추가된 테스트가 GUARDED AC에 등록되었는지 확인한다.

### Universal AC gate

**적용 범위:** 이 게이트가 보는 것은 계획서에 적힌 AC뿐 아니라 **구현 중 새로 추가한 모든 검증**이다. 계획 밖에서 슬쩍 추가된 테스트도 `--require-coverage`를 통해 걸린다.

각 작업(AC)마다 다음 필드를 정확히 이 형식으로 채운다:

```markdown
### T{n}: {제목}
- **AC:**
  - Given {상황}, When {행위}, Then {기대}
  - **Verify:**     <타깃 테스트를 지목하는 실행 명령 한 줄>
  - **Breaker:**    `<파일경로>` :: `<old>` -> `<new>`
  - **Expect-red:** <리터럴 문자열. 정규식 아님>
  - **Observed:**   미관찰 | <breaker 적용 후 실제 출력 1~3행>
  - **Negative:**   (선택) <제품이 나쁜 입력·상태에서 어떻게 실패해야 하는가>
```

**필드 규칙:**

- `Verify`는 그 AC가 지목하는 **타깃 테스트로 좁힌다**(`pytest tests/x.py::test_y -q` 등). 광역 스위트·typecheck·lint·build는 계획 단위 게이트이지 AC breaker 판정 대상이 아니다.
- `Breaker` 문법은 3가지뿐이다:
  - 교체: `` `<path>` :: `<old>` -> `<new>` `` (백틱으로 감쌀 것. 빈 `new`는 `` `` ``)
  - 삭제: `` DELETE `<path>` ``
  - 이름변경: `` RENAME `<src>` -> `<dst>` ``
  - 시나리오가 여러 개인 AC는 `Breaker:`를 반복해도 된다(같은 AC의 `Expect-red`를 공유한다). 하네스가 시나리오 수와 breaker 수를 세어 미보호분을 출력한다.
- **Breaker에 "그 기능을 통째로 삭제" 또는 "테스트 코드를 수정"이라고 적는 것은 무효다.** breaker 경로가 테스트 경로 패턴에 매치하면 자기참조로 거부된다(`INVALID/self-referential`).
- `Expect-red`는 **리터럴 부분문자열**이다(정규식이 아니다). 전부 지켜야 통과한다:
  - 정규식 메타문자(`. ^ $ * + ? { } [ ] \ | ( )`) 없음
  - 길이 6자 이상
  - 일반 실패 어휘(`fail`, `error`, `assert`, `exception`, `panic`, `traceback` 등)만으로 구성되지 않음
  - **저장소의 테스트 소스 파일 어딘가에 그 리터럴이 그대로 존재**해야 한다 — 예: `assert x == y, "AC-T1-STORED-VALUE"`. 실패가 테스트에서 나왔음을 확인하는 핵심 방어선이다.
  - `Verify` 명령 문자열 자체에 포함되지 않음 (오라클 밀수 차단)
  - `Breaker`의 `new` 텍스트에 포함되지 않음 (breaker가 심은 심볼명을 시그니처로 쓰는 우회 차단)
- `Breaker: N/A — external-service | human-visual | hardware-perf | manual-approval` — 자동 breaker를 만들 수 없을 때만, 이 닫힌 목록에서만 사유를 고른다. 판정은 `UNGUARDED`(종료 코드 1)이며, `--accept-unguarded T7,T12`로 **정확한 AC ID 집합**을 승인해야 `PASS-WITH-WAIVERS`로 통과한다 — 개수만 맞추는 것은 무효다.
- `Observed`가 `미관찰`인 채로는 그 AC를 완료 표시할 수 없다(Inviolable Principle 4). 하네스는 매번 재실행하며, 계획서에 적힌 `Observed` 텍스트는 판정 입력이 아니다.

**하네스 실행법:**
```
python3 .agents/skills/plan-acc/breaker.py <plan.md> --repo <root> [--require-coverage] [--repeat N] [--accept-unguarded T7,T12] [--json]
```

---

## 이 게이트의 관할 경계

**`GUARDED`의 의미:** 반복 실행한 모든 표본에서 ① baseline 명령이 0으로 종료했고 ② mutant 명령이 비정상 종료했으며 ③ 정규화된 mutant 출력에 선언된 리터럴 시그니처가 있었고 ④ baseline 출력에는 없었으며 ⑤ 그 시그니처가 **테스트 소스 파일에서 온 문자열**이라는 뜻이다.

**보장하지 않는 것:** 그 편집이 요구 속성을 대표하는가 · 검증이 제품의 실제 진입점을 지나가는가 · 실패가 타깃 테스트 본문에서 발생했는가 · 편집과 실패 사이의 인과 · 그 AC 밖의 속성.

즉 이 게이트는 **"검증이 아무것도 관측하지 않는다"를 배제**하지, **"검증이 올바른 것을 관측한다"를 증명하지 않는다.**

이 정직한 경계를 숨기면 이 게이트가 고치려던 바로 그 과신이 재생산된다. 그래서 아래 표는 줄이지 않고 그대로 싣는다 — `GUARDED`가 나왔어도 다음은 **여전히 통과한다.**

| ID | 통과하는 것 | 실증 |
|---|---|---|
| **A** | **Breaker를 엉뚱한 계층·상수에 지목** | 프로덕션이 `RETRY_LIMIT`를 안 쓰는데 테스트는 상수만 본다 → GUARDED |
| **B** | **검증이 제품 진입점을 지나가지 않음** | validator는 옳게 테스트하나 `post_transfer`가 호출하지 않는다. 악의가 아니라 계층 배선 가정에서 나오는 함정 |
| **C** | **AC로 적히지 않은 속성** | 예: "flush 전 역방향 동기화"처럼 AC에 없는 요구 |
| **D** | **결합 회귀** | 두 곳을 동시에 바꿔야 드러나는 것. breaker는 단일 최소 편집 |
| **E** | **단일 mutant 과적합** | 작성자가 고른 mutant 하나를 죽인다고 같은 속성의 다른 결함까지 감지하는 것은 아니다 |
| **F** | **반복은 확률적 증거일 뿐** | `--repeat 2`는 flaky를 줄이지만 없애지 못한다 |
| **G** | **실패의 귀속 미확인** | 시그니처가 mutant 출력 어딘가에 있다는 것만 확인한다. 그것이 종료 원인인지, 타깃 테스트에서 나왔는지는 E-4(테스트 소스에 존재)로 간접 확인할 뿐 실행 시점 귀속은 아니다 |
| **H** | **상주성(residency)** | 실측 코퍼스에서 `Verification:` 의 19.7%(202/1024)가 grep/curl/육안이었다. 이런 Verify는 유효하지만 두 번 다시 실행되지 않는 관행을 막지 못한다 |
| **I** | **`Verify`의 부작용** | `.git` refs·objects 쓰기, 네트워크, 외부 DB, 데몬 이탈(`setsid`). 표준 라이브러리로 임의 명령을 샌드박싱할 수 없다 |
| **J** | **`Breaker: N/A` 사유의 진위** | 예: ERD 정합성을 `manual-approval`로 적었으나 실제로는 자동 비교 가능한 경우 — 하네스는 사유의 진위를 판정하지 못한다 |
| **K** | **좁은 `Verify`가 놓치는 것** | 통합 배선, 번들·export 계약, 테스트 순서 오염, 모노레포 호환성 (의도적 트레이드오프) |
| **L** | **시나리오–오라클 희석** | 실측 재측정에서 424개 블록이 시나리오 ≥2, 189개 블록이 ≥3이었다. AC 블록당 breaker 1개뿐이면 시나리오가 여러 개라도 1개만 보호된다. 하네스는 강제하지 않고 "n개 미보호"로 가시화만 한다 |
| **M** | **테스트 이름 일괄 나열** | 한 GUARDED 블록에 이름 여러 개를 적으면 전부 covered로 카운트된다(L과 다른 문제) |
| **N** | **탐지 못 하는 테스트 선언 형태** | Python — `pytest_generate_tests` 동적 생성·`setattr` 주입·metaclass·`unittest.FunctionTestCase`·상속 활성화·doctest·`parametrize` 케이스만 추가 / JS·TS — `test.each`·`it.concurrent.each`·`test(nameVariable, fn)`·`Deno.test({name,fn})`·`Bun.test`·팩토리 반복 생성·중첩 `describe` suite 경로 손실 / Go — `t.Run` 서브테스트·테이블 row 추가·testify suite 메서드·`Fuzz*`/`Benchmark*`/`Example*` / **Dart·Rust·Java는 아예 탐지 대상 밖** |
| **O** | **환경 의미론 차이** | SQLite↔PostgreSQL, headless CI↔GPU |
| **P** | **단일 행·UTF-8 텍스트 제약** | 여러 줄 편집·바이너리 파일은 breaker로 표현할 수 없다 → `INVALID` |

---

## Phase 4: Output Integration

1. **Planning Document**: Save the completed plan to `{resolved_output_repo}/.claude/plan-acc/{YYYY-MM-DD-HHmm}_{slug}.md`.
2. **Task Tracking**: Add tasks with the runtime's native plan tracker and embed Given/When/Then ACs. If no tracker exists, keep the same list in the planning document.

```markdown
# plan-acc: {goal}

**Date:** {ISO timestamp}
**Archetype:** {template name}
**Confidence:** {HIGH / MEDIUM / LOW}
**Selection method:** {selection method}
**Base-SHA:** {40자리 hex — `git rev-parse HEAD`}

## Q&A Log

### Template-specific
- **{Q1}:** {user answer}
- ...

## Tasks (with AC)

### T1: {task title}
- **Effort:** {S/M/L}
- **AC:**
  - Given {context}, When {action}, Then {expected}
  - **Verify:**     {타깃 테스트를 지목하는 실행 명령 한 줄}
  - **Breaker:**    `{path}` :: `{old}` -> `{new}`
  - **Expect-red:** {리터럴 문자열. 정규식 아님}
  - **Observed:**   미관찰
  - **Negative:**   (선택) {제품이 나쁜 입력·상태에서 어떻게 실패해야 하는가}
```
