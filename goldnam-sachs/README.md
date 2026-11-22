# Goldnam Sachs — Phase 0

기존 엔진을 보존 이식한 개발 골격입니다. 종목 분석 제품이나 배포 완료본이 아닙니다.
이번 범위는 Phase 0뿐입니다. 기존 Streamlit 서비스에는 변경을 적용하지 않았습니다.

- 기준 저장소: https://github.com/NAMSSAJANG/Stock-Analyzer
- 기준 커밋: `3cce17f65d56cc266af9f354cf137c000af64fb9`
- 기준 폴더: `analyzer-by-kijungnam-v6c-0.1`
- 명세 원문: [docs/SPEC.md](docs/SPEC.md)
- 결정·유보 사항: [docs/DECISIONS.md](docs/DECISIONS.md)
- 실제 검사 결과: [docs/PHASE0_REPORT.md](docs/PHASE0_REPORT.md)

## 로컬 개발과 검사

Python 3.12, uv 0.13.9, Node 24, pnpm 12.21.0을 사용합니다.
아래 명령의 작업 디렉터리는 공백 없는 `goldnam-sachs`입니다.

```bash
cd goldnam-sachs
uv sync --frozen --all-groups --extra api
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=goldnam_engine --cov-report=term-missing
uv run python scripts/run_legacy_checks.py smoke_test.py
uv run python scripts/run_legacy_checks.py test_trade_ui.py
uv run python scripts/run_legacy_checks.py test_execution_ui.py
uv run python scripts/run_legacy_checks.py test_analysis_ui.py
uv run python scripts/validate_blueprint.py
docker compose config --quiet
cd web
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

pytest는 기본적으로 외부 소켓을 차단하고 `live` 마커를 제외합니다. 로컬 ASGI 테스트에
필요한 Unix 소켓만 허용합니다. 현재 live 테스트는 없습니다. 화면 회귀도 실제 시세를
조회하지 않는 독립 subprocess로 실행합니다.

```bash
# 컨테이너 없이 개발용 API만 실행
uv run --extra api uvicorn api.main:app --reload
# 별도 터미널
cd web && pnpm dev
```

`GET /health`는 `status=scaffold`만 반환합니다. 데이터 준비 완료를 뜻하지 않습니다.
웹은 개발 준비 안내만 출력합니다. 제품 API·화면은 Phase 5·6에서 구현합니다.

## Compose 초안

```bash
docker compose -p goldnam-phase0 up --build
# API: http://localhost:8000/health, 웹: http://localhost:3000
docker compose -p goldnam-phase0 down
```

Postgres는 호스트에 포트를 공개하지 않는 로컬 전용 trust 인증입니다. Render에서 이 설정을
쓰지 않습니다. DB 볼륨은 재시작 후 유지되고 API는 아직 DB에 데이터를 읽거나 쓰지 않습니다.
프록시 CA가 필요한 환경에서는 인증서를 이미지에 넣지 않고 BuildKit secret으로 전달할 수 있습니다.

```bash
docker build --secret id=build_ca,src=/path/to/ca-bundle.crt -t goldnam-phase0-api .
docker build --secret id=build_ca,src=/path/to/ca-bundle.crt -f web/Dockerfile -t goldnam-phase0-web .
docker compose -p goldnam-phase0 up --no-build
```

## 구조와 이식 원칙

- `engine/goldnam_engine/`: 웹 프레임워크를 import하지 않는 계산 패키지.
- `engine/tests/`: 기존 49개, smoke, 이식·경계·속성 검사.
- `engine/tests/legacy_ui/`: 기존 화면 회귀 전용 파일. 배포 이미지와 wheel에는 포함하지 않음.
- `api/`: liveness 골격. `jobs/`: 후속 Phase용 실행 차단 placeholder.
- `web/`: 정적 빌드 가능한 Next.js 골격. `web/theme/`: 임시 기본 토큰.
- `docs/migration-map.json`: 원본 파일과 패키지 위치 대응표.
- 저장소 루트 `.github/workflows/goldnam-ci.yml`: Python·웹 PR 검사. 배포 단계 없음.

기존 `weighted` 기본값, 과열 판정, 고정 환율, 단일 종목 검증은 **보존된 v6 동작**입니다.
새 점수 산식이나 검증 근거로 공개하지 않습니다. 해당 수정은 명세의 Phase 1~4로 유보했습니다.
`sitecustomize`는 실행 가능한 위치에 넣지 않았고 원본은 `docs/legacy/sitecustomize.py.txt`에 보관합니다.

앱 버전은 `engine/goldnam_engine/_version.py` 한 곳이 원천입니다. Python 배포 메타데이터는
PEP 440에 따라 `0.0.0a1`로 정규화되지만 API와 웹 표시는 원래 SemVer 문자열을 사용합니다.

## Render 초안

`render.yaml`은 새 리소스 이름의 초안이며 자동 배포는 꺼져 있습니다. Blueprint 연결·동기화·배포는
수행하지 않았습니다. Free Postgres는 1 GB이며 생성 30일 뒤 만료되므로 영구 저장소로 사용할
요금제 결정은 Phase 8에서 해야 합니다. 계정 리소스나 비용은 생성하지 않았습니다.

2026-11-23에 확인한 공식 문서:
[Blueprint](https://render.com/docs/blueprint-spec),
[무료 한도](https://render.com/docs/free), [요금표](https://render.com/pricing).
DB에는 점수·검증 요약만 두고 원시 시세와 상세 검증은 Parquet로 분리합니다. 임시 무료 DB를
사용한다면 1 GB 중 70%를 경고선으로 잡고 요약 보관 기간을 90일에서 30일로 줄이는 안을
Phase 1에서 실제 행 크기·인덱스 측정 후 확정합니다. 현재는 테이블이 없어 용량을 보장하지 않습니다.

실데이터 검증용 주간 workflow와 배치 업로드는 Phase 4까지 활성화하지 않습니다.
