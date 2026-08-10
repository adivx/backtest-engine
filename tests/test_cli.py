"""Smoke tests for the CLI wiring (data → strategy → engine → report)."""

import io
import os
import unittest
from contextlib import redirect_stdout

from backtest.cli import build_parser, main

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                      "sample_data", "sample_ohlcv.csv")


class TestSyntheticRun(unittest.TestCase):
    def test_ma_cross_prints_summary(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["--seed", "11", "--trades", "2"])
        out = buf.getvalue()
        self.assertIn("ma_cross", out)
        self.assertIn("Sharpe", out)

    def test_buy_hold_benchmark(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["--strategy", "buy_hold", "--seed", "1",
                  "--years", "1", "--no-trades"])
        self.assertIn("buy_hold", buf.getvalue())

    def test_no_trades_hides_log(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["--seed", "11", "--no-trades"])
        self.assertNotIn("Round-trips", buf.getvalue())


class TestCsvRun(unittest.TestCase):
    def test_real_csv_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["--csv", SAMPLE, "--no-trades"])
        out = buf.getvalue()
        self.assertIn("Final equity", out)
        self.assertIn("ma_cross", out)

    def test_missing_csv_exits_1(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--csv", "/nonexistent/nope.csv"])
        self.assertEqual(ctx.exception.code, 1)


class TestStrategyErrors(unittest.TestCase):
    def test_fast_ge_slow_exits_1_cleanly(self):
        # MovingAverageCross rejects fast >= slow; the CLI must surface that
        # as a clean error, not a traceback.
        with self.assertRaises(SystemExit) as ctx:
            main(["--fast", "60", "--slow", "20", "--no-trades"])
        self.assertEqual(ctx.exception.code, 1)


class TestArgParser(unittest.TestCase):
    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            build_parser().parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_strategy_choices(self):
        args = build_parser().parse_args(["--strategy", "ma_cross"])
        self.assertEqual(args.strategy, "ma_cross")


if __name__ == "__main__":
    unittest.main()
