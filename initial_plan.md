# Automated Mean-Reversion Scalping System: Build Plan

**High-beta crypto perpetuals · Maker-only execution · Edge-gated deployment · July 2026**

## 1. Executive Framing

This plan provides a rigorous roadmap for the development and deployment of an automated scalping system. The architecture prioritizes early edge validation, maker-only routing, durable state management, and portfolio-level risk controls to ensure institutional-grade reliability and risk mitigation.

*   **Honest objective:** Not "the most impressive strategy ever built," but a bot with genuinely positive expectancy after all costs that cannot blow up its account. That outcome alone would place the system ahead of the overwhelming majority of retail automation attempts.
*   **Core principle:** No infrastructure is built until the edge survives a hostile backtest, and no capital is deployed until live shadow performance falls inside the backtest's Monte Carlo confidence bands. Every phase gates the next.

## 2. Key System Design Principles

*   **Edge-First Validation:** No infrastructure is built until the strategy survives a hostile backtest. Phase 0 results gate all engineering effort.
*   **Hostile Fill Modeling:** Expectancy must be positive under pessimistic assumptions, assuming maker fills only on trade-through and incorporating full fee schedules and slippage.
*   **Latency Optimization:** Systems are colocated in Tokyo (AWS ap-northeast-1) to achieve single-digit millisecond RTT to the matching engine, ensuring competitiveness in limit-order placement.
*   **Correlation Caps:** Risk is managed at the portfolio level, enforcing a maximum of 1–2 concurrent positions to avoid over-exposure to systemic crypto beta.
*   **Empirical Benchmarking:** Performance is evaluated against Monte Carlo drawdown bands and out-of-sample data, ensuring statistical significance before live deployment.

## 3. Phase 0 — Edge Validation (gates everything)

No infrastructure code is written until this phase passes. If it fails, iterate on the signal for the cost of a data pipeline and a backtest harness — not for the cost of €200 and six weeks of execution engineering.

### Task 0.1 — Historical Data Acquisition
*   **Deliverable:** Two or more years of 1-second k-line or aggTrade-level data for all candidate tickers, spanning at least one full regime cycle: chop, trend, and crash.
*   **Validation:** Data integrity checks pass: no gaps larger than the bar interval, timestamps monotonic, volumes non-negative, coverage of at least one drawdown exceeding 40% in the underlying.
*   **Kill criteria:** Only recent bull-market data is available. An edge validated in one regime is not validated.

### Task 0.2 — Backtest with Hostile Fill Model
*   **Deliverable:** Vectorized backtest of the 3σ Bollinger + fast-RSI signal under deliberately pessimistic assumptions: maker fills granted only when price trades through the limit level (touch does not fill); full maker fee schedule for the candidate venue; funding payments accrued over holding periods; stop-market exit slippage haircut of 0.3–0.5% minimum on high-beta alts (cascade conditions slip far worse than mid-book quotes suggest). Both exit structures tested: (a) fixed 2%/6% bracket, (b) reversion to middle band with a hard time stop.
*   **Validation:** Positive expectancy after all costs, confirmed out-of-sample via walk-forward analysis: parameters tuned on year 1, tested untouched on year 2. Never tune on the full dataset. Edge must survive in at least two distinct market regimes.
*   **Kill criteria:** Expectancy ≤ 0.05R after costs, or the edge exists in only one regime, or profitability depends on fills the hostile model disallows. **HARD STOP**: do not proceed to Phase 1.

### Task 0.3 — Monte Carlo Drawdown Mapping
*   **Deliverable:** Resample the backtested trade sequence 10,000 times. Extract expected max drawdown, P95 drawdown, and longest losing streak.
*   **Validation:** Live kill thresholds and circuit-breaker levels in Phases 4–5 are set from these empirical distributions, not from arbitrary round numbers. A normal losing streak must be distinguishable from a broken system before capital is at risk.
*   **Kill criteria:** Distribution shows P95 drawdown exceeding 40% of equity at the intended risk-per-trade: reduce position sizing or reject the strategy.

## 4. Phase 1 — Infrastructure and Data Plumbing

### Task 1.1 — Exchange API, Environment, and Colocation
*   **Deliverable:** Secure Python/Node environment connected to the chosen venue's futures testnet, deployed on a VPS in AWS ap-northeast-1 (Tokyo) for single-digit-millisecond RTT to the matching engine. API keys stored in environment secrets, IP-whitelisted, withdrawal permissions disabled.
*   **Validation:** Script authenticates and pulls account balance via REST in under 100ms from the VPS. Keys with withdrawal enabled are treated as a security failure.
*   **Kill criteria:** Failure to secure keys properly, or inability to connect without timeouts. Running the chase logic from a Dublin residential connection is a design failure, not a tuning problem.

### Task 1.2 — Websocket Ingestion and User Data Stream
*   **Deliverable:** Asynchronous websocket client streaming 1-second k-lines for the candidate basket, plus a subscription to the user data stream for order and fill events. Fill status is never polled via REST. NTP clock-drift monitoring included (exchanges reject requests with >1s drift).
*   **Validation:** Stream runs 24 hours with zero disconnects or memory leaks; automatic reconnect and resync completes within 5 seconds; listen-key keepalive verified.
*   **Kill criteria:** Silent websocket drop without automatic reconnect and resync within 5 seconds, or fill detection dependent on REST polling.

### Task 1.3 — Durable State Journal (new)
*   **Deliverable:** Every state transition and order action journaled to SQLite (WAL mode) before the API call is made, with idempotent clientOrderIds so a crash mid-request cannot double-fire. On boot, local state is reconciled against the exchange; the exchange is always the source of truth, the journal records intent.
*   **Validation:** `kill -9` the process mid-trade, restart, and recover the correct state. Polling alone cannot distinguish "order never sent" from "order sent, response lost" — the journal plus idempotent IDs can.
*   **Kill criteria:** Any recovery path that can duplicate an order or orphan a position without a stop.

## 5. Phase 2 — Signal Generation and Filters

### Task 2.1 — Extreme Volatility Detection
*   **Deliverable:** Rolling buffer computing the 3-standard-deviation Bollinger Band and 5-period RSI on the timeframe selected by Phase 0. Trigger state logged when price pierces the 3σ band with RSI > 85 (overbought) or < 15 (oversold).
*   **Validation:** Trigger states logged accurately against replayed historical ticks; computation adds negligible latency (the true latency budget lives in the network, per Task 1.1).
*   **Kill criteria:** Signal parameters drift from the Phase 0 validated configuration without a re-run of the walk-forward test.

### Task 2.2 — Execution State Machine
*   **Deliverable:** State management across `WAITING` → `SIGNAL_GENERATED` → `ORDER_PLACED` → `FILLED` → `MANAGING_POSITION` → `FLAT`, backed by the Task 1.3 journal.
*   **Validation:** Correct state identified after restart mid-trade via journal-plus-exchange reconciliation.
*   **Kill criteria:** State machine permits two concurrent opposite signals on the same asset.

### Task 2.3 — Filter Layer (new): trade quality over trade frequency
*   **Spread filter:** Skip entries when the spread exceeds a set bps threshold — a wide spread means a thin book, and a passive fill into a thin book is toxic.
*   **Funding filter:** Skip or reduce size when the funding rate is extreme against the trade direction; extreme funding on a squeeze candidate is a warning, not an opportunity.
*   **Correlation cap:** Maximum 1–2 concurrent positions across the entire basket. Five simultaneous longs on correlated alts is one 5x-sized trade.
*   **Circuit breakers (three-layer discipline, encoded):** Daily loss limit (e.g., −6% equity → flat and halt until next UTC day), max consecutive-loss halt, and a volatility halt when realized vol exceeds the backtested regime — the signal was not validated for that environment.

## 6. Phase 3 — Execution and Risk Module

### Task 3.1 — Maker Order Routing and Bounded Chasing
*   **Deliverable:** Post-only limit order (timeInForce GTX) at the current best bid/ask on signal fire, so a crossed order is rejected rather than silently becoming a taker fill. If unfilled within 3 seconds, cancel and replace at the new best bid/ask, maximum 3 retries. Additional bound: abort the chase entirely if price has moved more than X ticks from the signal price — chasing a runaway move converts a mean-reversion entry into an unvalidated momentum entry.
*   **Validation:** No taker fills ever occur; cancel/replace cycle respects API rate limits with backoff; chase abort triggers correctly on fast moves.
*   **Kill criteria:** A market order fires, or an unbounded cancel/replace loop hits rate limits.

### Task 3.2 — Automated Stop and Bracket Management
*   **Deliverable:** On entry fill, immediately place `STOP_MARKET` with `closePosition: true` (survives partial fills). The opposing take-profit structure — fixed bracket or reversion-to-mean exit — is whichever Phase 0 validated. Binance futures has no native OCO: a supervisor loop cancels the surviving bracket leg when the other fills, and that cancel is itself journaled and retried. Leverage locked at the Phase 0 validated level (10x ceiling).
*   **Validation:** Testnet entries show the stop on the exchange within 500ms of fill; bracket-leg cancellation verified under partial-fill scenarios.
*   **Kill criteria:** Stop-loss not on the exchange within 500ms of entry fill. If this occurs, the architecture is fundamentally unsafe for leverage — full stop and redesign.

## 7. Phase 4 — Shadow-Live Validation (new)

Testnet validates code paths, not edge: its order book is fantasy liquidity. This phase runs the complete system against live market data with real order logic but a paper ledger, applying the same hostile fill rules as the Phase 0 backtest.

*   **Deliverable:** 200+ shadow trades executed against live data with the hostile fill model (trade-through fills only, full fees, funding, slippage haircut).
*   **Validation:** Shadow expectancy falls inside the Phase 0 Monte Carlo confidence band; live signal frequency and fill rates match backtest assumptions.
*   **Kill criteria:** Signal frequency or fill rates diverge materially from the backtest — the fill model was optimistic and live capital would bleed. Return to Phase 0 with the live data.

## 8. Phase 5 — Live Burn-in

*   **Deliverable:** Live API keys, isolated futures wallet funded with exactly €200. Position sizing: €20 margin per trade controlling €200 notional at 10x. Minimum 100 live trades executed autonomously; no intervention except for critical software bugs.
*   **Validation:** Realized performance evaluated against the Phase 0 Monte Carlo bands — not a raw win-rate eyeball. Realized stop-exit slippage compared against the modeled haircut.
*   **Kill criteria:** Equity breaches the P95 backtested drawdown (empirical threshold, not an arbitrary −50%), or realized slippage on stop exits exceeds 2x the modeled haircut, or the sizing algorithm ever attempts to deploy full equity as margin on a single trade. Any breach: kill the bot, extract logs, return to Phase 0.

## 9. Gate Summary

| Gate | Passes when | Fails to |
| :--- | :--- | :--- |
| **Phase 0** | Positive expectancy after hostile costs, out-of-sample, across ≥2 regimes; drawdown distribution acceptable | Full stop — iterate signal, no build |
| **Phase 1** | 24h stable ingestion; `kill -9` recovery correct; Tokyo VPS RTT verified | Fix infrastructure before signal work |
| **Phase 2** | State machine sound; filters active; parameters match validated config | No execution module work |
| **Phase 3** | Stop on exchange <500ms; zero taker fills; bounded chase | Redesign — unsafe for leverage |
| **Phase 4** | 200+ shadow trades inside Monte Carlo band | Return to Phase 0 with live data |
| **Phase 5** | 100+ live trades inside empirical bands; slippage ≤2x model | Kill bot, extract logs, Phase 0 |
