"""
02_chat_completion.py
---------------------
Multi-turn conversation through the local Portkey gateway.

What this shows:
  - Multi-turn message history (system + user + assistant + user)
  - Gateway logs the full message array with token counts
  - Temperature and max_tokens control response style

Run:
    python 02_chat_completion.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from common import get_client, single_target_config, divider, get_text, PRIMARY_MODEL, PRIMARY_PROVIDER

def run():
    divider("02 — Multi-Turn Chat Completion")

    config = single_target_config()
    client = get_client(config=config)

    conversation = [
        {"role": "system", "content": "You are a concise technical assistant. Keep answers to 2 sentences."},
        {"role": "user",   "content": "What is Kubernetes?"},
    ]

    print(f"  Provider: {PRIMARY_PROVIDER}  |  Model: {PRIMARY_MODEL}\n")

    # ── Turn 1 ────────────────────────────────────────────────────────────────
    print("  Turn 1 → What is Kubernetes?")
    r1 = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=conversation,
        max_tokens=128,
        temperature=0.3,
    )
    reply1 = get_text(r1).strip()
    print(f"  Assistant: {reply1}\n")
    conversation.append({"role": "assistant", "content": reply1})

    # ── Turn 2 ────────────────────────────────────────────────────────────────
    conversation.append({"role": "user", "content": "How does it relate to Docker?"})
    print("  Turn 2 → How does it relate to Docker?")
    r2 = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=conversation,
        max_tokens=128,
        temperature=0.3,
    )
    reply2 = get_text(r2).strip()
    print(f"  Assistant: {reply2}\n")

    # ── Turn 3 ────────────────────────────────────────────────────────────────
    conversation.append({"role": "assistant", "content": reply2})
    conversation.append({"role": "user", "content": "What is a Pod in Kubernetes?"})
    print("  Turn 3 → What is a Pod in Kubernetes?")
    r3 = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=conversation,
        max_tokens=128,
        temperature=0.3,
    )
    print(f"  Assistant: {get_text(r3).strip()}\n")

    usage = getattr(r3, "usage", None)
    if usage:
        print(f"  Final turn tokens: {usage.total_tokens}")
    print("\n  ✅  Gateway logged all 3 turns — run: docker compose logs portkey")


if __name__ == "__main__":
    run()
