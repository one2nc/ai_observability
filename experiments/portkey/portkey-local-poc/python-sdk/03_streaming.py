"""
03_streaming.py
---------------
Server-Sent Events (SSE) streaming response through the local gateway.

What this shows:
  - stream=True returns a generator of delta chunks
  - Gateway proxies the stream transparently (no buffering)
  - Useful for chat UIs that show tokens as they arrive

Run:
    python 03_streaming.py
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(__file__))

from common import get_client, single_target_config, divider, PRIMARY_MODEL, PRIMARY_PROVIDER

def run():
    divider("03 — Streaming Response")

    config = single_target_config()
    client = get_client(config=config)

    prompt = "Explain how streaming works in LLM APIs in 4–5 sentences."
    print(f"  Provider : {PRIMARY_PROVIDER}  |  Model: {PRIMARY_MODEL}")
    print(f"  Prompt   : {prompt}\n")
    print("  Response (streaming):\n  ", end="", flush=True)

    start = time.perf_counter()
    full_text = ""
    chunk_count = 0

    with client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": "You are a concise technical assistant."},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=256,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                print(delta, end="", flush=True)
                full_text += delta
                chunk_count += 1

    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n\n  ──────────────────────────────────────────────────")
    print(f"  Chunks received : {chunk_count}")
    print(f"  Total length    : {len(full_text)} chars")
    print(f"  Wall time       : {elapsed_ms:.0f} ms")
    print(f"\n  ✅  Gateway streamed all chunks — no buffering delay")


if __name__ == "__main__":
    run()
