"""OpenLIT setup for the OpenAI Agents working-metrics experiment."""

import logging
import os

import openlit
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

log = logging.getLogger(__name__)


def init_instrumentation(app) -> None:
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    service_name = os.environ["OTEL_SERVICE_NAME"]

    openlit.init(
        service_name=service_name,
        environment="benchmark",
        otlp_endpoint=endpoint,
        disable_batch=True,
        capture_message_content=False,
        disable_metrics=False,
    )
    FastAPIInstrumentor.instrument_app(app)
    log.info("status=openlit_initialized service=%s endpoint=%s", service_name, endpoint)
