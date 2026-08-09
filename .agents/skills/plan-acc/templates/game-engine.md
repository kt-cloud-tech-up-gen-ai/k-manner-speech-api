# Template: Game Engine & Interactive

**Template ID:** `game-engine` · **Revision:** 1 (created 2026-05-12)
**기획 관심사:** 게임 규칙 정확성, 렌더링 성능(60fps), AI 통합(KataGo/TF.js), 인터랙션, 상태 관리

## Template Q&A

1. 게임/도메인 규칙은 어디 정의되어 있나요? (논문 / 위키 / 기존 구현 / TBD)
   - TBD면 → STOP. 규칙 명세부터 확정.
2. 새로운 규칙 구현인가요, 기존 엔진 통합인가요? (KataGo, Stockfish 등)
3. 판정/점수 계산의 단위 테스트 케이스를 몇 개 이상 작성할 건가요?
4. 렌더링 기술은? (Canvas 2D / WebGL / SVG / DOM)
5. 목표 FPS 또는 인터랙션 latency는? (예: 60fps 유지, 클릭→반응 50ms 이내)
6. 상태 관리: 어떤 라이브러리? 영속화(localStorage/IndexedDB) 필요?
7. AI 통합 시: 추론 위치는? (서버 / WebWorker / WebAssembly)
8. 사용자 입력: 마우스/터치/키보드 모두 지원? 단축키 규약?
9. 멀티 디바이스 (데스크탑/태블릿/모바일) 지원 범위?
10. 게임 진행 저장/공유 기능 필요한가요?

## Mandatory AC Checklist

- [ ] 도메인 규칙 단위 테스트가 N개 이상 작성되고 통과해야 한다.
- [ ] 콘솔 또는 dev tools를 통해 측정된 FPS / latency 수치가 만족스러워야 한다.
- [ ] E2E 시나리오(게임 시작 → 1회 진행 → 종료)가 정상 작동해야 한다.
- [ ] 모바일/데스크탑 양쪽에서 레이아웃이 지원 범위 내로 올바르게 작동해야 한다.
- [ ] 입력에 따른 화면 반영 검증이 자동화되어야 한다.
