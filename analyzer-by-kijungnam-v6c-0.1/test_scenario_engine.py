"""Numerical, data-boundary and snapshot regressions for Scenario Lab."""
from dataclasses import replace
import json
import unittest

from scenario_engine import ScenarioInputs, evaluate, implied_growth, make_snapshot, source_defaults


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.base = ScenarioInputs(100., 10., 20., 10., growth=.1, margin=.2,
                                   capex=.1, dilution=0., multiple=10., years=1,
                                   discount=.1, tax=.25, depreciation=.05, working_capital=.02)

    def test_hand_calculated_cash_flow_and_ev_bridge(self):
        r = evaluate(self.base)
        # Sales 110; EBIT 22; tax 5.5; D&A 5.5; capex 11; WC 0.2 => FCFF 10.8.
        self.assertAlmostEqual(r["flows"][0]["fcff"], 10.8)
        self.assertAlmostEqual(r["terminal"], 275.)
        self.assertAlmostEqual(r["value"], ((10.8 + 275) / 1.1 - 20) / 10)

    def test_scale_invariance_and_net_cash(self):
        r = evaluate(self.base)
        scaled = replace(self.base, revenue=100e6, shares=10e6, net_debt=20e6)
        self.assertAlmostEqual(evaluate(scaled)["value"], r["value"])
        self.assertAlmostEqual(evaluate(replace(self.base, net_debt=-20))["value"] - r["value"], 4.)

    def test_capex_and_dilution_effects(self):
        base = evaluate(self.base)["value"]
        self.assertLess(evaluate(replace(self.base, capex=.3))["value"], base)
        self.assertAlmostEqual(evaluate(replace(self.base, dilution=.1))["value"], base / 1.1)

    def test_losses_do_not_create_tax_refunds(self):
        r = evaluate(replace(self.base, margin=-.1, depreciation=.2))
        self.assertEqual(r["flows"][0]["taxes"], 0.)

    def test_negative_equity_remains_visible(self):
        self.assertLess(evaluate(replace(self.base, net_debt=10000))["value"], 0.)

    def test_invalid_inputs_rejected(self):
        for field, value in [("revenue", 0), ("shares", -1), ("price", 0), ("net_debt", float("nan")),
                             ("growth", float("inf")), ("years", 1.5), ("years", True), ("years", 11),
                             ("multiple", 0), ("discount", 0), ("capex", -1), ("margin", -1)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evaluate(replace(self.base, **{field: value}))

    def test_implied_growth_recovers_input_across_horizons(self):
        for years in (1, 3, 5, 10):
            original = replace(self.base, years=years, growth=.27)
            reverse = implied_growth(replace(original, price=evaluate(original)["value"]))
            self.assertEqual(reverse["status"], "unique")
            self.assertAlmostEqual(reverse["roots"][0], .27, places=7)

    def test_implied_growth_boundaries_and_out_of_range(self):
        for growth in (-.6, 1.):
            original = replace(self.base, net_debt=0, growth=growth)
            r = implied_growth(replace(original, price=evaluate(original)["value"]))
            self.assertAlmostEqual(r["roots"][0], growth)
        self.assertEqual(implied_growth(replace(self.base, price=1e9))["status"], "outside_range")

    def test_non_monotonic_case_returns_both_roots(self):
        case = ScenarioInputs(100., 1., -1 - (50 / 1.21) * .45 * .65, 1., years=2,
                              margin=.1, capex=.6, tax=0., depreciation=0., working_capital=0.,
                              dilution=0., multiple=10., discount=.1)
        r = implied_growth(case)
        self.assertEqual(r["status"], "multiple")
        for actual, expected in zip(r["roots"], [-.55, -.35]):
            self.assertAlmostEqual(actual, expected)

    def test_zero_growth_sensitivity_is_not_a_unique_expectation(self):
        case = replace(self.base, margin=.1, tax=0., depreciation=0., capex=.2, working_capital=0.,
                       multiple=1., net_debt=-100., price=10.)
        self.assertEqual(implied_growth(case)["status"], "indeterminate")

    def test_provider_missing_values_and_currency_mismatch(self):
        r = source_defaults({"currency": "USD", "financialCurrency": "KRW", "currentPrice": 10,
                             "totalRevenue": 2e9, "sharesOutstanding": 1e8, "totalDebt": 0})
        self.assertEqual(r["revenue"], 2000.)
        self.assertEqual(r["shares"], 100.)
        self.assertIsNone(r["net_debt"])
        self.assertIsNone(r["price"])
        self.assertFalse(r["currency_compatible"])
        self.assertIsNone(source_defaults({})["price"])

    def test_valid_zero_debt_and_quote_fallback(self):
        r = source_defaults({"currency": "KRW", "financialCurrency": "KRW", "regularMarketPrice": 80000,
                             "totalDebt": 0, "totalCash": 2e9, "sharesOutstanding": float("nan")})
        self.assertEqual(r["net_debt"], -2000.)
        self.assertEqual(r["price"], 80000.)
        self.assertIsNone(r["shares"])

    def test_snapshot_freezes_source_and_keeps_distinct_ids(self):
        source = {"original": {"revenue": 100}}
        a = make_snapshot(self.base, "TEST", "USD", source, "test")
        b = make_snapshot(self.base, "TEST", "USD", source)
        source["original"]["revenue"] = 1
        self.assertEqual(a["source"]["original"]["revenue"], 100)
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(json.loads(json.dumps(a, allow_nan=False))["inputs"]["revenue"], 100)


if __name__ == "__main__":
    unittest.main()
