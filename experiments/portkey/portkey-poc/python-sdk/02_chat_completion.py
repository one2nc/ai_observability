"""
02_chat_completion.py
---------------------
Multi-turn conversation routed through Portkey Cloud.

What this shows:
  - Full message history (system + user + assistant) is preserved across 3 turns
  - Portkey Cloud logs each turn as a separate trace entry
  - Context is maintained entirely in the client — gateway is stateless

Dashboard proof:
  app.portkey.ai/logs → 3 entries with the same trace_id (if metadata tracing is on)
  Each entry shows the cumulative prompt token count growing as history grows.
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
    print(f"  Turns  : 3  (full message history passed each time)\n")

    conversation = [
        {"role": "system", "content": "You are a concise technical assistant. Max 2 sentences per reply."},
    ]

    user_messages = [
        "What is Docker?",
        "How does it differ from a VM?",
        "What is Docker Compose?",
    ]

    for i, user_msg in enumerate(user_messages, 1):
        conversation.append({"role": "user", "content": user_msg})
        print(f"  Turn {i} → {user_msg}")

        start = time.perf_counter()
        resp = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=conversation,
            max_tokens=80,
        )
        ms = (time.perf_counter() - start) * 1000

        reply = get_text(resp).strip()
        print(f"  Bot   → {reply}")

        usage = getattr(resp, "usage", None)
        if usage:
            print(f"  Tokens: prompt={usage.prompt_tokens}  completion={usage.completion_tokens}  ({ms:.0f} ms)\n")
        else:
            print(f"  Latency: {ms:.0f} ms\n")

        conversation.append({"role": "assistant", "content": reply})

    print(f"  ✅  All 3 turns routed through Portkey Cloud with full history preserved")


if __name__ == "__main__":
    run()
