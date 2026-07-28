# Task 0.3 Stage 1 (coarse screen) status (PLAN.md §3)

Living progress snapshot for Task 0.3's Stage 1 screen — split out of
`task0_1_status.md` once it outgrew that file. Not a spec (see `PLAN.md`).

Per PLAN.md's two-stage Task 0.3 design, Stage 1 (`vector_screen.py`) is a vectorized,
optimistic-fill screen that eliminates dead parameter regions before the expensive
event-driven Stage 2 engine is built. **Screening results are never gate evidence.**

## What's built (unit tests green, `ruff`/`pyright` clean throughout)

- `src/scalpbot/backtest/costs.py` — fee/funding cost model. `maker_fee_bps` corrected to
  `1.5` (was `-0.5`) after verifying against Hyperliquid's own fee docs (2026-07-27):
  base tier is a cost, not a rebate, at this account's volume tier.
- `src/scalpbot/backtest/screen_config.py` — expands `configs/research.yaml`'s `screen:`
  block into `StrategyConfig`s. Grid axes: Bollinger period × sigma, RSI period ×
  thresholds, exit mode (bracket/mean_revert), `signal_direction`
  (mean_revert/momentum — momentum only pairs with bracket exits).
- `src/scalpbot/backtest/vector_screen.py` — the screen itself. Known, documented,
  conservative simplifications: stop-priority tie-break when a trade's window touches
  both stop and target; position sequencing that blocks new entries for a trade's full
  max-hold window; no funding modeled (Task 0.1 ingested price candles, not funding
  history — a real, tracked gap for Stage 2). Timeframe-aware (`_bar_seconds`) so
  `mean_revert`'s `time_stop_s` converts correctly at any resolution, not just 1s.
- `src/scalpbot/backtest/resample.py` — pure OHLCV resampling to coarser bars, used for
  the fee-drag diagnostic (Phase A.2 below).
- `src/scalpbot/backtest/research_ledger.py` — every evaluated config gets a
  `research/ledger.md` row, including zero-trade configs. No silent retries.
- `src/scalpbot/data/loader.py` — shared partition loader, extracted from `report.py`.
- `src/scalpbot/data/universe.py` + `scripts/build_universe.py` — Task 0.2 universe
  selection (volume-rank + listing-age, no lookahead; `spread_bps_max` deliberately
  unenforced — no historical spread data in either corpus).
- `scripts/run_screen.py` — CLI; `--signal-direction`/`--bollinger-period` filters exist
  purely to keep a single invocation inside this environment's ~10-minute command budget
  (a full 324-config grid does not fit in one call; ~70-110 configs reliably does).

## Round 1 — anchor candidate, lookback 600-2400s (10-40min): kill signal, partial coverage

168 config evaluations (all 108 BTCUSDT, ~56% of ETHUSDT) before a performance problem
cut the run short. **Zero positive.** Best -0.0447R (ETHUSDT), worst -0.0937R (BTCUSDT).
Trade counts were enormous (4,000-43,000/config over 21 months) — far too frequent for
genuine 3σ extremes, pointing at the lookback being too narrow to represent real
dislocations on 1s bars (fee-harvesting noise, not trading extremes).

## Round 2 — anchor candidate, lookback 3600-14400s (1-4h): kill signal, full coverage

Fixed the lookback (widened per Round 1's diagnosis) and the performance bug (numpy-array
candidate loop instead of `iter_rows`). **432/432 configs, all 4 symbols, zero positive.**
Best per symbol: BTC -0.0349R, ETH -0.0375R, SOL -0.0331R, DOGE -0.0426R. `mean_revert`
exits clearly beat `bracket` (up to 65% win rate) but average win size still didn't clear
average loss + costs. Notable: results got *worse*, not better, as lookback grew
1h→2h→4h — the sweet spot (if any) is nearer 40min-1h, not further out.

## Round 3 — full "zoom out": kill signal, comprehensive coverage

User-directed after Round 2's result, given 600 straight negative trials risked becoming
directionless grid search (the multiple-testing trap `deflated_expectancy`/the plateau
check exist to guard against — not yet built, but the discipline already applies
informally). Three parallel workstreams, each answering a different question:

**Phase A — bounded follow-up on the existing signal (no new data):**
- **A.1, isolate RSI period**: added `rsi.period: [60, 300]` (1min/5min) alongside the
  original `[5, 14]` (5s/14s — PLAN.md's "fast RSI" anchor). **Did not rescue the
  signal** — slower RSI periods performed the same or slightly worse than the fast
  anchor at every Bollinger period tested (all three, exhaustively, on BTCUSDT). Rules
  out "fast RSI firing on tick noise" as an independent cause distinct from the
  Bollinger-lookback issue Round 1→2 already fixed.
- **A.2, isolate timeframe/fee-drag** (`scripts/run_timeframe_screen.py`, resampling
  already-ingested 1s data to 1min/5min — no new ingestion): **partially confirmed the
  fee-drag hypothesis.** 1-minute bars remained clearly negative with *large, robust*
  t-stats (-13 to -22 across thousands of trades — a real, reliable negative effect, not
  noise). 5-minute bars dropped to hundreds of trades and mostly-negative-but-closer-to-
  breakeven results; the one apparent positive outlier (SOLUSDT +0.33R) had only 13
  trades and t=0.74 — not statistically significant, a small-sample artifact, not a
  discovery. Verdict: overtrading/fee-drag was real and partially explains Round 1-2's
  severity, but removing most of it still doesn't produce a reliable edge, just noise in
  both directions on samples too small to resolve.
- **A.3**: added `standard_error`/`t_stat` to `_summarize`'s output — used throughout
  this round to separate "robust negative" from "small-sample noise," including on the
  handful of nominally-positive results below.

**Phase C — a structurally different signal family, momentum/breakout (no new data):**
Added `signal_direction` (mean_revert/momentum) — momentum bets a band-pierce
*continues* rather than reverts (long on upper-band pierce + RSI overbought, the mirror
image of the anchor). **Also a clean kill.** BTCUSDT: full 108-config momentum grid,
zero positive, best -0.0403R (t=-2.98, n=433 — a real, if modest, negative effect).
ETHUSDT: best -0.0237R (t=-1.52). DOGEUSDT: best real result ~flat, -0.0014R (t=-0.08,
statistically indistinguishable from zero — the closest to breakeven anywhere this
round). SOLUSDT: top nominal result +0.2148R had **2 trades** (t=1.89) — a textbook
small-sample noise artifact, not a real edge; flagged explicitly rather than chased.

**Phase B — Task 0.2 universe selection: built, widening deliberately stopped.**
`data/universe.py` and `scripts/build_universe.py` are built and unit-tested (real
fixtures: no-lookahead ranking, listing-age floor, both verified against hand-built
multi-symbol volume histories) — that part is genuinely done and reusable. Widening the
screened universe past the 4-symbol pilot basket to `AVAXUSDT, LINKUSDT, LTCUSDT,
ADAUSDT, DOTUSDT` needed ingesting 5 more symbols' full tick-level history — realistically
hours of wall-clock time — and was stopped partway (AVAXUSDT ~88% done, the other four not
started) on user direction: those 5 coins aren't meaningfully less efficient than the
pilot 4, so re-running the *same, already-thrice-killed* signal family on them had low
expected information value relative to the ingestion cost. Round 4 (below) was the
higher-value use of the same effort. **Status: infrastructure ready, data incomplete,
deliberately not resumed — reconsider only alongside a signal with a real reason to
expect a wider/less-efficient universe would behave differently** (resume via
`scripts/ingest_binance.py --symbols AVAXUSDT,LINKUSDT,LTCUSDT,ADAUSDT,DOTUSDT`,
idempotent/resumable, if that reason ever exists).

## Round 4 — cross-venue basis dislocation: inconclusive, not a kill (data-starved)

User pushed back mid-Round-3 on continuing to widen the *same* signal family to
similarly-liquid coins ("has anything been solved?") — fair challenge. Stopped the
universe-widening ingestion (low expected information value: the 5 candidate symbols
aren't meaningfully less efficient than the pilot 4) and built a genuinely different
hypothesis instead, using data already on disk: **cross-venue basis dislocation** — bet
the Binance/Hyperliquid price *basis* reverts, not that either venue's own price does.
Economically closer to arbitrage (a real convergence mechanism) than a statistical
pattern in one series.

Implementation reused the existing Bollinger/RSI machinery almost entirely:
`vector_screen._compute_indicators`/`_evaluate_config` generalized with a
`source_column` parameter (defaults to `"close"`, preserving every prior round's
behavior exactly — verified via the full existing test suite passing unchanged) so the
*same* band-pierce entry logic can run against a `basis_bps` series instead of price,
while P&L still realizes against Hyperliquid's own tradeable price. New:
`backtest/basis_signal.py::build_basis_corpus` (resamples Binance to 1h, joins against
HL's native-1h candles, computes basis in bps) and `scripts/run_basis_screen.py` (36
bracket-only, mean_revert-only configs — momentum doesn't have the same economic
rationale for a basis bet).

**Result: inconclusive, not a kill.** Ran in ~30 seconds (tiny sample). Every symbol's
basis corpus has only ~2,160 overlapping hourly bars (Hyperliquid's `venue_corpus.start`
of 2026-01-01 to the 2026-04-01 holdout boundary — ~90 days at 1h resolution, itself
near the ceiling of what `candleSnapshot`'s ~200-215-day rolling cache can provide at
this granularity). Trade counts topped out at **4** across all 144 config×symbol
evaluations; most were 0-2. The nominal "best" results (+0.33R) all have 1-2 trades —
meaningless. This is categorically different from Rounds 1-3's clean kills (thousands of
trades, |t-stat| up to 29): **there isn't enough data here to reject or confirm the
hypothesis**, not "tested and found wanting." (Also surfaced a minor display bug: `t_stat`
can blow up to nonsensical magnitudes — e.g. `-1.4e15` — when a 2-trade sample has
near-zero variance in `r_net`, a division-by-near-zero artifact in `_summarize`. Doesn't
change any conclusion since n=2 is uninterpretable regardless of the reported t-stat;
worth a guard if this path gets reused, not fixed here.)

**What this means concretely**: the basis-dislocation hypothesis remains genuinely
untested at this sample size, not disproven. Getting a real read would need either more
Hyperliquid history than the info API's rolling cache can provide at 1h resolution
(a different ingestion source, not attempted), or accepting a fundamentally small-sample
research question. Flagged plainly rather than either oversold as a discovery or
misreported as a fourth kill.

## Round 5 — funding-rate-extreme: suggestive but underpowered, not a kill, not a discovery

Continuing from Round 4's open question ("has anything been solved?" — fair challenge):
before committing to the big `hyperliquid-archive` S3 investment, checked whether a
*different*, verified-available data source could give a cheap, fast read. Empirically
curled Hyperliquid's `fundingHistory` info-API endpoint directly: unlike `candleSnapshot`,
it is **not** a rolling cache — real data confirmed back to at least 2023-06-01 (2023-01-01
returns empty, consistent with pre-listing, not a depth limit). It's paginated instead, at
exactly 500 records/request for wide ranges — but a single UTC day (24 hourly events) is
far under that, so day-by-day ingestion needed no pagination loop, same shape as the
existing candle pipeline. Built `data/hyperliquid_funding.py` (mirrors
`hyperliquid_candles.py`), ingested the **full** 2024-07-01→2026-06-30 window for all 4
pilot symbols (verified against a fresh curl — values matched exactly), zero failed days.

**Signal**: bet that extreme *accumulated* funding pressure (crowded positioning) precedes
a squeeze back toward flat — a real, well-known perp-market mechanism, not a price
technical. Reused Round 4's `source_column` machinery unchanged
(`vector_screen.screen_grid(..., source_column="funding_pressure")`); new
`backtest/funding_signal.py::build_funding_corpus` joins HL's own OHLC with a rolling
trailing-hours sum of funding_rate, computed over the full funding history before joining
down to the shorter candle window (so the indicator itself is fully warmed up, not wasting
any of the short window on warm-up).

**Two real bugs found and fixed before trusting any result**:
1. Funding-event timestamps carry a few-to-tens-of-ms jitter (`...78`, `...05`, never
   `...00`) while candle timestamps are exact hour boundaries — an exact-equality join
   silently dropped the vast majority of otherwise-overlapping hours (first real run:
   67 rows instead of thousands). Fixed by flooring funding timestamps to the hour before
   joining; added a regression test (`test_build_funding_corpus_floors_funding_jitter...`)
   so this can't silently regress.
2. `hl_candles` wasn't filtered to pre-holdout before use (unlike Round 4's Binance data)
   — HL's candle corpus spans past the holdout boundary, so the first fixed run still
   risked trading on holdout rows. Fixed by filtering `open_time_ms <
   signal_corpus.holdout_start_ms` before building the corpus, matching Round 4's
   discipline. (Round 4 itself was unaffected — its inner join was already implicitly
   bounded by the Binance side, which *was* filtered.)

**Result, honestly**: better-populated than Round 4 (max 34 trades vs. max 4) but still
underpowered to conclude anything either way. 144 config×symbol evaluations: 15 positive
(10%), 129 negative. Best: BTCUSDT +0.110R (n=13, t=0.74); the single largest-sample
positive result is ETHUSDT +0.090R (n=32, t=1.05) — the best-populated result of the whole
round, and still nowhere near conventional significance (|t|≳1.65 for even weak
one-tailed significance). **This sits genuinely between Rounds 1-3 (thousands of trades,
robust kills) and Round 4 (≤4 trades, uninterpretable)** — modestly suggestive, not
disproven, not proven. Reported as exactly that, not rounded up to a discovery or down to
a fourth kill.

### Combined tally across the three *conclusive* rounds

**1,694 config×symbol evaluations logged in `research/ledger.md`.** Only 39 show
positive expectancy (2.3%) — and of those, only **3** have ≥30 trades (all SOLUSDT
momentum, expectancy 0.01-0.04R, none statistically significant). Every other nominal
"positive" is a 0-2-trade artifact. **There is no meaningfully-sized, statistically
significant positive result anywhere in this session's screening.**

### Verdict

Two structurally different signal families (mean-reversion, momentum), three lookback
regimes (10-40min, 1-4h, plus the 1min/5min resample diagnostic), four RSI periods, all
four pilot symbols: a comprehensive, consistent, well-earned kill signal for **this**
screened design space — naive Bollinger/RSI-based signals (either direction) on the
pilot-basket majors, under this hostile-adjacent cost model, at these timeframes. Not
proof no edge exists anywhere in crypto perps — the real, structural gaps that remain
untested are (a) a wider, less-arbed universe (Phase B, infrastructure ready, data
pending) and (b) a genuinely different feature class (order-flow/funding/cross-venue
signals, not price-and-oscillator technicals). Round 4 attempted the cross-venue-basis
variant of (b) and came back genuinely inconclusive (data-starved, not negative) rather
than adding a fourth kill; Round 5 (funding-rate-extreme, also feature class (b)) landed
in between — better-populated than Round 4 but still short of any conventional
significance threshold. Both are honest open questions, not closed ones.

**What's actually been resolved vs. still open, stated plainly:**
- **Resolved**: price-technical signals (Bollinger/RSI, either direction, three lookback
  regimes, four RSI periods) on the pilot-basket majors don't have a real edge net of
  costs. 1,694 trials, robust statistics, not going to flip with more of the same.
- **Still open**: whether *any* signal built from Hyperliquid-specific structural data
  (cross-venue basis, funding pressure) has real edge. Both attempts so far are
  underpowered because the tradeable-price side is capped at ~90 pre-holdout days —
  a data ceiling, not a negative result. The `hyperliquid-archive` S3 bucket
  (`market_data`/`asset_ctxs`, official, free, not yet format-inspected) is the
  concrete, named path to actually answering this, not just running the same
  underpowered probe a third time.

Per this round's own stated discipline: three conclusive kills plus two inconclusive,
data-limited probes on the two most promising untested hypotheses is the point to report
plainly and make a real infrastructure-investment decision (pursue deeper HL history via
the S3 archive, or stop here) rather than continuing to spin up more small-sample probes
against the same ~90-day ceiling.

## Known, non-blocking gaps (backlog)

- No funding modeled in the screen (see above) — a real, not cosmetic, gap for anything
  beyond directional price screening.
- Phase B's universe widening is incomplete, stopped deliberately — see above.
- `_summarize`'s `t_stat` can report nonsensical magnitudes (seen: ~1e15) on very
  small samples with near-zero `r_net` variance (division by a near-zero standard
  error) — cosmetic given n this small is already uninterpretable, but worth a guard
  (e.g. suppress below some minimum n) if small-sample screens like Round 4 recur.
- The screen's conservative tie-break/sequencing simplifications (documented in
  `vector_screen.py`'s module docstring) bias toward *understating* edge, not overstating
  it — consistent with Stage 1's job, but worth remembering if a future signal comes
  close to the bar rather than missing it by an order of magnitude.
