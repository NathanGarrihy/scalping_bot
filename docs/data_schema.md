# Data schema and partition layout (Task 0.1)

Source of truth for column *definitions* is `src/scalpbot/data/schema.py` (the code that
actually enforces/tests them); this document mirrors it for humans and adds the
partition-layout and symbol-naming context that doesn't belong in a schema constant. Keep
both in sync when either changes.

Neither on-disk schema is `scalpbot.core.events.Candle`. `core` is pure and must never
import the data layer (CLAUDE.md, enforced by `.claude/hooks/guard_core_purity.py`); these
schemas are the data layer's own richer, provenance-tagged archival contract. Translating
ingested rows into `Candle` events is a future backtest-driver concern, not this task's.

## Partition layout

```
{root}/{venue}/{kind}/{symbol}/{interval}/{date}.parquet
```

- `root` defaults to `./data/` (gitignored), configurable per CLI invocation.
- `venue` is `binance` or `hyperliquid`.
- `kind` is `klines` (Binance) or `candles` (Hyperliquid).
- `symbol` uses each venue's own native naming (see below) — no cross-venue normalization
  in the path itself.
- One file per symbol/interval/UTC day. Day-partitioning matches Binance's own daily-zip
  granularity and gives both pipelines a natural resumability unit.
- Writers stage to `{date}.parquet.tmp` and `os.replace()` to the final name only after a
  shape check passes; a stray `.tmp` file left by a killed process is ignored by readers and
  overwritten by the next run. See `src/scalpbot/data/paths.py` for the exact mechanism.
- `{root}/reports/integrity_report_{run_ts}.json` holds saved output from
  `scripts/data_report.py`.

## Binance signal-research corpus — `BINANCE_KLINE_SCHEMA`

Source: `data.binance.vision`, USD-M futures daily **aggTrades** archive, resampled into 1s
bars by our own code. **Binance's USD-M futures market has no native 1s kline endpoint** —
confirmed empirically (`.../klines/{symbol}/1s/...` 404s; only 1m+ intervals exist for
futures). PLAN.md §3's "1s k-line / aggTrade data" phrasing anticipated exactly this: we
download tick-level aggTrades and build the 1s bars ourselves
(`src/scalpbot/data/binance_archive.py::resample_to_1s_bars`).

Every second of the UTC day gets a row, including seconds with zero trades: those bars
forward-fill `open`/`high`/`low`/`close` from the prior bar's close with `volume = 0`,
matching how Binance's own native klines already represent thin-book gaps. This means an
"empty" second is expected data (common on the less liquid pilot-basket symbols), not an
integrity gap — the gap-detection logic in `integrity.py` operates on genuinely missing
rows (e.g. a whole missing day), not zero-volume seconds.

| Column | Type | Meaning |
| :--- | :--- | :--- |
| `symbol` | Utf8 | Binance USD-M naming, e.g. `BTCUSDT` |
| `open_time_ms` | Int64 | Kline open time, exchange ms epoch, UTC |
| `close_time_ms` | Int64 | Kline close time, exchange ms epoch, UTC |
| `open`, `high`, `low`, `close` | Float64 | Price |
| `volume` | Float64 | Base-asset volume |
| `quote_volume` | Float64 | Quote-asset volume |
| `n_trades` | Int64 | Trade count in the bar |
| `taker_buy_base_volume` | Float64 | Taker-buy portion, base asset |
| `taker_buy_quote_volume` | Float64 | Taker-buy portion, quote asset |
| `source` | Utf8 | Constant `"binance_archive"` |

## Hyperliquid venue-calibration corpus — `HYPERLIQUID_CANDLE_SCHEMA`

Source: HL info API `candleSnapshot`. One row per closed candle, **interval fixed at `1h`**.

Confirmed empirically: `candleSnapshot` is a rolling cache, not full history — it serves
roughly the most recent ~5000 bars per (coin, interval), so retention depth scales inversely
with granularity (1m ≈ 3 days, 5m ≈ 15-20 days, 15m ≈ 30-50 days, 1h ≈ 200-215 days). Since
`configs/research.yaml`'s `venue_corpus.start` (2026-01-01) is ~207 days back from a typical
run date, only `1h` or coarser reliably covers that whole window through the info API alone —
finer intervals silently truncate or return empty for older days rather than erroring, which
is why this is fixed at `1h` rather than left as a config knob. This is coarser than the
signal-research corpus's 1s bars, but this corpus's job is fee/funding/regime/cross-venue-basis
calibration, not microstructure — spread/depth precision is Task 0.3's deferred L2 work.

Response field names (raw JSON, all price/volume fields returned as **strings**, cast to
float on ingestion): `t` (open ms), `T` (close ms, unused — not in our schema), `s` (coin),
`i` (interval), `o`/`h`/`l`/`c` (price strings), `v` (volume string), `n` (trade count, int).

Day-partition requests use `endTime = day_start_ms + 86_400_000 - 1` (not the exact next-day
boundary) — `candleSnapshot` is inclusive of `endTime`, so an exact next-midnight boundary
returns a 25th row belonging to the next day.

| Column | Type | Meaning |
| :--- | :--- | :--- |
| `symbol` | Utf8 | HL coin name, e.g. `BTC` (no `USDT` suffix) |
| `interval` | Utf8 | Venue-native interval string, fixed at `1h` |
| `open_time_ms` | Int64 | Candle open time, exchange ms epoch, UTC |
| `open`, `high`, `low`, `close` | Float64 | Price |
| `volume` | Float64 | Volume |
| `n_trades` | Int64 | Trade count, if the response provides it |
| `source` | Utf8 | Constant `"hyperliquid_info_api"` |

## Symbol naming

Binance and Hyperliquid name the same instrument differently. A small hardcoded map for the
pilot basket only lives alongside the Hyperliquid pipeline (not a general universe-mapping
engine — that's Task 0.2's job):

| Binance (USD-M) | Hyperliquid |
| :--- | :--- |
| `BTCUSDT` | `BTC` |
| `ETHUSDT` | `ETH` |
| `SOLUSDT` | `SOL` |
| `DOGEUSDT` | `DOGE` |

## Deferred: Hyperliquid L2 order-book snapshots

The `hyperliquid-archive` public S3 bucket's L2 order-book snapshots are **not** ingested by
Task 0.1. That data is needed for Task 0.3's hostile fill-model calibration (spread
distributions, depth-at-touch), not for Task 0.1's regime-coverage / cross-venue-basis
checks. See `src/scalpbot/data/hyperliquid_l2_stub.py` for the documented no-op placeholder.

## Holdout quarantine

The signal-research corpus's final `holdout_months` (per `configs/research.yaml`,
currently 3) is downloaded like any other data — it's real data that should exist on disk —
but is excluded from every check in `scripts/data_report.py`'s output. It stays quarantined
until the walk-forward finale (PLAN.md §3.3) unseals it for its single use.
