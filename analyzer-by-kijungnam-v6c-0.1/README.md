# Stock Analyzer v6_A_0.3

Multi-Lens Stock Setup & Decision System.

A Streamlit-based stock analysis tool for evaluating company quality, trend, momentum, relative strength, market conditions, entry setups, and risk. Pullback Entry and Momentum Entry are evaluated separately.

## Main Features

- V6 Integrated Decision Dashboard
- Opportunity & Company Quality
- Pullback / Momentum Entry
- Quant Profile, Chart Interpretation & CAN SLIM
- US / KR Market Regime
- Risk & Support / Resistance
- Options Analysis
- Setup Scanner
- Score History & Historical Entry Validation
- Trade Lab: cost-inclusive accounting, liquidation comparison, risk sizing,
  staged buy budgets, downside stress comparison, and CSV exports
- Historical validation: Wilson reference intervals, matched-date benchmark
  excess returns, and worst observed outcomes

먼저 [업로드 안내](업로드_안내.md)를 확인하세요. 수정 내역·클로드 평가 대조·검증 범위는 [개선사항_v6_A_0.3.md](개선사항_v6_A_0.3.md)에 정리했습니다.

새 기능: 과거 진입 검증 화면에서 다음 날 시가·손절·목표·매매비용을 반영한 별도 체결 검증과 CSV를 제공합니다.

## Run

```bash
pip install -r requirements.txt
python verify_release.py
streamlit run app.py
```

Python 3.12에서 검증했습니다. 기존 실행 중인 앱을 종료한 뒤 새 버전으로 다시 실행하세요.
Trade Lab은 종목 검색이나 인터넷 시세 조회 없이 사용할 수 있습니다.
수수료·매도세·체결오차의 기본값은 0이며 사용자가 직접 입력합니다.
통화 선택은 금액의 단위 표시이며 자동 환전 기능이 아닙니다.

## Offline checks

```bash
python -m unittest test_trade_engine test_calculations_v602 test_execution_engine
python smoke_test.py
python test_trade_ui.py
python test_analysis_ui.py
python test_execution_ui.py
```

Trade Lab 계산 결과는 같은 브라우저 세션 안에서 유지됩니다. 계산 조건을 바꾸면
이전 결과를 숨기고 재계산을 안내합니다. 브라우저 종료 후에도 보관하려면 CSV를 저장하세요.
새 ZIP은 실행 코드·검증 코드·설명서만 포함하며 기존 History DB는 포함하지 않습니다.
기존 History를 이전하려면 앱을 종료한 상태에서 `.data/stock_analyzer_v6.sqlite`를
새 폴더의 같은 위치에 복사하세요. 원본 DB는 먼저 별도로 보관하세요.

12M 수익률은 종가 253개가 필요합니다. 이력이 부족하면 해당 지표를 제외하므로
이전 버전과 일부 점수가 달라질 수 있습니다. 과거 검증 캐시도 새 버전으로 다시 계산됩니다.

Public market data may be delayed, incomplete, or temporarily unavailable.

**For informational and educational purposes only. This project does not constitute investment advice.**
