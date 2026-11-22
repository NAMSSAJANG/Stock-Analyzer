# Goldnam Sachs v0.0.0-a.1

미국·한국 주식의 **순위, 타이밍, 리스크·수량, 과거 근거**를 따로 보여주는 개인용 앱입니다. 비밀번호 로그인과 휴대폰 화면을 구현했습니다. 기존 `analyzer-by-kijungnam-v6c-0.1` 엔진·테스트를 보존했으며 기존 서비스는 변경하지 않았습니다.

**배포하지 않았습니다.** 미국 511종목 검증에서 6개 Setup/청산 조합 중 5개의 기대값이 음수이고, 나머지도 무작위 진입보다 낮았습니다. 재무 PIT 키가 없어 종합 점수는 **미검증**, 한국 전체 유니버스 검증은 KRX 공급자 실패로 미완료입니다. 수익성이 입증된 제품으로 해석하지 않습니다.

[명세](docs/SPEC.md) · [추가 결정](docs/ADDENDUM.md) · [검증 결과](docs/PHASE4_REPORT.md) · [모바일 화면](docs/PHASE6_REPORT.md) · [Trade Lab](docs/PHASE7_REPORT.md) · [최종 상태](docs/PHASE8_REPORT.md) · [폰트 후보/라이선스](web/brand/FONTS.md)

## NAMSSA의 Render 배포 절차

### 1. 앱 비밀번호 해시 준비

Python 3.12, uv 0.13.9, Node 24, pnpm 12.21.0을 사용합니다.

```bash
cd goldnam-sachs
uv sync --frozen --all-groups --extra api
uv run python scripts/hash_passcode.py
```

숨김 입력으로 12자 이상 비밀번호를 두 번 입력합니다. `.data/passcode.env`가 권한 0600으로 생성됩니다. 파일의 `APP_PASSCODE_HASH` 값을 Render에 복사하세요. 평문 비밀번호를 채팅·GitHub·명령 인자에 넣지 않습니다. 스크립트는 기존 파일을 덮어쓰지 않습니다.

OpenDART 키와 SEC 연락처는 나중에 설정할 수 있습니다. 없으면 해당 데이터는 미설정/부분 상태입니다. `SEC_USER_AGENT`는 `Goldnam Sachs contact@example.com` 형식으로 실제 연락 가능한 이메일을 포함합니다.

### 2. 새 Blueprint 생성 — 여기부터 비용 발생

1. [Render Dashboard](https://dashboard.render.com/)에서 본인의 **Hobby workspace**를 선택합니다. Hobby는 워크스페이스 요금제이며 앱·DB 비용과 별개입니다.
2. **New → Blueprint**에서 `NAMSSAJANG/Stock-Analyzer` 저장소를 연결합니다.
3. 브랜치 **`goldnam/v0.0.0-a.1`**, Blueprint 경로 **`goldnam-sachs/render.yaml`**을 지정합니다. 파일이 push되어 있어야 합니다.
4. 미리보기의 새 리소스가 **goldnam-sachs / goldnam-sachs-db 두 개**, 지역이 모두 **Singapore**인지 확인합니다. 기존 Streamlit 서비스가 변경 대상이면 연결 대상을 다시 확인합니다.
5. 앱 **0.5c-512mb**(옛 Starter), DB **0.1c-256mb**(옛 Basic-256mb), 저장 공간 **1GB**, 자동 확장 꺼짐을 확인합니다. YAML에 용량을 명시하여 기본 15GB 선택을 피합니다.
6. `APP_PASSCODE_HASH`에 위 해시를 넣습니다. `SESSION_SECRET`은 Render가 생성하고 `DATABASE_URL`은 DB 내부 주소를 연결합니다. `OPENDART_API_KEY`, `SEC_USER_AGENT`는 준비된 값만 입력합니다. 아직 없으면 빈 값으로 둡니다. 입력 화면이 생략을 허용하지 않으면 생성 전 이 두 `sync:false` 항목만 제거하고, 나중에 Environment에서 추가합니다.
7. 예상 금액을 확인한 뒤 **NAMSSA가 생성/배포 버튼을 누릅니다**. Docker가 Next 정적 화면과 FastAPI를 함께 빌드합니다. 자동 배포는 꺼져 있으므로 후속 업데이트도 수동입니다.
8. `/api/v1/health`에서 `auth_configured`, `database_configured`가 true인지 확인합니다. `/`는 로그인으로 이동해야 합니다. `/health`는 기존 테스트 호환 경로입니다.

로그인 출처는 Render의 `RENDER_EXTERNAL_URL`을 사용합니다. 사용자 도메인을 추가했다면 `PUBLIC_BASE_URL`에 그 HTTPS origin만 설정하고 재배포합니다(경로 없이).

### 3. GitHub 시크릿과 첫 배치

저장소 **Settings → Secrets and variables → Actions → New repository secret**에 등록합니다.

| 시크릿 | 값 |
|---|---|
| `GOLDNAM_DATABASE_URL` | Render DB **Connect → External** 주소. `?sslmode=require` 추가(기존 쿼리가 있으면 `&sslmode=require`) |
| `OPENDART_API_KEY` | 준비한 OpenDART 키 |
| `SEC_USER_AGENT` | 실제 SEC 연락처 문자열 |

앱은 Internal, GitHub Actions는 External DB 주소를 사용합니다. GitHub 러너 IP가 바뀌므로 Blueprint DB 외부 허용 목록은 `0.0.0.0/0`입니다. 외부 연결에는 DB 인증과 TLS가 필요합니다. 고정 IP 러너라면 CIDR을 좁힐 수 있습니다. `ipAllowList: []`는 외부 배치를 차단합니다.

**Actions → Goldnam research batches → Run workflow**에서 브랜치, `daily`, `both`를 선택합니다. 휴일이면 `as_of`에 직전 거래일(YYYY-MM-DD)을 넣습니다. 키 없이도 시세 팩터·타이밍은 계산하지만 종합 점수는 결측 기준을 지킵니다. 한국 KRX가 계속 실패하면 해당 작업은 실패로 남고 미국 작업은 독립 실행됩니다.

이후 `validate`, `both`를 실행합니다. 상세 Parquet는 Actions artifact(30일), 화면용 요약은 DB에 저장합니다. **현재 검증 배치는 가격 팩터만 검증합니다.** 키 설정만으로 재무 시계열 검증이 자동 완성되지 않으며, 가격 검증을 종합 점수 근거로 승격하지 않습니다.

스케줄은 workflow가 GitHub 기본 브랜치에 들어간 뒤 동작합니다. 이 작업은 자동 merge하지 않습니다. 사용자 검토·merge 후 일정:

- 한국: 평일 15:50 KST (UTC 06:50)
- 미국: 평일 16:40 EST / 17:40 EDT (UTC 21:40)
- 주간 검증: 토요일 12:17 KST (UTC 03:17)

거래소 달력으로 휴장일을 건너뛰고 예정 실행이 장 마감 전이면 거부합니다. GitHub 스케줄은 지연될 수 있습니다. DB 시크릿이 없으면 명시적으로 skip합니다.

### 4. 배포 점검과 홈 화면 추가

```bash
uv run python scripts/post_deploy_check.py https://본인앱.onrender.com
# 실제 공급자 시세까지 검사
uv run python scripts/post_deploy_check.py https://본인앱.onrender.com --live-prices
```

비밀번호는 숨김 입력합니다. health·미인증 차단·쿠키·주요 API·로그아웃을 확인하며 시크릿/응답 데이터는 출력하지 않습니다. 실제 시세는 공급자 상태에 따라 실패할 수 있습니다.

- iPhone: Safari에서 HTTPS 주소 → 로그인 → 공유 → **홈 화면에 추가**.
- Android: Chrome에서 HTTPS 주소 → 로그인 → 메뉴 → **홈 화면에 추가/앱 설치**.
- 설정에서 테마를 고른 뒤 설치하면 해당 로고를 사용합니다. 기존 아이콘 변경은 OS에 따라 제거 후 재추가가 필요할 수 있습니다.
- 오프라인에서는 연결 없음과 마지막 조회 시각만 표시합니다. API와 로그인된 페이지를 서비스워커 캐시에 저장하지 않습니다.
- 세션 30일, HttpOnly·Secure·SameSite=Lax. 로그아웃 또는 해시 변경 시 기존 세션 무효화.

## 월 비용 — 2026-11-23 공식 문서 확인

| 구성 | Hobby | 앱 | DB 계산 자원 | DB 저장 1GB | 합계 |
|---|---:|---:|---:|---:|---:|
| 현재 Blueprint | $0 | $7 | $6 | $0.30 | **$13.30** |
| 앱 1c-2g 선택 | $0 | $25 | $6 | $0.30 | $31.30 |
| 임시 무료 실험 | $0 | $0 | $0 | 포함 | $0, sleep·DB 30일 만료 |

세금·초과 트래픽·별도 사용료 제외. DB 5GB 선택 시 저장 요금은 $1.50입니다. **$13은 계산 자원만 합친 값**입니다. 저장 자동 확장은 꺼져 있으므로 용량을 확인하고 직접 늘립니다. 축소는 불가합니다. 이력이 쌓이면 1GB를 넘을 수 있습니다.

공개 GitHub 저장소의 표준 Actions는 무료 범위에서 실행됩니다. 비공개 전환 시 무료 분량과 artifact 비용을 확인하세요. 이 작업에서 유료 리소스를 생성하거나 배포하지 않았습니다.

[가격](https://render.com/pricing) · [플랜](https://render.com/docs/compute-plans) · [DB 저장·연결](https://render.com/docs/postgresql-creating-connecting) · [Blueprint](https://render.com/docs/blueprint-spec) · [무료 제한](https://render.com/docs/free)

## 로컬 실행과 검사

```bash
uv sync --frozen --all-groups --extra api
pnpm -C web install --frozen-lockfile
uv run python scripts/export_openapi.py
pnpm -C web generate:api
pnpm -C web build
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=goldnam_engine --cov=api --cov=jobs --cov-report=term-missing
pnpm -C web lint
pnpm -C web typecheck
pnpm -C web test
uv run python scripts/run_legacy_checks.py smoke_test.py
uv run python scripts/run_legacy_checks.py test_trade_ui.py
uv run python scripts/run_legacy_checks.py test_execution_ui.py
uv run python scripts/run_legacy_checks.py test_analysis_ui.py
uv run python scripts/validate_blueprint.py
docker compose config --quiet
```

기본 pytest는 네트워크 차단, live 제외입니다. 실제 공급자는 `uv run pytest -m live --force-enable-socket ...`로 명시적으로 검사합니다. 키 없는 PIT live는 skip이며 통과로 세지 않습니다.

Compose는 앱 하나와 DB 하나입니다. `.env`에 해시·충분히 긴 무작위 세션 시크릿을 넣고(Argon2 해시는 `$` 확장을 막도록 작은따옴표로 감쌉니다) `docker compose -p goldnam-local up --build`로 실행합니다. `http://localhost:10000`, 로컬 DB 포트 비공개/trust 인증. Secure 쿠키의 localhost 정책이 브라우저마다 달라 **폰은 실제 HTTPS 배포 주소**로 확인합니다. 자동 검사는 HTTPS fixture 서버를 씁니다. 테스트 코드·비밀번호는 운영 이미지에 포함하지 않습니다.

```bash
pnpm -C web exec playwright install --with-deps chromium webkit
openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/goldnam-e2e.key -out /tmp/goldnam-e2e.crt -days 1 -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
PYTHONPATH=. uv run python web/e2e/server.py
# 다른 터미널
pnpm -C web exec playwright test
pnpm -C web exec node e2e/lighthouse.mjs
```

프록시 빌드 CA는 `docker build --secret id=build_ca,src=/path/to/ca-bundle.crt -t goldnam-sachs:alpha .`로 이미지에 남기지 않고 전달할 수 있습니다.

## v6 가져오기·백업·가정

```bash
uv run goldnam import-v6 /path/to/stock_analyzer_v6.sqlite --dry-run
# DATABASE_URL 설정 후 새 DB에 병합
uv run goldnam import-v6 /path/to/stock_analyzer_v6.sqlite
uv run goldnam import-v6 /path/to/history.json
```

원본 SQLite는 읽기 전용. 폰에서는 **기록 → v6 JSON 가져오기**(2MB 이하). 같은 종목/날짜 재가져오기는 중복되지 않습니다. `legacy_history`, `score_version=v6`로 새 점수와 분리합니다. 관심종목·거래 일지·설정·v6 이력은 **설정 → JSON 내보내기/가져오기**로 옮깁니다. 분석 이력/배치 전체 백업은 Render DB export를 사용합니다.

Trade Lab은 저장한 비용을 적용합니다. 통화는 표시 단위이며 환전하지 않습니다. 모든 보유·현금·계좌 숫자를 같은 통화로 입력하세요. 최대 8종목, 업종 2종목/30%, 히트 6% 한도를 적용합니다. 거래 일지는 시간 입력이 없어 **거래일 이전**에 알려진 점수·계획만 연결합니다. 없으면 결측을 표시하며 미래/당일 종가를 소급하지 않습니다.

히트맵은 시가총액을 확보한 배치 종목만 표시합니다. 외부 시세·실적 일정·환율은 출처와 시각을 확인하세요. 한국 공급자 제한은 [Phase 4](docs/PHASE4_REPORT.md)에 공개했습니다.

## 운영 제약

단일 사용자·단일 worker·단일 인스턴스입니다. 로그인 제한(분당 5회)은 메모리에 있어 재시작 시 초기화됩니다. 신뢰되지 않은 forwarded IP를 사용하지 않으므로 Render 프록시 뒤의 클라이언트가 제한을 공유할 수 있습니다. 다중 사용자로 확대하려면 공유 rate limiter와 신뢰 프록시 설정이 필요합니다.

DB 용량·앱 메모리·배치 실패 알림을 확인하세요. 512MB에서 긴 체결 검증을 동시에 반복하면 부담이 될 수 있으므로 유니버스 전체 계산은 Actions에서 합니다.

정보 제공·학습 목적이며 투자 조언이 아닙니다. Goldnam Sachs는 개인 프로젝트이며 Goldman Sachs와 관련이 없습니다.
