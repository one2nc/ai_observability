"""
common.py
---------
Shared helpers for the Portkey Cloud POC Python SDK demos.

All cloud demos use a single Portkey API key — no base_url override,
no provider/customHost/api_key embedded in config. Portkey Cloud handles
routing, caching, guardrails, and analytics transparently.
"""

import json
import os
from pathlib import Path
from portkey_ai import Portkey

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY", "")
PRIMARY_MODEL   = os.getenv("PRIMARY_MODEL",   "@test/gpt-4.1")
FALLBACK_MODEL  = os.getenv("FALLBACK_MODEL",  "@test/gpt-4")


def make_config(d: dict) -> str:
    """Serialise a routing/cache config dict to the JSON string Portkey expects."""
    return json.dumps(d)


def get_client(config: str = None) -> Portkey:
    """
    Return a Portkey client pointed at Portkey Cloud (api.portkey.ai).

    For cloud demos the client only needs the API key — no base_url.
    Pass an optional config string to enable routing strategies, cache, etc.
    """
    kwargs = {"api_key": PORTKEY_API_KEY}
    if config:
        kwargs["config"] = config
    return Portkey(**kwargs)


def get_text(response) -> str:
    """Extract the assistant text from a chat completion response."""
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        return str(response)
