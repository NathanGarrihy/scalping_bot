# Automated Mean-Reversion Scalping System: Build Plan v2

**High-beta crypto perpetuals · Hyperliquid · Maker-only execution · Edge-gated deployment · July 2026**

Supersedes `initial_plan.md` (kept for history). Two forces drove this revision: the July 1, 2026
MiCA enforcement deadline removed Binance as a viable venue for EU-resident traders, and a design
review identified overfitting risk and backtest/live divergence as the two failure modes most
likely to kill the project even if every task in v1 was executed correctly.

## 1. Executive Framing

*   **Honest objective:** Not "the most impressive strategy ever built," but a bot with genuinely
    positive expectancy after all costs that cannot blow up its account. That outcome alone places
    the system ahead of the overwhelming majority of retail automation attempts.
*   **Core principle:** No infrastructure is built until the edge survives a hostile backtest, and
    no capital is deployed until live shadow performance falls inside the backtest's Monte Carlo
    confidence bands. Every phase gates the next, and every gate is an executable script that
    prints PASS or FAIL from run artifacts — promotion is never a judgment call.
*   **Venue: Hyperliquid.** Binance ceased serving EU users on July 1, 2026 (no MiCA license).
    Among the venues actually reachable from Ireland, Hyperliquid dominates for this strategy
    class: maker rebate at base tier (a maker-only scalper is *paid* to trade rather than paying
    0.02%), self-custody (no exchange counterparty risk), native TP/SL order grouping (eliminates
    the v1 OCO-supervisor hack), agent wallets that are trade-only by construction, free
    historical data via public S3, and node infrastructure in Tokyo — consistent with the v1
    colocation choice. The regulated alternative (Kraken Pro: MiCA via the Central Bank of
    Ireland + MiFID II derivatives passporting) remains the documented fallback; the exchange
    adapter interface (§10) exists precisely so the venue can be swapped without touching the
    strategy core.
*   **Venue risk acknowledged:** Hyperliquid access for EU retail is a regulatory grey zone (MiCA
    regulates intermediaries; a decentralized protocol arguably sits outside it) rather than an
    explicitly authorized channel, and DEX infrastructure carries protocol risk a CEX does not.
    Mitigations: strict venue-adapter seam, small capital (€200), self-custody, and a standing
    quarterly review of the regulatory position.

## 2. Key System Design Principles

*   **Edge-first validation:** Phase 0 results gate all engineering effort.
*   **Hostile fill modeling:** Expectancy must be positive under pessimistic assumptions — maker
    fills granted only on trade-through, full venue fee schedule (verified live, not assumed from
    docs), hourly funding accrual, and punitive stop-slippage haircuts.
*   **One strategy implementation:** The strategy core is a pure, deterministic function driven
    identically by the backtest replayer, the shadow engine, and the live engine. Backtest/live
    divergence is the #1 silent killer of retail systems; sharing the code path eliminates the
    largest source of it.
*   **Overfitting treated as the default outcome:** Every experiment is logged; parameter plateaus
    are required; walk-forward splits are purged and embargoed; one final holdout is touched
    exactly once. A strategy that cannot survive this discipline never had an edge.
*   **Latency proportionality:** Tokyo colocation (AWS ap-northeast-1) for single-digit-ms RTT to
    the Hyperliquid nodes. Python is acceptable because the latency budget lives in the network,
    not the interpreter, for 1s-bar mean reversion.
*   **Portfolio-level risk:** Correlation cap of 1–2 concurrent positions; three-layer circuit
    breakers; empirical (Monte Carlo) kill thresholds, never round numbers.

## 3. Phase 0 — Edge Validation (gates everything)

No infrastructure code is written until this phase passes. If it fails, iterate on the signal for
the cost of a data pipeline and a backtest harness — not for the cost of €200 and six weeks of
execution engineering.

### Task 0.1 — Historical Data Acquisition (two-source strategy)
*   **Deliverable:**
    *   **Signal-research corpus:** 2+ years of 1s k-line / aggTrade data from the Binance public
        archive (`data.binance.vision` — still freely downloadable post-EU-exit), spanning at
        least one full regime cycle (chop, trend, crash) and one ≥40% drawdown in the underlying.
        Rationale: Hyperliquid launched perps in 2023 and lists many alts later, so its own
        history is too short for multi-regime validation; cross-venue price basis on liquid perps
        is negligible relative to a 3σ signal.
    *   **Venue-calibration corpus:** Recent months of Hyperliquid data — L2 book snapshots from
        the public `hyperliquid-archive` S3 bucket plus candles/trades from the info API — used to
        calibrate the fill model, spread distributions, and cost model on the venue actually
        traded.
    *   All data landed as Parquet with a documented schema; ingestion is idempotent and resumable.
*   **Validation:** Integrity gate passes: no gaps larger than the bar interval, monotonic
    timestamps, non-negative volumes, regime coverage confirmed. Cross-venue sanity check: HL vs
    Binance mid-price basis on overlapping periods is small relative to signal amplitude.
*   **Kill criteria:** Only recent bull-market data available, or HL microstructure (spreads,
    depth) so different from Binance's that a Binance-validated signal is untransferable.

### Task 0.2 — Universe Selection (survivorship-bias guarded)
*   **Deliverable:** Rule-based candidate basket: rolling volume rank, spread ceiling (bps),
    listing age ≥ 90 days, not flagged for delisting — evaluated **as-of each historical date**,
    so the backtest trades the universe that was selectable then, not the survivors visible today.
    Universe rules are config, re-runnable, and produce a dated universe file per rebalance.
*   **Validation:** Universe time series reconstructs without lookahead; every backtest trade maps
    to a symbol that was in-universe on its entry date.
*   **Kill criteria:** Basket selection requires manual judgment per symbol (unautomatable = untestable).

### Task 0.3 — Backtest with Hostile Fill Model
*   **Deliverable:** Two-stage backtest of the mean-reversion family (3σ Bollinger + fast RSI as
    the anchor candidate) under deliberately pessimistic assumptions:
    *   **Stage 1 — vectorized coarse screen** (polars) over the parameter grid: eliminates dead
        regions cheaply. Screening only; never cited as evidence.
    *   **Stage 2 — event-driven replay** through the *production strategy core* (§10) with the
        hostile fill model: maker fills only when price trades **through** the limit level (touch
        ≠ fill), full verified fee schedule (maker rebate applied only when the fill model grants
        a maker fill), **hourly** funding accrued over holding periods, stop-market exit slippage
        haircut of 0.3–0.5% minimum on high-beta alts.
    *   Both exit structures tested: (a) fixed 2%/6% bracket, (b) reversion to middle band with a
        hard time stop.
*   **Anti-overfitting protocol (hard requirements):**
    *   **Research ledger:** every configuration ever evaluated is appended to
        `research/ledger.md` (config hash, data range, result). The number of trials feeds a
        deflated-Sharpe-style discount on the winner. No silent retries.
    *   **Parameter plateau:** the chosen configuration's neighbors in parameter space must also
        be profitable. A spike optimum is treated as noise and rejected.
    *   **Walk-forward with purged, embargoed splits:** parameters tuned on each training window,
        tested untouched on the following window; an embargo gap between train and test prevents
        leakage through overlapping holding periods. Never tune on the full dataset.
    *   **Single-use holdout:** the most recent N months are quarantined and evaluated exactly
        once, after all iteration stops. A second look at the holdout resets the quarantine clock
        with fresh data.
*   **Validation:** Positive expectancy after all costs on walk-forward out-of-sample AND on the
    single-use holdout, in ≥2 distinct regimes, on a parameter plateau, after the multiple-testing
    discount.
*   **Kill criteria:** Expectancy ≤ 0.05R after costs, edge exists in only one regime,
    profitability depends on fills the hostile model disallows, or the winner sits on a spike
    optimum. **HARD STOP:** do not proceed to Phase 1.

### Task 0.4 — Monte Carlo Drawdown Mapping
*   **Deliverable:** Resample the validated trade sequence 10,000 times. Extract expected max
    drawdown, P95 drawdown, and longest losing streak.
*   **Validation:** Live kill thresholds and circuit-breaker levels in Phases 4–5 are set from
    these empirical distributions. A normal losing streak must be distinguishable from a broken
    system before capital is at risk.
*   **Kill criteria:** P95 drawdown exceeds 40% of equity at the intended risk-per-trade: reduce
    sizing or reject the strategy.

## 4. Phase 1 — Infrastructure and Data Plumbing

### Task 1.1 — Venue Access, Environment, and Colocation
*   **Deliverable:** Python 3.12 environment on a VPS in AWS ap-northeast-1 (Tokyo), connected to
    the Hyperliquid **testnet**. Authentication via a dedicated **agent wallet** (trade-only by
    construction — cannot withdraw) operating a dedicated **subaccount**; the master wallet key
    never touches the VPS. Secrets in environment variables, never in the repo.
*   **Validation:** Info and exchange endpoints reachable with RTT consistent with Tokyo
    colocation; agent wallet can place/cancel on testnet; a withdrawal attempt from the agent
    wallet fails by construction.
*   **Kill criteria:** Master key material on the VPS, or RTT inconsistent with colocation.
    Running the chase loop from a Dublin residential connection is a design failure, not a tuning
    problem.

### Task 1.2 — Websocket Ingestion and Order-Event Stream
*   **Deliverable:** Asyncio websocket client streaming candles and book tops for the basket
    (`fast: true` where the 2s book cadence is needed — the June 2026 API change made 5s the
    default), plus `userEvents`/`orderUpdates` subscriptions for fill and order state. Fill status
    is never polled via REST. NTP clock-drift monitoring included.
*   **Validation:** 24h soak with zero missed heartbeats and no memory growth; automatic reconnect
    and full resync (open orders + positions re-fetched, subscriptions re-established) within 5
    seconds of a forced disconnect.
*   **Kill criteria:** Silent websocket drop without automatic resync, or fill detection dependent
    on REST polling.

### Task 1.3 — Durable State Journal
*   **Deliverable:** Every state transition and order intent journaled to SQLite (WAL mode)
    **before** the API call, with idempotent client order IDs (cloids) so a crash mid-request
    cannot double-fire. On boot, local state reconciles against the exchange; the exchange is the
    source of truth, the journal records intent.
*   **Validation:** `kill -9` mid-trade, restart, correct state recovered — automated as a chaos
    test in CI, not a one-off manual check. Polling alone cannot distinguish "order never sent"
    from "order sent, response lost"; the journal plus cloids can.
*   **Kill criteria:** Any recovery path that can duplicate an order or orphan a position without a stop.

### Task 1.4 — Rate-Limit Budgeter
*   **Deliverable:** Central token-bucket module enforcing both Hyperliquid limits: the per-IP
    aggregate weight (1200/min) and the **address-based** budget (1 request per 1 USDC traded,
    10k initial buffer). Every outbound request passes through it; the chase loop's worst case
    (cancel/replace × basket size) is provably within budget at the €200 account's trading volume.
*   **Validation:** Sustained-operation simulation shows headroom; budgeter refuses requests
    rather than letting the venue reject them.
*   **Kill criteria:** Any code path that bypasses the budgeter.

## 5. Phase 2 — Signal Generation and Filters

### Task 2.1 — Extreme Volatility Detection
*   **Deliverable:** O(1) rolling computation of the 3σ Bollinger Band and fast RSI on the
    timeframe selected by Phase 0, inside the deterministic core. Trigger state logged when price
    pierces the 3σ band with RSI beyond the validated thresholds.
*   **Validation:** Replay of historical ticks produces triggers identical to the Phase 0
    backtest — same code, same output, bit-for-bit.
*   **Kill criteria:** Signal parameters drift from the frozen validated configuration (§10)
    without a re-run of the walk-forward protocol.

### Task 2.2 — Execution State Machine
*   **Deliverable:** Explicit transition table across `WAITING → SIGNAL → ORDER_PLACED → FILLED →
    MANAGING_POSITION → FLAT` (plus `HALTED`), backed by the Task 1.3 journal. Illegal transitions
    raise; property-based tests (hypothesis) assert invariants: never two concurrent opposite
    signals on one asset, never a position without a resting stop in `MANAGING_POSITION`.
*   **Validation:** Correct state recovered after restart mid-trade via journal-plus-exchange
    reconciliation; property suite green.
*   **Kill criteria:** State machine permits two concurrent opposite signals on the same asset.

### Task 2.3 — Filter Layer: trade quality over trade frequency
*   **Spread filter:** Skip entries when spread exceeds a bps threshold — a wide spread means a
    thin book, and a passive fill into a thin book is toxic.
*   **Funding filter:** Skip or downsize when the **hourly** funding rate is extreme against the
    trade direction (thresholds recalibrated from Binance's 8h convention).
*   **Correlation cap:** Max 1–2 concurrent positions across the basket. Five simultaneous longs
    on correlated alts is one 5x-sized trade.
*   **Regime/volatility halt:** Halt entries when realized vol (asset and BTC-level) exceeds the
    backtested regime envelope — the signal was not validated for that environment.
*   **Circuit breakers (three-layer, encoded):** daily loss limit (−6% equity → flat and halt
    until next UTC day), max consecutive-loss halt (threshold from the Monte Carlo streak
    distribution), and the volatility halt above.

## 6. Phase 3 — Execution and Risk Module

### Task 3.1 — Maker Order Routing and Bounded Chasing
*   **Deliverable:** **ALO** (add-liquidity-only) limit order at best bid/ask on signal fire — a
    crossing order is rejected by the venue, never silently filled as taker. If unfilled in 3s,
    cancel and replace at the new best, max 3 retries, all through the rate budgeter. Chase aborts
    entirely if price has moved more than X ticks from signal price — chasing a runaway move
    converts a mean-reversion entry into an unvalidated momentum entry.
*   **Validation:** Zero taker fills across the full testnet campaign; chase abort triggers on
    fast moves; worst-case chase request count within budget.
*   **Kill criteria:** Any taker fill, or an unbounded cancel/replace loop.

### Task 3.2 — Native Bracket Management
*   **Deliverable:** On entry fill, immediately place the venue's **native TP/SL** (position-tied,
    grouped, reduce-only stop-market + take-profit) — Hyperliquid's order grouping replaces the v1
    OCO-supervisor loop, removing an entire class of race conditions. The TP structure is
    whichever exit Phase 0 validated. Leverage locked at the validated level (10x ceiling),
    isolated margin. Bracket placement is journaled and retried on failure; a position without a
    resting stop for >500ms triggers an immediate flatten.
*   **Validation:** Testnet entries show the stop resting on the venue within 500ms of fill,
    including partial-fill scenarios.
*   **Kill criteria:** Stop not on the exchange within 500ms of entry fill. If this cannot be
    met, the architecture is unsafe for leverage — full stop and redesign.

### Task 3.3 — Deadman Watchdog and Killswitch
*   **Deliverable:** An **independent process** (separate systemd unit) that watches the engine's
    heartbeat file/socket; on silence beyond a threshold it cancels all orders and flattens all
    positions through its own minimal venue client. Plus `killswitch.py`: one command that
    cancels-all, flattens, and halts, usable from a phone over SSH.
*   **Validation:** Kill the engine process mid-position; watchdog flattens within its threshold.
    Killswitch drill executed successfully from outside the VPS.
*   **Kill criteria:** Watchdog shares a failure domain with the engine (same process/venv crash
    takes both down).

## 7. Phase 4 — Shadow-Live Validation

Testnet validates code paths, not edge: its order book is fantasy liquidity. This phase runs the
complete production system against **live mainnet market data** with real order logic but a paper
ledger applying the same hostile fill rules as Phase 0.

*   **Deliverable:** 200+ shadow trades on live data: trade-through fills only, verified fees,
    hourly funding, slippage haircut. Same binary, same config hash, ledger swapped.
*   **Validation:** Shadow expectancy inside the Phase 0 Monte Carlo confidence band; live signal
    frequency, spread distributions, and would-be fill rates match backtest assumptions.
*   **Kill criteria:** Signal frequency or fill rates diverge materially from backtest — the fill
    model was optimistic and live capital would bleed. Return to Phase 0 with the live data.

## 8. Phase 5 — Live Burn-in

*   **Deliverable:** Agent wallet on a dedicated subaccount funded with exactly €200 (USDC).
    Sizing: €20 margin per trade controlling €200 notional at 10x, isolated. Minimum 100 live
    trades executed autonomously; no intervention except critical software bugs (every
    intervention logged in the research ledger).
*   **Validation:** Realized performance evaluated against the Phase 0 Monte Carlo bands — not a
    raw win-rate eyeball. Realized stop-exit slippage compared against the modeled haircut.
    Realized maker-fill rate compared against the hostile fill model's grant rate.
*   **Kill criteria:** Equity breaches the P95 backtested drawdown; realized stop slippage exceeds
    2x the modeled haircut; or the sizing algorithm ever attempts full-equity margin on one trade.
    Any breach: killswitch, extract logs, return to Phase 0.

## 9. Gate Summary

Every gate is an executable script in `gates/` reading run artifacts and printing PASS/FAIL.
Gates fail closed: an unimplemented or errored gate is a FAIL.

| Gate | Passes when | Fails to |
| :--- | :--- | :--- |
| **Phase 0** | Positive expectancy after hostile costs, on walk-forward OOS **and** single-use holdout, ≥2 regimes, parameter plateau, post-discount; P95 drawdown ≤ 40% | Full stop — iterate signal, no build |
| **Phase 1** | 24h stable ingestion; kill-9 chaos test green; Tokyo RTT verified; budgeter enforced | Fix infrastructure before signal work |
| **Phase 2** | State-machine property suite green; filters active; live config hash matches frozen validated hash | No execution module work |
| **Phase 3** | Stop resting <500ms; zero taker fills; bounded chase within budget; watchdog drill passed | Redesign — unsafe for leverage |
| **Phase 4** | 200+ shadow trades inside Monte Carlo band; fill/frequency assumptions confirmed | Return to Phase 0 with live data |
| **Phase 5** | 100+ live trades inside empirical bands; slippage ≤ 2x model | Killswitch, extract logs, Phase 0 |

## 10. Architecture Invariants

*   **Deterministic core:** `scalpbot.core` is pure — `(state, event, config) → actions` — with
    no I/O, no clock reads, no randomness. The backtest engine, shadow engine, and live engine are
    thin drivers feeding it events and executing its actions. One implementation, three harnesses.
*   **Frozen-config discipline:** The Phase 0 winner is serialized to `configs/strategy/` and
    hash-pinned. The live engine computes the hash at boot and **refuses to start** on mismatch.
    Changing any parameter means re-running the walk-forward protocol and re-freezing.
*   **Venue adapter seam:** All venue I/O goes through the `ExchangeAdapter` protocol
    (`venues/base.py`). Hyperliquid is the first implementation; a Kraken adapter is the
    regulatory hedge. The core never imports a venue module.
*   **Journal-before-send:** No order request leaves the process before its intent is durable.
*   **Observability:** Structured JSONL logs, SQLite metrics, Telegram alerts on halts, fills,
    errors, and watchdog events; a report script plots live equity against the Monte Carlo bands.
*   **Research ledger:** Append-only record of every experiment — the overfitting audit trail.

## 11. Standing Reviews

*   **Regulatory (quarterly):** Hyperliquid's EU posture; Bybit EU's MiFID derivatives rollout;
    Kraken adapter viability. Venue exit plan: killswitch → withdraw to self-custody → adapter swap.
*   **Fee/API (monthly, automated where possible):** verify live fee tier, funding cadence, and
    API contract against the cost model's parameters; alert on drift.
*   **Tax records:** every fill exported (CSV/Parquet) with timestamps and fees for Irish
    CGT/income reporting.
