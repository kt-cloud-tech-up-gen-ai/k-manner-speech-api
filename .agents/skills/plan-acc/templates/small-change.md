# Template: Small Change

**Template ID:** `small-change` · **Revision:** 0 (proposed 2026-05-13)
**기획 관심사:** 동작 보존, 회귀 위험, 변경 범위 폭주 방지, 빠른 시각/자동 검증
**Scope guard:** XS (< 1h) or S (1–4h)만. M 이상이면 archetype 재라우팅 권장.

## Template Q&A

1. 변경 유형 분류:
   (a) pure refactor (no behavior change intended)
   (b) UX/UI rearrangement (사용자가 보는 위치/이름만)
   (c) cosmetic (comment, formatting, naming)
   (d) config / dependency
   (e) bug fix (intentional behavior change)
   (f) 복합 — 명시
2. 영향 파일/줄 수 예상: 1 file / 1–3 files / 3+ files?
3. 회귀 위험도:
   - 낮음 (격리된 변경, 단일 함수 내부)
   - 중간 (공유 utility, 여러 호출자)
   - 높음 (핵심 경로, 외부 인터페이스)
4. 보존 대상 명시: 어떤 동작/상태/key/시그니처를 그대로 두는가? (구체적으로)
5. 의도된 동작 변경 있음? YES면 그 변경을 명시 (회귀 vs 의도된 변경 구분)
6. 검증 방식:
   - 자동 테스트 그린 (기존 suite)
   - 수동 시각/기능 확인 (체크리스트로 enumerate)
   - 사용자 승인 필요한가?
7. 롤백 전략: 단순 git revert로 충분한가, 데이터 마이그레이션 동반인가?

## Mandatory AC Checklist

- [ ] 기존 자동 테스트가 모두 그린 상태여야 한다 (테스트가 없는 경우 명시할 것).
- [ ] "보존 대상"으로 명시된 항목이 실제로 정상 보존되었음을 한 줄씩 확인해야 한다.
- [ ] 의도되지 않은 동작 변경이 0건이어야 한다 (수동 체크리스트 등으로 검증).
- [ ] 변경 범위가 사전 추정 범위 대비 ±50% 이내여야 한다 (스코프 폭발 감지).
- [ ] 의도된 변경 사항이 있는 경우, 해당 동작도 별도 수동/자동 검증을 완료해야 한다.
- [ ] XS/S 스코프(최대 4시간) 안에서 완전히 완료되어야 한다 (초과 시 archetype 재라우팅).
