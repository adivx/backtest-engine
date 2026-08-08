# Security policy

backtest-engine is an analytics library and CLI. It reads OHLCV bars (synthetic
or from a CSV), simulates a strategy, and prints statistics. It holds no
credentials, makes no network calls, and executes no user-supplied code beyond
your own strategy class.

## Reporting a vulnerability

If you find a bug with security implications (for example, a crash or unbounded
resource use on malformed CSV input, or an issue in the execution model), open
a private issue or email the maintainer directly. We'll respond within a few
days.

## Scope / guarantees

- Malformed CSV input should raise a clean `DataError`, never execute code or
  read outside the supplied file.
- No data or metrics module may make a network call.
- Strategies run in-process by design; only load strategy code you trust.
