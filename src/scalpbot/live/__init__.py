"""Live/shadow runtime: asyncio engine, durable journal, reconciliation,
bounded chase with rate budgeting, deadman watchdog, killswitch.

Everything here is a driver around scalpbot.core — no strategy logic lives in
this package."""
