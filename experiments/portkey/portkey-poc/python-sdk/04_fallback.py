"""
04_fallback.py
--------------
Automatic fallback routing — primary target fails, secondary target recovers.

What this shows:
  - Primary model is intentionally invalid → returns 4xx
  - Portkey Cloud detects the failure and retries the next target automatically
  - Client receives a 200 — zero application code change required
  - Both attempts appear under the same trace_id in the dashboard

Dashboard proof:
  app.portkey.ai/logs → expand trace →
    target[0] : @test/invalid-trigger-fallback  status=4xx  FAILED
    target[1] : @test/gpt-4                     status=200  SUCCESS
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from common import get_client, get_text, make_config, PRIMARY_MODEL, FALLBACK_MODEL


def run():
    config = make_config({
        "strategy": {"mode": "fallback"},
        "targets": [
            {"override_params": {"model": "@test/invalid-trigger-fallback"}},  # fails 4xx
            {"override_params": {"model": FALLBACK_MODEL}},                    # succeeds
        ],
    })
    client = get_client(config)

    print(f"  Route    : Python SDK → api.portkey.ai → fallback chain")
    print(f"  Primary  : @test/invalid-trigger-fallback  → FAIL (4xx)")
    print(f"  Fallback : {FALLBACK_MODEL}                → SUCCESS\n")

    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": "Explain what fallback routing means in 2 sentences."},
            ],
            max_tokens=100,
        )
        ms = (time.perf_counter() - start) * 1000
        print(f"  Response : {get_text(resp).strip()}\n")
        print(f"  Latency  : {ms:.0f} ms  (includes failed primary attempt)")
        print(f"\n  ✅  Fallback worked — client received 200 despite primary failure")
        print(f"  📋  Dashboard → Logs → expand trace:")
        print(f"        target[0]: FAILED  (4xx)")
        print(f"        target[1]: SUCCESS (200)  ← same trace_id")
    except Exception as exc:
        print(f"  ❌  All targets failed: {exc}")


if __name__ == "__main__":
    run()
