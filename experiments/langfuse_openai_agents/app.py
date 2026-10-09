"""OpenAI Agents incident-triage demo observed by OpenLIT and Langfuse."""

import logging
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_AGENTS_API",
    "LANGFUSE_HOST",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "OTEL_SERVICE_NAME",
)
missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException  # noqa: E402
from openai import OpenAIError  # noqa: E402
from opentelemetry import trace  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.instrument import init_instrumentation  # noqa: E402

app = FastAPI(title="OpenLIT + Langfuse + OpenAI Agents", version="0.1.0")
init_instrumentation(app)
tracer = trace.get_tracer(__name__)

from agents import Runner  # noqa: E402

from src import agent as agent_module  # noqa: E402
from src import langfuse_native as lf  # noqa: E402

DEFAULT_USER_ID = os.environ.get("DEMO_USER_ID", "demo-user")
MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "3"))


@app.on_event("startup")
def startup() -> None:
    if lf.check_auth():
        log.info("status=langfuse_auth_ok host=%s", os.environ["LANGFUSE_HOST"])
        lf.ensure_prompt()
    else:
        log.warning(
            "status=langfuse_auth_failed host=%s — traces will not arrive; "
            "check keys with 'make langfuse-keys' in ../../infra",
            os.environ["LANGFUSE_HOST"],
        )


@app.on_event("shutdown")
def shutdown() -> None:
    # The SDK buffers in a background thread; flush so nothing is lost on exit.
    lf.client().flush()
    tracer_provider = trace.get_tracer_provider()
    force_flush = getattr(tracer_provider, "force_flush", None)
    if force_flush is not None:
        force_flush()


class AskRequest(BaseModel):
    query: str
    session_id: str | None = None
    user_id: str | None = None


class AskResponse(BaseModel):
    query: str
    answer: str
    # Returned so a client can attach a score to this exact run.
    trace_id: str | None
    session_id: str


class FeedbackRequest(BaseModel):
    trace_id: str
    # True/False thumbs up/down, or a 0..1 float for a graded rating.
    helpful: bool | None = None
    value: float | None = None
    comment: str | None = None


async def run_triage(query: str, session_id: str, user_id: str) -> tuple[str, str | None]:
    """One triage request. OpenLIT exports the active OTel trace to Langfuse."""
    # Prompt management: instructions come from Langfuse, not from the code, so
    # they can be edited and versioned in the UI without a redeploy.
    instructions, prompt = lf.fetch_prompt()

    attributes = lf.triage_attributes(session_id, user_id, prompt)
    attributes["input.value"] = query
    with tracer.start_as_current_span("incident-triage", attributes=attributes) as span:
        span_context = span.get_span_context()
        trace_id = f"{span_context.trace_id:032x}" if span_context.is_valid else None
        # agent.py is byte-identical to experiments 6 and 7; the managed prompt
        # is applied via clone() so that stays true and the comparison is fair.
        scoped_agent = agent_module.agent.clone(instructions=instructions)
        result = await Runner.run(scoped_agent, query, max_turns=MAX_TURNS)
        answer = str(result.final_output)
        span.set_attribute("output.value", answer)

    return answer, trace_id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    session_id = req.session_id or f"triage-{uuid.uuid4().hex[:8]}"
    user_id = req.user_id or DEFAULT_USER_ID
    try:
        answer, trace_id = await run_triage(req.query, session_id, user_id)
    except OpenAIError as exc:
        log.exception("status=model_request_failed")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "model_request_failed",
                "message": str(exc),
                "hint": "Check OPENAI_API_KEY, OPENAI_BASE_URL, and the selected OPENAI_MODEL.",
            },
        ) from exc
    return AskResponse(
        query=req.query, answer=answer, trace_id=trace_id, session_id=session_id
    )


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Attach a score to a completed trace — the half of Langfuse that is not OTel."""
    if req.helpful is not None:
        lf.record_score(
            trace_id=req.trace_id,
            name="user-feedback",
            value=1 if req.helpful else 0,
            data_type="BOOLEAN",
            comment=req.comment or ("thumbs up" if req.helpful else "thumbs down"),
        )
    elif req.value is not None:
        lf.record_score(
            trace_id=req.trace_id,
            name="user-rating",
            value=req.value,
            data_type="NUMERIC",
            comment=req.comment,
        )
    else:
        return {"status": "ignored", "reason": "provide either 'helpful' or 'value'"}
    return {"status": "recorded", "trace_id": req.trace_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8006")))
