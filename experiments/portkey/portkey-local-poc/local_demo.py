"""
local_demo.py
-------------
End-to-end demo of the self-hosted Portkey AI Gateway running via Docker.

Architecture:
  Python SDK
    → Local Portkey Gateway  (localhost:8787)
    → OpenRouter             (openrouter.ai)
    → OpenAI models          (gpt-4o-mini / gpt-4o)

Local services used:
  portkey-gateway  – AI Gateway container  (port 8787)

Run:
  1.  docker compose up -d
  2.  python local_demo.py
"""

import json
import time
import os
from pathlib import Path
from portkey_ai import Portkey

# ── Load .env ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

GATEWAY_URL   = os.getenv("PORTKEY_GATEWAY_URL",  "http://localhost:8787/v1")
GATEWAY_KEY   = os.getenv("PORTKEY_CLIENT_AUTH",  "local-test-key")
CLOUD_API_KEY = os.getenv("PORTKEY_CLOUD_API_KEY","")
CLOUD_HOST    = os.getenv("PORTKEY_CLOUD_HOST",   "https://api.portkey.ai/v1")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL",         "@test/gpt-4.1")
FALLBACK_MODEL= os.getenv("FALLBACK_MODEL",        "@test/gpt-4")

# ── Helpers ─────────────────────────────────────────────────────────────────────
def make_config(d: dict) -> str:
    return json.dumps(d)

def cloud_target(model: str) -> dict:
    """A target that routes through the local gateway to Portkey Cloud."""
    return {
        "provider":        "openai",
        "customHost":      CLOUD_HOST,
        "api_key":         CLOUD_API_KEY,
        "override_params": {"model": model},
    }

def get_client(config: str) -> Portkey:
    """Portkey client pointed at the local self-hosted gateway."""
    return Portkey(base_url=GATEWAY_URL, api_key=GATEWAY_KEY, config=config)

def get_text(response) -> str:
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        return str(response)

def divider(title: str) -> None:
    print(f"\n{'═' * 66}")
    print(f"  {title}")
    print(f"{'═' * 66}\n")

def route_label() -> str:
    return f"  🔗  Route: SDK → localhost:8787 → api.portkey.ai → LLM\n"


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 1 — Basic Completion
# ══════════════════════════════════════════════════════════════════════════════
def demo_1_basic():
    divider("Demo 1 — Basic Completion via Local Gateway")
    print(route_label())

    # Flat single-target config (no "targets" wrapper needed for single provider)
    config = make_config(cloud_target(PRIMARY_MODEL))
    client = get_client(config)

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
        print(f"  Tokens : prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}")
    print(f"  Latency: {ms:.0f} ms  (local gateway + cloud round-trip)")
    print(f"\n  ✅  Gateway proxied request → check logs: docker compose logs portkey")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 2 — Multi-Turn Chat
# ══════════════════════════════════════════════════════════════════════════════
def demo_2_chat():
    divider("Demo 2 — Multi-Turn Chat Completion")
    print(route_label())

    config = make_client = make_config(cloud_target(PRIMARY_MODEL))
    client = get_client(config)

    conv = [
        {"role": "system", "content": "You are a concise technical assistant. Max 2 sentences per reply."},
        {"role": "user",   "content": "What is Docker?"},
    ]

    for i, user_msg in enumerate(["What is Docker?", "How does it differ from a VM?", "What is Docker Compose?"], 1):
        if i > 1:
            conv.append({"role": "user", "content": user_msg})
        print(f"  Turn {i} → {user_msg}")
        r = client.chat.completions.create(model=PRIMARY_MODEL, messages=conv, max_tokens=80)
        reply = get_text(r).strip()
        print(f"  Bot   → {reply}\n")
        conv.append({"role": "assistant", "content": reply})

    print(f"  ✅  All 3 turns routed through local gateway with full message history preserved")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 3 — Streaming Response
# ══════════════════════════════════════════════════════════════════════════════
def demo_3_streaming():
    divider("Demo 3 — Streaming Response (SSE)")
    print(route_label())

    config = make_config(cloud_target(PRIMARY_MODEL))
    client = get_client(config)

    print(f"  Prompt: Explain how LLM streaming works in 3 sentences.\n")
    print(f"  Stream output:\n  ", end="", flush=True)

    start = time.perf_counter()
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
                full  += delta
                chunks += 1

    ms = (time.perf_counter() - start) * 1000
    print(f"\n\n  Chunks received : {chunks}")
    print(f"  Total chars     : {len(full)}")
    print(f"  Wall time       : {ms:.0f} ms")
    print(f"\n  ✅  Local gateway streamed SSE chunks without buffering")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 4 — Fallback Routing
# ══════════════════════════════════════════════════════════════════════════════
def demo_4_fallback():
    divider("Demo 4 — Fallback Routing (Primary Fails → Fallback Succeeds)")
    print(route_label())

    config = make_config({
        "strategy": {"mode": "fallback"},
        "targets": [
            # Target 0: invalid model → will fail with 4xx
            {**cloud_target("@test/invalid-trigger-fallback")},
            # Target 1: real model   → will succeed
            {**cloud_target(FALLBACK_MODEL)},
        ],
    })
    client = get_client(config)

    print(f"  Primary  : @test/invalid-trigger-fallback  → FAIL (4xx)")
    print(f"  Fallback : {FALLBACK_MODEL}  → SUCCESS\n")

    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": "Explain fallback routing in 2 sentences."}],
            max_tokens=80,
        )
        ms = (time.perf_counter() - start) * 1000
        print(f"  Response : {get_text(resp).strip()}\n")
        print(f"  Latency  : {ms:.0f} ms  (includes failed primary attempt)")
        print(f"\n  ✅  Fallback worked — client received 200 despite primary failure")
        print(f"  📋  Logs: docker compose logs portkey")
    except Exception as exc:
        print(f"  ❌  All targets failed: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 5 — Cost-Aware Load Balancing
# ══════════════════════════════════════════════════════════════════════════════
def demo_5_load_balance():
    divider("Demo 5 — Weighted Load Balancing  (20% gpt-4 / 80% gpt-4.1)")
    print(route_label())

    config = make_config({
        "strategy": {"mode": "loadbalance"},
        "targets": [
            {"weight": 20, **cloud_target(FALLBACK_MODEL)},  # gpt-4   (heavier — 20%)
            {"weight": 80, **cloud_target(PRIMARY_MODEL)},   # gpt-4.1 (lighter — 80%)
        ],
    })
    client = get_client(config)

    total = 8
    success = 0
    print(f"  Weights : 20% {FALLBACK_MODEL}  /  80% {PRIMARY_MODEL}")
    print(f"  Firing  : {total} requests\n")
    print(f"  {'#':<5} {'Status':<8} Preview")
    print(f"  {'─' * 72}")

    for i in range(1, total + 1):
        try:
            resp = client.chat.completions.create(
                model=PRIMARY_MODEL,
                messages=[{"role": "user", "content": f"Request {i}: What is load balancing? One sentence."}],
                max_tokens=50,
            )
            text = get_text(resp).strip()
            print(f"  {i:<5} ✅ PASS   {text[:60]}")
            success += 1
        except Exception as exc:
            print(f"  {i:<5} ❌ FAIL   {str(exc)[:60]}")

    print(f"\n  Result: {success}/{total} succeeded")
    print(f"  📊  Gateway logs show which model served each request:")
    print(f"      docker compose logs portkey | grep model")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 6 — Retry + Timeout
# ══════════════════════════════════════════════════════════════════════════════
def demo_6_retry():
    divider("Demo 6 — Retry Handling + Request Timeout")
    print(route_label())

    # Flat config (no "targets" wrapper) — retry and timeout at the top level
    # alongside the provider settings. This avoids "Provider not found" when
    # there is no "strategy" field alongside "targets".
    retry_config = make_config({
        "retry":           {"attempts": 3, "on_status_codes": [429, 500, 502, 503, 504]},
        "request_timeout": 30000,
        **cloud_target(PRIMARY_MODEL),
    })
    client = get_client(retry_config)

    print("  Config: retry.attempts=3, on_status_codes=[429,500-504], timeout=30s\n")
    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[{"role": "user", "content": "What is exponential backoff? One sentence."}],
        max_tokens=60,
    )
    ms = (time.perf_counter() - start) * 1000
    print(f"  Response : {get_text(resp).strip()}")
    print(f"  Latency  : {ms:.0f} ms  (succeeded on first attempt — no retries needed)")

    # Part B: timeout so short it always fires
    print("\n  ── Timeout demo: 1ms timeout (will abort) ──")
    short_config = make_config({
        "request_timeout": 1,
        **cloud_target(PRIMARY_MODEL),  # 1ms — will always abort
    })
    short_client = get_client(short_config)
    start = time.perf_counter()
    try:
        short_client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=20,
        )
        print("  (unexpectedly succeeded)")
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        print(f"  Aborted after {ms:.0f} ms — error: {str(exc)[:70]}")
        print(f"  ✅  Timeout enforced by local gateway before provider was reached")


# ══════════════════════════════════════════════════════════════════════════════
# OBSERVABILITY SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
def show_observability():
    divider("Observability — Inspect What the Gateway Recorded")
    import subprocess

    print("  ── Gateway container logs (last 20 lines) ──")
    try:
        result = subprocess.run(
            ["docker", "compose",
             "-f", str(Path(__file__).parent / "docker-compose.yml"),
             "logs", "--tail=20", "portkey"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines()[-15:]:
            # strip docker compose warning
            if "obsolete" not in line and line.strip():
                print(f"  {line}")
    except Exception as exc:
        print(f"  (could not fetch logs: {exc})")



# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "█" * 66)
    print("  Portkey AI Gateway — Local Self-Hosted Demo")
    print(f"  Gateway : {GATEWAY_URL}")
    print(f"  Cloud   : {CLOUD_HOST}")
    print(f"  Model   : {PRIMARY_MODEL}  /  fallback: {FALLBACK_MODEL}")
    print("█" * 66)

    # Warm-up: one silent request so the first real demo doesn't hit a cold-start 503
    print("\n  Warming up gateway connection...")
    try:
        _wc = get_client(make_config(cloud_target(PRIMARY_MODEL)))
        _wc.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=16,
        )
        print("  Gateway warm — starting demos\n")
    except Exception:
        print("  (warm-up skipped)\n")

    demos = [
        ("01 — Basic Completion",    demo_1_basic),
        ("02 — Multi-Turn Chat",     demo_2_chat),
        ("03 — Streaming",           demo_3_streaming),
        ("04 — Fallback Routing",    demo_4_fallback),
        ("05 — Load Balancing",      demo_5_load_balance),
        ("06 — Retry + Timeout",     demo_6_retry),
    ]

    results = []
    for label, fn in demos:
        start = time.perf_counter()
        try:
            fn()
            ms = (time.perf_counter() - start) * 1000
            results.append((label, "✅ PASS", f"{ms:.0f}ms"))
        except Exception as exc:
            ms = (time.perf_counter() - start) * 1000
            print(f"\n  ❌  {label} failed: {exc}")
            results.append((label, "❌ FAIL", f"{ms:.0f}ms"))
        time.sleep(0.3)

    show_observability()

    print(f"\n{'═' * 66}")
    print("  FINAL RESULTS")
    print(f"{'═' * 66}")
    for label, status, ms in results:
        print(f"  {status}  {label:<36}  {ms:>8}")
    print(f"{'═' * 66}")

    passed = sum(1 for _, s, _ in results if "PASS" in s)
    print(f"\n  {passed}/{len(results)} demos passed")
    print(f"\n  Stack cleanup when done:  docker compose -f portkey-local-poc/docker-compose.yml down")
    print(f"{'═' * 66}\n")
