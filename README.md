# backtest-engine
<p align="center">
  <a href="https://github.com/adivx/backtest-engine/actions"><img src="https://img.shields.io/github/actions/workflow/status/adivx/backtest-engine/ci.yml?branch=main&label=CI&logo=github" /></a>
  <img src="https://img.shields.io/github/license/adivx/backtest-engine" />
  <img src="https://img.shields.io/github/last-commit/adivx/backtest-engine" />
  <img src="https://img.shields.io/github/repo-size/adivx/backtest-engine" />
</p>



A lightweight, dependency-light **event-driven backtesting engine** for Python 3.9+.
Pick a strategy, point it at (synthetic or real) OHLCV bars, and get back a full
performance report — Sharpe, Sortino, max drawdown, CAGR, and a round-trip trade
log — all in pure stdlib math. `rich` is the only third-party dependency (for the CLI).

Third piece of a quant portfolio:

| Project | Shows |
|---|---|
| [ticker-terminal](https://github.com/adivx/ticker-terminal) | data engineering / live market data |
| [option-pricer](https://github.com/adivx/option-pricer) | derivatives math (Black–Scholes + Greeks) |
| **backtest-engine** | strategy design, execution simulation, risk metrics |

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/backtest --seed 11 --trades 4
```

```
╭───────────────────── backtest — ma_cross · synthetic 5y · seed=11 · 1,260 bars ──────────────────────╮
│ Initial capital        $100,000.00                                                                   │
│ Final equity           $163,500.63                                                                   │
│                                                                                                      │
│ Total return           +63.50%                                                                       │
│ CAGR                   +10.34%                                                                       │
│ Annualized vol         18.60%                                                                        │
│ Sharpe ratio           0.62                                                                          │
│ Sortino ratio          0.78                                                                          │
│ Max drawdown           -31.65%  (2021-05-28 → 2023-08-25)                                            │
│                                                                                                      │
│ Trades                 10  (win rate +50.00%)                                                        │
│ Profit factor          2.66                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────╯
                         Round-trips (10 total, showing 4)                          
┏━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┓
┃ # ┃ Entry      ┃ Exit       ┃ Entry px ┃ Exit px ┃ Shares ┃        PnL ┃  Return ┃
┡━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━┩
│ 1 │ 2020-03-26 │ 2020-11-30 │   107.97 │  145.91 │    926 │ +35,140.79 │ +35.14% │
│ 2 │ 2021-01-08 │ 2021-03-05 │   154.41 │  154.67 │    875 │    +232.11 │  +0.17% │
│ 3 │ 2021-03-29 │ 2021-07-05 │   169.96 │  195.75 │    796 │ +20,540.34 │ +15.17% │
│ 4 │ 2022-01-04 │ 2022-02-22 │   152.27 │  150.56 │  1,024 │  -1,756.41 │  -1.13% │
└───┴────────────┴────────────┴──────────┴─────────┴────────┴────────────┴─────────┘
```

## Usage

```bash
backtest                                     # MA-cross (20/60) on 5y synthetic data
backtest --strategy buy_hold --years 10      # benchmark vs. buy-and-hold
backtest --csv sample_data/sample_ohlcv.csv  # run on real bars
backtest --fast 10 --slow 30 --years 1       # tune the crossover pair
backtest --commission 10 --slippage 0.001    # model realistic execution costs
```

| Flag | Default | Meaning |
|---|---|---|
| `--strategy` | `ma_cross` | `buy_hold` or `ma_cross` |
| `--fast` / `--slow` | 20 / 60 | SMA periods for the crossover |
| `--csv FILE` | — | load OHLCV bars from CSV (`date,open,high,low,close,volume`) |
| `--years` / `--seed` / `--start-price` / `--drift` / `--volatility` | 5 / random / 100 / 0.08 / 0.25 | synthetic data controls |
| `--initial-cash` / `--commission` / `--slippage` | 100000 / 0 / 0 | execution model |
| `--trades N` / `--no-trades` | 10 / off | trade-log display |

## How it works

Strategies are **signals, not trades**: a strategy maps the price history to a
*target position* in `[0, 1]` (fraction of equity to hold). The engine executes
that target at the **next bar's open** — so a strategy never fills on the same bar
that produced its signal. This is the classic way to remove lookahead bias.

```python
from backtest.data import generate_synthetic
from backtest.engine import Backtest
from backtest.strategy import MovingAverageCross

bars   = generate_synthetic(seed=11)                    # 1,260 reproducible bars
result = Backtest(initial_cash=100_000, commission=10).run(
    bars, MovingAverageCross(fast=20, slow=60))

result.equity_curve   # mark-to-market equity at each close
result.trades         # round-trip trade log (entry, exit, PnL, return %)
result.final_equity   # just the number
```

A strategy is just a class with one method:

```python
from backtest.data import Bar
from backtest.strategy import Strategy

class EmaOfNothing(Strategy):          # your edge goes here
    name = "ema_of_nothing"
    def target_position(self, history: list[Bar], index: int) -> float:
        # 1.0 = fully invested, 0.0 = flat, anything in between is allowed
        return 0.0
```

### Execution model

- Full equity is mark-to-market at each bar's close.
- Target changes are filled at the next open, paying optional flat `commission`
  and price-based `slippage` in the direction of the trade.
- Trades are reported as **round-trips** (position leaves zero → returns to zero);
  weighted-average entry price across adds.

### Metrics

`backtest/metrics.py` computes `total_return`, `CAGR`, annualized volatility,
`Sharpe`, `Sortino`, `max_drawdown`, `win_rate`, and `profit_factor` — all with
well-defined behavior at the edges (zero variance, no losses, single-bar series).
`summarize()` returns every metric as one dict, ready to feed a report.

## Development

```bash
.venv/bin/python -m unittest discover -s tests    # 28 tests, stdlib unittest
```

## Roadmap

- [ ] Position sizing (fractional targets are already supported by the engine)
- [ ] Short selling and leverage
- [ ] Multiple-asset portfolios and portfolio-level metrics
- [ ] Performance attribution (MAE/MFE, trade clustering)
- [ ] CSV export of the equity curve for plotting

## License

MIT
