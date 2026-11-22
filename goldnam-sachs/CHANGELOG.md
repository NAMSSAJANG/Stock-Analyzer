# 변경 기록

## Phase 0 · 2026-11-23

- 기존 v6 엔진과 49개 테스트를 `goldnam_engine` 패키지 구조로 보존 이식.
- 옵션 계산과 UI 분리, 비활성 sitecustomize 원본 보관.
- Python 3.12·uv lock·ruff·strict mypy·pytest와 85% 커버리지 게이트 추가.
- 실행 구문 보존 검사, 경계·속성 검사 및 기존 smoke/UI 회귀 실행기 추가.
- FastAPI liveness, Next.js 정적 빌드, 후속 배치용 placeholder 추가.
- 경로 제한 CI와 Render/Compose 초안 추가. 배포 없음.
