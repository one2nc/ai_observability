"""
common.py
---------
Shared client factory and config helpers for all local Portkey examples.

Request flow:
  Python SDK  →  Local Gateway (localhost:8787)  →  Portkey Cloud (api.portkey.ai)  →  LLM
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Tuple
from portkey_ai import Portkey

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# ── Local Gateway ──────────────────────────────────────────────────────────────
GATEWAY_URL     = os.getenv("PORTKEY_GATEWAY_URL", "http://localhost:8787/v1")
PORTKEY_API_KEY = os.getenv("PORTKEY_CLIENT_AUTH", "local-test-key")

# ── Portkey Cloud (backend) ────────────────────────────────────────────────────
CLOUD_API_KEY = os.getenv("PORTKEY_CLOUD_API_KEY", "")
CLOUD_HOST    = os.getenv("PORTKEY_CLOUD_HOST",    "https://api.portkey.ai/v1")

# ── Models ─────────────────────────────────────────────────────────────────────
PRIMARY_MODEL    = os.getenv("PRIMARY_MODEL",    "@test/gpt-4.1")
FALLBACK_MODEL   = os.getenv("FALLBACK_MODEL",   "@test/gpt-4")
PRIMARY_PROVIDER = os.getenv("PRIMARY_PROVIDER", "openai")


# ── Config helpers ─────────────────────────────────────────────────────────────
def make_config(cfg: dict) -> str:
    return json.dumps(cfg)


def _target(model: str = PRIMARY_MODEL, **extra) -> dict:
    """Single provider target routed through Portkey Cloud."""
    return {
        "provider":        "openai",
        "customHost":      CLOUD_HOST,
        "api_key":         CLOUD_API_KEY,
        "override_params": {"model": model},
        **extra,
    }


def get_client(config: Optional[str] = None, **kwargs) -> Portkey:
    """Portkey client pointed at the local self-hosted gateway."""
    opts = {"base_url": GATEWAY_URL, "api_key": PORTKEY_API_KEY}
    if config:
        opts["config"] = config
    opts.update(kwargs)
    return Portkey(**opts)


def single_target_config(model: str = PRIMARY_MODEL, **extra) -> str:
    return make_config({**_target(model), **extra})


def fallback_config(primary: str = PRIMARY_MODEL, fallback: str = FALLBACK_MODEL) -> str:
    return make_config({
        "strategy": {"mode": "fallback"},
        "targets":  [_target(primary), _target(fallback)],
    })


def load_balance_config(weights: List[Tuple[int, str]]) -> str:
    return make_config({
        "strategy": {"mode": "loadbalance"},
        "targets":  [{**_target(model), "weight": w} for w, model in weights],
    })


def retry_config(model: str = PRIMARY_MODEL, attempts: int = 3, timeout_ms: int = 30_000) -> str:
    return make_config({
        "retry":           {"attempts": attempts, "on_status_codes": [429, 500, 502, 503, 504]},
        "request_timeout": timeout_ms,
        **_target(model),
    })


# ── Display helpers ────────────────────────────────────────────────────────────
def divider(title: str) -> None:
    print(f"\n{'═' * 62}")
    print(f"  {title}")
    print(f"{'═' * 62}\n")


def get_text(response) -> str:
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        return str(response)
