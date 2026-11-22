# 데이터 공급자 계약

확인일: 2026-11-23 (한국). 공식 문서 확인과 실계정 호출 성공은 별개다.

- [yfinance download](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html): 수정 OHLC, 시작 포함/끝 제외. 종료일 +1일로 요청한다.
- [FinanceDataReader](https://github.com/FinanceData/FinanceDataReader): 한국 종목 코드, USD/KRW. 한국 시세 우선, 미국 시세 폴백.
- [SEC XBRL API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [자동 접근](https://www.sec.gov/about/developer-resources): company_tickers → CIK companyfacts. 연락처 User-Agent 필수. 직렬 요청 간격 0.15초(10 requests/s 미만). 단위/기간/공시일로 선택; 미래 정정공시 제외.
- [OpenDART 공시검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001), [고유번호](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018), [원본 XBRL](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019019): 종목 → corpCode.xml → list.json(last_reprt_at=N, 접수일 범위, 페이지네이션) → fnlttXbrl.xml(rcept_no, reprt_code). 당시 제출된 원본만 사용한다. 현재 연도별 계정 API 결과를 과거 PIT라고 저장하지 않는다. 직접 문서 요청 503 후 검색 도구의 공식 문서 열기로 계약 확인.
- [pykrx](https://github.com/sharebook-kr/pykrx): 지수 이름으로 KOSPI200/KOSDAQ150 구성 조회. 업종 미확보 시 결측, 시장 전체 순위로 확장한다.
- [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars): XNYS/XKRX 거래일과 휴장. 캘린더의 미래 일정은 변경될 수 있다.
- 미국 현재 구성은 Wikipedia의 S&P500/Nasdaq100 표를 합집합으로 저장한다. 과거 구성 복원으로 주장하지 않는다. 원문 표 변경/접속 실패 시 마지막 스냅샷과 stale 표시.

## 제한

SEC/OpenDART 키는 사용자가 나중에 설정하기로 했다. 라이브 PIT 수집은 미검증이다. XBRL 표준 태그만 인식하며 사용자 확장 태그는 누락될 수 있다. 연결/별도 다중 인스턴스가 모호한 공시는 제외한다. 한국 비12월 결산사의 분기 보고서 매핑은 확인 전 제외한다. 연간 손익·재무상태와 별도의 분기 YoY를 사용하며, 누적 반기 수치를 분기값으로 간주하지 않는다. 한국 실적일은 확보된 소스가 없어 미확인이다.

캐시는 실패를 성공으로 저장하지 않는다. 3회 지수 재시도, 5분 음성 캐시/회로 차단, 최신 소스 우선 후 stale 복구. OHLCV Parquet는 삭제 가능한 캐시이며 원본 조회·기준 시각을 유지한다. SQL 영구 저장소와 역할을 구분한다.
