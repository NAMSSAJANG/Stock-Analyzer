"""Offline UI checks for fills, stale results, and stale-module deployment."""
from streamlit.testing.v1 import AppTest


def verify(at):
    assert not at.exception, [x.message for x in at.exception]


at = AppTest.from_string('''
import streamlit as st
from test_execution_engine import ExecutionTests
from execution_lab import render_execution_lab
f, s = ExecutionTests().fixture(signal_count=5)
render_execution_lab(f, s, "TEST", 75)
''', default_timeout=30).run()
verify(at)
at.number_input(key="ex_days").set_value(3).run()
at.button(key="ex_run").click().run()
verify(at)
assert any("순수익률(%)" in d.value for d in at.dataframe)
at.number_input(key="ex_buy").set_value(.1).run()
verify(at)
assert not at.dataframe
assert any("바뀌었습니다" in i.value for i in at.info)
at.button(key="ex_run").click().run()
verify(at)
assert any("평균 순수익률(%)" in d.value and (d.value["평균 순수익률(%)"].dropna() < 0).all()
           for d in at.dataframe)

# Reproduce an already-loaded incompatible legacy module. The application must
# still use the release's own core and open Trade Lab successfully.
legacy = AppTest.from_string('''
import sys
import runpy
from types import ModuleType
sys.modules["trade_engine"] = ModuleType("trade_engine")
runpy.run_path("app.py", run_name="__main__")
''', default_timeout=30).run()
verify(legacy)
next(r for r in legacy.radio if "🧮 Trade Lab" in r.options).set_value("🧮 Trade Lab").run()
verify(legacy)
assert any("Trade Lab" in h.value for h in legacy.header)

missing = AppTest.from_string('''
import builtins
import runpy
from unittest.mock import patch
original_import = builtins.__import__
def missing_trade(name, *args, **kwargs):
    if name == "trade_core":
        raise ModuleNotFoundError("simulated missing trade_core")
    return original_import(name, *args, **kwargs)
with patch("builtins.__import__", side_effect=missing_trade):
    runpy.run_path("app.py", run_name="__main__")
''', default_timeout=30).run()
verify(missing)
assert any("전체 파일" in e.value and "Reboot" in e.value for e in missing.error)
print("Execution UI and incompatible legacy-module startup checks passed")
