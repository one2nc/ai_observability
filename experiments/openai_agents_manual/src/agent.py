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

TOOLS = {
    "check_service_health": lambda service: json.dumps(
        {
            "checkout": {"status": "degraded", "error_rate": 0.18, "p95_ms": 2400},
            "payments": {"status": "healthy", "error_rate": 0.002, "p95_ms": 180},
            "catalog": {"status": "healthy", "error_rate": 0.001, "p95_ms": 95},
        }.get(service.lower(), {"status": "unknown"})
    ),
    "lookup_runbook": lambda service: {
        "checkout": "Check payment dependency, inspect 5xx logs, then roll back the latest checkout deployment.",
        "payments": "Check provider status and payment queue depth before enabling failover.",
        "catalog": "Check cache hit rate and database replica lag.",
    }.get(service.lower(), "No runbook found; escalate to the owning team."),
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
]

SYSTEM_PROMPT = (
    "You triage production incidents. Always call check_service_health and "
    "lookup_runbook for the affected service. Return severity, evidence, and "
    "the next three actions. Do not invent telemetry."
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

            # --- No tool calls → done ---
            if not choice.tool_calls:
                break

            # --- Tool dispatch ---
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
                    workflow_duration.record(tool_elapsed, {
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": call.function.name,
                    })

                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": call.id,
                })

        workflow_elapsed = time.perf_counter() - workflow_start
        workflow_span.set_attribute("gen_ai.usage.input_tokens", total_input_tokens)
        workflow_span.set_attribute("gen_ai.usage.output_tokens", total_output_tokens)
        workflow_duration.record(workflow_elapsed, {
            "gen_ai.operation.name": "invoke_workflow",
            "gen_ai.request.model": model,
        })

    return choice.content or ""
