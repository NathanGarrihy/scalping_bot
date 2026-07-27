# Task 0.1 status (PLAN.md §3, Historical Data Acquisition)

Living progress snapshot for Task 0.1 — not a spec (see `PLAN.md`) and not the schema
reference (see `data_schema.md`). Delete once Task 0.2 work starts in earnest.

## Ingestion progress (pilot basket: BTC, ETH, SOL, DOGE)

Complete as of 2026-07-27. Both `scripts/ingest_binance.py` and
`scripts/ingest_hyperliquid.py` finished with zero failed days.

| Symbol | Binance 1s klines (2024-07-01 → 2026-06-30, 730 days) | HL 1h candles (2026-01-01 → present) |
| :--- | :--- | :--- |
| BTC | 730/730 — complete | 206/206 — complete |
| ETH | 730/730 — complete | 206/206 — complete |
| SOL | 730/730 — complete | 206/206 — complete |
| DOGE | 730/730 — complete | 206/206 — complete |

## Verification — PASSED

`scripts/data_report.py` ran against the real corpus on 2026-07-27
(`data/reports/integrity_report_1785136826.txt`). All of PLAN.md §3 Task 0.1's validation
conditions hold:

- **Gaps/monotonicity**: 0 gaps across all 8 series (4 Binance + 4 Hyperliquid).
- **Negative volume**: none found.
- **Regime coverage (pre-holdout)**: all four symbols clear the ≥40% drawdown bar with
  margin — BTC 52.6%, ETH 66.3%, SOL 77.2%, DOGE 83.5% — each with both chop and trend
  days represented.
- **Cross-venue basis**: small throughout — mean 0.64–1.16 bps, p95 4.4–10.3 bps (DOGE
  widest, still tight) across 2160 overlapping bars per pair.

**Task 0.1 is done.** Its own PLAN.md validation bar is met on real data, not just
plausible in code. Task 0.2 (universe selection) and Task 0.3 (backtest engine, currently
100% stub) can start.

## Known, non-blocking gaps (backlog)

- `tests/unit/test_data_schema.py` asserts column *names* only — no dtype assertions. A
  dtype regression in `schema.py` wouldn't be caught by this file alone.
- No test runs the integrity/report chain against the real on-disk corpus, or covers
  multiple/adjacent gaps and a gap spanning a day-partition boundary (only single
  synthetic gaps are tested today).
- Signal corpus date range (`2024-07-01` → `2026-06-30`) satisfies the "2+ years" floor
  exactly at the boundary (24 months, ~21 after the 3-month holdout carve-out) — fine for
  now, worth keeping in mind when sizing walk-forward windows later.

## Scaffolding note (not a Task 0.1 item, flagged for awareness)

`pyproject.toml`/`uv.lock` already pin `hyperliquid-python-sdk` and `websockets` — Phase 1
dependencies, resolved ahead of the Phase 0 gate passing. Everything under
`src/scalpbot/{backtest,live,venues,shadow,ops}/` is currently inert
(`raise NotImplementedError`, each citing the PLAN.md task it's blocked on), which is fine
as pure interface/spec work — but the dependency pins are the one place "ahead of gate" is
already a fact on disk. Nothing to do about it now; just don't let it become the reason
Phase 1 code gets written before this doc says Task 0.1 is closed out.
