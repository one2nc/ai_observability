"""
05_load_balance.py
------------------
Weighted load balancing across two models through the local gateway.

What this shows:
  - 80% of requests go to gpt-4o-mini (cheaper, faster)
  - 20% of requests go to gpt-4o   (higher quality, costlier)
  - Distribution is probabilistic, visible in gateway logs
  - Zero application code changes when weights are adjusted

Cost rationale:
  gpt-4o-mini → ~$0.15 / 1M input tokens
  gpt-4o      → ~$2.50 / 1M input tokens
  80/20 mix   → ~65% cost reduction vs all-gpt-4o

Run:
    python 05_load_balance.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from common import (
    get_client, load_balance_config, divider, get_text,
    PRIMARY_MODEL, FALLBACK_MODEL, make_config, _target,
)


def run():
    divider("05 — Weighted Load Balancing (20% gpt-4 / 80% gpt-4.1)")

    config = load_balance_config([
        (80, PRIMARY_MODEL),   # gpt-4.1 — lighter, cheaper  (80%)
        (20, FALLBACK_MODEL),  # gpt-4   — heavier, costlier (20%)
    ])

    client = get_client(config=config)
    total = 10
    success = 0

    print(f"  Config  : 80% {PRIMARY_MODEL}  /  20% {FALLBACK_MODEL}")
    print(f"  Sending : {total} requests\n")
    print(f"  {'#':<5} {'Status':<8} {'Preview (60 chars)'}")
    print(f"  {'─' * 80}")

    for i in range(1, total + 1):
        try:
            resp = client.chat.completions.create(
                model=PRIMARY_MODEL,
                messages=[{"role": "user", "content": f"Query {i}: What is load balancing? One sentence."}],
                max_tokens=80,
            )
            text = get_text(resp).strip()
            print(f"  {i:<5} ✅ PASS   {text[:60]}")
            success += 1
        except Exception as exc:
            print(f"  {i:<5} ❌ FAIL   {str(exc)[:60]}")

    print(f"\n  Result: {success}/{total} requests succeeded")
    print(f"  📊  Check gateway logs to see actual model distribution:")
    print(f"      docker compose logs portkey | grep -i 'model'")


if __name__ == "__main__":
    run()
