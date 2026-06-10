"""
01_basic_completion.py
----------------------
Simplest possible request through the local Portkey gateway.

What this shows:
  - SDK pointed at http://localhost:8787/v1 instead of api.openai.com
  - Gateway logs the request and forwards it to OpenAI
  - Response is identical to a direct OpenAI call

Run:
    python 01_basic_completion.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from common import get_client, single_target_config, divider, get_text, PRIMARY_MODEL, PRIMARY_PROVIDER, GATEWAY_URL

def run():
    divider("01 — Basic Completion via Local Gateway")

    print(f"  Gateway : {GATEWAY_URL}")
    print(f"  Provider: {PRIMARY_PROVIDER}")
    print(f"  Model   : {PRIMARY_MODEL}\n")

    # Build a single-target config (embeds the provider API key)
    config = single_target_config()
    client = get_client(config=config)

    prompt = "What is an AI Gateway? Answer in exactly two sentences."
    print(f"  Prompt  : {prompt}\n")

    response = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": "You are a concise technical assistant."},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=256,
    )

    print(f"  Response:\n  {get_text(response).strip()}\n")

    usage = getattr(response, "usage", None)
    if usage:
        print(f"  Tokens used  : {usage.total_tokens} (prompt={usage.prompt_tokens}, completion={usage.completion_tokens})")
    print(f"  Model reported: {getattr(response, 'model', 'n/a')}")
    print("\n  ✅  Check gateway logs: docker compose logs -f portkey")


if __name__ == "__main__":
    run()
