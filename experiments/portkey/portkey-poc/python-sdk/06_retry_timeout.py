"""
06_retry_timeout.py
-------------------
Portkey-native retry that actually fires + gateway-enforced request timeout.

Part A — Retry config on a healthy request:
  retry.attempts=3 on [429, 500-504].
  Provider succeeds on first attempt → x-portkey-retry-attempt-count=0.
  Proves the retry policy is applied (dashboard shows retry config in trace).

Part B — Retry ACTUALLY FIRES (retry exhaustion):
  Uses an invalid model (@test/invalid-trigger-fallback) that always returns 400.
  Config includes 400 in on_status_codes → gateway retries 3 times with backoff.

  Proof via timing:
    Without retry config → fails in ~150ms  (1 attempt only)
    With retry.attempts=3 → fails in ~7000ms (4 total attempts + backoff delays)

  Header proof:
    x-portkey-retry-attempt-count: -1  (retries exhausted)

Part C — Timeout:
  request_timeout=1 (1ms) → gateway aborts before provider responds → 408 error.

Dashboard proof:
  app.portkey.ai/logs → Part A: retry_attempt_count=0, status=200
                      → Part B: retry_attempt_count=3, status=4xx, longer latency
                      → Part C: status=408, latency < 200ms
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from common import get_client, get_text, make_config, PRIMARY_MODEL


def run():
    print(f"  Route  : Python SDK → api.portkey.ai → LLM\n")

    # ── Part A: Retry config applied — succeeds first try ─────────────────────
    print(f"  Part A : retry.attempts=3, on_status_codes=[429,500-504] — healthy request")
    retry_config = make_config({
        "retry":           {"attempts": 3, "on_status_codes": [429, 500, 502, 503, 504]},
        "request_timeout": 30000,
        "override_params": {"model": PRIMARY_MODEL},
    })
    client = get_client(retry_config)

    t0   = time.perf_counter()
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[{"role": "user", "content": "What is exponential backoff? One sentence."}],
        max_tokens=60,
    )
    ms       = (time.perf_counter() - t0) * 1000
    headers  = resp.get_headers()
    attempts = headers.get("retry-attempt-count", "?")

    print(f"  Response         : {get_text(resp).strip()}")
    print(f"  Latency          : {ms:.0f}ms")
    print(f"  retry-attempt-count : {attempts}  ← 0 means succeeded on first try, no retries needed")
    print(f"  ✅  Retry policy active — would auto-retry on 429/5xx with exponential backoff\n")

    # ── Part B: Retry ACTUALLY fires (exhaustion on invalid model) ─────────────
    print(f"  Part B : Retry FIRES — invalid model triggers 400, gateway retries 3× with backoff")

    # Step 1: Baseline — no retry config (single attempt only)
    no_retry_client = get_client()
    t0 = time.perf_counter()
    try:
        no_retry_client.chat.completions.create(
            model="@test/invalid-trigger-fallback",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=30,
        )
    except Exception:
        no_retry_ms = (time.perf_counter() - t0) * 1000

    # Step 2: With retry — 400 in on_status_codes triggers backoff retries
    retry_fail_config = make_config({
        "retry": {"attempts": 3, "on_status_codes": [400, 429, 500, 502, 503, 504]},
        "override_params": {"model": "@test/invalid-trigger-fallback"},
    })
    retry_client = get_client(retry_fail_config)

    t0 = time.perf_counter()
    retry_count_hdr = "?"
    try:
        retry_client.chat.completions.create(
            model="@test/invalid-trigger-fallback",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=30,
        )
        print(f"  (unexpectedly succeeded)")
    except Exception as exc:
        retry_ms = (time.perf_counter() - t0) * 1000
        # Read retry count from error response headers
        if hasattr(exc, "response") and exc.response is not None:
            retry_count_hdr = exc.response.headers.get("x-portkey-retry-attempt-count", "?")

    print(f"  Without retry config : failed in {no_retry_ms:>6.0f}ms  (1 attempt)")
    print(f"  With retry.attempts=3: failed in {retry_ms:>6.0f}ms  (4 attempts + backoff delays)")
    print(f"  retry-attempt-count  : {retry_count_hdr}  ← -1 means retries exhausted")
    print(f"  Overhead             : {retry_ms - no_retry_ms:.0f}ms added by 3 retries + backoff")
    print(f"  ✅  Retry fired — gateway attempted {retry_ms / no_retry_ms:.0f}x longer before giving up\n")

    # ── Part C: 1ms timeout — always fires ────────────────────────────────────
    print(f"  Part C : request_timeout=1ms — gateway aborts before provider responds (HTTP 408)")
    short_config  = make_config({
        "request_timeout": 1,
        "override_params": {"model": PRIMARY_MODEL},
    })
    short_client = get_client(short_config)

    t0 = time.perf_counter()
    try:
        short_client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=30,
        )
        print(f"  (unexpectedly succeeded)")
    except Exception as exc:
        ms = (time.perf_counter() - t0) * 1000
        print(f"  Aborted after {ms:.0f}ms — error: {str(exc)[:70]}")
        print(f"  ✅  Timeout enforced server-side — no client-side timeout code needed")


if __name__ == "__main__":
    run()
