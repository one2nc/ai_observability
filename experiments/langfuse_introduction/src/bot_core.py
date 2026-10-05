"""
bot_core.py — shared building blocks for every stage.

Two goals:
  1. Load Langfuse credentials from .env (so you set them in ONE place).
  2. Provide a `chat_llm()` that works with NO API key (deterministic mock),
     and automatically upgrades to a real OpenAI call if OPENAI_API_KEY is set.

This means every stage in the tour is runnable immediately after you start
your local Langfuse instance — no model account required.
"""

import os
import time
import hashlib

from dotenv import load_dotenv

# Load .env BEFORE importing langfuse anywhere downstream.
load_dotenv()

# Silence the harmless LibreSSL warning on macOS system Python.
os.environ.setdefault("PYTHONWARNINGS", "ignore")

# ── Decide whether we have a real LLM available ──────────────────────────
USE_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
BASEURL = os.getenv("OPENAI_BASE_URL")

SYSTEM_PROMPT_FALLBACK = (
    "You are a concise, friendly support assistant for a company called Acme. "
    "Answer in 1-3 sentences."
)


def _mock_reply(messages):
    """
    A deterministic fake LLM. Same input -> same output, so traces are
    reproducible and you can demo evaluation without burning tokens.
    """
    user_text = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_text = m["content"]
            break

    lowered = user_text.lower()
    if "refund" in lowered:
        reply = "You can request a refund within 30 days from your Orders page. Need the link?"
    elif "hours" in lowered or "open" in lowered:
        reply = "Acme support is open Monday to Friday, 9am to 6pm your local time."
    elif "reset" in lowered and "password" in lowered:
        reply = "To reset your password, click 'Forgot password' on the login screen and follow the email."
    elif "hello" in lowered or "hi" in lowered:
        reply = "Hi! I'm the Acme assistant. How can I help you today?"
    else:
        # Deterministic but input-dependent filler so different inputs differ.
        h = hashlib.sha1(user_text.encode()).hexdigest()[:6]
        reply = f"Thanks for your message. I've noted your request (ref {h}). A teammate can follow up."

    # Pretend token usage, proportional to text length.
    usage = {
        "input": sum(len(m["content"].split()) for m in messages),
        "output": len(reply.split()),
    }
    return reply, usage


def chat_llm(messages, model=None):
    """
    Unified chat call. Returns (reply_text, usage_dict).
    Mirrors the shape of an OpenAI chat completion so swapping in the
    real API is a one-line change.
    """
    model = model or MODEL_NAME

    if USE_OPENAI:
        # Real call. Imported lazily so the mock path needs no openai install.
        from openai import OpenAI
        client = None
        if BASEURL:
          client = OpenAI(base_url=BASEURL)
        else:
          client = OpenAI()
        t0 = time.time()
        resp = client.chat.completions.create(model=model, messages=messages)
        _ = time.time() - t0
        text = resp.choices[0].message.content
        usage = {
            "input": resp.usage.prompt_tokens,
            "output": resp.usage.completion_tokens,
        }
        return text, usage

    # Mock path: tiny sleep so latency shows up as non-zero in Langfuse.
    time.sleep(0.15)
    return _mock_reply(messages)


def banner(stage_no, title):
    print("\n" + "=" * 64)
    print(f"  STAGE {stage_no} — {title}")
    print(f"  LLM backend: {'OpenAI (' + MODEL_NAME + ')' if USE_OPENAI else 'deterministic mock (no API key)'}")
    print("=" * 64)
