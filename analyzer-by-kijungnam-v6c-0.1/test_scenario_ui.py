"""Offline real Streamlit interaction checks; no network or shared DB."""
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


class ScenarioUITests(unittest.TestCase):
    def verify(self, at):
        self.assertFalse(at.exception, [e.message for e in at.exception])

    def test_slider_snapshot_and_menu_round_trip(self):
        at = AppTest.from_string('''
import streamlit as st
from scenario_lab import render_scenario_lab
if st.radio("Menu", ["Scenario", "Other"], key="test_menu") == "Scenario":
    render_scenario_lab()
''', default_timeout=30).run()
        self.verify(at)
        value = at.metric[0].value
        growth = next(s for s in at.slider if "성장률" in s.label)
        growth.set_value(30.).run()
        self.verify(at)
        self.assertNotEqual(at.metric[0].value, value)
        at.button(key="sc_save").click().run()
        self.verify(at)
        first = at.session_state["scenario_records"][0]
        self.assertEqual(first["inputs"]["growth"], .3)
        next(s for s in at.slider if "성장률" in s.label).set_value(40.).run()
        at.button(key="sc_save").click().run()
        self.assertEqual(at.session_state["scenario_records"][0], first)
        self.assertEqual(len(at.session_state["scenario_records"]), 2)
        at.radio(key="test_menu").set_value("Other").run()
        at.radio(key="test_menu").set_value("Scenario").run()
        self.verify(at)
        self.assertEqual(next(s.value for s in at.slider if "성장률" in s.label), 40.)

    def test_no_fabricated_values_manual_confirmation_and_stale_results(self):
        at = AppTest.from_string('''
from scenario_lab import render_scenario_lab
render_scenario_lab("TEST", lambda s: {"currency":"USD", "financialCurrency":"USD",
    "totalRevenue":100000000, "sharesOutstanding":10000000, "currentPrice":10,
    "totalDebt":20000000, "totalCash":0})
''', default_timeout=30).run()
        self.verify(at)
        self.assertEqual(len(at.metric), 0)
        at.button(key="sc_load").click().run()
        self.verify(at)
        self.assertEqual(len(at.metric), 0)
        at.checkbox[0].check().run()
        self.verify(at)
        self.assertGreater(len(at.metric), 0)
        next(n for n in at.number_input if "比較" in n.label or "비교 가격" in n.label).set_value(12.).run()
        self.verify(at)
        self.assertEqual(len(at.metric), 0)
        self.assertFalse(at.checkbox[0].value)

    def test_currency_mismatch_never_prefills_quote(self):
        at = AppTest.from_string('''
from scenario_lab import render_scenario_lab
render_scenario_lab("TEST", lambda s: {"currency":"USD", "financialCurrency":"KRW",
    "totalRevenue":100000000, "sharesOutstanding":10000000, "currentPrice":10,
    "totalDebt":0, "totalCash":0})
''', default_timeout=30).run()
        at.button(key="sc_load").click().run()
        self.verify(at)
        self.assertIsNone(next(n.value for n in at.number_input if "비교 가격" in n.label))
        self.assertEqual(len(at.metric), 0)
        self.assertTrue(any("통화" in w.value for w in at.warning))

    def test_main_menu_opens_without_stock_selection(self):
        at = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=30).run()
        self.verify(at)
        next(r for r in at.radio if "🔭 Scenario Lab" in r.options).set_value("🔭 Scenario Lab").run()
        self.verify(at)
        self.assertTrue(any("Scenario Lab" in h.value for h in at.header))
        self.assertGreater(len(at.metric), 0)


if __name__ == "__main__":
    unittest.main()
