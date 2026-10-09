"""Langfuse features that are not spans: prompts, scores, sessions.

Prompt versions, scores and dataset experiments are Langfuse API objects rather
than telemetry. No span you can emit creates a prompt version or uploads an
experiment run, which is the fundamental reason Langfuse can answer questions
OpenLLMetry and OpenLIT cannot.

`triage_attributes` returns OTel span attributes for the request root that
OpenLIT exports to Langfuse.
"""

import logging
import os

from langfuse import get_client

log = logging.getLogger(__name__)

PROMPT_NAME = os.environ.get("LANGFUSE_PROMPT_NAME", "incident-triage-instructions")

# Fallback when Langfuse has no copy of the prompt yet. Identical to the
# instructions hardcoded in agent.py, so behaviour is unchanged on first boot.
DEFAULT_INSTRUCTIONS = (
    "You triage production incidents. For the affected service, always call "
    "check_service_health, lookup_runbook, and check_dependencies. "
    "For every service returned by check_dependencies, call both "
    "check_service_health AND check_dependencies on it to trace the full "
    "dependency chain. Keep following dependencies until you reach services "
    "with no further dependencies. Only then synthesize your triage report "
    "with severity, evidence, and the next three actions. Do not invent telemetry."
)


def client():
    """Langfuse SDK client. Reads LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY from env."""
    return get_client()


def check_auth() -> bool:
    try:
        return bool(client().auth_check())
    except Exception as exc:  # noqa: BLE001 - startup diagnostics only
        log.warning("status=langfuse_auth_check_failed error=%s", exc)
        return False


def ensure_prompt() -> None:
    """Create the managed prompt on first run so the UI has something to edit."""
    lf = client()
    try:
        lf.get_prompt(PROMPT_NAME)
        log.info("status=prompt_exists name=%s", PROMPT_NAME)
    except Exception:  # noqa: BLE001 - "not found" is not a typed error here
        lf.create_prompt(
            name=PROMPT_NAME,
            prompt=DEFAULT_INSTRUCTIONS,
            labels=["production"],
            type="text",
            commit_message="initial version, copied from agent.py",
        )
        log.info("status=prompt_created name=%s", PROMPT_NAME)


def fetch_prompt():
    """Return (instructions, prompt_client). prompt_client may be None.

    Falls back to the hardcoded instructions if Langfuse is unreachable, so a
    Langfuse outage degrades observability rather than taking the agent down.
    """
    try:
        prompt = client().get_prompt(PROMPT_NAME, label="production")
        return prompt.compile(), prompt
    except Exception as exc:  # noqa: BLE001
        log.warning("status=prompt_fetch_failed falling_back=true error=%s", exc)
        return DEFAULT_INSTRUCTIONS, None


def triage_attributes(session_id: str, user_id: str, prompt=None):
    """Attributes stamped on the OTel root span for one triage request.

    Langfuse's prompt object is still used to fetch/version instructions, but
    OpenLIT owns trace export in this experiment.
    """
    attrs = {
        "session.id": session_id,
        "user.id": user_id,
        "langfuse.tags": "agent,incident-triage",
        "langfuse.trace.name": "incident-triage",
    }
    if prompt is not None:
        attrs["langfuse.prompt.name"] = getattr(prompt, "name", PROMPT_NAME)
        version = getattr(prompt, "version", None)
        if version is not None:
            attrs["langfuse.prompt.version"] = str(version)
    return attrs


def record_score(trace_id: str, name: str, value, data_type: str, comment=None) -> None:
    lf = client()
    lf.create_score(
        trace_id=trace_id,
        name=name,
        value=value,
        data_type=data_type,
        comment=comment,
    )
    lf.flush()
    log.info("status=score_recorded trace_id=%s name=%s value=%s", trace_id, name, value)
