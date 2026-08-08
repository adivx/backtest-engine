"""Command-line interface: run a backtest from the terminal.

Examples
--------
    backtest                                    # MA-cross (default) on synthetic data
    backtest --strategy buy_hold --years 10     # benchmark against the market
    backtest --csv AAPL.csv --fast 10 --slow 30 # run on real bars from a CSV
    backtest --commission 10 --slippage 0.001   # model realistic execution costs
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .data import DataError, generate_synthetic, load_csv
from .engine import Backtest, BacktestResult
from .metrics import summarize
from .strategy import STRATEGIES, BuyAndHold, MovingAverageCross

console = Console()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="backtest",
        description="Run a trading-strategy backtest and print the results.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--strategy",
        choices=sorted(STRATEGIES),
        default="ma_cross",
        help="signal-generation strategy to test",
    )
    p.add_argument("--fast", type=int, default=20, help="fast SMA period (ma_cross)")
    p.add_argument("--slow", type=int, default=60, help="slow SMA period (ma_cross)")

    source = p.add_argument_group("data source")
    source.add_argument("--csv", metavar="FILE", help="load real OHLCV bars from a CSV (date,open,high,low,close,volume)")
    source.add_argument("--years", type=float, default=5.0, help="years of synthetic data")
    source.add_argument("--seed", type=int, default=None, help="random seed for reproducible synthetic data")
    source.add_argument("--start-price", type=float, default=100.0, help="starting price")
    source.add_argument("--drift", type=float, default=0.08, help="annualized drift (synthetic)")
    source.add_argument("--volatility", type=float, default=0.25, help="annualized volatility (synthetic)")

    costs = p.add_argument_group("execution")
    costs.add_argument("--initial-cash", type=float, default=100_000.0)
    costs.add_argument("--commission", type=float, default=0.0, help="flat $ per trade")
    costs.add_argument("--slippage", type=float, default=0.0, help="fraction of price per trade")

    p.add_argument("--trades", type=int, default=10, help="max trade rows to print")
    p.add_argument("--no-trades", action="store_true", help="hide the trade log")
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")
    return p


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float, signed: bool = True) -> str:
    """Signed percentages get green/red coloring; unsigned ones are plain."""
    if not signed:
        return f"{value:.2f}%"
    color = "green" if value >= 0 else "red"
    return f"[{color}]{value:+.2f}%[/{color}]"


def _print_summary(result: BacktestResult, strategy_name: str, data_label: str) -> None:
    s = summarize(result.equity_curve, result.trades, result.initial_cash)
    dd, peak_idx, trough_idx = (
        s["max_drawdown_pct"],
        s["dd_peak_idx"],
        s["dd_trough_idx"],
    )
    peak_date = result.dates[peak_idx] if peak_idx < len(result.dates) else "-"
    trough_date = result.dates[trough_idx] if trough_idx < len(result.dates) else "-"

    lines = [
        f"[bold]{'Initial capital':<22}[/bold] {_fmt_money(s['initial_cash'])}",
        f"[bold]{'Final equity':<22}[/bold] {_fmt_money(s['final_equity'])}",
        "",
        f"[bold]{'Total return':<22}[/bold] {_fmt_pct(s['total_return_pct'])}",
        f"[bold]{'CAGR':<22}[/bold] {_fmt_pct(s['cagr_pct'])}",
        f"[bold]{'Annualized vol':<22}[/bold] {_fmt_pct(s['annual_vol_pct'], signed=False)}",
        f"[bold]{'Sharpe ratio':<22}[/bold] {s['sharpe']:.2f}",
        f"[bold]{'Sortino ratio':<22}[/bold] {s['sortino']:.2f}",
        f"[bold]{'Max drawdown':<22}[/bold] {_fmt_pct(-s['max_drawdown_pct'])}  [dim]({peak_date} → {trough_date})[/dim]",
        "",
        f"[bold]{'Trades':<22}[/bold] {s['num_trades']}  (win rate {_fmt_pct(s['win_rate_pct'])})",
        f"[bold]{'Profit factor':<22}[/bold] {s['profit_factor']:.2f}",
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold]backtest[/bold] — {strategy_name} · {data_label}",
            border_style="cyan",
        )
    )


def _print_trades(result: BacktestResult, limit: int) -> None:
    trades = result.trades
    if not trades:
        console.print("[dim]No completed round-trips to show.[/dim]")
        return
    table = Table(title=f"Round-trips ({len(trades)} total, showing {min(limit, len(trades))})")
    table.add_column("#", justify="right")
    table.add_column("Entry", style="dim")
    table.add_column("Exit", style="dim")
    table.add_column("Entry px", justify="right")
    table.add_column("Exit px", justify="right")
    table.add_column("Shares", justify="right")
    table.add_column("PnL", justify="right")
    table.add_column("Return", justify="right")
    for i, t in enumerate(trades[:limit], start=1):
        pnl_style = "green" if t.pnl >= 0 else "red"
        ret = t.return_pct
        table.add_row(
            str(i),
            t.entry_date,
            t.exit_date,
            f"{t.entry_price:,.2f}",
            f"{t.exit_price:,.2f}",
            f"{t.shares:,.0f}",
            f"[{pnl_style}]{t.pnl:+,.2f}[/{pnl_style}]",
            f"[{pnl_style}]{ret:+.2f}%[/{pnl_style}]",
        )
    console.print(table)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    try:
        if args.csv:
            bars = load_csv(args.csv)
            data_label = f"{args.csv} ({len(bars):,} bars)"
        else:
            bars = generate_synthetic(
                start_price=args.start_price,
                years=args.years,
                drift=args.drift,
                volatility=args.volatility,
                seed=args.seed,
            )
            seed_label = f"seed={args.seed}" if args.seed is not None else "random"
            data_label = f"synthetic {args.years:g}y · {seed_label} · {len(bars):,} bars"
    except DataError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise SystemExit(1) from exc

    if args.strategy == "ma_cross":
        strategy = MovingAverageCross(fast=args.fast, slow=args.slow)
    else:
        strategy = BuyAndHold()

    try:
        result = Backtest(
            initial_cash=args.initial_cash,
            commission=args.commission,
            slippage=args.slippage,
        ).run(bars, strategy)
    except ValueError as exc:
        console.print(f"[red]error[/red] {exc}")
        raise SystemExit(1) from exc

    _print_summary(result, strategy.name, data_label)
    if not args.no_trades:
        _print_trades(result, args.trades)


if __name__ == "__main__":
    main()
