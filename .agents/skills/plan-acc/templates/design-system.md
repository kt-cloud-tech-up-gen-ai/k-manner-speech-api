# Template: Design System

**Template ID:** `design-system` · **Revision:** 1 (created 2026-05-12)
**기획 관심사:** 디자인 토큰, 컴포넌트 API, 접근성(WCAG), Storybook 문서화, 테스트 커버리지

## Template Q&A

1. 이 컴포넌트(들)는 새로 만드는 건가요, 기존 것 확장인가요?
2. 디자인 토큰 변경이 포함되나요? (색상/타이포/스페이싱)
   - YES → 토큰 충돌 검증 방식은?
3. API 시그니처 props가 기존 컴포넌트와 일관되어야 하는 규칙이 있나요? (예: variant, size, disabled)
4. 접근성 요구 수준은? (WCAG 2.1 A / AA / AAA)
5. Storybook 스토리는 몇 개 필요한가요? (default, variants, error states, ...)
6. axe-playwright a11y 자동 검증 통과가 AC인가요?
7. 단위 테스트 커버리지 목표는? (기본 80%)
8. 배포 채널: npm public / GitHub Packages / monorepo local?
9. 브라우저 / 프레임워크 지원 매트릭스는?
10. 시각 회귀 테스트 (Chromatic, Percy 등)를 도입하나요?

## Mandatory AC Checklist

- [ ] 모든 새 컴포넌트는 Storybook 스토리 1개 이상 존재해야 한다.
- [ ] axe-playwright 0 violations를 통과해야 한다.
- [ ] 단위 테스트 커버리지 ≥ 80%를 달성해야 한다.
- [ ] 토큰 변경 시 visual diff를 첨부해야 한다.
- [ ] CHANGELOG.md에 변경 내용을 기록해야 한다.
