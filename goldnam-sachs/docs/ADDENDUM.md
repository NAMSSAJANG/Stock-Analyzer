# Goldnam Sachs · 추가 결정사항 (ADDENDUM)

작성: NAMSSA · 2026-11-23 · Phase 0 보고서를 확인한 뒤 확정한 내용

이 문서는 `SPEC.md`보다 우선한다. 여기 없는 내용은 `SPEC.md`를 따른다.

## A1. Phase 0 마무리

1. 폴더 이름을 공백 없는 `goldnam-sachs/`로 바꾼다. README, CI 경로 필터, Dockerfile, compose, `render.yaml`, 스크립트의 모든 참조를 함께 고친다.
2. 작업은 브랜치 `goldnam/v0.0.0-a.1`에 Phase 단위로 커밋한다. push하고 `main` 대상 PR을 열어 원격 CI 결과를 확인한다. push 권한이 없으면 NAMSSA가 실행할 git 명령을 정확히 적는다.
3. 원격 CI가 통과하면 `docs/PHASE0_REPORT.md`에 결과를 추가하고 Phase 0을 완료로 표시한다.

## A2. 진행 범위와 방식

- Phase 1부터 Phase 8까지 순서대로, Phase마다 "다음"을 기다리지 않고 이어서 진행한다.
- Phase마다 `docs/PHASE{n}_REPORT.md`를 Phase 0과 같은 형식으로 남긴다. 완료 기준별 표, 테스트 결과 원문, 변경 파일, 남은 문제를 담는다.
- 아래 경우에만 멈추고 NAMSSA에게 묻는다.
    - 비용이 생기는 일
    - API 키나 연락처가 필요한 일
    - 명세끼리 충돌해 구현 방향이 갈리는 일
- 묻는 동안에도 그 질문과 무관한 작업은 계속한다.
- Phase 4 검증 결과가 나쁘거나 근거가 약하면, 좋아 보이게 파라미터를 고치지 않고 그대로 보고한다. 조정은 SPEC 7장 C의 규칙(학습 구간에서만)을 따른다.

## A3. 필요한 비밀값

Phase 1을 시작할 때 아래 목록을 먼저 보고한다. 값이 오기 전에는 해당 소스를 건너뛰는 상태로 구현하고, 테스트는 모킹으로 한다. 비밀값은 코드·커밋·로그에 남기지 않는다.

| 변수 | 용도 | 누가 넣나 |
| --- | --- | --- |
| `OPENDART_API_KEY` | 한국 재무제표(PIT) | NAMSSA |
| `SEC_USER_AGENT` | 미국 SEC 요청 헤더의 연락처 | NAMSSA |
| `DATABASE_URL` | Render Postgres | Render가 자동 연결 |
| `APP_PASSCODE_HASH` | 앱 로그인 (A5) | NAMSSA가 생성 스크립트로 만듦 |
| `SESSION_SECRET` | 세션 서명 | Render에서 자동 생성 |

## A4. 배포 구조 변경 (SPEC 3장을 대체)

폰에서 쓰고 로그인을 단순하게 하려고, 웹과 API를 **하나의 Render Web Service**로 합친다.

| 구성 | Render 서비스 | 내용 |
| --- | --- | --- |
| 앱 | Web Service, Starter(상시 가동) | FastAPI가 `/api/v1`을 제공하고, Next.js 정적 빌드 결과를 같은 서버에서 정적 파일로 제공. 같은 주소라 쿠키 로그인이 단순해짐 |
| DB | Render Postgres, 가장 작은 유료 플랜 | 점수·검증 요약·관심종목·거래 일지·설정. 무료 Postgres(30일 만료)는 개발용 옵션으로만 문서화 |
| 일일 점수 | GitHub Actions 스케줄 | 미국·한국 장 마감 후 각각 실행. 거래소 달력으로 휴장일은 건너뜀. 결과를 Postgres에 기록 |
| 주간 검증 | GitHub Actions 스케줄 + 수동 실행 | 요약은 Postgres, 상세 결과는 Actions 아티팩트 |

- 지역(region)은 한국에서 가까운 Singapore로 한다. 앱과 DB는 같은 지역에 둔다.
- `render.yaml`은 이 구조로 다시 쓴다. Blueprint 연결, 리소스 생성, 배포는 하지 않는다. NAMSSA가 직접 한다.
- 무료 플랜으로 돌리는 방법(서비스가 잠드는 점, DB 30일 만료)은 README에 대안으로만 적는다.
- 관심종목·거래 일지·설정은 JSON 내보내기/가져오기를 만들어, DB를 바꿔도 옮길 수 있게 한다.

## A5. 폰 사용 (Phase 6에 포함)

앱이 공개 주소에 올라가므로 접근 보호와 모바일 화면이 필수다.

### 접근 보호

- 단일 사용자 로그인. 비밀번호는 `APP_PASSCODE_HASH`(argon2 등 표준 해시)와 비교한다. 해시 생성 스크립트를 `scripts/`에 둔다.
- 로그인하면 HttpOnly, Secure, SameSite=Lax 세션 쿠키를 발급한다. 유효기간은 30일.
- `/api/v1/health`를 뺀 모든 API와 화면은 로그인이 필요하다.
- 로그인 시도는 IP당 분당 5회로 제한한다.
- 모든 페이지에 `noindex`를 넣어 검색엔진에 노출되지 않게 한다.

### 모바일 화면

- 모바일 우선으로 설계한다. 기준 폭은 375~430px이고, 데스크톱은 SPEC 9장 레이아웃을 따른다.
- 모바일 내비게이션은 하단 탭 바다. 홈, 스크리너, 검색, 기록, 설정.
- 종목 화면은 한 열로 쌓는다. 순서는 결론 띠 → 차트 → 진입 계획 → 과거 근거 → 상세 탭.
- 표는 모바일에서 카드 목록으로 바뀐다. 터치 대상은 최소 44px이다.
- 차트는 손가락으로 확대·이동할 수 있어야 한다.
- 숫자는 고정폭 숫자, 등락은 색과 함께 ▲▼ 기호를 쓴다.

### 홈 화면 앱(PWA)

- 웹 앱 매니페스트와 아이콘(로고에서 생성), `theme-color` #181818을 넣는다. `display: standalone`.
- iPhone(Safari)과 Android(Chrome)에서 "홈 화면에 추가"로 앱처럼 열린다.
- 오프라인 시에는 "연결 없음" 화면과 마지막으로 본 데이터의 시각을 보여준다.

### 모바일 완료 기준

- Playwright로 iPhone 계열(390×844)과 Android 계열(412×915) 뷰포트에서 로그인 → 종목 검색 → 종목 화면 → 스크리너 흐름을 테스트한다.
- 각 화면의 모바일 스크린샷을 보고서에 넣는다.
- Lighthouse PWA·접근성 점검 결과를 보고서에 넣는다.

## A6. 브랜드 (SPEC 9장 보완)

- 화면 배경은 #181818, 나머지는 무채색과 Pretendard다. 색은 등락과 상태 표시에만 쓴다.
- **Personal 테마 로고(기본):** 블루 정사각형(#6698C9) 위에 검정 "Goldnam Sachs" 워드마크. 서체는 굵은 콘덴스드 세리프 계열의 무료 라이선스(OFL) 서체 후보 3개를 제시하고, NAMSSA가 고르기 전에는 첫 번째 후보로 둔다. SVG로 만든다.
- **Goldnam 테마 로고(공개용):** `assets/logo-goldnam-lime.jpg` (라임 #C4F750, 잉크 #12150E). SVG로 다시 그려 두되, 원본 비율과 구성을 유지한다.
- 앱 아이콘(PWA)은 현재 테마 로고에서 생성한다.
- 하단에 버전 `v0.0.0-a.1`과 면책 문구를 둔다.

## A7. Phase 8 완료 기준 (보완)

- `README.md`에 NAMSSA가 그대로 따라 할 Render 배포 절차를 단계별로 쓴다. Blueprint 연결, 환경변수 입력, GitHub Actions 시크릿 등록, 첫 배치 실행, 폰에서 접속·홈 화면 추가까지.
- 배포된 주소를 넣으면 로그인·health·주요 API를 확인하는 점검 스크립트 `scripts/post_deploy_check.py`를 만든다.
- 예상 월 비용을 플랜별로 표로 적는다. 금액은 작업 시점에 Render 요금표에서 확인한 값과 확인 날짜를 함께 쓴다.
