# Phase 5 · API와 접근 보호

2026-11-23. **로컬 완료**. 외부 Render 배포는 하지 않았다.

| 완료 기준 | 결과 |
|---|---|
| 명세의 모든 API 경로 | 구현·각 경로 테스트 통과 |
| 공통 envelope / RFC 9457 | 통과. 입력 오류에 비밀번호/원문 입력을 되돌려주지 않음 |
| 검색·분석·시세·스크리너·시장·검증 | 통과. 데이터 실패와 부분 점수 구분 |
| 관심종목·일지·설정·JSON 이관 | 통과. 일지는 해당 거래일에 저장된 점수만 스냅샷으로 연결 |
| Trade Lab·단일 종목 체결 검증 | 기존 Decimal 엔진 연결·테스트 통과 |
| 로그인 보호 | Argon2·30일 HttpOnly/Secure/SameSite=Lax, 취소/만료/비밀번호 변경 무효화, IP 5회/분, CSRF·경로 우회 회귀 통과 |
| 실제 Postgres | 18 임시 로컬 컨테이너에서 재접속 보존·upsert·조회·삭제 **1 passed** |
| API 회귀 | **11 passed** (기존 health 포함) |
| OpenAPI → TypeScript | 21개 경로 생성 성공, strict TypeScript typecheck 통과 |
| mypy·ruff·format | 통과 |

원문: [API](test-results/phase5-api.txt), [Postgres](test-results/phase5-postgres.txt), [스키마/타입](test-results/phase5-openapi.txt), [전체 엔진+API 중간 검사](test-results/phase4-5-local.txt)(121 passed, 91.74%; 이후 보안 회귀 추가).

변경: api/{main,auth,schemas,service}.py, API 테스트, data/store.py, scripts/export_openapi.py·hash_passcode.py, trade/lab.py(API 시뮬레이션 기반), web/generated. 로그인은 API가 처음부터 보호되도록 Phase 6보다 앞서 구현했다. 실제 사용자 비밀번호/키를 받거나 생성하지 않았고, 테스트는 명시적인 테스트 전용 문자열을 사용했다.

예외 공개 경로: health, 로그인과 로그인에 필요한 JS/CSS/폰트/아이콘, robots, 오프라인 화면·매니페스트·서비스워커. 공개 정적 자산 경로로 인증된 HTML에 접근하는 우회도 차단한다. API/화면은 no-store·noindex, 쓰기 요청은 동일 출처만 허용한다. /health는 Phase 0의 호환용 scaffold 응답이며 운영 상태는 /api/v1/health를 사용한다.

TypeScript는 openapi-typescript 7.13.0의 공식 peer(^5.x)에 맞춰 5.9.3으로 고정했다. TypeScript 6으로 생성 자체는 가능했지만 지원 범위 밖 경고를 남기지 않도록 호환판을 선택했다. 설치된 버전은 package.json/lock에 고정한다.

현재 DB가 미설정이면 health는 configuration_required, 로그인은 503으로 안전하게 닫힌다. API가 실제 재무·검증 근거를 만들어 내지 않는다. 운영용 세션/비밀번호 설정, 모바일 브라우저 흐름과 배포 점검은 후속 Phase에서 확인한다.
