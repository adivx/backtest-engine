import math
import unittest

from backtest.engine import Trade
from backtest.metrics import (
    annualized_volatility,
    cagr,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    summarize,
    total_return,
    win_rate,
)


def trade(pnl):
    return Trade("", "", 0, 0, 0, pnl, 0.0)


class TestTotalReturn(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(total_return([100.0, 150.0]), 0.5)
        self.assertAlmostEqual(total_return([100.0, 100.0]), 0.0)

    def test_short_curve(self):
        self.assertEqual(total_return([]), 0.0)
        self.assertEqual(total_return([100.0]), 0.0)


class TestCAGR(unittest.TestCase):
    def test_doubling_over_one_year(self):
        # 252 daily returns spanning 100 -> 200 is exactly one year.
        curve = [100.0] + [100.0 + i * (100.0 / 252) for i in range(1, 253)]
        self.assertAlmostEqual(cagr(curve), 1.0, places=4)

    def test_no_return(self):
        curve = [100.0] * 253
        self.assertAlmostEqual(cagr(curve), 0.0, places=6)


class TestDrawdown(unittest.TestCase):
    def test_known_case(self):
        curve = [100.0, 120.0, 80.0, 130.0]
        dd, peak, trough = max_drawdown(curve)
        self.assertAlmostEqual(dd, 40.0 / 120.0, places=6)
        self.assertEqual((peak, trough), (1, 2))

    def test_monotonic_up_is_zero(self):
        curve = [100.0, 101.0, 102.0, 103.0]
        dd, _, _ = max_drawdown(curve)
        self.assertEqual(dd, 0.0)

    def test_half_loss(self):
        dd, _, _ = max_drawdown([100.0, 50.0, 100.0])
        self.assertAlmostEqual(dd, 0.5)


class TestRiskRatios(unittest.TestCase):
    def test_flat_series_zero_vol(self):
        # Float accumulation can leave ~1e-16 dust; treat that as zero.
        self.assertAlmostEqual(annualized_volatility([0.01] * 100), 0.0, places=12)
        self.assertEqual(sharpe_ratio([0.01] * 100), 0.0)
        self.assertEqual(sortino_ratio([0.01] * 100), 0.0)

    def test_sharpe_scales_with_mean(self):
        hi = sharpe_ratio([0.01, -0.005, 0.02] * 50)
        lo = sharpe_ratio([0.005, -0.005, 0.01] * 50)
        self.assertGreater(hi, lo)

    def test_short_inputs(self):
        self.assertEqual(sharpe_ratio([0.01]), 0.0)
        self.assertEqual(annualized_volatility([0.01]), 0.0)


class TestTradeStats(unittest.TestCase):
    def test_win_rate(self):
        self.assertAlmostEqual(win_rate([trade(10), trade(-5), trade(3), trade(8)]), 0.75)
        self.assertEqual(win_rate([]), 0.0)

    def test_profit_factor(self):
        self.assertAlmostEqual(profit_factor([trade(10), trade(20), trade(-5)]), 6.0)
        self.assertEqual(profit_factor([trade(10), trade(5)]), math.inf)


class TestSummarize(unittest.TestCase):
    def test_headline_metrics(self):
        curve = [100_000.0, 110_000.0, 95_000.0, 120_000.0]
        s = summarize(curve, [trade(5000.0), trade(-3000.0), trade(8000.0)], 100_000.0)
        self.assertAlmostEqual(s["final_equity"], 120_000.0)
        self.assertAlmostEqual(s["total_return_pct"], 20.0)
        # Peak at index 1 (110k), trough at index 2 (95k).
        self.assertAlmostEqual(s["max_drawdown_pct"], 15_000 / 110_000 * 100.0)
        self.assertEqual((s["dd_peak_idx"], s["dd_trough_idx"]), (1, 2))
        self.assertEqual(s["num_trades"], 3)
        self.assertAlmostEqual(s["win_rate_pct"], 200.0 / 3, places=4)
        self.assertAlmostEqual(s["profit_factor"], 13_000 / 3_000, places=6)

    def test_single_bar_curve(self):
        s = summarize([100_000.0], [], 100_000.0)
        self.assertAlmostEqual(s["final_equity"], 100_000.0)
        self.assertAlmostEqual(s["total_return_pct"], 0.0)
        self.assertEqual(s["num_trades"], 0)
        self.assertEqual(s["sharpe"], 0.0)


if __name__ == "__main__":
    unittest.main()
