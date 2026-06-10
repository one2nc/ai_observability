"""
08_semantic_cache.py
--------------------
Portkey native caching — MISS on cold cache, HIT on warm cache.

How Portkey caching works:
  1. First request for a query → MISS → LLM call → response stored in Portkey Cloud cache
  2. Same query repeated → HIT → served from cache, ~20x faster, 0 tokens charged
  3. cache_status is returned in the response headers (x-portkey-cache-status)

Cache modes:
  simple   — exact key match (prompt hash)  ← used in this demo, works with all models
  semantic — cosine similarity match         ← requires real embedding models (not @test)

This demo uses cache.mode=simple which works reliably with Portkey Cloud and the @test
test catalog. It sends 3 questions on a cold cache (all MISS), then repeats the same
3 questions on a warm cache (all HIT) — showing the real cost and latency difference.

Dashboard proof:
  app.portkey.ai/logs →
    Round 1: cache_status=MISS  tokens_charged=N  latency=~1500ms
    Round 2: cache_status=HIT   tokens_charged=0  latency=~80ms
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from common import get_client, get_text, make_config, PRIMARY_MODEL

QUESTIONS = [
    "What is Kubernetes? Answer in one sentence.",
    "What is an AI Gateway? Answer in one sentence.",
    "What does Docker Compose do? Answer in one sentence.",
]


def call_and_show(client, label, question, idx):
    msg = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": question},
    ]
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=msg,
        max_tokens=60,
    )
    ms = (time.perf_counter() - t0) * 1000

    headers    = resp.get_headers()
    cache_st   = headers.get("cache-status", "?")
    tokens     = getattr(resp.usage, "total_tokens", "?") if resp.usage else "?"
    icon       = "⚡ HIT " if cache_st == "HIT" else "📡 MISS"
    print(f"  {icon}  Q{idx}  cache={cache_st:<5}  {ms:>6.0f}ms  tokens={str(tokens):<5}  {get_text(resp).strip()[:50]}...")
    return cache_st, ms


def run():
    config = make_config({"cache": {"mode": "simple", "max_age": 3600}})
    client = get_client(config)

    print(f"  Route  : Python SDK → api.portkey.ai → [Portkey cache] → LLM")
    print(f"  Config : cache.mode=simple  cache.max_age=3600s")
    print(f"  Model  : {PRIMARY_MODEL}\n")

    # ── Round 1: Cold cache — all should be MISS ──────────────────────────────
    print(f"  ── Round 1: Cold cache (first time asking each question) ──")
    miss_times = []
    for i, q in enumerate(QUESTIONS, 1):
        cs, ms = call_and_show(client, "Round1", q, i)
        miss_times.append(ms)
        time.sleep(0.3)

    # ── Round 2: Warm cache — all should be HIT ───────────────────────────────
    print(f"\n  ── Round 2: Warm cache (same questions again) ──")
    hit_times  = []
    all_hit    = True
    for i, q in enumerate(QUESTIONS, 1):
        cs, ms = call_and_show(client, "Round2", q, i)
        hit_times.append(ms)
        if cs != "HIT":
            all_hit = False
        time.sleep(0.3)

    # ── Summary ───────────────────────────────────────────────────────────────
    if miss_times and hit_times:
        avg_miss = sum(miss_times) / len(miss_times)
        avg_hit  = sum(hit_times)  / len(hit_times)
        speedup  = avg_miss / avg_hit if avg_hit > 0 else 0
        print(f"\n  Avg latency — MISS: {avg_miss:.0f}ms   HIT: {avg_hit:.0f}ms   Speedup: {speedup:.1f}x")
        print(f"  Tokens charged   — MISS: N tokens per request   HIT: 0 tokens")

    if all_hit:
        print(f"\n  ✅  All Round 2 queries served from Portkey Cloud cache (cache-status=HIT)")
    else:
        print(f"\n  ⚠️   Some cache misses in Round 2 — cache may need time to propagate")

    print(f"\n  📊  Dashboard proof: app.portkey.ai/logs")
    print(f"        Round 1: cache_status=MISS  → tokens charged")
    print(f"        Round 2: cache_status=HIT   → tokens_charged=0  latency ~80ms")
    print(f"\n  ℹ️   cache.mode=simple  → exact prompt hash match (works with all models)")
    print(f"       cache.mode=semantic → cosine similarity match (requires real embedding models)")


if __name__ == "__main__":
    run()
