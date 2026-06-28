"""Manual OTel instrumentation setup: traces, metrics, logs via OTLP."""

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
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.logging import LoggingInstrumentor

log = logging.getLogger(__name__)


def init_instrumentation(app) -> None:
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    service_name = os.environ["OTEL_SERVICE_NAME"]
    resource = Resource.create({"service.name": service_name})

    # Traces
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(trace_provider)

    # Metrics
    duration_buckets = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
    token_buckets = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)

    duration_view = View(
        instrument_name="gen_ai.client.operation.duration",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=duration_buckets),
    )
    token_view = View(
        instrument_name="gen_ai.client.token.usage",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=token_buckets),
    )

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        export_interval_millis=5000,
    )
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
        views=[duration_view, token_view],
    ))

    # Logs
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(
        SimpleLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
    )
    set_logger_provider(log_provider)
    logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=log_provider))
    LoggingInstrumentor().instrument(set_logging_format=False)

    # FastAPI
    FastAPIInstrumentor.instrument_app(app)
    log.info("status=otel_initialized service=%s endpoint=%s", service_name, endpoint)
