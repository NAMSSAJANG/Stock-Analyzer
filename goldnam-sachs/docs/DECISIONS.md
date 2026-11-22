# Phase 0 결정 기록

날짜: 2026-11-23 (Asia/Seoul). 검증 run_id: 해당 없음 — 산식 변경 없이 보존 이식.

1. 사용자 요청을 따라 `Goldnam Sachs` 폴더를 기존 기반 폴더와 나란히 둔다.
   명세 예시의 소문자 폴더명보다 사용자가 지정한 이름을 우선한다.
2. Phase 0의 “로직 변경 없이 이식”을 우선한다. 벡터화·3단계 국면·EMA20 Zone 개선·결측 기본값
   제거·진입 상태 수정은 각 후속 Phase에서 수행한다. 기존 계산을 새 `score-v0.1`로 취급하지 않는다.
3. 의존 관계를 보존하기 위해 명세의 유지 엔진 외에도 setup/risk/scoring/consensus/quant/scanner/cache/history를
   함께 이식했다. SQLiteHistoryStore와 scanner는 v6 호환용이며 새 API 상태 저장에 연결하지 않는다.
4. 옵션 파일에서 계산 함수와 데이터 클래스를 추출한다. Streamlit/Plotly 표시 함수와 공급자 캐시 코드는
   회귀 전용 UI fixture에 남긴다. 원본 계산 함수·상수·dataclass는 정규화 AST 지문으로 확인한다.
5. `sitecustomize` 자동 monkey patch는 새 패키지에서 폐기한다. 명시적 호출 기반 `load_krx_listing`을
   보존하고, 기존 hotfix 파일은 비실행 텍스트로 보관한다. 정식 DataResult 어댑터는 Phase 1이다.
6. strict mypy 전체 엔진 검사에서 모듈 제외·ignore_errors를 사용하지 않는다. 기존 동적 금융 입력과
   이질적 dict 반환에는 명시적 Any를 유지하고, pandas/numpy 추론 차이는 런타임 동작을 바꾸지 않는
   cast로 보완한다. 향후 공개 API 모델은 Phase 5에서 구체화한다. 타입 없는 외부 패키지
   FinanceDataReader/yfinance의 import에만 missing-import 예외가 있다.
7. 49개 기존 테스트의 기대값은 바꾸지 않는다. import·mock 대상 경로와 포맷만 변경한다.
   기존 테스트·fixture 실행 구문 자체도 원본 지문과 비교한다. UI 검사는 기존 테스트 원문을
   별도 프로세스에서 실행하고, 그 프로세스 안에서만 이전 모듈 이름을 이식 엔진에 연결한다.
8. Python 라이브러리는 설치·검증한 안정 버전으로 직접 고정하고 uv.lock에 전이 의존성을 고정했다.
   웹도 pnpm-lock.yaml을 사용한다. TypeScript 7.0.2는 typescript-eslint 8.73.0이 지원하지 않아
   TypeScript 6.0.3을 쓴다. ESLint 10.15.0도 Next 의존 플러그인의 peer 범위를 벗어나 9.39.5로
   고정했다. 9.x는 npm에서 deprecated로 표시되지만 현재 이 조합의 지원 범위에 맞는 버전이며
   린트·타입·빌드 검사를 실제로 통과했다. 플러그인 지원이 맞춰지면 함께 올린다.
9. 웹 골격은 제품 화면이 아니다. 로고·Pretendard·Personal/Goldnam 테마·차트·Tailwind·Playwright
   화면 테스트는 Phase 6에서 구현한다. 브랜드 이미지와 폰트 선택은 그 시점의 입력이며 Phase 0을 막지 않는다.
10. 명세의 85% 엔진 커버리지는 전체 패키지 기준으로 적용한다. 테스트가 어려운 모듈을 제외하지 않는다.
    단위 검사는 외부 소켓을 차단한다. 기존 scanner의 외부 공급자 경로는 아직 live 검증하지 않았다.
11. 루트 CI 파일은 새 폴더 변경 PR과 수동 실행만 대상으로 한다. 기존 서비스 배포를 피하기 위해
    이번 작업에서 push/PR 생성/원격 workflow 실행을 하지 않는다. 로컬 동일 명령 성공과 원격 CI
    성공을 구분하며, 원격 CI는 미실행 상태로 보고한다.
12. Render Blueprint는 로컬 JSON Schema 검사만 수행한다. Free DB의 만료와 용량은 공식 문서로
    확인했지만 유료 요금제 선택·리소스 생성·배포는 Phase 8로 남긴다. Compose 테스트의 CA 전달은
    빌드 secret을 사용하며 이미지에 인증서를 저장하거나 TLS 검증을 끄지 않는다.

후속 명세 확인 항목(Phase 0 차단 아님):

- 5장: 재무 3팩터가 모두 없으면 가격 2팩터뿐이어서 “최소 3팩터” 조건상 종합 점수는 산출 불가다.
  Phase 2에서는 이 조건을 우선하고 가격 부분 정보 배지는 별개로 표시해야 한다.
- 7장 B의 최대 20일 규칙과 6장의 B/C 최대 120일을 Phase 4에서는 청산 방식별로 구분해야 한다.
- 7장 증권거래세·SEC/OpenDART 규칙은 해당 Phase에서 최신 공식 문서를 확인한다.
