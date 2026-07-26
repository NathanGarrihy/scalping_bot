# scalpbot — working conventions

Read PLAN.md before any nontrivial change. The project is phase-gated: do not build code for a
phase whose predecessor gate has not passed (gates live in `gates/`, they fail closed).

## Commands

- `uv sync` — env setup (pinned Python 3.12; uv invoked as `py -m uv` if not on PATH)
- `uv run pytest` — must stay green at all times
- `uv run ruff check` / `uv run pyright` — lint and types, clean before commit
- `uv run python scripts/smoke_hl.py` — keyless connectivity check against HL testnet

## Architecture rules (violations are bugs, not style)

- `scalpbot.core` is **pure**: no I/O, no `time.time()`, no randomness, no venue imports.
  It consumes `core.events` types and emits `core.strategy` actions. Backtest, shadow, and
  live are drivers around it — never fork strategy logic into a driver.
- All venue I/O goes through the `ExchangeAdapter` protocol in `venues/base.py`.
- Journal-before-send: order intent is durable in SQLite (WAL) before the API call fires.
  Client order IDs (cloids) are idempotent.
- Every outbound request goes through the rate-limit budgeter (Hyperliquid enforces both
  per-IP weight and address-based budgets).
- Strategy parameters come only from `configs/strategy/*.yaml`. A config with
  `status: CANDIDATE` must never drive live trading; the live engine verifies the frozen hash.
- Every research experiment gets a row in `research/ledger.md` — including failures.

## Style

- Python 3.12, `from __future__ import annotations`, frozen dataclasses for events/actions,
  pydantic for configs. Line length 100 (ruff).
- Tests: unit + hypothesis property tests for the state machine; replay tests use golden
  event streams; chaos tests kill the process mid-trade and assert recovery.
