"""OpenLIT setup that exports traces directly to Langfuse over OTLP."""

import base64
import logging
import os
from pathlib import Path

import openlit

log = logging.getLogger(__name__)


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def init_instrumentation(app) -> None:
    langfuse_host = os.environ["LANGFUSE_HOST"].rstrip("/")
    public_key = os.environ["LANGFUSE_PUBLIC_KEY"]
    secret_key = os.environ["LANGFUSE_SECRET_KEY"]
    service_name = os.environ["OTEL_SERVICE_NAME"]

    auth = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    endpoint = f"{langfuse_host}/api/public/otel"

    openlit.init(
        service_name=service_name,
        application_name=service_name,
        environment="benchmark",
        otlp_endpoint=endpoint,
        otlp_headers={"Authorization": f"Basic {auth}"},
        disable_batch=_truthy(os.environ.get("OPENLIT_DISABLE_BATCH"), False),
        capture_message_content=_truthy(os.environ.get("OPENLIT_CAPTURE_MESSAGE_CONTENT"), True),
        disable_metrics=True,
        disable_events=True,
        pricing_json=os.environ.get("OPENLIT_PRICING_JSON")
        or str(Path(__file__).with_name("pricing.empty.json")),
    )
    log.info("status=openlit_initialized backend=langfuse endpoint=%s", endpoint)
