# Template: Web Application

**Template ID:** `web-application` · **Revision:** 1 (created 2026-05-12)
**기획 관심사:** API 설계, 사용자 인증, 배포 자동화, 모니터링, 문서화, 비용/latency 추적

## Template Q&A

1. 신규 앱인가요, 기존 앱에 기능 추가인가요?
   - 추가면 → 영향받는 기존 화면/엔드포인트 목록은?
2. 프론트엔드 스택은? (Next.js / SvelteKit / Vue / React+Vite / 기타)
3. 백엔드: REST / GraphQL / gRPC / serverless / 없음?
4. 데이터 저장: Firestore / Postgres / MongoDB / Redis / S3?
5. 인증 필요? 방식은? (Firebase Auth / OAuth / JWT / 세션)
6. 사용자 권한 모델: 단일 권한 / 역할 기반 / 정책 기반?
7. 결제/외부 API 통합이 있나요? 어떤 서비스?
8. 배포 환경: dev / staging / prod 각각 어디에? (Vercel, Firebase, AWS, ...)
9. 모니터링/에러 추적: Sentry / Datadog / 없음?
10. 사용자 데이터 처리: 개인정보 보호 요구사항(GDPR, 한국 개보법)은?
11. 성능 SLA가 있나요? (예: p95 응답시간 < 500ms)
12. API 문서화: Swagger / OpenAPI / 자유 README / 없음?

## Mandatory AC Checklist

- [ ] API 엔드포인트별 통합 테스트 최소 1개(happy + error 경로)가 통과해야 한다.
- [ ] 프로덕션 또는 스테이징 환경 배포 및 헬스체크를 통과해야 한다.
- [ ] 인증 시나리오 E2E 검증을 만족해야 한다 (해당 시).
- [ ] 모니터링 대시보드 또는 에러 알람이 1개 이상 설정되어야 한다.
- [ ] README에 로컬 개발 환경 setup 가이드 및 1개 이상의 사용 예제가 존재해야 한다.
- [ ] 에러 발생 시 5xx 응답이 의도된 사용자 친화적 메시지로 잘 노출되는지 검증해야 한다.
