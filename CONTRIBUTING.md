# Contributing

## Setup
    python3 -m venv .venv
    .venv/bin/pip install -e .

## Run the tests
    .venv/bin/python -m unittest discover -s tests -v

## Layout
- `backtest/` — package: event loop, strategy interface, portfolio, reporting.
- `sample_data/` — CSV fixtures used by the demo and tests.
- `tests/` — unittest suite, one module per subsystem.

## Style
- Pure stdlib analytics; no third-party runtime deps.
- A strategy is a class with `generate_signals(series)`; wire it into the engine,
  don't special-case it in the loop.
- Every new strategy / report metric needs a docstring and a unittest.

## Adding a new report metric
- Implement the computation in the reporting module.
- Add it to the output table and the docstring.
- A unittest on a known dataset (in `sample_data/`) plus a regression check
  that existing metrics are unchanged.

## Pull requests
- Small, single-purpose commits. Back every claim with a test.
- Keep the stdlib constraint — that is the point of this project.
