"""Manual tool-loop agent without the OpenAI Agents SDK."""

import json
import logging
import time

from openai import AsyncOpenAI
from opentelemetry import trace, metrics

log = logging.getLogger(__name__)

tracer = trace.get_tracer("agent")
meter = metrics.get_meter("agent")

workflow_duration = meter.create_histogram(
    "gen_ai.client.operation.duration",
    description="Duration of GenAI operations",
    unit="s",
)
token_usage = meter.create_histogram(
    "gen_ai.client.token.usage",
    description="Token usage per model call",
    unit="token",
)

# --- Tools ---

# Dependency graph: each service lists its upstream dependencies.
# check_dependencies returns these, prompting the model to check each one.
#
# Designed for predictable turn counts:
#   auth        → no deps        → completes in 1 turn (health + runbook + deps, no deeper)
#   payments    → ledger          → completes in 2 turns (check payments, then check ledger)
#   catalog     → search, inventory → completes in 3 turns (catalog → deps → check each)
#   checkout    → payments, catalog, auth → needs 4+ turns (hits max_turns)
#
DEPENDENCY_GRAPH = {
    "checkout": ["payments", "catalog", "auth"],
    "payments": ["ledger"],
    "catalog": ["search-index", "inventory"],
    "auth": [],
    "ledger": [],
    "search-index": [],
    "inventory": [],
}

# Simulated latency per service (seconds).
DEPENDENCY_LATENCY = {
    "checkout": 0.5,
    "payments": 0.3,
    "catalog": 0.2,
    "auth": 0.1,
    "ledger": 1.5,        # slow - simulates database
    "search-index": 0.8,  # moderate
    "inventory": 0.1,
}


def _check_dependencies(service: str) -> str:
    """Return upstream dependencies with simulated latency."""
    svc = service.lower()
    log.info("status=tool_called tool=check_dependencies service=%s", svc)
    deps = DEPENDENCY_GRAPH.get(svc)
    if deps is None:
        return json.dumps({"error": f"Unknown service: {svc}"})
    latency = DEPENDENCY_LATENCY.get(svc, 0.1)
    time.sleep(latency)  # simulate slow dependency resolution
    log.info("status=dependencies_resolved service=%s dependencies=%s latency_ms=%d", svc, ",".join(deps) if deps else "none", int(latency * 1000))
    return json.dumps({
        "service": svc,
        "dependencies": deps,
        "resolution_time_ms": int(latency * 1000),
    })


def _check_service_health(service: str) -> str:
    """Return synthetic live health data for a named service."""
    svc = service.lower()
    log.info("status=tool_called tool=check_service_health service=%s", svc)
    data = {
        "checkout": {"status": "degraded", "error_rate": 0.18, "p95_ms": 2400},
        "payments": {"status": "healthy", "error_rate": 0.002, "p95_ms": 180},
        "catalog": {"status": "degraded", "error_rate": 0.05, "p95_ms": 850},
        "auth": {"status": "healthy", "error_rate": 0.001, "p95_ms": 50},
        "ledger": {"status": "degraded", "error_rate": 0.08, "p95_ms": 3200},
        "search-index": {"status": "degraded", "error_rate": 0.12, "p95_ms": 1200},
        "inventory": {"status": "healthy", "error_rate": 0.001, "p95_ms": 45},
    }.get(svc, {"status": "unknown"})
    return json.dumps(data)


def _lookup_runbook(service: str) -> str:
    """Return the first response steps for a named service."""
    svc = service.lower()
    log.info("status=tool_called tool=lookup_runbook service=%s", svc)
    return {
        "checkout": "Check payment dependency, inspect 5xx logs, then roll back the latest checkout deployment.",
        "payments": "Check provider status and payment queue depth before enabling failover.",
        "catalog": "Check cache hit rate and database replica lag.",
    }.get(svc, "No runbook found; escalate to the owning team.")


TOOLS = {
    "check_service_health": _check_service_health,
    "lookup_runbook": _lookup_runbook,
    "check_dependencies": _check_dependencies,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "check_service_health",
            "description": "Return synthetic live health data for a named service.",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string", "description": "Service name"}},
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_runbook",
            "description": "Return the first response steps for a named service.",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string", "description": "Service name"}},
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_dependencies",
            "description": "Return upstream service dependencies. Use this to trace which services a given service depends on. Returns the dependency list and resolution time.",
            "parameters": {
                "type": "object",
                "properties": {"service": {"type": "string", "description": "Service name"}},
                "required": ["service"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You triage production incidents. For the affected service, always call "
    "check_service_health, lookup_runbook, and check_dependencies. "
    "For every service returned by check_dependencies, call both "
    "check_service_health AND check_dependencies on it to trace the full "
    "dependency chain. Keep following dependencies until you reach services "
    "with no further dependencies. Only then synthesize your triage report "
    "with severity, evidence, and the next three actions. Do not invent telemetry."
)


def _dispatch_tool(name: str, arguments: str) -> str:
    args = json.loads(arguments)
    fn = TOOLS.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    return fn(**args)


async def run_agent(query: str, client: AsyncOpenAI, model: str, max_turns: int = 4) -> str:
    """Run the tool loop with manual OTel instrumentation."""
    common_attrs = {"gen_ai.request.model": model, "server.address": "api.openai.com"}

    with tracer.start_as_current_span("invoke_workflow", attributes={
        "gen_ai.operation.name": "invoke_workflow",
        **common_attrs,
    }) as workflow_span:
        workflow_start = time.perf_counter()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        total_input_tokens = 0
        total_output_tokens = 0

        for turn in range(max_turns):
            # --- Model call ---
            with tracer.start_as_current_span("chat", attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.turn": turn,
                **common_attrs,
            }) as chat_span:
                chat_start = time.perf_counter()
                response = await client.chat.completions.create(
                    model=model, messages=messages, tools=TOOL_SCHEMAS,
                )
                chat_elapsed = time.perf_counter() - chat_start

                choice = response.choices[0].message
                input_tokens = response.usage.prompt_tokens if response.usage else 0
                output_tokens = response.usage.completion_tokens if response.usage else 0
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                chat_span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                chat_span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                chat_span.set_attribute("gen_ai.response.model", response.model)

                metric_attrs = {"gen_ai.operation.name": "chat", "gen_ai.request.model": model}
                workflow_duration.record(chat_elapsed, metric_attrs)
                token_usage.record(input_tokens, {**metric_attrs, "gen_ai.token.type": "input"})
                token_usage.record(output_tokens, {**metric_attrs, "gen_ai.token.type": "output"})

            # --- No tool calls -> done ---
            if not choice.tool_calls:
                log.info("status=turn_complete turn=%d action=synthesized", turn + 1)
                break

            # --- Tool dispatch ---
            tool_names = [call.function.name for call in choice.tool_calls]
            messages.append(choice)
            for call in choice.tool_calls:
                with tracer.start_as_current_span("execute_tool", attributes={
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": call.function.name,
                }) as tool_span:
                    tool_start = time.perf_counter()
                    result = _dispatch_tool(call.function.name, call.function.arguments)
                    tool_elapsed = time.perf_counter() - tool_start

                    tool_span.set_attribute("gen_ai.tool.result_length", len(result))
                    tool_span.set_attribute("gen_ai.tool.duration_s", tool_elapsed)
                    workflow_duration.record(tool_elapsed, {
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": call.function.name,
                    })

                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": call.id,
                })
            log.info("status=turn_complete turn=%d action=tool_calls tools=%s", turn + 1, ",".join(tool_names))
        else:
            log.warning("status=max_turns_reached max_turns=%d", max_turns)

        workflow_elapsed = time.perf_counter() - workflow_start
        workflow_span.set_attribute("gen_ai.usage.input_tokens", total_input_tokens)
        workflow_span.set_attribute("gen_ai.usage.output_tokens", total_output_tokens)
        workflow_span.set_attribute("gen_ai.turns", turn + 1)
        workflow_duration.record(workflow_elapsed, {
            "gen_ai.operation.name": "invoke_workflow",
            "gen_ai.request.model": model,
        })

    return choice.content or ""
