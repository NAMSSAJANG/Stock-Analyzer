# Analyzer by Kijung V3.3

시장 환경부터 종목의 펀더멘털·테크니컬·진입 전략까지 한 흐름으로 연결하는 Streamlit 투자 의사결정 대시보드입니다. V3의 상세 분석을 유지하면서 Market Dashboard와 AI Score History를 추가했습니다.

## V3.3 주요 기능

- **Market Health**: 0~100 점수, Strong/Good/Neutral/Weak/Very Weak 등급, AI Confidence, Market Brief
- **Market Pulse 12종**: S&P 500, Nasdaq 100, SOX, VIX, Gold, Silver, WTI, Copper, USD/KRW, DXY, Bitcoin, Ethereum
- 각 Market Pulse 카드에 현재값, 등락률, 전일 종가=0% 기준 장중 sparkline
- PC 4열 × 3행, 모바일 2열 × 6행
- 미국채 2Y/10Y/30Y/10Y-2Y와 HYG/LQD/Credit Spread 보조 패널
- **AI Score History**: SQLite에 종목별 일별 스냅샷 누적, 이전 점수·변화량·변화 카테고리 표시
- 사이드바를 열지 않아도 사용할 수 있는 상단 `분석 / 시장환경 / Lab` 버튼형 메뉴
- 종합·펀더멘털·테크니컬·시장환경·추세/진입 분야별 상세 AI 브리핑
- 종합점수 해석, 실제 산출근거, 긍정·주의요인
- 펀더멘털, 테크니컬, 시장환경, 뉴스 점수
- 장기·단기 추세와 AI 눌림목 점수 및 산출근거
- 추천 진입가격대, 추천 비중, 3단계 분할 진입 전략
- 이동평균선, 진입구간, 지지·저항, 무효화선 통합 차트
- 돌파·지지·무효화 시나리오와 기간별 수익률
- 기간별 수익률 상승 초록색·하락 빨간색 표시
- Experimental Lab 메뉴(Coming Soon)

## 실행

Python 3.10 이상을 권장합니다.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## GitHub / Streamlit Community Cloud 배포

1. 이 폴더의 전체 파일을 GitHub 저장소에 업로드합니다.
2. Streamlit Community Cloud에서 저장소와 `app.py`를 선택합니다.
3. 별도 API 키 없이 실행할 수 있습니다.

앱 실행 중 `data/score_history.db`가 자동 생성됩니다. 로컬에서는 기록이 유지됩니다. Streamlit Community Cloud의 로컬 디스크는 재시작·재배포 시 초기화될 수 있으므로 장기 영구 저장이 필요하면 외부 DB로 교체해야 합니다. DB 파일은 개인정보를 담지 않으며 티커·점수·산출근거만 저장합니다.

## 프로젝트 구조

```text
.
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/config.toml
├── data/.gitkeep
└── modules/
    ├── analysis_engine.py
    ├── history_store.py
    ├── market_data.py
    └── models.py
```

## 데이터와 한계

가격·재무·뉴스 데이터는 Yahoo Finance를 사용하며 지연, 누락 또는 제공 중단이 발생할 수 있습니다. Market Health와 종목 점수는 설명 가능한 규칙 기반 참고값이며 미래 수익률을 예측하거나 보장하지 않습니다. 본 프로젝트는 교육·정보 제공용이며 투자 권유가 아닙니다.
