"""A small OpenAI Agents incident-triage workflow."""

import json
import os

from agents import (
    Agent,
    Runner,
    function_tool,
    set_default_openai_api,
    set_default_openai_client,
)
from openai import AsyncOpenAI

agents_api = os.environ["OPENAI_AGENTS_API"]
if agents_api not in {"responses", "chat_completions"}:
    raise RuntimeError("OPENAI_AGENTS_API must be 'responses' or 'chat_completions'")

client_kwargs = {"api_key": os.environ["OPENAI_API_KEY"]}
if os.environ.get("OPENAI_BASE_URL"):
    base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
    if not base_url.endswith("/v1"):
        raise RuntimeError("OPENAI_BASE_URL must include the OpenAI-compatible /v1 path")
    client_kwargs["base_url"] = base_url

set_default_openai_api(agents_api)
set_default_openai_client(AsyncOpenAI(**client_kwargs), use_for_tracing=False)


@function_tool
def check_service_health(service: str) -> str:
    """Return synthetic live health data for a named service."""
    services = {
        "checkout": {"status": "degraded", "error_rate": 0.18, "p95_ms": 2400},
        "payments": {"status": "healthy", "error_rate": 0.002, "p95_ms": 180},
        "catalog": {"status": "healthy", "error_rate": 0.001, "p95_ms": 95},
    }
    return json.dumps(services.get(service.lower(), {"status": "unknown"}))


@function_tool
def lookup_runbook(service: str) -> str:
    """Return the first response steps for a named service."""
    runbooks = {
        "checkout": "Check payment dependency, inspect 5xx logs, then roll back the latest checkout deployment.",
        "payments": "Check provider status and payment queue depth before enabling failover.",
        "catalog": "Check cache hit rate and database replica lag.",
    }
    return runbooks.get(service.lower(), "No runbook found; escalate to the owning team.")


agent = Agent(
    name="incident-triage-agent",
    model=os.environ["OPENAI_MODEL"],
    instructions=(
        "You triage production incidents. Always call check_service_health and "
        "lookup_runbook for the affected service. Return severity, evidence, and "
        "the next three actions. Do not invent telemetry."
    ),
    tools=[check_service_health, lookup_runbook],
)


async def run_agent(query: str) -> str:
    result = await Runner.run(agent, query, max_turns=4)
    return str(result.final_output)
