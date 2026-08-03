import unittest

from backtest.data import generate_synthetic
from backtest.engine import Backtest
from backtest.strategy import BuyAndHold, MovingAverageCross


class TestBacktest(unittest.TestCase):
    def setUp(self):
        self.bars = generate_synthetic(seed=11, years=3)

    def test_buy_and_hold_zero_cost_tracks_price(self):
        result = Backtest(initial_cash=100_000).run(self.bars, BuyAndHold())
        first_open = self.bars[1].open
        expected = 100_000 * self.bars[-1].close / first_open
        self.assertAlmostEqual(result.final_equity, expected, delta=0.5)
        self.assertEqual(len(result.equity_curve), len(self.bars))

    def test_flat_during_warmup(self):
        strategy = MovingAverageCross(fast=20, slow=60)
        result = Backtest().run(self.bars, strategy)
        self.assertEqual(result.equity_curve[strategy.warmup() - 1], 100_000.0)

    def test_ma_cross_produces_trades(self):
        result = Backtest().run(self.bars, MovingAverageCross(20, 60))
        self.assertGreater(len(result.trades), 0)
        for t in result.trades:
            self.assertGreater(t.entry_price, 0)
            self.assertLessEqual(t.exit_date, self.bars[-1].date)

    def test_costs_reduce_equity(self):
        clean = Backtest().run(self.bars, MovingAverageCross(20, 60))
        costly = Backtest(commission=10.0, slippage=0.001).run(
            self.bars, MovingAverageCross(20, 60)
        )
        self.assertLess(costly.final_equity, clean.final_equity)

    def test_returns_length(self):
        result = Backtest().run(self.bars, BuyAndHold())
        self.assertEqual(len(result.returns()), len(self.bars) - 1)

    def test_empty_bars_rejected(self):
        with self.assertRaises(ValueError):
            Backtest().run([], BuyAndHold())

    def test_invalid_cash_rejected(self):
        with self.assertRaises(ValueError):
            Backtest(initial_cash=0)


if __name__ == "__main__":
    unittest.main()
