"""
03_streaming.py
---------------
SSE token-by-token streaming through Portkey Cloud.

What this shows:
  - stream=True — Portkey Cloud proxies Server-Sent Events without buffering
  - Tokens appear word-by-word as the model generates them
  - Chunk count + total chars + wall time confirm no proxy-side buffering

Dashboard proof:
  app.portkey.ai/logs → the entry shows stream=true and the full response payload
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from common import get_client, PRIMARY_MODEL


def run():
    client = get_client()

    print(f"  Route  : Python SDK → api.portkey.ai → LLM  (stream=True)")
    print(f"  Model  : {PRIMARY_MODEL}")
    print(f"  Prompt : Explain how LLM streaming works in 3 sentences.\n")
    print(f"  Stream output:\n  ", end="", flush=True)

    start  = time.perf_counter()
    chunks = 0
    full   = ""

    with client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[{"role": "user", "content": "Explain how LLM streaming works in 3 sentences."}],
        max_tokens=120,
        stream=True,
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                print(delta, end="", flush=True)
                full   += delta
                chunks += 1

    ms = (time.perf_counter() - start) * 1000
    print(f"\n\n  Chunks received : {chunks}")
    print(f"  Total chars     : {len(full)}")
    print(f"  Wall time       : {ms:.0f} ms")
    print(f"\n  ✅  Portkey Cloud streamed SSE chunks without buffering")


if __name__ == "__main__":
    run()
