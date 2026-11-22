# Phase 6 · 로그인·모바일 웹

2026-11-23. 정적 Next.js 화면을 FastAPI와 같은 주소로 제공한다. 실제 데이터가 없을 때 부분 점수·미검증·소스 실패를 표시한다. 브라우저 테스트는 명시적 고정 데이터이며 실제 투자 성과가 아니다.

| 완료 기준 | 상태 / 증거 |
|---|---|
| 홈·검색·종목·스크리너·근거·시장·설정·기록·Trade Lab | 구현, 정적 빌드 성공 |
| iPhone 390×844 / Android 412×915 흐름 | WebKit / Chromium 각각 로그인→검색→종목→스크리너 통과 |
| 데스크톱 | 1440×1000 동일 흐름 통과 |
| 부분 점수 배지 | 재무 없는 테스트 데이터에서 표시·스크린샷 확인 |
| 모바일 카드·하단 5탭·종목 한 열 순서 | Playwright 확인 및 이미지 육안 검토 |
| 로그인 보호 | 실제 Argon2·Secure/HttpOnly/SameSite 쿠키 사용, API 회귀 테스트 |
| PWA | 두 테마 standalone manifest·아이콘 200, Chromium 오프라인 안내·마지막 조회 시각, 캐시에 offline.html/js만 있는지 확인 |
| 접근성 | 로그인·종목 axe 위반 0. Lighthouse 접근성 양 화면 100 |
| 로고·폰트 | OFL Roboto Serif 첫 후보 SVG, Pretendard 자체 호스팅, 원본/라이선스 보존 |

## 실행 결과

[브라우저 원문](test-results/phase6-browser.txt): **3 passed (22.5s)**. [빌드 원문](test-results/phase6-build.txt). [Lighthouse 요약](../docs/lighthouse/summary.json), 상세 JSON은 같은 폴더. 첫 측정 성능 로그인/종목은 요약 참조. 점수를 임의로 올려 쓰지 않는다. 콘솔 HEAD 405는 정적 호스트의 HEAD 지원을 추가해 수정했으며 최종 재검증에 포함한다.

Lighthouse 13은 PWA category를 제공하지 않는다. PWA는 Playwright로 매니페스트/아이콘/서비스워커/오프라인/개인 캐시 부재를 별도로 확인했다. 로컬 자체 서명 인증서 때문에 WebKit의 서비스워커 신뢰 검증은 제외했고, WebKit에서 로그인·검색·종목·스크리너·테마 흐름은 실제 실행했다. 실물 iPhone 설치는 사용자가 배포한 뒤 확인해야 한다.

환경의 WebKit 의존 라이브러리는 Debian 공식 패키지를 임시 폴더에 풀어 사용했다. 호스트 패키지 목록 점검은 생략했으나 실제 WebKit 브라우저 실행과 화면 검사는 생략하지 않았다. CI는 공식 `playwright install --with-deps`를 사용한다.

## 화면

| 화면 | iPhone | Android | 데스크톱 |
|---|---|---|---|
| 로그인 | [이미지](screenshots/iphone-login.png) | [이미지](screenshots/android-login.png) | [이미지](screenshots/desktop-login.png) |
| 홈 | [이미지](screenshots/iphone-home.png) | [이미지](screenshots/android-home.png) | [이미지](screenshots/desktop-home.png) |
| 검색 | [이미지](screenshots/iphone-search.png) | [이미지](screenshots/android-search.png) | [이미지](screenshots/desktop-search.png) |
| 종목 | [이미지](screenshots/iphone-stock.png) | [이미지](screenshots/android-stock.png) | [이미지](screenshots/desktop-stock.png) |
| 스크리너 | [이미지](screenshots/iphone-screener.png) | [이미지](screenshots/android-screener.png) | [이미지](screenshots/desktop-screener.png) |
| 공개 테마 | [이미지](screenshots/iphone-settings-goldnam.png) | [이미지](screenshots/android-settings-goldnam.png) | [이미지](screenshots/desktop-settings-goldnam.png) |

변경: web/app·components·lib·theme·public, API 정적 호스트/조회 계약, 배치 타이밍/리스크, 브라우저 테스트, SVG/아이콘 생성 스크립트. 기록 가져오기 계약과 Trade Lab 비용/한도 보정도 후속 화면 연결을 위해 추가했다. Phase 7에서 가져오기·비교 화면과 원래 Trade Lab 회귀를 마무리한다.

남은 외부 조건: PIT 키, 한국 유니버스 공급자 정상 응답, 실제 Render 배포 및 실물 홈 화면 추가. 이 작업에서는 배포하지 않는다.
