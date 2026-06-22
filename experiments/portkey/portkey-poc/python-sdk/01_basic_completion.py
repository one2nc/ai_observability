"""
01_basic_completion.py
----------------------
Simplest Portkey Cloud request — single model, no routing config.

What this shows:
  - SDK points directly at api.portkey.ai using just the Portkey API key
  - No provider key or base_url needed — Portkey Cloud handles auth and routing
  - Token usage and latency are logged automatically in the Portkey dashboard

Dashboard proof:
  app.portkey.ai/logs → latest entry shows model, tokens, latency, prompt, response
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from common import get_client, get_text, PRIMARY_MODEL


def run():
    client = get_client()

    print(f"  Route  : Python SDK → api.portkey.ai → LLM")
    print(f"  Model  : {PRIMARY_MODEL}")
    print(f"  Prompt : What is an AI Gateway? Two sentences only.\n")

    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": "You are a concise technical assistant."},
            {"role": "user",   "content": "What is an AI Gateway? Two sentences only."},
        ],
        max_tokens=100,
    )
    ms = (time.perf_counter() - start) * 1000

    print(f"  Response:\n  {get_text(resp).strip()}\n")
    usage = getattr(resp, "usage", None)
    if usage:
        print(f"  Tokens : prompt={usage.prompt_tokens}  completion={usage.completion_tokens}  total={usage.total_tokens}")
    print(f"  Latency: {ms:.0f} ms")
    print(f"\n  ✅  Request logged → app.portkey.ai/logs")


if __name__ == "__main__":
    run()
