# Phase 8 · 배포 준비와 최종 상태

2026-11-23. **배포 준비 구현 완료, 실제 Render 생성·배포 없음**. 기존 서비스 변경·main merge·유료 리소스 생성은 하지 않았다. 실제 외부 데이터 완료 기준은 아래처럼 부분 충족이다.

| Phase | 완료 기준 상태 |
|---|---|
| 0 기존 이식 | 통과. 원본 19개 모듈 AST·기존 49개 테스트 보존, 기존 원격 CI 통과 |
| 1 공급자 | 모킹/폴백/캐시 통과, US/KR 시세 3개씩 live 통과. PIT 6개는 키/연락처 미설정으로 skip |
| 2 점수·배치 | 결측·정수·메타데이터·미국 518종목 측정 통과. 재무 부족으로 종합 점수 산출 불가를 그대로 표시 |
| 3 전략 수정 | 실패 재현 후 회귀 통과. 과열·저항·트리거·환율·미확인 실적 규칙 반영 |
| 4 검증 | 합성 통과. US 511종목 및 KR 부분 1종목 실제 A/B/C·계좌 보고. **KR 전체·PIT 재무 시계열·종합 근거 미완료** |
| 5 API | 26개 경로 계약·인증·오류·저장 테스트, OpenAPI→TS 생성 |
| 6 웹·모바일 | iPhone WebKit/Android Chromium/desktop 흐름 통과. axe 위반 0. 개인 데이터를 캐시하지 않는 PWA 구현 |
| 7 Trade Lab·기록 | 기존 회귀·시드 재현·비용·갭·포트폴리오·v6 읽기 전용 가져오기 통과. 모바일 입력 흐름 통과 |
| 8 Render 준비 | 단일 앱+유료 최소 DB+Singapore Blueprint schema 통과, Docker·Postgres·재시작 유지 통과, README·Actions·점검 스크립트 작성. **새 Render 계정에서의 실제 배포는 미실행** |

## 실제 최종 검사

- Python: **134 passed, 13 deselected**, 12 subtests, engine/api/jobs 통합 커버리지 **86.48%**. [원문](test-results/final-python.txt)
- ruff check/format, strict mypy(65 source files): 통과. [lint](test-results/final-lint.txt), [mypy](test-results/final-mypy.txt)
- 원래 4종 스크립트: 모두 통과. [원문](test-results/phase7-legacy.txt)
- 웹 lint/typecheck/Vitest/정적 build: [원문](test-results/final-web.txt)
- Playwright: **4 passed, 2 skipped (28.2초)**. 3브라우저 탐색은 모두 실행, Trade Lab/기록 중복 흐름만 2브라우저에서 생략. [원문](test-results/phase7-browser-final.txt)
- Lighthouse: 로그인 성능/접근성/best-practices **100/100/100**, 종목 **73/100/100**. [요약](lighthouse/summary.json). PWA category가 제거된 Lighthouse 13이므로 PWA는 manifest/icon/offline/cache 자동 검사로 별도 확인.
- 운영 Docker: 비관리자 UID 10001로 기동, 정적/API 로그인 보호, PostgreSQL 쓰기/읽기, 재시작 유지, 로그아웃 확인. [원문](test-results/phase8-container.txt), [빌드](test-results/phase8-docker-build.txt)
- 배포 점검 스크립트: 로컬 HTTPS fixture 대상으로 통과. [원문](test-results/post-deploy-local.txt). Render 실배포 점검으로 세지 않음.
- 미국 최종 일일 배치: 2026-11-20 기준 **518/518 시세**, 재무 미설정으로 종합 **0개**, 타이밍·리스크를 포함해 **28.032초**(따뜻한 가격 캐시, DB 쓰기 제외). [원문](test-results/final-us-batch.txt)
- 로컬 실제 PostgreSQL live 통합 테스트 **1 passed**. [원문](test-results/final-postgres.txt)
- Render: 최신 공식 JSON schema 로컬 검증 통과. [근거 문서](RENDER_PREPARATION.md), [원문](test-results/final-blueprint.txt). 원격 리소스 생성/validation API 미실행.

## 알려진 한계와 사용자에게 남은 작업

1. 사용자가 OpenDART·SEC 설정을 나중에 하기로 했다. 키는 코드/로그에 없다. 수집 계약은 구현했지만 PIT 실수집과 종합 점수의 과거 근거는 완료로 표시하지 않는다.
2. KRX 유니버스 API 빈 응답, 삼성전자/NAVER 장기 OHLC 품질 실패로 한국 전체 검증을 못했다. 검사를 완화하거나 값을 보정하지 않았다.
3. 현재 구성 유니버스 생존 편향. 미국 518개 중 7개는 장기 검증에 포함하지 못했다. 최종 수익성이 좋지 않아 파라미터/기본 청산을 최적화하지 않았다.
4. 스마트폰 크기·WebKit/Chromium 자동 테스트를 수행했다. 실물 폰의 홈 화면 설치는 사용자가 HTTPS 배포 후 확인한다. 자체 서명 로컬 WebKit 서비스워커 신뢰 검사는 제외하고 Chromium에서 offline/cache를 확인했다.
5. 앱은 단일 사용자/worker이며 프록시 뒤 rate limit은 보수적으로 공유될 수 있다. Light mode는 명세의 낮은 우선순위 항목으로 미구현. 종목 Lighthouse 성능 73, 레이아웃 이동/주 스레드 비용 개선 여지.
6. 비용은 Hobby $0 + 앱 $7 + DB $6 + 저장 1GB $0.30 = **월 $13.30**, 세금/초과 사용 제외. 최종 Blueprint 생성·배포는 NAMSSA가 README대로 직접 실행한다.

원격 PR CI 상태는 아래 추적 절에 기록한다. 이 보고서의 로컬 테스트와 혼동하지 않는다.

## 원격 CI 추적

Phase 2까지 원격 CI 성공을 확인했다. 최종 브랜치 push 후 원격 검사를 추적 중이며 최종 결과는 이 절에 추가한다.
