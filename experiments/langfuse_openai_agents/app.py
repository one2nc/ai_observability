"""OpenAI Agents incident-triage demo, observed with Langfuse only.

No OpenLLMetry, no OpenLIT, no OTel collector gateway. The only observability
dependency is the `langfuse` SDK, and agent spans come from the Agents SDK's own
tracing interface — see src/langfuse_tracing.py.
"""

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

from fastapi import FastAPI  # noqa: E402
from langfuse import observe  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src import langfuse_tracing  # noqa: E402

# Replaces the Agents SDK's default processor, which would upload traces to
# OpenAI. Must happen before the first Runner.run().
langfuse_tracing.install()

from agents import Runner  # noqa: E402

from src import agent as agent_module  # noqa: E402
from src import langfuse_native as lf  # noqa: E402

app = FastAPI(title="Langfuse + OpenAI Agents", version="0.1.0")

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


@observe(name="incident-triage")
async def run_triage(query: str, session_id: str, user_id: str) -> tuple[str, str | None]:
    """One triage request. @observe makes this the root Langfuse trace."""
    # Prompt management: instructions come from Langfuse, not from the code, so
    # they can be edited and versioned in the UI without a redeploy.
    instructions, prompt = lf.fetch_prompt()

    with lf.triage_attributes(session_id, user_id, prompt):
        trace_id = lf.current_trace_id()
        # agent.py is byte-identical to experiments 6 and 7; the managed prompt
        # is applied via clone() so that stays true and the comparison is fair.
        scoped_agent = agent_module.agent.clone(instructions=instructions)
        result = await Runner.run(scoped_agent, query, max_turns=MAX_TURNS)
        answer = str(result.final_output)
        lf.set_trace_io(input_value=query, output=answer)

    return answer, trace_id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    session_id = req.session_id or f"triage-{uuid.uuid4().hex[:8]}"
    user_id = req.user_id or DEFAULT_USER_ID
    answer, trace_id = await run_triage(req.query, session_id, user_id)
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
