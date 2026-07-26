"""scalpbot — gate-driven mean-reversion scalping system for Hyperliquid perps.

See PLAN.md at the repo root. Architecture invariant: `scalpbot.core` is pure and
deterministic; backtest, shadow, and live are drivers around it.
"""

__version__ = "0.1.0"
