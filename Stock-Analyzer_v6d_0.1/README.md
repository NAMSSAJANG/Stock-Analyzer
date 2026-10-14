# Stock Analyzer v-6d_0.1

Streamlit 개인 테스트 버전. 기존 V6.0.22 계열 엔진을 별도 패키지로 복사하고 웹 화면, 데이터 조회, 분석 연결, 저장을 분리했습니다.

## 실행

Windows: PowerShell에서 이 폴더의 `start.ps1`을 실행하거나 아래 명령을 사용합니다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m streamlit run app.py --server.address 127.0.0.1
```

기본 주소는 http://127.0.0.1:8501 입니다. 시작 파일은 `app.py`, 버전은 `v-6d_0.1`입니다.

## 구현 범위

- 오늘의 시장: 한국·미국 지표, 지수 차트, 가격 기반 매크로 비교, 종목별 공급처 뉴스.
- 후보 찾기: 선택한 대표 종목/관심종목의 가격 변화·50일 평균·거래량 비교. 전체 시장 Scanner 아님.
- 종목 분석: Company, Technical, MarketRegime, Opportunity, Setup, Risk, Consensus 연결. 분석 실행 시 입력 자료와 결과를 저장.
- 투자 가설: 사용자가 관심 이유·반대 근거·확인 질문을 작성하고 저장.
- 일정: Yahoo Finance의 기업 실적 예정일/범위, 출처 있는 경제·기업 일정 직접 등록, 추적 저장.
- 내 투자: 관심종목·메모·질문 지속 저장, 관련 분석 이동, 추적 일정, JSON 백업 내보내기.
- 기록: 추가 방식의 분석·판단 기록, 이전 점수·확인 사항 비교. 같은 입력과 엔진 버전의 중복 분석은 저장하지 않음.

## 테스트 범위와 운영 경계

한 PC의 한 사용자를 위한 버전입니다. 로그인 없이 로컬 DB를 공유하므로 여러 사용자에게 그대로 공개하지 마세요. 서버는 기본적으로 localhost에만 바인딩됩니다. 데이터는 `.data/workspace.sqlite`에 저장됩니다. 환경변수 `ANALYZER_DATA_DIR`로 영구 저장 경로를 지정할 수 있습니다. 외부 호스팅에서 임시 디스크를 쓰면 기록이 사라질 수 있습니다.

실제 가격·기업 정보·뉴스·실적 예정일은 Yahoo Finance/yfinance에서 조회합니다. 실시간 또는 전체 종목의 제공을 보장하지 않습니다. 원문 링크·기준일·수집 시각을 표시하고, 실패 시 마지막 정상 캐시가 있으면 지연 상태로 보여줍니다. 조회는 요청별 65초에 중단되며 새로고침으로 재시도할 수 있습니다. 기본 캐시는 15분, 화면 캐시는 10분입니다. 자동 백그라운드 갱신이 아니라 화면 조회/분석 실행 시 갱신합니다.

일봉은 배당·분할 조정 가격이며 장중에는 미완성 당일 일봉이 포함될 수 있습니다. 주문용 실시간 호가가 아닙니다. 기업 정보는 현재 조회 자료이므로 과거 시점 재무 자료를 사용한 백테스트가 아닙니다. 뉴스는 공급처의 종목별 검색 결과이며 직접 언급·수혜를 보장하지 않습니다. 한국어 자동 번역, AI 기사 요약, 기업 관계 그래프는 미연결입니다.

경제지표 자동 달력, 옵션 분석, 동종기업 상대평가, 보유 계좌·손익·주문 실행, 외부 알림, 백업 복원 UI, Strategy Lab과 OOS/Walk-forward는 이번 테스트 범위에 포함하지 않았습니다. 원본의 Calibration 등 엔진 파일은 보존하되 전체 전략 검증으로 표시하지 않습니다.

## 엔진 보존과 수정점

`engine/`는 원본 계산 코드를 보존하고 import만 상대 경로로 변경했습니다. `engine-provenance.json`에 원본·복사본 해시가 있습니다. 원본 위치: `obsidian-v6-c-0.1-update/working/program-source/analyzer-by-kijungnam-v6-c-0.1`.

`analysis_service.py`가 다음 입력·표시 보정을 수행합니다.

- 한국 거래대금을 위험 엔진에 넣기 전에 원/달러로 환산. 환율 없으면 분석 보류.
- 실적 미확인 표시를 중립과 분리. 위험 엔진의 미확인 기본값은 그대로 유지하고 화면에서 그 한계를 표시.
- 기준지수 부족 시 상대강도/종합 분석 보류. 시장 자료는 종목 가격 기준일 이후 행을 제거.
- 가격 7일 초과, 회사 자료 충족도 부족, 실적 미확인 등은 확인 필요로 표시. 이 상태를 매수 허가로 사용하지 않음.
- 입력 묶음·엔진 버전·자료 수집 상태를 함께 저장. 분석/판단/입력 테이블에는 수정·삭제 방지 트리거 적용.

## 구성

```text
app.py                 Streamlit 화면과 이동
provider.py            캐시·시간 제한·실패 복구
provider_worker.py     외부 자료 수집
analysis_service.py    기존 엔진 연결과 데이터 상태 표시
engine/                기존 순수 계산 엔진
store.py               SQLite 개인 데이터·입력·분석·판단 저장
tests/                 계산·저장·실제 화면 흐름 검증
```

테스트: `.venv/Scripts/python.exe -m unittest discover -s tests -v`

개발 참고: [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest), [yfinance Ticker](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html).
