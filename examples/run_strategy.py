"""Run the MA-cross strategy through the library API and print a report.

This mirrors what the `backtest` CLI does, but shows the Python API instead:
load bars, pick a strategy, run the engine, and summarize the results — all
with pure stdlib math under the hood.

Run from the repo root (after ``pip install -e .``):

    python examples/run_strategy.py          # uses sample_data/sample_ohlcv.csv
    python examples/run_strategy.py --synthetic
"""

import argparse
import os
import sys

from backtest.engine import Backtest
from backtest.metrics import summarize
from backtest.strategy import BuyAndHold, MovingAverageCross

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "sample_data",
                          "sample_ohlcv.csv")


def load_bars(use_synthetic: bool):
    if use_synthetic or not os.path.exists(SAMPLE_CSV):
        from backtest.data import generate_synthetic
        bars = generate_synthetic(seed=11, years=5)
        print(f"data: synthetic 5y, seed=11 ({len(bars):,} bars)")
        return bars
    from backtest.data import load_csv
    bars = load_csv(SAMPLE_CSV)
    print(f"data: {os.path.relpath(SAMPLE_CSV)} ({len(bars):,} bars)")
    return bars


def report(bars, strategy, initial_cash=100_000.0, commission=10.0):
    result = Backtest(initial_cash=initial_cash, commission=commission).run(
        bars, strategy)
    m = summarize(result.equity_curve, result.trades, initial_cash)
    print(f"\nstrategy: {strategy.name}")
    print(f"  final equity   ${m['final_equity']:,.2f}")
    print(f"  total return   {m['total_return_pct']:+.2f}%")
    print(f"  CAGR           {m['cagr_pct']:+.2f}%")
    print(f"  Sharpe         {m['sharpe']:.2f}")
    print(f"  max drawdown   {m['max_drawdown_pct']:.2f}%")
    print(f"  trades         {m['num_trades']}  (win rate {m['win_rate_pct']:.0f}%)")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true",
                        help="use seeded synthetic bars instead of the sample CSV")
    parser.add_argument("--commission", type=float, default=10.0,
                        help="flat $ commission per trade")
    args = parser.parse_args()

    try:
        bars = load_bars(args.synthetic)
    except Exception as exc:  # load_csv raises DataError on malformed input
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report(bars, MovingAverageCross(fast=20, slow=60), commission=args.commission)
    report(bars, BuyAndHold(), commission=args.commission)
    return 0


if __name__ == "__main__":
    sys.exit(main())
