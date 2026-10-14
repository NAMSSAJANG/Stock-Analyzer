import unittest

import numpy as np
import pandas as pd

from calibration_cache import calibration_key
from execution_engine import run_execution_study
from trade_core import Costs


class ExecutionTests(unittest.TestCase):
    def fixture(self, bars=None, signal_count=1):
        bars = bars or [[100, 105, 95, 100]] * 7
        frame = pd.DataFrame(bars, columns=["Open", "High", "Low", "Close"],
                             index=pd.bdate_range("2025-01-01", periods=len(bars)))
        signals = pd.DataFrame({"date": frame.index[:signal_count].strftime("%Y-%m-%d"),
                                "pullback": 80, "momentum": 0,
                                "pullback_stop_loss": 90, "pullback_target1": 120,
                                "momentum_stop_loss": 90, "momentum_target1": 120})
        return frame, signals

    def first(self, bars, **kwargs):
        f, s = self.fixture(bars)
        ledger, _ = run_execution_study(f, s, holding_days=3, **kwargs)
        return ledger.iloc[0]

    def test_next_open_not_signal_close_and_costs(self):
        row = self.first([[100, 101, 99, 100], [110, 115, 105, 112],
                          [112, 119, 100, 115], [115, 119, 100, 118]],
                         costs=Costs(.01, .02, .01, .01))
        expected = (118 * .99 * .97 / (110 * 1.01 * 1.01) - 1) * 100
        self.assertAlmostEqual(row["순수익률(%)"], expected)
        self.assertEqual(row["진입 시가"], 110)
        self.assertEqual(row["사유"], "기간 종료")
        self.assertEqual(row["보유 거래일"], 3)

    def test_both_barriers_stop_first_on_entry_day(self):
        row = self.first([[100, 105, 95, 100], [100, 125, 85, 110],
                          [110, 115, 100, 110], [110, 115, 100, 110]])
        self.assertEqual(row["청산 기준가"], 90)
        self.assertEqual(row["보유 거래일"], 1)
        self.assertIn("손절 우선", row["사유"])

    def test_stop_gap_fills_open(self):
        row = self.first([[100, 105, 95, 100], [100, 105, 95, 100],
                          [80, 85, 75, 82], [82, 85, 80, 82]])
        self.assertEqual(row["청산 기준가"], 80)
        self.assertEqual(row["사유"], "손절 갭")

    def test_target_gap_uses_conservative_limit(self):
        row = self.first([[100, 105, 95, 100], [100, 105, 95, 100],
                          [130, 135, 125, 132], [132, 135, 125, 132]])
        self.assertEqual(row["청산 기준가"], 120)

    def test_target_touch(self):
        row = self.first([[100, 105, 95, 100], [100, 121, 95, 115],
                          [110, 115, 100, 110], [110, 115, 100, 110]])
        self.assertEqual(row["사유"], "목표")

    def test_invalid_entry_gap_is_excluded(self):
        f, s = self.fixture()
        f.iloc[1] = [80, 85, 75, 80]
        ledger, summary = run_execution_study(f, s, holding_days=3)
        self.assertEqual(ledger.iloc[0]["상태"], "제외")
        self.assertEqual(summary.iloc[0]["체결 사례"], 0)

    def test_no_overlap_and_full_window_required(self):
        f, s = self.fixture(signal_count=7)
        ledger, summary = run_execution_study(f, s, holding_days=3)
        self.assertEqual(summary.iloc[0]["체결 사례"], 2)
        self.assertEqual(ledger["사유"].tolist().count("기존 포지션 보유 중"), 4)
        self.assertEqual(ledger.iloc[-1]["사유"], "최대 보유기간 데이터 부족")

    def test_incomplete_window_excluded_even_when_target_already_hit(self):
        f, s = self.fixture([[100, 105, 95, 100], [100, 125, 95, 120]])
        ledger, _ = run_execution_study(f, s, holding_days=3)
        self.assertEqual(ledger.iloc[0]["상태"], "제외")

    def test_strategies_are_independent(self):
        f, s = self.fixture()
        s["momentum"] = 80
        _, summary = run_execution_study(f, s, holding_days=3)
        self.assertEqual(summary["체결 사례"].tolist(), [1, 1])

    def test_missing_plan_is_excluded(self):
        f, s = self.fixture()
        s["pullback_stop_loss"] = np.nan
        ledger, _ = run_execution_study(f, s, holding_days=3)
        self.assertEqual(ledger.iloc[0]["상태"], "제외")

    def test_invalid_bars_do_not_silently_shorten_history(self):
        f, s = self.fixture()
        for bad in (np.nan, 0, np.inf):
            changed = f.astype(float).copy()
            changed.iloc[2, 0] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                run_execution_study(changed, s)
        with self.assertRaises(ValueError):
            run_execution_study(f.iloc[::-1], s)
        with self.assertRaises(ValueError):
            run_execution_study(pd.concat([f, f.iloc[-1:]]), s)

    def test_missing_signal_date_is_rejected(self):
        f, s = self.fixture()
        s["date"] = "2020-01-01"
        with self.assertRaises(ValueError):
            run_execution_study(f, s)

    def test_future_after_exit_does_not_change_trade(self):
        f, s = self.fixture()
        original, _ = run_execution_study(f, s, holding_days=3)
        f.iloc[4:] = [200, 210, 190, 200]
        changed, _ = run_execution_study(f, s, holding_days=3)
        pd.testing.assert_frame_equal(original, changed)


class CacheTests(unittest.TestCase):
    def test_signal_plans_do_not_use_future_prices(self):
        from calibration_engine import run_setup_calibration
        from smoke_test import make_momentum
        frame, benchmark = make_momentum()
        original, _ = run_setup_calibration(frame, benchmark)
        revised = frame.copy()
        revised.loc[revised.index[-10:], ["Open", "High", "Low", "Close"]] *= 2
        changed, _ = run_setup_calibration(revised, benchmark)
        columns = ["date", "pullback", "momentum", "pullback_stop_loss", "pullback_target1",
                   "momentum_stop_loss", "momentum_target1"]
        pd.testing.assert_frame_equal(original.iloc[:-10][columns], changed.iloc[:-10][columns])

    def test_stock_and_benchmark_revisions_invalidate_result(self):
        f, _ = ExecutionTests().fixture()
        key = calibration_key("TEST", 75, f, f)
        self.assertEqual(key, calibration_key("TEST", 75, f.copy(), f.copy()))
        revised = f.copy()
        revised.iloc[0, 3] += 1
        self.assertNotEqual(key, calibration_key("TEST", 75, revised, f))
        self.assertNotEqual(key, calibration_key("TEST", 75, f, revised))
        self.assertNotEqual(key, calibration_key("TEST", 80, f, f))
        self.assertNotEqual(key, calibration_key("TEST", 75, f, None))


class KoreanSearchTests(unittest.TestCase):
    def test_default_fallback_when_all_endpoints_fail(self):
        from korean_stock_search import load_krx_listing, search_krx_listing

        def unavailable(*args):
            raise ConnectionError("offline")

        listing = load_krx_listing(stock_listing=unavailable)
        self.assertEqual(search_krx_listing("삼성전자", listing)[0]["symbol"], "005930.KS")


if __name__ == "__main__":
    unittest.main()
