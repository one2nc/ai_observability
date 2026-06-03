"""OpenLLMetry instrumentation: auto-instruments OpenAI SDK + FastAPI."""

import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from traceloop.sdk import Traceloop

log = logging.getLogger(__name__)


def init_instrumentation(app=None) -> None:
    """Initialize OpenLLMetry (Traceloop) + logs export."""
    otlp_endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]
    service_name = os.environ["OTEL_SERVICE_NAME"]

    resource = Resource.create({"service.name": service_name})

    # Traceloop handles traces + metrics + auto-instruments OpenAI SDK
    trace_exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
    metric_exporter = OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics")

    Traceloop.init(
        app_name=service_name,
        exporter=trace_exporter,
        metrics_exporter=metric_exporter,
        resource_attributes={"service.name": service_name},
        disable_batch=True,
    )

    # Logs (Traceloop doesn't handle logs)
    log_exporter = OTLPLogExporter(endpoint=f"{otlp_endpoint}/v1/logs")
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
    set_logger_provider(log_provider)
    handler = LoggingHandler(level=logging.INFO, logger_provider=log_provider)
    logging.getLogger().addHandler(handler)
    LoggingInstrumentor().instrument(set_logging_format=False)

    log.info("status=openllmetry_initialized endpoint=%s service=%s", otlp_endpoint, service_name)

    if app:
        FastAPIInstrumentor.instrument_app(app)
        log.info("status=fastapi_instrumented")
