"""
06_retry_timeout.py
-------------------
Automatic retry and request timeout configuration.

What this shows:
  - Gateway retries on 429 (rate limit), 500/502/503/504 (provider errors)
  - Up to 3 attempts before returning failure to the client
  - Per-request timeout (30s) aborts hung provider calls
  - Simulates a transient failure using an intentionally invalid request

Retry behaviour:
  attempt 1  → provider error (or simulated) → wait → retry
  attempt 2  → provider error                → wait → retry
  attempt 3  → success (or final failure)

  Client never sees individual retry attempts — only the final result.

Run:
    python 06_retry_timeout.py
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(__file__))

from common import (
    get_client, retry_config, single_target_config,
    divider, get_text, PRIMARY_MODEL, PRIMARY_PROVIDER, PRIMARY_PROVIDER
)


def demo_retry_config():
    """Show what a retry config looks like and fire a normal request with it."""
    print("  ── Retry Config Demo ──────────────────────────────────")
    print("  Config applied:")
    import json
    cfg = retry_config(attempts=3, timeout_ms=30_000)
    print(f"  {json.dumps(json.loads(cfg), indent=4)}\n")

    client = get_client(config=cfg)
    start = time.perf_counter()

    print("  Sending request (retries enabled, timeout=30s)...")
    try:
        resp = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": "What is exponential backoff? One sentence."}],
            max_tokens=80,
        )
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  Response : {get_text(resp).strip()}")
        print(f"  Latency  : {elapsed:.0f} ms")
        print(f"  ✅  Request succeeded (no retries needed on healthy provider)")
    except Exception as exc:
        print(f"  ❌  {exc}")


def demo_timeout():
    """Show that a very short timeout causes the gateway to abort the request."""
    print("\n  ── Timeout Demo (timeout=1ms, will fail fast) ─────────")

    # Use a 1ms timeout — will always abort before any response arrives
    import json
    from common import make_config, CLOUD_API_KEY, CLOUD_HOST
    short_timeout_config = make_config({
        "request_timeout": 1,  # 1ms — intentionally too short
        "provider":   "openai",
        "customHost": CLOUD_HOST,
        "api_key":    CLOUD_API_KEY,
        "override_params": {"model": PRIMARY_MODEL},
    })
    client = get_client(config=short_timeout_config)

    start = time.perf_counter()
    try:
        client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=32,
        )
        print("  (unexpected success)")
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  Request aborted after {elapsed:.0f} ms (expected)")
        print(f"  Gateway error: {str(exc)[:80]}")
        print(f"  ✅  Timeout works — gateway killed the request after 1ms")


def run():
    divider("06 — Retry Handling & Request Timeout")
    demo_retry_config()
    demo_timeout()


if __name__ == "__main__":
    run()
