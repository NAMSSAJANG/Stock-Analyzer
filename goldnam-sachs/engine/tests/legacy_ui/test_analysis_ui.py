"""Offline checks of the updated analysis panels with synthetic prices."""
from streamlit.testing.v1 import AppTest


def verify(at):
    assert not at.exception, [x.message for x in at.exception]


sizing = AppTest.from_string('''
import app
from types import SimpleNamespace
setup = SimpleNamespace(name="Test", entry_price=100, stop_loss=90, target1=120, risk_pct=10)
risk = SimpleNamespace(position_size_multiplier=.75, level="MODERATE")
app.render_position_sizing(setup, "TEST", risk, "테스트")
''', default_timeout=30).run()
verify(sizing)
sizing.text_input(key="acct_Test_TEST").set_value("nan").run()
verify(sizing)
assert any("올바르게" in x.value for x in sizing.info)
sizing.text_input(key="acct_Test_TEST").set_value("10,000").run()
sizing.number_input(key="sizing_cash_Test_TEST").set_value(299.0).run()
verify(sizing)
assert any(m.label == "참고 수량" and m.value == "2주" for m in sizing.metric)
sizing.number_input(key="sizing_weight_Test_TEST").set_value(1.0).run()
verify(sizing)
assert any(m.label == "참고 수량" and m.value == "1주" for m in sizing.metric)

cal = AppTest.from_string('''
import app
from smoke_test import make_momentum
from core_models import MarketRegimeSnapshot
frame, bench = make_momentum()
import streamlit as st
if st.checkbox("가격 갱신 테스트", key="test_refresh"):
    frame.loc[frame.index[-1], "Close"] *= 1.001
market = MarketRegimeSnapshot("US", 72, "Risk-On", {}, {}, 1.0, "")
tech = app.build_technical_snapshot(frame, bench)
risk = app.build_risk_snapshot(tech, market, 30)
zones = app.build_zones(frame, tech)
setups = app.build_setups(float(frame.Close.iloc[-1]), tech, market, zones, risk)
app.render_calibration({"setups": setups, "frame": frame, "benchmark": bench}, "TEST")
''', default_timeout=30).run()
verify(cal)
cal.slider[0].set_value(30).run()
next(b for b in cal.button if "과거 진입 검증 실행" in b.label).click().run()
verify(cal)
assert any("95% 참고구간 하한(%)" in d.value.columns for d in cal.dataframe)
assert any("평균 시장 초과수익(%p)" in d.value.columns for d in cal.dataframe)
cal.button(key="ex_run").click().run()
verify(cal)
assert any("체결 사례" in d.value.columns for d in cal.dataframe)
cal.checkbox(key="test_refresh").check().run()
verify(cal)
assert not any("95% 참고구간 하한(%)" in d.value.columns for d in cal.dataframe)
assert any("과거 진입 검증 실행" in i.value for i in cal.info)
print("Analysis sizing and calibration UI checks passed")
