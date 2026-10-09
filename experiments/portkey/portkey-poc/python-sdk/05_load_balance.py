"""
05_load_balance.py
------------------
Weighted load balancing — traffic split across two models by weight.

What this shows:
  - 8 requests distributed 20% gpt-4 / 80% gpt-4.1 via a config JSON change
  - No application code redeploy needed — policy lives entirely in the config
  - Dashboard Analytics → Requests by Model confirms the split

Dashboard proof:
  app.portkey.ai/analytics → Requests by Model →
    @test/gpt-4.1  ~80%
    @test/gpt-4    ~20%
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from common import get_client, get_text, make_config, PRIMARY_MODEL, FALLBACK_MODEL


def run():
    config = make_config({
        "strategy": {"mode": "loadbalance"},
        "targets": [
            {"weight": 20, "override_params": {"model": FALLBACK_MODEL}},   # gpt-4   20%
            {"weight": 80, "override_params": {"model": PRIMARY_MODEL}},    # gpt-4.1 80%
        ],
    })
    client = get_client(config)

    total   = 8
    success = 0

    print(f"  Route  : Python SDK → api.portkey.ai → loadbalance")
    print(f"  Split  : 20% {FALLBACK_MODEL}  /  80% {PRIMARY_MODEL}")
    print(f"  Firing : {total} requests\n")
    print(f"  {'#':<5} {'Status':<8} Preview")
    print(f"  {'─' * 70}")

    for i in range(1, total + 1):
        try:
            resp = client.chat.completions.create(
                model=PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user",   "content": f"Request {i}: What is load balancing? One sentence."},
                ],
                max_tokens=50,
            )
            text = get_text(resp).strip()
            print(f"  {i:<5} ✅ PASS   {text[:60]}")
            success += 1
        except Exception as exc:
            print(f"  {i:<5} ❌ FAIL   {str(exc)[:60]}")

    print(f"\n  Result : {success}/{total} succeeded")
    print(f"\n  ✅  Config-only change — no code redeploy needed")
    print(f"  📊  Dashboard → Analytics → Requests by Model → confirms 20/80 split")


if __name__ == "__main__":
    run()
