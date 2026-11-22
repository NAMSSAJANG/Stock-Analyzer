"""Execution assumptions are separate from close-to-close calibration statistics."""
import streamlit as st

from calibration_cache import data_signature
from execution_engine import EXECUTION_LOGIC_VERSION, run_execution_study
from trade_core import Costs


def render_execution_lab(frame, detail, symbol, threshold):
    with st.expander("다음 날 시가 · 손절·목표 체결 검증", expanded=False):
        st.caption("신호일 종가까지 계산한 손절·목표를 고정하고 다음 거래일 시가로 신규 진입합니다. 아래 결과는 개별 거래의 성과이며 계좌 전체 누적 수익률이 아닙니다.")
        c = st.columns(4)
        days = c[0].number_input("최대 보유 거래일", 1, 60, 20, key="ex_days")
        buy = c[1].number_input("매수 수수료 (%)", 0.0, 10.0, 0.0, .01, key="ex_buy")
        sell = c[2].number_input("매도 수수료 (%)", 0.0, 10.0, 0.0, .01, key="ex_sell")
        tax = c[3].number_input("매도 거래세 (%)", 0.0, 10.0, 0.0, .01, key="ex_tax")
        slip = st.number_input("불리한 체결오차 (%)", 0.0, 10.0, 0.0, .01, key="ex_slip")
        st.markdown("각 진입 방식은 독립적으로 한 포지션만 보유합니다. 다음 시가가 손절가 이하 또는 목표가 이상이면 진입을 제외합니다. 손절 아래로 갭 하락하면 시가로 청산하고, 하루에 손절·목표가 모두 닿으면 **손절 우선**으로 계산합니다. 목표가 위로 갭 상승하면 보수적으로 목표가에 체결합니다. 진입 당일도 보유기간에 포함하며, 최대 보유기간 전체 데이터가 있는 신호만 평가합니다.")
        st.caption("부분 체결·호가·거래정지·유동성 한도는 모델링하지 않습니다. 조정 OHLC 기준이며 과거 시장점수는 기존 Calibration과 같이 50점입니다. 수수료·세금·체결오차 기본값은 0이므로 원하는 가정을 직접 입력하세요.")
        signature = (EXECUTION_LOGIC_VERSION, symbol, threshold, data_signature(frame, detail),
                     days, buy, sell, tax, slip)
        key = f"execution_result_{symbol}"
        if st.button("체결 조건 검증 실행", key="ex_run"):
            st.session_state.pop(key, None)
            try:
                ledger, summary = run_execution_study(frame, detail, threshold, days,
                                                      Costs(buy / 100, sell / 100, tax / 100, slip / 100))
                st.session_state[key] = (signature, ledger, summary)
            except ValueError as exc:
                st.error(str(exc))
        saved = st.session_state.get(key)
        if saved and saved[0] != signature:
            st.info("체결 조건이나 데이터가 바뀌었습니다. 체결 조건 검증을 다시 실행하세요.")
            return
        if saved:
            _, ledger, summary = saved
            st.dataframe(summary, hide_index=True, width="stretch")
            st.dataframe(ledger, hide_index=True, width="stretch")
            st.download_button("체결 검증 CSV", ledger.to_csv(index=False).encode("utf-8-sig"),
                               f"{symbol}_execution.csv", "text/csv", key="ex_csv")
            if summary.empty or not summary["체결 사례"].sum():
                st.info("이 조건에서 체결된 사례가 없습니다. 제외 사유를 확인하세요.")
