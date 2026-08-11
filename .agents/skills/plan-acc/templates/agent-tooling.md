# Template: Agent Tooling & Plugins

**Template ID:** `agent-tooling` · **Revision:** 2 (updated 2026-05-25)
**기획 관심사:** Skill/Hook/MCP/Plugin 통합, 자율 실행, CLI 설치, 에러 회복, Vault 통합

## Template Q&A

1. 통합 타입은? (Antigravity plugin / Claude skill / hook / MCP server / CLI / 복합)
2. 호출 방식은? (slash command / 자동 활성화 / hook 트리거 / cron / skill match)
3. 자율 실행(claude-loop 또는 Antigravity goal 모드)에서 작동해야 하나요? YES면 사용자 질문 없이 진행 가능해야 합니다 → 사전 결정사항 무엇?
4. Vault / 외부 시스템 통합이 있나요? (Obsidian, Notion, Linear 등) → 파일 형식과 동시성 가정은?
5. 설치 방법은? (install-antigravity.sh / install.sh / npm / pip / git submodule)
6. 다른 skill / plugin / 도구와 충돌 가능성은? (이름, 슬래시 명령, 파일 경로, plugin.json)
7. 실패 시 회복 전략은? (재시도 / 사용자 알림 / 무시)
8. 로그/메트릭은 어디에 저장하나요?
9. 버전 호환성: 기존 사용자가 어떻게 업그레이드?
10. 보안: 자격 증명/토큰/API 키 처리 방식은?

## Mandatory AC Checklist

- [ ] install-antigravity.sh 또는 install.sh 등의 설치 스크립트가 완벽히 작동해야 한다.
- [ ] plugin.json 및 SKILL.md 검증을 성공해야 한다.
- [ ] 헬스체크 또는 dry-run 모드가 존재해야 한다.
- [ ] ~/.gemini/ 또는 ~/.claude/ 또는 Vault에 부작용 발생 시 위치를 명시해야 한다.
- [ ] 자율 실행 모드일 경우 사용자 질문 0개를 보장해야 한다.
- [ ] README에 사용 예제가 1개 이상 존재해야 한다.
- [ ] 회복 시나리오 (실패 후 재실행)가 검증되어야 한다.
