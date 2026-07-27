# scalpbot

Gate-driven mean-reversion scalping system for Hyperliquid perpetuals. Maker-only execution,
hostile backtesting, empirical kill thresholds. **Read [PLAN.md](PLAN.md) first** — it defines the
phases, and no phase's code is built until the previous phase's gate script passes.

## Status

**Phase 0 (edge validation) — Task 0.1 (data acquisition) done, universe selection and the
hostile backtest not started.** `src/scalpbot/data/` ingests the Binance signal-research
corpus (1s bars, resampled from aggTrades — Binance USD-M futures has no native 1s klines)
and the Hyperliquid venue-calibration corpus (1h candles via the info API) — see
`docs/data_schema.md`. Run `uv run python scripts/data_report.py` for the integrity/regime/
cross-venue-basis report. Per the plan, infrastructure work is still blocked until
`gates/gate0_edge.py` and `gates/gate0_drawdown.py` print PASS — Tasks 0.2 and 0.3 are next.

## Quickstart

```sh
uv sync                       # creates .venv on pinned Python 3.12
uv run pytest                 # skeleton test suite (must stay green)
uv run ruff check
uv run python scripts/smoke_hl.py   # public testnet info endpoint, no keys needed
```

## Layout

| Path | What it is |
| :--- | :--- |
| `src/scalpbot/core/` | Deterministic strategy core — pure functions, no I/O, no clock. Shared verbatim by backtest, shadow, and live. |
| `src/scalpbot/venues/` | `ExchangeAdapter` protocol + Hyperliquid implementation. The core never imports a venue. |
| `src/scalpbot/data/` | Binance-archive (signal research) and Hyperliquid-archive (venue calibration) ingestion → parquet. |
| `src/scalpbot/backtest/` | Hostile fill model, event-driven replay, walk-forward, Monte Carlo. |
| `src/scalpbot/live/` | Asyncio engine, WAL journal, reconciliation, bounded chase, watchdog, killswitch. |
| `src/scalpbot/shadow/` | Paper ledger applying hostile fill rules to live data (Phase 4). |
| `gates/` | Executable phase gates. Fail closed: unimplemented = FAIL. |
| `configs/` | Research params, candidate strategy configs (hash-frozen once validated), live risk caps. |
| `research/ledger.md` | Append-only record of every experiment — the overfitting audit trail. |

## Non-negotiable invariants

1. The strategy core is pure and deterministic; backtest/shadow/live differ only in the driver.
2. Order intent hits the SQLite WAL journal before any request leaves the process.
3. The live engine refuses to start unless the strategy config hash matches the gate-approved frozen hash.
4. Every outbound request passes the rate-limit budgeter.
5. Gates fail closed.
