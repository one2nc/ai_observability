"""Test Bifrost routing using same client pattern as rag.py.

Requires env vars: EMBED_API_KEY, EMBED_BASE_URL, EMBED_MODEL, CHAT_API_KEY, CHAT_BASE_URL, CHAT_MODEL
"""

import os
import openai


def _embed_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=os.environ["EMBED_API_KEY"],
        base_url=os.environ["EMBED_BASE_URL"],
    )


def _chat_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=os.environ["CHAT_API_KEY"],
        base_url=os.environ["CHAT_BASE_URL"],
    )


# 1. Chat through Bifrost
print(f"1. Chat via {os.environ['CHAT_BASE_URL']} model={os.environ['CHAT_MODEL']}")
try:
    client = _chat_client()
    r = client.chat.completions.create(
        model=os.environ["CHAT_MODEL"],
        messages=[{"role": "user", "content": "Say hi in one word."}],
    )
    print(f"   PASS: {r.choices[0].message.content} (tokens={r.usage.total_tokens})")
except Exception as e:
    print(f"   FAIL: {e}")

print()

# 2. Embeddings via EMBED_BASE_URL (should be direct OpenRouter)
print(f"2. Embed via {os.environ['EMBED_BASE_URL']} model={os.environ['EMBED_MODEL']}")
try:
    client = _embed_client()
    r = client.embeddings.create(model=os.environ["EMBED_MODEL"], input=["hello"])
    print(f"   PASS: dims={len(r.data[0].embedding)}")
except Exception as e:
    print(f"   FAIL: {e}")

print()

# 3. Embeddings via Bifrost (expected to fail)
print(f"3. Embed via {os.environ['CHAT_BASE_URL']} model=openrouter/text-embedding-3-small (expected FAIL)")
try:
    client = openai.OpenAI(
        api_key=os.environ["CHAT_API_KEY"],
        base_url=os.environ["CHAT_BASE_URL"],
    )
    r = client.embeddings.create(model="openrouter/text-embedding-3-small", input=["hello"])
    print(f"   UNEXPECTED PASS: dims={len(r.data[0].embedding)}")
except Exception as e:
    print(f"   FAIL (expected): {e}")
