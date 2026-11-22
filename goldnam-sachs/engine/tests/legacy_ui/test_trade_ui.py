"""Offline Streamlit interaction checks: python test_trade_ui.py."""
from pathlib import Path
from streamlit.testing.v1 import AppTest


def verify(at):
    assert not at.exception, [x.message for x in at.exception]


at = AppTest.from_string("from trade_lab import render_trade_lab\nrender_trade_lab()", default_timeout=30).run()
verify(at)
at.button(key="tl_calc").click().run()
verify(at)
assert len(at.dataframe) >= 3
at.button(key="tl_sim").click().run()
verify(at)
assert any(len(d.value) == 15 for d in at.dataframe)
# An unrelated input rerun must retain computed results and their downloads.
at.number_input(key="tl_win").set_value(60.0).run()
verify(at)
assert any(len(d.value) == 15 for d in at.dataframe)
assert any(m.label == "청산 후 단순보유 대비" for m in at.metric)
# Relevant changes hide stale results until recalculation.
at.number_input(key="tl_bf").set_value(0.1).run()
verify(at)
assert not any(len(d.value) == 15 for d in at.dataframe)
assert any("계산 조건이 바뀌었습니다" in x.value for x in at.info)
at.button(key="tl_sim").click().run()
verify(at)
assert any(len(d.value) == 15 for d in at.dataframe)
at.text_input(key="tl_path").set_value("70, nan, 80").run()
at.button(key="tl_sim").click().run()
verify(at)
assert at.error
at.text_input(key="tl_path").set_value("70, 80, 60, 90").run()
at.button(key="tl_sim").click().run()
verify(at)
assert any(len(d.value) == 18 for d in at.dataframe)
at.number_input(key="tl_available").set_value(999999.0).run()
verify(at)
assert any("계좌 평가액 이하" in x.value for x in at.info)
at.number_input(key="tl_available").set_value(1400.0).run()
at.number_input(key="tl_reserve").set_value(100.0).run()
verify(at)
plans = [d.value for d in at.dataframe if "하락 시 청산 총자산" in d.value.columns]
assert plans and (plans[0]["매수수량"] == 0).all()
at.number_input(key="tl_shares").set_value(0).run()
verify(at)
at.button(key="tl_sim").click().run()
verify(at)
at.number_input(key="tl_cash").set_value(0.0).run()
verify(at)
assert any("초기 총자산" in x.value for x in at.info)
app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=30).run()
verify(app)
menu = next(r for r in app.radio if "🧮 Trade Lab" in r.options)
menu.set_value("🧮 Trade Lab").run()
verify(app)
assert any("Trade Lab" in h.value for h in app.header)
print("Trade Lab UI and main-menu integration checks passed")
