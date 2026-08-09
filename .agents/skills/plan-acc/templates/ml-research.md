# Template: ML Research & Pipeline

**Template ID:** `ml-research` · **Revision:** 1 (created 2026-05-12)
**기획 관심사:** 학습/추론 파이프라인, 데이터셋 버전관리, 실험 추적, 벤치마크 점수, 재현성, 하드웨어 제약, 모델 아티팩트

## Template Q&A

### A. 모델 & 추론
1. 작업 종류는? (학습 training / 추론만 inference / fine-tuning / 평가만 evaluation)
2. 모델은 어떻게 호출되나요? (로컬 / API / Hugging Face / 자체 호스팅 / from scratch)
3. 모델 아키텍처는? (CNN / Transformer / YOLO 계열 / DETR / LLM 등 — 라이선스 호환 확인 필수)
4. 입력 데이터 형식과 규모는? (이미지/텍스트/오디오/표 데이터, KB/MB/GB/TB)
5. 출력 형식: 자유 생성 / 구조화 JSON / 분류 라벨 / 바운딩 박스 / 마스크?

### B. 데이터셋 & 라벨링
6. 데이터 출처는? (Roboflow / 자체 수집 / 공개 데이터셋명 / 합성 데이터)
7. 라이선스 호환 확인했나요? (Apache 2.0 / BSD / MIT 외 사용 정책)
8. 데이터 버전 관리: DVC / Git LFS / 수동 / 없음?
9. 라벨링 정책: 누가 / 어떤 도구 / inter-annotator agreement 측정?
10. train/val/test 분할 방식과 비율은? 분포 누수(leakage) 검증은?

### C. 평가 & 벤치마크
11. 평가 지표는? (정확도/F1/mAP/IoU/recall@N/perplexity 등 — 구체적 수치)
    - 목표 없음 → STOP. 평가 기준 정의 필수.
12. 베이스라인은? (이전 모델 / SOTA / 인간 수행 능력 / random)
13. 벤치마크 데이터셋은? (held-out test, public benchmark명)
14. 실패 케이스 카테고리화 계획은? (false positive / false negative / edge case)

### D. 인프라 & 재현성
15. 하드웨어: Apple Silicon MPS / CUDA / TPU / CPU only? VRAM 요구는?
16. 실험 추적: wandb / mlflow / 수동 로그 / 없음?
17. 설정 관리: hydra / argparse / YAML / 하드코딩?
18. 재현성: seed 고정 / 의존성 lockfile (uv.lock, poetry.lock, requirements.txt) / Docker?
19. 모델 아티팩트 저장: 어디 / 어떤 포맷 (.pt, .onnx, .safetensors) / 버전 관리?

### E. 운영 & 배포
20. 비용/시간 예산: 학습 1 epoch 시간, API 단가, GPU 시간 한도?
21. 추론 latency 목표? (예: < 100ms per image)
22. 프로덕션 배포 형태? (배치 / 실시간 API / CLI / 라이브러리 / 노트북만)
23. 실패한 추론 (hallucination, low-confidence, error) 처리 정책은?

## Mandatory AC Checklist

- [ ] 평가 데이터셋에서 측정된 베이스라인 및 목표 수치(구체적 metric 값)가 제시되어야 한다.
- [ ] 파이프라인 end-to-end 1회 실행(학습 또는 추론 전체 흐름)에 성공해야 한다.
- [ ] 실험 추적 시스템에 1회 이상 실험 로깅(wandb run ID 또는 동등물)을 완료해야 한다.
- [ ] 재현 스크립트 + seed + lockfile이 커밋되어야 한다.
- [ ] 실패 케이스 최소 3개에 대한 분석 결과가 명시되어야 한다.
- [ ] 데이터셋 라이선스 명시 및 호환성 검증이 완료되어야 한다.
- [ ] 모델/데이터 아티팩트가 git에 포함되지 않았음을 확인해야 한다.
