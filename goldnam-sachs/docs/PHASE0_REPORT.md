# Phase 0 재개 결과 — 완료 (2026-11-23)

ADDENDUM A1에 따라 폴더를 `goldnam-sachs/`로 변경하고 `goldnam/v0.0.0-a.1` 브랜치를 push했다.
PR: https://github.com/NAMSSAJANG/Stock-Analyzer/pull/2
원격 CI: https://github.com/NAMSSAJANG/Stock-Analyzer/actions/runs/45052720776
검증 커밋: `5862610abbf4ac4863d71cc1e294d40838353b53`.
Python·웹 job 모두 success. 원문 메타데이터는 `test-results/phase0-remote-ci.json`.

추가 수정: pytest CLI에서 프로젝트 모듈을 못 찾던 문제를 pythonpath 설정으로 해결했다.
재검사 원문: `75 passed, 2 warnings in 19.70s`, 커버리지 90.28%.
현재 Phase 0 완료 기준은 모두 통과했다. main 병합·리소스 생성·배포는 하지 않았다.

---

아래는 이전 세션의 원본 보고서(당시 원격 CI 미실행 상태)이다.

# Phase 0 결과 — 2026-11-23

**구현 및 로컬 검증 완료. 원격 GitHub CI 실행은 미완료. Phase 1은 시작하지 않음.**

작업 위치: `Stock-Analyzer/Goldnam Sachs`. 기존 기반 폴더의 추적 파일 변경은 0건이며,
원격 저장소 push·PR 생성·기존 서비스 변경·Render 연결·배포는 수행하지 않았다.

## 이해한 범위와 실행 계획

순위·타이밍·리스크를 분리하는 새 제품의 골격을 만들되, 이번 단계에서는 v6 계산 동작을 보존한다.
데이터 결측 정책, 새 팩터·점수·검증, 제품 API·화면은 이후 Phase의 일이다.
진행 순서는 원본 테스트 → 패키지 이식 → 타입/도구/CI → 인프라 초안 → 회귀·보존 검증이었다.
구현을 막는 질문은 없었다. 후속 명세의 해석 항목은 DECISIONS.md에 기록했다.

## 완료 기준별 상태

| 완료 기준 | 상태 | 실제 근거 |
| --- | --- | --- |
| 11장 저장소 골격 | 통과 | engine/api/jobs/web/docs, 버전 원천, 설정·lock 파일 |
| 기존 엔진 로직 보존 이식 | 통과 | 19개 모듈 실행 AST 비교 + trade 호환 export 동일성 검사 |
| 기존 49개 테스트가 새 위치에서 통과 | 통과 | 원본 49/49, 이식본 49/49, 기대값·fixture 실행 구문 보존 검사 |
| 기존 smoke·화면 회귀 보존 | 통과 | smoke와 Trade Lab·체결·분석 UI 각각 독립 실행 성공 |
| ruff | 통과 | lint 및 format 검사 |
| mypy strict | 통과 | 엔진·API·jobs 36개 소스 파일, ignore_errors/모듈 제외 없음 |
| CI 설정 | 통과 | 저장소 루트 `.github/workflows/goldnam-ci.yml`, PR 경로 필터, 읽기 권한, 배포 없음 |
| 원격 CI 통과 | **미확인** | push·원격 workflow 실행을 하지 않음. 로컬 성공을 원격 성공으로 대체하지 않음 |
| Render Blueprint 초안 | 통과 | 공식 JSON Schema snapshot으로 검증. 원격 Render validation·sync 미실행 |
| Docker Compose 초안 | 통과 | config 검사, 이미지 빌드, API·웹·DB 로컬 기동 및 종료 |
| 엔진 커버리지 ≥85% | 통과 | 전체 1,616 statements, 157 missing, **90.28%** |
| 웹 도구 골격 | 통과 | lint, TypeScript, Vitest, Next.js 정적 빌드 |

원격 CI 통과까지 요구하는 Phase 0 전체 완료 기준은 아직 충족했다고 선언하지 않는다.
다음 Phase로 넘어가지 않는다.

## 테스트 결과 원문 발췌

원본 49개 — [전체 로그](test-results/baseline/unit.txt)

```text
49 passed, 1 warning, 12 subtests passed in 6.80s
```

이식본 기존 49개 — [전체 로그](test-results/migrated-unit.txt)

```text
49 passed, 1 warning, 12 subtests passed in 5.68s
```

전체 Python — [전체 로그](test-results/pytest.txt), [커버리지 JSON](test-results/coverage.json)

```text
TOTAL                                                     1616    157    90%
Coverage JSON written to file docs/test-results/coverage.json
Required test coverage of 85.0% reached. Total coverage: 90.28%
======================= 75 passed, 2 warnings in 22.02s ========================
```

75개 = 기존 49 + 경계·속성 20 + 이식 보존 4 + smoke 1 + API 골격 1.
경계 검사는 옵션 체인 계산, PIT 국면 입력 절단, KRX 폴백 순서, 음수 PER/PBR 가드,
History 왕복, 비용 포함 수량 한도, 백분위 범위를 포함한다. live 데이터 검증은 하지 않았다.

ruff·mypy — [ruff](test-results/ruff.txt), [mypy](test-results/mypy.txt)

```text
All checks passed!
49 files already formatted
Success: no issues found in 36 source files
```

독립 smoke·UI — [smoke](test-results/smoke.txt), [Trade Lab](test-results/trade-ui.txt),
[체결](test-results/execution-ui.txt), [분석](test-results/analysis-ui.txt)

```text
V6 offline smoke tests passed
Trade Lab UI and main-menu integration checks passed
Execution UI and incompatible legacy-module startup checks passed
Analysis sizing and calibration UI checks passed
```

웹 — [lint](test-results/web-lint.txt), [타입 검사](test-results/web-types.txt),
[Vitest](test-results/web-test.txt), [빌드](test-results/web-build.txt)

```text
 Test Files  1 passed (1)
      Tests  1 passed (1)
```

로컬 컨테이너 — [HTTP/DB 확인](test-results/local-http.txt),
[API 빌드](test-results/docker-api-build.txt), [웹 빌드](test-results/docker-web-build.txt)

```text
GET http://127.0.0.1:8000/health -> HTTP 200
{"status":"scaffold","version":"0.0.0-a.1"}
GET http://127.0.0.1:3000/ -> HTTP 200
Static scaffold heading and Korean placeholder: PASS
/run/postgresql:5432 - accepting connections
```

테스트 컨테이너·네트워크·테스트용 DB 볼륨은 종료·삭제했다. 기존 서비스와 무관한 로컬 검사다.
초기 Docker 빌드 실패 로그도 `test-results/docker-build.txt`에 남겼다. 프록시 CA 전달 후 성공했다.

## 변경 파일

모든 변경은 새 `Goldnam Sachs/`와 새 `.github/workflows/goldnam-ci.yml`에 한정한다.
전체 상대 경로 목록은 [CHANGED_FILES.txt](CHANGED_FILES.txt), 이식 대응은
[migration-map.json](migration-map.json)에 있다.

- 엔진: models, trade, factors, scoring, timing, risk, regime, validation, data.
- 검사: 기존 테스트·smoke, UI fixture와 실행기, 실행 구문 지문, 경계·속성 검사.
- 도구: pyproject.toml, uv.lock, Python 버전, pnpm lock, ruff/mypy/pytest 설정, CI.
- 골격: API health, jobs 실행 차단 placeholder, Next 정적 페이지, 테마 토큰.
- 인프라·문서: Dockerfile 2개, Compose, Render 초안, README, 명세 원문, 결정·결과 기록.

## 남은 문제와 제한

1. 원격 CI는 미실행이다. 이 작업에서 저장소를 push하거나 기존 서비스 배포를 유발하지 않았다.
2. 기존 12개 개선 항목은 Phase 0에서 고치지 않았다. 원본 보존이 목적이며, 새 API는 기존 점수나
   오래된 중립 기본값을 사용자 분석 결과로 제공하지 않는다.
3. 새 점수·데이터 어댑터·실데이터 검증·DB 저장·제품 UI는 미구현이다. jobs 명령도 의도적으로 종료한다.
4. 기존 동적 dict/금융 입력에 Any가 남아 있다. strict 검사 통과가 모든 런타임 입력의 정형화를 뜻하지 않는다.
5. 웹 ESLint/TypeScript는 최신 주버전의 플러그인 호환성 문제 때문에 지원되는 버전으로 고정했다.
   구체적인 버전과 사유는 DECISIONS.md에 있다.
6. 전체 pytest의 경고 2개는 FastAPI/Starlette의 httpx TestClient deprecation과 KRX 폴백 테스트 중
   차단된 socket 생성 시도다. UI 로그의 `simulated missing trade_core` 예외는 기존 오류 처리 검사의
   의도된 입력이며, 마지막 성공 출력과 함께 확인했다. 경고를 숨기지 않았다.
7. Render Free Postgres는 30일 만료이므로 최종 영구 저장 용도로 확정하지 않았다.
8. 주간 검증 workflow·Tailwind·Playwright·브랜드 리소스는 각각 Phase 4·6·8 범위다.

재현 명령은 README.md에 있으며 라이브러리 버전은 uv.lock 및 pnpm-lock.yaml로 고정되어 있다.
