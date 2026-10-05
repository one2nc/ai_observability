"""Offline eval loop: dataset + experiment run against the triage agent.

This is the capability neither OpenLLMetry nor OpenLIT has any answer to. Both
tell you the agent got slower or more expensive; neither tells you whether it got
*worse*. Here we pin a fixed set of triage questions, run the whole set through
the live agent, score every answer, and upload the results so two runs can be
diffed in the UI.

Change the prompt in Langfuse (or OPENAI_MODEL), run this again, then compare in
Datasets -> agent-triage-qa -> Runs.

Usage:  make eval        (the app must already be up)
"""

import logging
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client  # noqa: E402
from langfuse.experiment import Evaluation  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
log = logging.getLogger(__name__)

DATASET_NAME = os.environ.get("LANGFUSE_DATASET_NAME", "agent-triage-qa")
APP_URL = os.environ.get("APP_URL", "http://localhost:8006")
REQUEST_TIMEOUT = float(os.environ.get("EVAL_TIMEOUT", "120"))

langfuse = get_client()

# (query, service the report must name, dependency it should surface)
SEED_ITEMS = [
    (
        "auth is showing errors. Triage the incident.",
        "auth",
        None,
    ),
    (
        "payments is showing errors. Triage the incident.",
        "payments",
        "ledger",
    ),
    (
        "catalog is showing errors. Triage the incident.",
        "catalog",
        "search-index",
    ),
    (
        "checkout is showing errors and high latency. Triage the incident.",
        "checkout",
        "payments",
    ),
]


def ensure_dataset() -> None:
    try:
        langfuse.get_dataset(DATASET_NAME)
        log.info("dataset '%s' already exists", DATASET_NAME)
        return
    except Exception:  # noqa: BLE001 - "not found" is untyped here
        pass

    langfuse.create_dataset(
        name=DATASET_NAME,
        description="Incident-triage smoke set for the OpenAI Agents workflow",
    )
    for query, service, dependency in SEED_ITEMS:
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            input={"query": query},
            expected_output={"service": service, "dependency": dependency},
        )
    log.info("created dataset '%s' with %d items", DATASET_NAME, len(SEED_ITEMS))


def task(*, item, **kwargs) -> str:
    """Run one dataset item through the live agent over HTTP."""
    response = httpx.post(
        f"{APP_URL}/ask",
        json={"query": item.input["query"], "user_id": "eval-harness"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["answer"]


def names_affected_service(*, input, output, expected_output, **kwargs):
    """The report is useless if it never names the service being triaged."""
    service = (expected_output or {}).get("service", "")
    hit = service.lower() in (output or "").lower()
    return Evaluation(name="names-service", value=1.0 if hit else 0.0)


def traces_dependency(*, input, output, expected_output, **kwargs):
    """Did it follow the dependency chain, or stop at the surface service?"""
    dependency = (expected_output or {}).get("dependency")
    if not dependency:
        # auth has no dependencies, so there is nothing to find. Not a failure.
        return Evaluation(
            name="traces-dependency", value=1.0, comment="no dependencies expected"
        )
    hit = dependency.lower() in (output or "").lower()
    return Evaluation(
        name="traces-dependency",
        value=1.0 if hit else 0.0,
        comment=f"looking for '{dependency}'",
    )


def cites_evidence(*, input, output, expected_output, **kwargs):
    """A triage report should quote telemetry, not just assert a conclusion."""
    text = (output or "").lower()
    markers = ("error_rate", "error rate", "p95", "%", "ms")
    found = [m for m in markers if m in text]
    return Evaluation(
        name="cites-evidence",
        value=1.0 if found else 0.0,
        comment=f"markers found: {found or 'none'}",
    )


def is_concise(*, input, output, expected_output, **kwargs):
    words = len((output or "").split())
    return Evaluation(
        name="concise", value=1.0 if words <= 300 else 0.0, comment=f"{words} words"
    )


def main() -> None:
    if not langfuse.auth_check():
        raise SystemExit(
            "Langfuse auth failed. Check LANGFUSE_* in .env against "
            "'make langfuse-keys' in ../../infra."
        )
    try:
        httpx.get(f"{APP_URL}/health", timeout=10).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"App not reachable at {APP_URL} — run 'make up' first. ({exc})")

    ensure_dataset()
    dataset = langfuse.get_dataset(DATASET_NAME)

    result = langfuse.run_experiment(
        name="agent-triage-eval",
        run_name=f"run-{os.environ.get('OPENAI_MODEL', 'unknown')}",
        data=dataset.items,
        task=task,
        evaluators=[names_affected_service, traces_dependency, cites_evidence, is_concise],
    )

    try:
        print(result.format())
    except Exception:  # noqa: BLE001 - formatting is a convenience only
        pass

    langfuse.flush()
    print(f"\nCompare runs in Langfuse -> Datasets -> {DATASET_NAME} -> Runs.")


if __name__ == "__main__":
    main()
