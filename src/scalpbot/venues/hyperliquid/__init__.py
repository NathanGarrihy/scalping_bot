"""Hyperliquid adapter (testnet + mainnet).

Venue facts baked into this implementation (verify on API-review cadence, PLAN.md §11):
- ALO time-in-force gives post-only semantics.
- Native TP/SL order grouping is position-tied — no OCO supervisor needed.
- Funding accrues hourly.
- Auth via agent wallet (trade-only by construction) on a dedicated subaccount.
- Rate limits: per-IP aggregate weight 1200/min AND address-based budget
  (1 request per 1 USDC traded, 10k initial buffer). June 2026 API change:
  2s l2Book cadence requires `fast: true` (default stepped back to 5s).
"""
