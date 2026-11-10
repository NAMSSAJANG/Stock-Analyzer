# v6_A_0.4 · Scenario Lab

기존 V6 분석에 **내 가정 → 가치 변화 → 가격에 내재된 기대치 → 가정 기록** 흐름을 추가했습니다.
실행 폴더 이름은 배포 경로 호환을 위해 `analyzer-by-kijungnam-v6c-0.1`을 유지합니다.
메인 시작 파일은 이 폴더의 `app.py`입니다.

## 사용 순서

1. 새 `🔭 Scenario Lab` 메뉴를 엽니다. 종목 없이도 가상 예제를 사용할 수 있습니다.
2. 실제 자료는 종목 검색·선택 후 `선택 종목 자료 불러오기`로 가져오거나 직접 입력합니다.
3. 매출·순차입금은 **백만 통화단위**, 주식 수는 **백만 주**, 가격은 **통화/주**입니다.
   자료의 단위·기간·통화·주식종류를 확인합니다. 금융업과 EBITDA가 0 이하인 기업은 이 모형에 적합하지 않습니다.
4. 성장률·영업이익률·CAPEX·희석·말기 EV/EBITDA를 조절합니다. 할인율·세율·감가상각·운전자본도 수정할 수 있습니다.
5. 주당 현재가치, 조건부 성장률 역산, 현금흐름, 성장률×배수 민감도를 확인합니다.
6. 근거 메모와 함께 `현재 가정 기록하기`를 누릅니다. 기록 펼침에서 JSON, 하단에서 현금흐름 CSV를 내보냅니다.

## 데이터와 기록

- Yahoo Finance/yfinance의 totalRevenue, sharesOutstanding, totalDebt, totalCash, currentPrice/regularMarketPrice를 사용합니다.
- 재무 통화와 가격 통화가 다르거나 확인되지 않으면 가격을 비웁니다. 환산·ADR 비율 처리는 자동으로 하지 않습니다.
- 빠진 순차입금 등을 0으로 대체하지 않습니다. 값이 없으면 계산을 보류합니다.
- 조회 시각은 캐시 자료를 가져온 시각일 수 있습니다. 공급처 mostRecentQuarter/regularMarketTime은 원자료 펼침에서 확인합니다.
- 성장률 등 초기 슬라이더 값과 MODEL A는 예시이며, 실제 컨센서스를 제공하지 않습니다.
- 종목별 입력 초안은 메뉴를 바꿔도 같은 세션에서 유지됩니다. 가상 예제와 실제 종목을 분리합니다.
- 기준 자료 변경 시 확인 체크가 초기화되고 이전 계산 결과는 숨겨집니다. 기록은 당시 입력·결과·출처·모형 버전을 새 스냅샷으로 추가합니다.
- 기록은 **브라우저 세션에만 보관**합니다(최대 100건). JSON 내보내기로 보관하세요. 서버 영구 DB·계정 동기화·JSON 복원은 이번 범위에 없습니다.
- 기존 점수 History와 매매 계산 엔진에는 시나리오 가정을 반영하지 않습니다.

## 계산 모형

각 연도 매출 = 전년 매출 × (1 + 성장률).

FCFF = EBIT − max(EBIT, 0) × 세율 + 감가상각 − CAPEX − 운전자본 증가.
운전자본 증가 = (당년 매출 − 전년 매출) × 운전자본 비율.

기업가치 = 기간별 FCFF 현재가치 합 + 마지막 연도 EBITDA × 말기 배수의 현재가치.
주주가치 = 기업가치 − **현재** 순차입금.
주당 모형 가치 = 주주가치 ÷ (현재 주식 수 × (1 + 희석률)^기간).

전체 현재가치를 말기 희석 주식 수로 나누는 단순화입니다. 주식 발행대금, 미래 차입금 변화,
이월결손과 환급, 자사주 매입, 투자와 성장의 인과관계는 반영하지 않습니다.
마이너스 잔여가치는 음수 주가 예측이 아닙니다. 금융업·복수 주식종류·ADR은 추가 모델링이 필요합니다.

역산은 −60~100% 범위의 매출 성장률을 다항식으로 풉니다. 음수 중간 현금흐름으로 가치가 비단조적일 수 있으므로
여러 실근이면 모두 표시하고 하나의 시장 기대치로 선택하지 않습니다. 범위 밖 또는 성장률을 특정할 수 없는 경우도 별도로 표시합니다.

계산 참고: [Damodaran — Cash Flow to the Firm](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/littlebook/cashflows.htm),
[Value/EBITDA Multiples](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/lectures/vebitnote.html).
이 단순화 모형과 UI 설계는 위 자료의 권고나 인증을 의미하지 않습니다.

## 검증과 실행

```bash
python -m pip install -r requirements.txt
python verify_release.py
python -m unittest test_trade_engine test_calculations_v602 test_execution_engine test_scenario_engine test_scenario_ui
python smoke_test.py
python test_trade_ui.py
python test_analysis_ui.py
python test_execution_ui.py
streamlit run app.py
```

추가 검증: 손계산 FCFF 대조, 단위 환산 불변성, CAPEX·희석 변화, 적자 세금,
복수 역산 해, 결측·통화 불일치, 스냅샷 독립성, 슬라이더 갱신, 메뉴 이동 후 복원, 기준 변경 시 결과 숨김.
수치·화면 자동 검증은 오프라인 합성자료 기준입니다. 실제 공급처 자료 정확성이나 배포 서버와의 연결을 보증하지 않습니다.
