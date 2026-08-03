"""Strategy framework.

A strategy maps the price history seen so far to a *target position* in
[0, 1] — the fraction of portfolio equity it wants in the market. The
engine is responsible for executing that target at the next bar's open,
which models how signals are actually traded and removes lookahead bias:
a strategy never trades on the bar that produced its signal.
"""

from __future__ import annotations

import abc

from .data import Bar


def sma(values: list[float], period: int) -> list[float]:
    """Simple moving average, ``None`` (not a number) while too short."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[float | None] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        out.append(running / period if i >= period - 1 else None)
    return out


class Strategy(abc.ABC):
    """Base class for signal-generation strategies."""

    name: str = "strategy"

    @abc.abstractmethod
    def target_position(self, history: list[Bar], index: int) -> float:
        """Desired exposure in [0, 1] at bar ``index``.

        ``history`` includes bars up to and including ``index`` — the
        strategy is allowed to peek at today's close to form tomorrow's
        signal, but never to trade on it.
        """
        raise NotImplementedError

    def warmup(self) -> int:
        """Bars of history needed before the strategy emits signals."""
        return 0


class BuyAndHold(Strategy):
    """Always fully invested — the market benchmark a backtest is graded against."""

    name = "buy_hold"

    def target_position(self, history: list[Bar], index: int) -> float:
        return 1.0


class MovingAverageCross(Strategy):
    """Golden-cross / death-cross: long when fast SMA > slow SMA, else flat.

    A workhorse momentum rule. The 50/200-day pair is the classic stock
    variant; shorter pairs (e.g. 10/30) suit more volatile names.
    """

    name = "ma_cross"

    def __init__(self, fast: int = 20, slow: int = 60) -> None:
        if fast >= slow:
            raise ValueError("fast period must be shorter than slow period")
        self.fast = fast
        self.slow = slow

    def warmup(self) -> int:
        return self.slow

    def target_position(self, history: list[Bar], index: int) -> float:
        closes = [bar.close for bar in history[: index + 1]]
        fast = sma(closes, self.fast)[-1]
        slow = sma(closes, self.slow)[-1]
        if fast is None or slow is None:
            return 0.0
        return 1.0 if fast > slow else 0.0


STRATEGIES: dict[str, type[Strategy]] = {
    BuyAndHold.name: BuyAndHold,
    MovingAverageCross.name: MovingAverageCross,
}
