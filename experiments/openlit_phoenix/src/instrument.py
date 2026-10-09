"""OpenLIT setup for the Phoenix trace sink experiment."""

import logging
import os

import openlit
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource

log = logging.getLogger(__name__)

DURATION_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
TOKEN_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
COST_BUCKETS = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def init_instrumentation(app) -> None:
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    service_name = os.environ["OTEL_SERVICE_NAME"]
    capture_message_content = env_bool("OPENLIT_CAPTURE_MESSAGE_CONTENT", True)
    resource = Resource.create({"service.name": service_name, "deployment.environment": "benchmark"})

    # Set up MeterProvider with custom bucket views BEFORE openlit.init()
    # so OpenLIT reuses it (it checks for existing MeterProvider).
    duration_view = View(
        instrument_name="gen_ai.client.operation.duration",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=DURATION_BUCKETS),
    )
    server_duration_view = View(
        instrument_name="gen_ai.server.request.duration",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=DURATION_BUCKETS),
    )
    ttft_view = View(
        instrument_name="gen_ai.server.time_to_first_token",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=DURATION_BUCKETS),
    )
    token_view = View(
        instrument_name="gen_ai.client.token.usage",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=TOKEN_BUCKETS),
    )
    cost_view = View(
        instrument_name="gen_ai.usage.cost",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=COST_BUCKETS),
    )
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        export_interval_millis=5000,
    )
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
        views=[duration_view, server_duration_view, ttft_view, token_view, cost_view],
    ))

    openlit.init(
        service_name=service_name,
        environment="benchmark",
        otlp_endpoint=endpoint,
        disable_batch=True,
        capture_message_content=capture_message_content,
        disable_metrics=False,
    )
    FastAPIInstrumentor.instrument_app(app)
    log.info(
        "status=openlit_initialized service=%s endpoint=%s capture_message_content=%s",
        service_name,
        endpoint,
        capture_message_content,
    )
