"""Keyless connectivity smoke test: pulls perp metadata from the Hyperliquid
testnet public info endpoint. Proves network path + API contract before any
wallet exists.

    uv run python scripts/smoke_hl.py [--mainnet]
"""

from __future__ import annotations

import sys
import time

import httpx

TESTNET = "https://api.hyperliquid-testnet.xyz/info"
MAINNET = "https://api.hyperliquid.xyz/info"


def main() -> int:
    url = MAINNET if "--mainnet" in sys.argv else TESTNET
    t0 = time.perf_counter()
    resp = httpx.post(url, json={"type": "meta"}, timeout=10.0)
    rtt_ms = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    universe = resp.json()["universe"]
    names = [a["name"] for a in universe]
    print(f"OK {url}")
    print(f"RTT (incl. TLS setup): {rtt_ms:.0f} ms")
    print(f"perp universe: {len(names)} assets; sample: {', '.join(names[:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
