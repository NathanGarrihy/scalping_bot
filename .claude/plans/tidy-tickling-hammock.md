# Phase E: funding-rate-extreme signal (Task 0.3, continuing the "zoom out" round)

## Context

Task 0.3 Stage 1 so far (`docs/task0_3_status.md`): three conclusive kills (price-based
mean-reversion and momentum, three lookback regimes, 1,694 trials) and one inconclusive
probe (cross-venue basis dislocation — a genuinely different, economically-motivated
hypothesis, but data-starved: Hyperliquid's `candleSnapshot` info-API endpoint only
serves a rolling ~200-215 day cache at 1h resolution, giving just ~90 usable pre-holdout
days / ~2,160 hourly bars, nowhere near enough trades to conclude anything).

Asked to plan the best next move. Researched two ways to get more/better Hyperliquid
history before deciding:

- **`fundingHistory` info-API endpoint — verified empirically, real history back to at
  least 2023.** Curled it directly: 2023-06-01 returns real hourly funding data,
  2023-01-01 returns empty (pre-listing, not a cache limit). A 1-year-wide request caps
  at exactly 500 records (~20.8 days) per call — a per-request page-size limit, not a
  rolling-cache depth limit like `candleSnapshot`. This means funding history can cover
  the **full** 2024-07-01→2026-06-30 signal-corpus window, unlike candles.
- **Official `hyperliquid-archive` S3 bucket** (`market_data`/`asset_ctxs`, lz4-compressed,
  updated ~monthly) genuinely has deeper L2/trade history and would fix the *price*-side
  sample-size problem for good (and serve Task 0.2's deferred spread criterion + Task
  0.3 Stage 2's eventual hostile-fill L2 needs) — but its exact binary format hasn't been
  inspected yet, so it can't be honestly scoped as an implementation plan yet. Named as
  the logical next investment, not built now.

Given that, the disciplined next move is the cheap, verified-available one first: ingest
real funding history and screen a funding-rate-extreme mean-reversion signal — a
genuinely different economic mechanism (crowded-positioning squeeze, not a price
technical) — before committing to the bigger S3-archive investment.

**Honest caveat carried forward**: the *tradeable* P&L side of this signal still needs
Hyperliquid's own price, which is still capped at the same ~90-day pre-holdout window as
the basis-dislocation probe (we already ingested candles at essentially the earliest
fetchable date — re-ingesting won't extend it further; only the S3 archive would). So
this experiment inherits Round 4's small-sample caveat for backtesting, even though the
*calibration* of "what counts as extreme funding" benefits from the full 2-year history.
Stated up front so a promising-looking small sample doesn't get over-read here either.

## Implementation

**1. `src/scalpbot/data/schema.py`** — add `HYPERLIQUID_FUNDING_SCHEMA`: `coin, open_time_ms,
funding_rate, premium, source` (mirrors `HYPERLIQUID_CANDLE_SCHEMA`'s shape/conventions).
Update `docs/data_schema.md` to match (existing pattern: keep both in sync).

**2. `src/scalpbot/data/hyperliquid_funding.py`** — near-direct mirror of
`hyperliquid_candles.py` (same raw-httpx/no-SDK style, same day-partition/resumability
pattern via `paths.py` unchanged, kind=`"funding"`). Key differences to get right:
- Request shape is **flat**, not nested under `"req"` like `candleSnapshot`:
  `{"type": "fundingHistory", "coin": coin, "startTime": ms, "endTime": ms}` — verified
  via direct curl against the real endpoint this session.
- A single UTC day (24 funding events) is far under the empirically-confirmed 500-record
  page cap, so — like `fetch_day_candles` — no pagination loop is needed per day.
- Reuse the same 429-is-retryable behavior `fetch_day_candles` already established
  empirically for this API.
- `partition_is_complete(..., min_rows=24, max_rows=24)`, same as candles.

**3. `scripts/ingest_hyperliquid_funding.py`** — CLI matching `scripts/ingest_hyperliquid.py`'s
pattern, defaulting to `signal_corpus.start`/`.end` (2024-07-01→2026-06-30) rather than
`venue_corpus`'s shorter window, since funding history actually covers it.

**4. `tests/unit/test_hyperliquid_funding.py`** — mirrors `test_hyperliquid_candles.py`:
`httpx.MockTransport`, real small fixture, flat-request-shape assertion, resumability,
retry-on-429.

**5. `src/scalpbot/backtest/funding_signal.py`** — `build_funding_corpus(hl_candles,
funding_history) -> pl.DataFrame`: joins HL's own OHLC (tradeable price, still the
~90-day-pre-holdout window) with a rolling `funding_pressure` column (trailing 24h summed
`funding_rate`, calibrated against the full funding history) computed from the much
longer funding series. Feeds into `vector_screen.screen_grid(...,
source_column="funding_pressure")` — reuses the same generalized machinery Round 4 built
(`_compute_indicators`/`_evaluate_config`'s `source_column` param), no further changes to
`vector_screen.py` needed.

**6. `scripts/run_funding_screen.py`** — small bounded grid mirroring
`run_basis_screen.py`'s structure: bracket-only, `mean_revert` direction only (extreme
funding reverting is the economic bet — no momentum variant here either). Direction
mapping: extreme-positive funding pressure (longs paying, crowded long) → short,
expecting a squeeze down; extreme-negative → long.

**Deliberately not modeled here**: funding accrual's own cost/credit during the hold
(`costs.py::funding_accrual` exists but stays unused, same as every other Stage 1 screen)
— kept methodologically consistent across all screens rather than selectively fixed for
the one experiment where the data happens to be available; still a documented Stage 2 gap.

## Verification

- `uv run pytest` / `ruff check` / `pyright` clean, same bar as every prior round.
- Real ingestion run (`scripts/ingest_hyperliquid_funding.py`), spot-checked against a
  fresh curl of the same endpoint/range to confirm the parsed data matches.
- Real screen run (`scripts/run_funding_screen.py`) against all 4 pilot symbols; read
  `n_trades`/`t_stat` before drawing any conclusion — if it's Round-4-small (single
  digits), report it as inconclusive like Round 4, not as a fourth kill or a discovery.
- Update `docs/task0_3_status.md` with a "Round 5" section following the established
  format (what was tested, real numbers, honest verdict).
- Name the `hyperliquid-archive` S3 investigation explicitly as the next decision point
  after this round's result is known, not folded into this plan.
