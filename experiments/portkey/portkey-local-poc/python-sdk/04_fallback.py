"""
04_fallback.py
--------------
Multi-provider fallback routing through the local gateway.

What this shows:
  - Primary target intentionally misconfigured → returns 4xx error
  - Gateway automatically retries on the fallback target
  - Client receives a 200 from the fallback with zero code changes
  - Both the failed attempt and the successful fallback appear in gateway logs

Request flow:
  Client → Portkey Gateway → OpenAI (FAIL) → Anthropic (SUCCESS) → Client

Run:
    python 04_fallback.py
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(__file__))

from common import (
    get_client, make_config, _target, divider, get_text,
    PRIMARY_MODEL, FALLBACK_MODEL,
)


def run():
    divider("04 — Multi-Provider Fallback")

    config = make_config({
        "strategy": {"mode": "fallback"},
        "targets": [
            _target("@test/invalid-trigger-fallback"),  # intentionally broken → 4xx
            _target(FALLBACK_MODEL),                    # real working fallback
        ],
    })

    client = get_client(config=config)

    print(f"  Primary  : @test/invalid-trigger-fallback  ← will FAIL (4xx)")
    print(f"  Fallback : {FALLBACK_MODEL}  ← will SUCCEED")
    print(f"  Prompt   : Explain what fallback routing means.\n")

    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": "Explain what fallback routing means in 2 sentences."},
            ],
            max_tokens=256,
        )
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  Response : {get_text(response).strip()}\n")
        print(f"  Latency  : {elapsed:.0f} ms  (includes failed primary attempt)")
        print(f"\n  ✅  Fallback worked!")
        print(f"  📋  Check logs: docker compose logs portkey | grep -E 'FAIL|SUCCESS|fallback'")
    except Exception as exc:
        print(f"  ❌  All fallback targets exhausted: {exc}")


if __name__ == "__main__":
    run()
