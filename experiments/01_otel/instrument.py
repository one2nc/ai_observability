"""Vanilla OpenTelemetry instrumentation: traces, metrics, logs exported via OTLP."""

import logging
import os

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

log = logging.getLogger(__name__)


def init_instrumentation(app=None) -> None:
    """Initialize OpenTelemetry traces, metrics, and logs with OTLP export."""
    otlp_endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]
    service_name = os.environ["OTEL_SERVICE_NAME"]

    resource = Resource.create({"service.name": service_name})

    # Traces
    trace_exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(SimpleSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # Metrics
    metric_exporter = OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics")
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
    metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)

    # Logs
    log_exporter = OTLPLogExporter(endpoint=f"{otlp_endpoint}/v1/logs")
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
    set_logger_provider(log_provider)
    handler = LoggingHandler(level=logging.INFO, logger_provider=log_provider)
    logging.getLogger().addHandler(handler)
    LoggingInstrumentor().instrument(set_logging_format=False)

    log.info("status=otel_initialized endpoint=%s service=%s", otlp_endpoint, service_name)

    if app:
        FastAPIInstrumentor.instrument_app(app)
        log.info("status=fastapi_instrumented")
