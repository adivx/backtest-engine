"""Market data: seeded synthetic OHLCV generation and CSV loading.

The synthetic generator walks geometric Brownian motion (GBM) and builds
realistic daily open/high/low/close bars around each move, so a strategy
has genuine intra-bar range to interact with. Everything is pure stdlib —
``random`` (seeded for reproducibility) plus ``math`` for the normal
inverse via Box-Muller.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Bar:
    """A single daily OHLCV bar."""

    date: str  # ISO format, e.g. "2026-08-03"
    open: float
    high: float
    low: float
    close: float
    volume: int


class DataError(Exception):
    """Raised when market data cannot be produced or parsed."""


def _standard_normal(rng: random.Random) -> float:
    """One standard-normal draw via Box-Muller."""
    u1 = rng.uniform(1e-9, 1.0)
    u2 = rng.uniform(0.0, 1.0)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def generate_synthetic(
    start_price: float = 100.0,
    years: float = 5.0,
    drift: float = 0.08,
    volatility: float = 0.25,
    seed: int | None = None,
    trading_days_per_year: int = 252,
) -> list[Bar]:
    """Generate ``trading_days_per_year * years`` daily GBM bars.

    ``drift`` and ``volatility`` are annualized. Passing a ``seed`` makes
    the exact same series reproducible — the engine's default.
    """
    if start_price <= 0:
        raise DataError("start_price must be positive")
    if years <= 0:
        raise DataError("years must be positive")
    if volatility < 0:
        raise DataError("volatility cannot be negative")

    rng = random.Random(seed)
    dt = 1.0 / trading_days_per_year
    sqrt_dt = math.sqrt(dt)
    mu = drift - 0.5 * volatility * volatility

    bars: list[Bar] = []
    price = start_price
    day = date(2020, 1, 2)  # arbitrary anchor; advances on trading days
    n = int(round(trading_days_per_year * years))

    for i in range(n):
        z = _standard_normal(rng)
        prev_close = price
        o = prev_close
        log_ret = mu * dt + volatility * sqrt_dt * z
        c = prev_close * math.exp(log_ret)

        # Intra-bar range scales with the day's shock magnitude.
        wiggle = 0.5 * volatility * sqrt_dt * abs(z)
        h = max(o, c) * (1.0 + wiggle)
        l = min(o, c) * (1.0 - wiggle)

        # Volume roughly mirrors the bar's range (jumpy, like real tape).
        v = int(rng.uniform(0.8, 1.2) * 1_000_000 * (h - l) / o * 50)

        bars.append(Bar(day.isoformat(), round(o, 4), round(h, 4), round(l, 4), round(c, 4), v))
        price = c
        # Skip weekends so the date axis looks like a market calendar.
        day += timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)

    return bars


def load_csv(path: str) -> list[Bar]:
    """Load OHLCV bars from a CSV with a header row.

    Expected columns (any order, names case-insensitive):
    ``date, open, high, low, close, volume``. Raises :class:`DataError`
    on missing columns, non-numeric prices, inverted high/low, or dates
    that are malformed, duplicated, or out of chronological order.
    """
    try:
        fh = open(path, newline="")
    except OSError as exc:
        raise DataError(f"cannot open {path}: {exc}") from exc

    with fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise DataError(f"{path}: no header row found")
        lowered = {name.strip().lower(): name for name in reader.fieldnames}

        required = ("date", "open", "high", "low", "close")
        missing = [col for col in required if col not in lowered]
        if missing:
            raise DataError(f"{path}: missing column(s): {', '.join(missing)}")

        bars: list[Bar] = []
        prev_date: date | None = None
        for lineno, row in enumerate(reader, start=2):
            try:
                o, h, l, c = (
                    float(row[lowered["open"]]),
                    float(row[lowered["high"]]),
                    float(row[lowered["low"]]),
                    float(row[lowered["close"]]),
                )
                raw_vol = row.get(lowered.get("volume", ""), "0").strip()
                vol = int(float(raw_vol)) if raw_vol else 0
            except (TypeError, ValueError) as exc:
                raise DataError(f"{path}:{lineno}: non-numeric price/volume") from exc

            if l > h:
                raise DataError(f"{path}:{lineno}: low ({l}) above high ({h})")
            date_str = row[lowered["date"]].strip()
            try:
                day = date.fromisoformat(date_str)
            except ValueError:
                raise DataError(
                    f"{path}:{lineno}: invalid date {date_str!r} (expected YYYY-MM-DD)"
                ) from None
            if prev_date is not None and day <= prev_date:
                raise DataError(
                    f"{path}:{lineno}: date {date_str!r} out of order or duplicated"
                )
            prev_date = day
            bars.append(Bar(date_str, o, h, l, c, vol))

    if not bars:
        raise DataError(f"{path}: no data rows")
    return bars
