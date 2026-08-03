"""Backtest engine: turns a strategy + price history into an equity curve.

Simulation model
----------------
- The portfolio starts fully in cash (``initial_cash``).
- A strategy's target position (fraction of equity in [0, 1]) is computed
  from bar ``i - 1``'s close and filled at bar ``i``'s **open** — no
  lookahead, and never a fill on the bar that generated the signal.
- Optional per-trade ``commission`` (flat $) and ``slippage`` (fraction of
  price, paid in the direction of the trade) model real execution costs.
- Trades are reported as round-trips: opened when the position leaves
  zero, closed when it returns to zero. Per-trade PnL excludes commission
  (it hits the equity curve instead); entry price is a weighted average
  across partial fills.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data import Bar
from .strategy import Strategy


@dataclass
class Trade:
    """A single round-trip: long from entry to exit."""

    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    pnl: float
    return_pct: float


@dataclass
class BacktestResult:
    """Everything produced by one :meth:`Backtest.run` call."""

    dates: list[str]
    equity_curve: list[float]
    trades: list[Trade] = field(default_factory=list)
    initial_cash: float = 0.0

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1]

    def returns(self) -> list[float]:
        """Daily simple returns over the equity curve (n - 1 values)."""
        curve = self.equity_curve
        if len(curve) < 2:
            return []
        return [
            (curve[i] / curve[i - 1] - 1.0) if curve[i - 1] else 0.0
            for i in range(1, len(curve))
        ]


class Backtest:
    """Event-driven backtest runner."""

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if commission < 0 or slippage < 0:
            raise ValueError("commission and slippage cannot be negative")
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

    def run(self, bars: list[Bar], strategy: Strategy) -> BacktestResult:
        """Simulate ``strategy`` over ``bars`` and return the results."""
        if not bars:
            raise ValueError("run() needs at least one bar")

        cash = self.initial_cash
        shares = 0.0
        entry_date: str | None = None
        entry_price = 0.0
        entry_shares = 0.0
        realized = 0.0

        dates: list[str] = []
        equity_curve: list[float] = []
        trades: list[Trade] = []

        for i, bar in enumerate(bars):
            # ---- 1. Execute yesterday's signal at today's open ------------
            if i >= 1:
                target = min(1.0, max(0.0, strategy.target_position(bars, i - 1)))
                equity_at_open = cash + shares * bar.open
                desired = target * equity_at_open / bar.open
                delta = desired - shares

                # Skip dust-sized rebalances (costs would swamp them).
                if abs(delta) * bar.open > 0.01 * self.initial_cash and abs(delta) > 1e-12:
                    is_buy = delta > 0.0
                    # Slip in the direction of the trade; buys pay more, sells net less.
                    fill = bar.open * ((1.0 + self.slippage) if is_buy else (1.0 - self.slippage))
                    cost = abs(delta) * fill + self.commission
                    cash = cash - cost if is_buy else cash + cost

                    if is_buy:
                        if abs(shares) < 1e-9:
                            shares = 0.0
                            entry_date, entry_price, entry_shares = bar.date, fill, delta
                        else:
                            # Weighted-average entry across adds.
                            entry_price = (entry_price * shares + delta * fill) / (shares + delta)
                            entry_shares += delta
                        shares += delta
                    else:
                        realized += abs(delta) * (fill - entry_price)
                        shares += delta  # delta < 0 here
                        if abs(shares) < 1e-9:
                            shares = 0.0
                            trades.append(
                                Trade(
                                    entry_date=entry_date or bar.date,
                                    exit_date=bar.date,
                                    entry_price=round(entry_price, 4),
                                    exit_price=round(fill, 4),
                                    shares=round(entry_shares, 4),
                                    pnl=round(realized, 2),
                                    return_pct=round(
                                        realized / (entry_price * entry_shares) * 100.0, 2
                                    )
                                    if entry_price * entry_shares
                                    else 0.0,
                                )
                            )
                            entry_date, entry_price, entry_shares, realized = None, 0.0, 0.0, 0.0

            # ---- 2. Mark to market at the close ---------------------------
            dates.append(bar.date)
            equity_curve.append(round(cash + shares * bar.close, 2))

        # If the strategy is still long at the end, close at the last close
        # so the trade log tells a complete story.
        if shares > 1e-9 and entry_date is not None:
            last = bars[-1]
            fill = last.close
            trades.append(
                Trade(
                    entry_date=entry_date,
                    exit_date=last.date,
                    entry_price=round(entry_price, 4),
                    exit_price=round(fill, 4),
                    shares=round(entry_shares, 4),
                    pnl=round(realized + shares * (fill - entry_price), 2),
                    return_pct=round(
                        (realized + shares * (fill - entry_price)) / (entry_price * entry_shares) * 100.0, 2
                    )
                    if entry_price * entry_shares
                    else 0.0,
                )
            )

        return BacktestResult(
            dates=dates,
            equity_curve=equity_curve,
            trades=trades,
            initial_cash=self.initial_cash,
        )
