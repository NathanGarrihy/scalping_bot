# Phase 0 State Assessment + Status Doc Updates

## Context

Senior-architect review of scalpbot's current state (full findings below). Verdict:
Task 0.1 (historical data acquisition) is well-built but not finished, and its own
validation condition has never been checked against real data. The Binance ingest is
still running in the background (SOLUSDT/DOGEUSDT not yet started; ETHUSDT partial).
Rather than exit plan mode with just an analysis, the user wants the *documentation*
updated now, while the download finishes, so the project's current state — what's done,
what's pending, what's not yet verified — is captured in the repo instead of living only
in this conversation.

## Assessment (unchanged from investigation)

**Not ready to proceed past Task 0.1.** Gates correctly fail closed (all `gates/*.py`
raise `NotImplementedError` → FAIL) — that part is working as designed. The gap is one
level up:

1. **Backfill incomplete against the 4-symbol pilot basket.** Binance 1s klines: BTC
   730/730 (done), ETH 471/730 (in progress), SOL 0/730, DOGE 0/730 (not started).
   Hyperliquid 1h candles: all four symbols complete (206/206 each).
2. **Task 0.1's own validation condition has never been checked.** `integrity.py` /
   `report.py` (gap detection, non-negative volume, ≥40%-drawdown regime coverage,
   cross-venue basis) are solid and well-tested but deliberately not wired to any gate —
   by design, they feed a human-read report. `data/reports/` doesn't exist yet;
   `scripts/data_report.py` has never been run against the real corpus. So whether the
   data actually contains a ≥40% drawdown, is gap-free, and has small HL/Binance basis is
   currently **unknown**, not passing.
3. **Phase-gate discipline is a passive banner, not an enforced control.**
   `phase_gate_banner.py` only prints status at session start; no `PreToolUse` hook stops
   Phase 1-3 code from being written early. Checked file-by-file, everything under
   `backtest/`, `live/`, `venues/`, `shadow/`, `ops/` is currently inert
   (`raise NotImplementedError`, each citing its blocking PLAN.md task) — a legitimate
   spec/interface stage, not a violation, as of now. The one thing already past pure spec:
   `pyproject.toml`/`uv.lock` pin `hyperliquid-python-sdk` and `websockets` (Phase 1
   deps), worth naming so it doesn't quietly become the seed of building Phase 1 early.
4. **Data-layer tests are genuinely solid** (real fixtures, hand-verified resample math,
   full `partition_is_complete` branch coverage), with two small gaps: `test_data_schema.py`
   checks column names only (no dtype assertions), and no test runs the integrity/report
   chain against the real on-disk corpus or covers multi-gap/boundary-spanning cases.

## Proposed documentation updates (this session, while ingest runs)

1. **New file: `docs/task0_1_status.md`** — a living status snapshot for Task 0.1, since
   no such doc currently exists and PLAN.md itself is a spec (not meant to track live
   progress). Contents:
   - Per-symbol ingestion table (Binance 1s klines, HL 1h candles) with current counts.
   - Explicit "not yet verified" callout: regime coverage / gap-freeness / cross-venue
     basis have not been checked against real data — `scripts/data_report.py` has not
     been run.
   - Outstanding action items, in order: finish Binance backfill (SOL, DOGE) → run
     `data_report.py` → read verdict before starting Task 0.2/0.3.
   - Known test gaps (dtype assertions, multi-gap coverage) as backlog notes, not blockers.
   - Note on the `hyperliquid-python-sdk`/`websockets` dependency pins being ahead of the
     current gate, for awareness.

2. **Small fix: `docs/data_schema.md`** — the Hyperliquid candle table's `interval`
   column example currently reads `e.g. "1m"`, but the pipeline and code fix this at
   `"1h"` only (`OUTPUT_INTERVAL = "1h"` in `hyperliquid_candles.py`). Correct the example
   to `"1h"` so the doc matches actual behavior.

Not touching `research/ledger.md` — that table is for logged backtest experiments/configs
(Task 0.3+), and no experiment has run yet; adding a row for data ingestion would misuse
its schema. Not editing `PLAN.md` itself — it's the versioned spec ("Supersedes
`initial_plan.md`"), not a status tracker.

## Verification

- `docs/task0_1_status.md` is new prose/markdown — no code to run; review by reading it
  back for accuracy once ingest finishes and counts are re-checked.
- `docs/data_schema.md` diff should be a one-line change; confirm by grepping for
  `"1m"`/`"1h"` in that file post-edit to ensure no other stale references remain.
- After the Binance ingest completes (background-monitored), re-run the per-symbol file
  counts and update the status doc's table before running `scripts/data_report.py`.
