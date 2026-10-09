"""OpenAI Agents SDK incident-triage workflow - same tools as openai_agents_manual."""

import json
import os
import time

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

# --- Same tools and data as openai_agents_manual ---

DEPENDENCY_GRAPH = {
    "checkout": ["payments", "catalog", "auth"],
    "payments": ["ledger"],
    "catalog": ["search-index", "inventory"],
    "auth": [],
    "ledger": [],
    "search-index": [],
    "inventory": [],
}

DEPENDENCY_LATENCY = {
    "checkout": 0.5,
    "payments": 0.3,
    "catalog": 0.2,
    "auth": 0.1,
    "ledger": 1.5,
    "search-index": 0.8,
    "inventory": 0.1,
}


@function_tool
def check_service_health(service: str) -> str:
    """Return synthetic live health data for a named service."""
    data = {
        "checkout": {"status": "degraded", "error_rate": 0.18, "p95_ms": 2400},
        "payments": {"status": "healthy", "error_rate": 0.002, "p95_ms": 180},
        "catalog": {"status": "degraded", "error_rate": 0.05, "p95_ms": 850},
        "auth": {"status": "healthy", "error_rate": 0.001, "p95_ms": 50},
        "ledger": {"status": "degraded", "error_rate": 0.08, "p95_ms": 3200},
        "search-index": {"status": "degraded", "error_rate": 0.12, "p95_ms": 1200},
        "inventory": {"status": "healthy", "error_rate": 0.001, "p95_ms": 45},
    }
    return json.dumps(data.get(service.lower(), {"status": "unknown"}))


@function_tool
def lookup_runbook(service: str) -> str:
    """Return the first response steps for a named service."""
    runbooks = {
        "checkout": "Check payment dependency, inspect 5xx logs, then roll back the latest checkout deployment.",
        "payments": "Check provider status and payment queue depth before enabling failover.",
        "catalog": "Check cache hit rate and database replica lag.",
    }
    return runbooks.get(service.lower(), "No runbook found; escalate to the owning team.")


@function_tool
def check_dependencies(service: str) -> str:
    """Return upstream service dependencies with simulated resolution latency."""
    svc = service.lower()
    deps = DEPENDENCY_GRAPH.get(svc)
    if deps is None:
        return json.dumps({"error": f"Unknown service: {svc}"})
    latency = DEPENDENCY_LATENCY.get(svc, 0.1)
    time.sleep(latency)
    return json.dumps({
        "service": svc,
        "dependencies": deps,
        "resolution_time_ms": int(latency * 1000),
    })


agent = Agent(
    name="incident-triage-agent",
    model=os.environ["OPENAI_MODEL"],
    instructions=(
        "You triage production incidents. For the affected service, always call "
        "check_service_health, lookup_runbook, and check_dependencies. "
        "For every service returned by check_dependencies, call both "
        "check_service_health AND check_dependencies on it to trace the full "
        "dependency chain. Keep following dependencies until you reach services "
        "with no further dependencies. Only then synthesize your triage report "
        "with severity, evidence, and the next three actions. Do not invent telemetry."
    ),
    tools=[check_service_health, lookup_runbook, check_dependencies],
)


async def run_agent(query: str) -> str:
    result = await Runner.run(agent, query, max_turns=30)
    return str(result.final_output)
