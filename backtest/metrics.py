"""Performance metrics computed from an equity curve and a trade log.

All statistics are deliberately stdlib-only and well-defined at the edges
(zero volatility, no losing trades, a single bar) so they never crash a
backtest. Returns/drawdowns use the conventions a quant desk would expect:

- CAGR and volatility are annualized on 252 trading days.
- Sharpe/Sortino use a risk-free rate of zero by default and are ``0.0``
  when there is no variance to measure.
- Drawdown is a positive fraction of the prior peak, e.g. ``0.25`` = -25%.
"""

from __future__ import annotations

import math

from .engine import Trade


def total_return(equity_curve: list[float]) -> float:
    """Total simple return: ``final / initial - 1``.

    Returns 0.0 for empty/flat curves to avoid crashes in edge cases.
    """
    if len(equity_curve) < 2 or equity_curve[0] == 0:
        return 0.0
    return equity_curve[-1] / equity_curve[0] - 1.0


def cagr(equity_curve: list[float], periods_per_year: int = 252) -> float:
    """Compound annual growth rate over ``n`` return periods.

    Returns 0.0 for degenerate curves (too short, zero initial, or non-positive
    final value) to keep downstream code safe.
    """
    periods = len(equity_curve) - 1
    if periods < 1 or equity_curve[0] == 0 or equity_curve[-1] <= 0:
        return 0.0
    return (equity_curve[-1] / equity_curve[0]) ** (periods_per_year / periods) - 1.0


def annualized_volatility(returns: list[float], periods_per_year: int = 252) -> float:
    """Sample standard deviation of daily returns, annualized.

    Returns 0.0 for series with < 2 observations (no variance defined).
    """
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var * periods_per_year)


def sharpe_ratio(
    returns: list[float], periods_per_year: int = 252, risk_free: float = 0.0
) -> float:
    """(excess return) / (volatility), annualized. Zero when vol is zero."""
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    rf_daily = risk_free / periods_per_year
    # Constant returns have genuinely zero variance; float rounding would
    # otherwise leave ~1e-16 dust and blow the ratio up.
    if max(returns) == min(returns):
        return 0.0
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return (mean - rf_daily) / math.sqrt(var) * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: list[float], periods_per_year: int = 252, risk_free: float = 0.0
) -> float:
    """Like Sharpe, but penalizes only downside (negative) returns."""
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    rf_daily = risk_free / periods_per_year
    downside = [r for r in returns if r < rf_daily]
    if not downside:
        return 0.0
    dmean = sum(downside) / len(downside)
    if max(downside) == min(downside):
        return 0.0
    dvar = sum((r - dmean) ** 2 for r in downside) / len(downside)
    return (mean - rf_daily) / math.sqrt(dvar) * math.sqrt(periods_per_year)


def max_drawdown(equity_curve: list[float]) -> tuple[float, int, int]:
    """Maximum peak-to-trough decline.

    Returns ``(drawdown, peak_index, trough_index)`` where ``drawdown`` is a
    positive fraction of the peak, e.g. ``(0.25, 10, 40)`` = a -25% peak-to-
    trough between bar 10 and bar 40.

    For empty curves returns (0.0, 0, 0).
    """
    if not equity_curve:
        return 0.0, 0, 0
    peak = equity_curve[0]
    peak_idx = 0
    worst = 0.0
    worst_peak, worst_trough = 0, 0
    for i, value in enumerate(equity_curve):
        if value > peak:
            peak, peak_idx = value, i
        dd = (peak - value) / peak if peak else 0.0
        if dd > worst:
            worst = dd
            worst_peak, worst_trough = peak_idx, i
    return worst, worst_peak, worst_trough


def win_rate(trades: list[Trade]) -> float:
    """Fraction of round-trips that closed with positive PnL.

    Returns 0.0 for empty trade list (avoids division by zero).
    """
    if not trades:
        return 0.0
    return sum(1 for t in trades if t.pnl > 0) / len(trades)


def profit_factor(trades: list[Trade]) -> float:
    """Gross profit / gross loss. ``inf`` if there were no losing trades.

    Returns 0.0 if no trades at all (safe for downstream reporting).
    """
    if not trades:
        return 0.0
    gross_win = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return gross_win / gross_loss


def summarize(
    equity_curve: list[float], trades: list[Trade], initial_cash: float
) -> dict[str, float | int]:
    """One dict of every headline metric, ready for a report/CLI table."""
    returns = [  # recompute returns so this works on arbitrary curves
        (equity_curve[i] / equity_curve[i - 1] - 1.0) if equity_curve[i - 1] else 0.0
        for i in range(1, len(equity_curve))
    ]
    drawdown, peak_idx, trough_idx = max_drawdown(equity_curve)
    return {
        "initial_cash": initial_cash,
        "final_equity": equity_curve[-1],
        "total_return_pct": total_return(equity_curve) * 100.0,
        "cagr_pct": cagr(equity_curve) * 100.0,
        "annual_vol_pct": annualized_volatility(returns) * 100.0,
        "sharpe": sharpe_ratio(returns),
        "sortino": sortino_ratio(returns),
        "max_drawdown_pct": drawdown * 100.0,
        "dd_peak_idx": peak_idx,
        "dd_trough_idx": trough_idx,
        "num_trades": len(trades),
        "win_rate_pct": win_rate(trades) * 100.0,
        "profit_factor": profit_factor(trades),
    }
