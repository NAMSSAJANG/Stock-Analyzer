"""Offline numerical regressions for v6_A_0.2: python -m unittest test_calculations_v602."""
import math
import random
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from calibration_engine import run_setup_calibration, wilson_interval
from technical_engine import _adx, build_technical_snapshot, period_return
from trade_engine import Costs, Position, affordable_shares, dec, plan_ladder, position_size, simulate, target_average


class AccountingTests(unittest.TestCase):
    def test_invalid_text_and_missing_values(self):
        for value in (None, "", "oops", "nan", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dec(value)

    def test_full_exit_has_exact_zero_basis(self):
        p = Position(3, "33.33333333333333333333333333", 10, 50)
        p.trade("매도", 3, 60)
        self.assertEqual(p.basis, 0)
        self.assertEqual(p.snapshot(60)["보유수량"], 0)

    def test_cost_components_reconcile(self):
        p = Position(0, 0, 2000, 100, Costs(.001, .002, .003, .01))
        p.trade("매수", 10, 100)
        p.trade("매도", 10, 100)
        s = p.snapshot(100)
        self.assertAlmostEqual(s["누적 수수료·거래세"], 5.96)
        self.assertAlmostEqual(s["누적 체결오차 비용"], 20)
        self.assertAlmostEqual(s["청산가정 총손익"], -25.96)
        self.assertEqual(s["체결 건수"], 2)

    def test_rejected_order_does_not_charge(self):
        p = Position(1, 100, 0, 100, Costs(.01, .01))
        before = p.snapshot(100)
        with self.assertRaises(ValueError):
            p.trade("매수", 1, 100)
        self.assertEqual(p.snapshot(100), before)

    def test_liquidation_break_even_includes_realized_profit(self):
        p = Position(10, 100, 100, 100, Costs(sell_fee=.01))
        p.trade("매도", 5, 120)
        be = p.snapshot(100)["전체투자 본전가"]
        self.assertAlmostEqual(p.snapshot(be)["청산가정 총손익"], 0, places=9)
        self.assertLess(be, p.snapshot(100)["잔여주식 본전가"])

    def test_net_hold_equality_and_drawdowns(self):
        rows, _ = simulate(10, 100, 0, [100, 120, 90], [], Costs(sell_fee=.1))
        for row in rows:
            self.assertEqual(row["청산가정 총자산"], row["단순보유 청산가정 총자산"])
            self.assertEqual(row["청산 후 단순보유 대비"], 0)
        self.assertEqual(rows[-1]["최대낙폭(%)"], -25)
        self.assertEqual(rows[-1]["청산가정 최대낙폭(%)"], -25)
        self.assertEqual(rows[0]["청산가정 기간수익률(%)"], -10)

    def test_generator_rules_are_not_consumed_by_validation(self):
        rule = {"매매": "매도", "조건": "이상", "기준가격": 110, "수량": 1}
        rows, journal = simulate(2, 100, 0, [100, 120], (r for r in [rule]))
        self.assertEqual(rows[-1]["보유수량"], 1)
        self.assertEqual(len(journal), 1)

    def test_invalid_rule_shape_and_fractional_holdings(self):
        with self.assertRaises(ValueError):
            simulate(1, 100, 100, [100, 120], [{"수량": 1}])
        with self.assertRaises(ValueError):
            target_average(1.5, 100, 70, 90)

    def test_reserved_sale_proceeds(self):
        p = Position(10, 100, 100, 100, recycle=False)
        p.trade("매도", 2, 100)
        self.assertEqual(p.snapshot(100)["매수가능 현금"], 100)
        p.trade("매수", 1, 100)
        self.assertEqual(p.snapshot(100)["매수가능 현금"], 0)
        self.assertEqual(p.snapshot(100)["현금"], 200)

    def test_many_trades_conserve_book_profit(self):
        rng = random.Random(61)
        p = Position(20, 100, 5000, 90, Costs(.001, .002, .001, .005))
        for _ in range(250):
            price = rng.randint(50, 180)
            if rng.random() < .5:
                quantity = min(rng.randint(1, 10), affordable_shares(p.cash, price, p.costs))
                side = "매수"
            else:
                quantity = min(rng.randint(1, 10), int(p.shares))
                side = "매도"
            if quantity:
                p.trade(side, quantity, price)
            s = p.snapshot(price)
            self.assertGreaterEqual(p.cash, 0)
            self.assertGreaterEqual(p.shares, 0)
            self.assertAlmostEqual(s["실현손익"] + s["평가손익"], s["총자산"] - float(p.initial_book), places=8)
            liquidation_cost = p.shares * (dec(price) - p.costs.sell_unit(price))
            self.assertAlmostEqual(s["청산가정 총손익"], s["실현손익"] + s["평가손익"] - float(liquidation_cost), places=8)


class SizingTests(unittest.TestCase):
    def test_known_risk_and_payoff(self):
        s = position_size(10000, 8000, 100, 90, 120, 1, 25)
        self.assertEqual(s["수량"], 10)
        self.assertEqual(s["손절 예상손실"], 100)
        self.assertEqual(s["목표 예상순이익"], 200)
        self.assertEqual(s["순손익비"], 2)
        self.assertAlmostEqual(s["손익분기 승률(%)"], 100 / 3)

    def test_cash_and_position_caps(self):
        self.assertEqual(position_size(10000, 299, 100, 90, 120)["수량"], 2)
        self.assertEqual(position_size(10000, 9000, 100, 90, 120, max_position_pct=5)["수량"], 5)
        self.assertEqual(position_size(10000, 9000, 100, 90, 120, risk_multiplier=.5)["수량"], 5)

    def test_costs_and_gap_reduce_quantity(self):
        base = position_size(10000, 10000, 100, 90, 120)
        cost = position_size(10000, 10000, 100, 90, 120, costs=Costs(.001, .002, .003, .01))
        gap = position_size(10000, 10000, 100, 90, 120, costs=Costs(.001, .002, .003, .01), gap_pct=5)
        self.assertLess(cost["수량"], base["수량"])
        self.assertLess(gap["수량"], cost["수량"])
        self.assertEqual(gap["손절 체결 가정가"], 85.5)
        self.assertLessEqual(gap["손절 예상손실"], 100)

    def test_no_positive_target_profit(self):
        s = position_size(10000, 10000, 100, 90, 101, costs=Costs(.02, .02))
        self.assertLess(s["순손익비"], 0)
        self.assertIsNone(s["손익분기 승률(%)"])

    def test_zero_budget(self):
        for kwargs in ({"risk_pct": 0}, {"max_position_pct": 0}, {"risk_multiplier": 0}):
            self.assertEqual(position_size(10000, 10000, 100, 90, 120, **kwargs)["수량"], 0)

    def test_invalid_risk_inputs(self):
        for args in [(100, 101, 100, 90, 120), (100, 10, 100, 100, 120), (100, 10, 100, -1, 120), (100, 10, 100, 90, 99)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                position_size(*args)

    def test_ladder_reserves_cash(self):
        rows = plan_ladder(1000, [100, 80], [1, 1], reserve_pct=20)
        self.assertEqual([r["매수수량"] for r in rows], [4, 5])
        self.assertEqual(rows[-1]["잔여 현금"], 200)
        rows = plan_ladder(1000, [100, 80], [1, 1], Costs(buy_fee=.01), reserve_pct=20)
        self.assertGreaterEqual(rows[-1]["잔여 현금"], 200)
        self.assertEqual(sum(r["투입액"] for r in rows), 626.2)

    def test_ladder_empty_zero_and_rounding(self):
        for reserve in (0, 20, 100):
            rows = plan_ladder(1000, ["33.3333"] * 7, [1] * 7, reserve_pct=reserve)
            self.assertGreaterEqual(rows[-1]["잔여 현금"], 1000 * reserve / 100)
        self.assertEqual(plan_ladder(0, [100], [1])[0]["매수수량"], 0)
        for prices, weights in (([], []), ([100], [0]), ([100], [1, 2])):
            with self.assertRaises(ValueError):
                plan_ladder(1000, prices, weights)


class StatisticsTests(unittest.TestCase):
    def test_return_counts_intervals(self):
        s = pd.Series(np.arange(1, 254, dtype=float))
        self.assertAlmostEqual(period_return(s, 22), (253 / 231 - 1) * 100)
        self.assertEqual(period_return(s, 252), 25200)
        self.assertTrue(math.isnan(period_return(s.iloc[:-1], 252)))

    def test_flat_prices_adx_finite_and_history_not_shortened(self):
        d = pd.DataFrame({k: [100.0] * 230 for k in ("Open", "High", "Low", "Close")})
        d["Volume"] = 1000
        adx, atr = _adx(d)
        self.assertEqual(adx.iloc[-1], 0)
        self.assertEqual(atr.iloc[-1], 0)
        tech = build_technical_snapshot(d)
        self.assertEqual(tech.adx, 0)
        self.assertTrue(math.isnan(tech.ret_12m))
        self.assertTrue(math.isfinite(tech.trend))

    def test_wilson_reference_and_extremes(self):
        low, high = wilson_interval(5, 10)
        self.assertAlmostEqual(low, 23.6593, places=4)
        self.assertAlmostEqual(high, 76.3407, places=4)
        self.assertAlmostEqual(wilson_interval(0, 10)[0], 0)
        self.assertAlmostEqual(wilson_interval(10, 10)[1], 100)
        self.assertGreater(wilson_interval(0, 10)[1], 0)
        self.assertTrue(math.isnan(wilson_interval(0, 0)[0]))
        with self.assertRaises(ValueError):
            wilson_interval(11, 10)

    def _calibrate(self, missing=False, absent=False):
        idx = pd.bdate_range("2024-01-01", periods=330)
        d = pd.DataFrame({"Close": 100 + np.arange(330) / 10}, index=idx)
        b = d * 2
        if missing:
            b = b.drop(idx[250])
        setup = SimpleNamespace(score=80, status="READY")
        with patch("calibration_engine.build_technical_snapshot"), patch("calibration_engine.build_risk_snapshot"), patch("calibration_engine.build_zones"), patch("calibration_engine.build_setups", return_value=SimpleNamespace(pullback=setup, momentum=setup)):
            return run_setup_calibration(d, None if absent else b)

    def test_benchmark_same_dates_and_no_fill(self):
        detail, summary = self._calibrate()
        self.assertEqual(summary.iloc[0]["Validation 20D"], 4)
        self.assertEqual(summary.iloc[0]["Benchmark Samples 20D"], 4)
        self.assertAlmostEqual(summary.iloc[0]["Avg Excess 20D"], 0)
        self.assertTrue(detail.tail(20)["excess_20d"].isna().all())
        _, missing = self._calibrate(missing=True)
        self.assertEqual(missing.iloc[0]["Benchmark Samples 20D"], 2)
        self.assertEqual(missing.iloc[0]["Validation 20D"], 4)

    def test_absent_benchmark_and_worst_case(self):
        detail, summary = self._calibrate(absent=True)
        row = summary.iloc[0]
        self.assertEqual(row["Benchmark Samples 20D"], 0)
        self.assertTrue(math.isnan(row["Avg Excess 20D"]))
        self.assertEqual(row["Worst MDD20"], 0)
        sample = detail.loc[detail["pullback_sample_20d"], "fwd_20d"]
        self.assertEqual(row["Worst 20D"], sample.min())


if __name__ == "__main__":
    unittest.main()
