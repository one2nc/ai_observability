"""Bridge the OpenAI Agents SDK's own tracing into Langfuse observations.

Langfuse ships no auto-instrumentor for the Agents SDK. The documented options
are third-party OTel instrumentors (OpenLIT, OpenLLMetry, OpenInference) — but
those are experiments 6 and 7, and using one here would mean the spans came from
somewhere other than Langfuse. So this experiment goes through the Agents SDK's
*own* tracing interface instead: `TracingProcessor` receives every span the SDK
emits, and we translate each one into a Langfuse observation.

The translation is close to 1:1, because Langfuse's observation types happen to
line up with the SDK's span-data types:

    AgentSpanData        -> as_type="agent"
    FunctionSpanData     -> as_type="tool"
    GenerationSpanData   -> as_type="generation"   (chat_completions mode)
    ResponseSpanData     -> as_type="generation"   (responses mode)
    GuardrailSpanData    -> as_type="guardrail"
    HandoffSpanData      -> as_type="span"

`set_trace_processors([...])` in `install()` *replaces* the SDK's default
processor, which would otherwise upload traces to OpenAI's own dashboard. After
that call, nothing leaves for OpenAI and everything goes to Langfuse.

Parenting is explicit rather than context-based. The SDK tracks its own span
hierarchy through `span.parent_id`, which has no relationship to the OTel context
Langfuse would otherwise use, so we keep an id -> observation map and create each
child off its resolved parent.
"""

import logging
import threading
from typing import Any

from agents.tracing import TracingProcessor, set_trace_processors
from langfuse import get_client

log = logging.getLogger(__name__)

# span_data class name -> Langfuse observation type
_TYPE_MAP = {
    "AgentSpanData": "agent",
    "FunctionSpanData": "tool",
    "MCPListToolsSpanData": "tool",
    "GenerationSpanData": "generation",
    "ResponseSpanData": "generation",
    "GuardrailSpanData": "guardrail",
    "HandoffSpanData": "span",
    "CustomSpanData": "span",
}


def _usage_details(usage: Any) -> dict[str, int] | None:
    """Normalize the SDK's usage dict to Langfuse's input/output convention."""
    if not isinstance(usage, dict):
        return None
    details: dict[str, int] = {}
    for src, dest in (
        ("input_tokens", "input"),
        ("output_tokens", "output"),
        ("prompt_tokens", "input"),
        ("completion_tokens", "output"),
        ("total_tokens", "total"),
    ):
        value = usage.get(src)
        if isinstance(value, int):
            details[dest] = value
    return details or None


def _describe(span_data: Any) -> tuple[str, str, dict[str, Any]]:
    """Return (langfuse_type, observation_name, extra kwargs) for a span."""
    kind = type(span_data).__name__
    as_type = _TYPE_MAP.get(kind, "span")

    # Every field access is defensive: the SDK's span-data classes differ per
    # kind, and a missing attribute must not break the agent run.
    name = getattr(span_data, "name", None)
    kwargs: dict[str, Any] = {}

    if kind == "AgentSpanData":
        kwargs["metadata"] = {
            "handoffs": getattr(span_data, "handoffs", None),
            "tools": getattr(span_data, "tools", None),
            "output_type": getattr(span_data, "output_type", None),
        }
    elif kind in {"FunctionSpanData", "MCPListToolsSpanData"}:
        kwargs["input"] = getattr(span_data, "input", None) or getattr(span_data, "server", None)
    elif kind == "GenerationSpanData":
        name = name or "generation"
        kwargs["input"] = getattr(span_data, "input", None)
        kwargs["model"] = getattr(span_data, "model", None)
        kwargs["model_parameters"] = getattr(span_data, "model_config", None)
    elif kind == "ResponseSpanData":
        name = name or "response"
        kwargs["input"] = getattr(span_data, "input", None)
    elif kind == "HandoffSpanData":
        name = (
            f"handoff {getattr(span_data, 'from_agent', '?')} -> "
            f"{getattr(span_data, 'to_agent', '?')}"
        )
    elif kind == "GuardrailSpanData":
        kwargs["metadata"] = {"triggered": getattr(span_data, "triggered", None)}

    return as_type, name or kind.replace("SpanData", "").lower() or "span", kwargs


def _finalize(span_data: Any) -> dict[str, Any]:
    """Fields only known once the span has finished."""
    kind = type(span_data).__name__
    updates: dict[str, Any] = {}

    output = getattr(span_data, "output", None)
    if kind == "ResponseSpanData":
        response = getattr(span_data, "response", None)
        output = getattr(response, "output", None) or output
        usage = getattr(response, "usage", None)
        if usage is not None and not isinstance(usage, dict):
            usage = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            }
        details = _usage_details(usage)
        if details:
            updates["usage_details"] = details
        model = getattr(response, "model", None)
        if model:
            updates["model"] = model
    elif kind == "GenerationSpanData":
        details = _usage_details(getattr(span_data, "usage", None))
        if details:
            updates["usage_details"] = details
    elif kind == "MCPListToolsSpanData":
        output = getattr(span_data, "result", None) or output
    elif kind == "CustomSpanData":
        updates["metadata"] = getattr(span_data, "data", None)

    if output is not None:
        updates["output"] = output
    return updates


class LangfuseTracingProcessor(TracingProcessor):
    """Turns Agents SDK trace/span callbacks into Langfuse observations.

    One caveat worth knowing: observation timings come from when the callbacks
    fire, not from the SDK's recorded `started_at`/`ended_at` strings, because
    Langfuse's `start_observation()` has no start-time parameter. The callbacks
    are synchronous with span start and end, so the difference is callback
    overhead — fine for latency comparison, not for sub-millisecond work.
    """

    def __init__(self) -> None:
        self._client = get_client()
        self._lock = threading.Lock()
        # Agents SDK trace_id / span_id -> Langfuse observation
        self._traces: dict[str, Any] = {}
        self._spans: dict[str, Any] = {}

    def on_trace_start(self, trace) -> None:
        # Called synchronously inside Runner.run, which app.py invokes inside an
        # @observe'd function — so the current Langfuse context is the request
        # root, and this observation nests under it correctly.
        try:
            obs = self._client.start_observation(
                name=getattr(trace, "name", None) or "agent-workflow",
                as_type="chain",
                metadata=getattr(trace, "metadata", None),
            )
            with self._lock:
                self._traces[trace.trace_id] = obs
        except Exception:
            log.exception("status=langfuse_trace_start_failed")

    def on_trace_end(self, trace) -> None:
        try:
            with self._lock:
                obs = self._traces.pop(trace.trace_id, None)
                # Drop any spans that never received on_span_end.
                stale = [k for k, v in self._spans.items() if v[1] == trace.trace_id]
                for key in stale:
                    self._spans.pop(key, None)
            if obs is not None:
                obs.end()
        except Exception:
            log.exception("status=langfuse_trace_end_failed")

    def _parent_for(self, span) -> Any:
        """Resolve a span's Langfuse parent: its parent span, else its trace."""
        if span.parent_id:
            entry = self._spans.get(span.parent_id)
            if entry is not None:
                return entry[0]
        return self._traces.get(span.trace_id)

    def on_span_start(self, span) -> None:
        try:
            as_type, name, kwargs = _describe(span.span_data)
            with self._lock:
                parent = self._parent_for(span)
            if parent is None:
                # No known parent: fall back to a root-level observation.
                obs = self._client.start_observation(name=name, as_type=as_type, **kwargs)
            else:
                obs = parent.start_observation(name=name, as_type=as_type, **kwargs)
            with self._lock:
                self._spans[span.span_id] = (obs, span.trace_id)
        except Exception:
            log.exception("status=langfuse_span_start_failed")

    def on_span_end(self, span) -> None:
        try:
            with self._lock:
                entry = self._spans.pop(span.span_id, None)
            if entry is None:
                return
            obs = entry[0]
            updates = _finalize(span.span_data)

            error = getattr(span, "error", None)
            if error:
                message = (
                    error.get("message") if isinstance(error, dict) else str(error)
                )
                updates["level"] = "ERROR"
                updates["status_message"] = message

            if updates:
                obs.update(**updates)
            obs.end()
        except Exception:
            log.exception("status=langfuse_span_end_failed")

    def force_flush(self) -> None:
        self._client.flush()

    def shutdown(self) -> None:
        self._client.flush()


def install() -> None:
    """Replace the SDK's default processor so traces go to Langfuse, not OpenAI."""
    set_trace_processors([LangfuseTracingProcessor()])
    log.info("status=langfuse_tracing_installed backend=langfuse")
