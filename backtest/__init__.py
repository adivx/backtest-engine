"""backtest-engine: a dependency-light event-driven backtesting engine.

Three layers:
- ``backtest.data``     — market data (seeded synthetic OHLCV + CSV loading)
- ``backtest.strategy`` — strategy framework (Buy-and-hold, MA cross, or your own)
- ``backtest.engine``   — event loop: signals -> fills -> equity curve + trade log
- ``backtest.metrics``  — performance statistics (Sharpe, drawdown, CAGR, ...)
"""

__version__ = "0.1.0"
