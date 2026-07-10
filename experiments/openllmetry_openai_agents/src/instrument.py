"""OpenLLMetry setup for the OpenAI Agents metrics-gap experiment."""

import logging
import os

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry._logs import set_logger_provider
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments

log = logging.getLogger(__name__)

# The OpenAI Agents SDK uses an Omit sentinel internally. OpenLLMetry copies these
# into span attributes, causing noisy "invalid attribute type" warnings. Suppress them.
logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)

DURATION_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
TOKEN_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)


def init_instrumentation(app) -> None:
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    service_name = os.environ["OTEL_SERVICE_NAME"]
    resource = Resource.create({"service.name": service_name})

    # Set up MeterProvider with custom bucket views for accurate histogram quantiles.
    metric_exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
    duration_view = View(
        instrument_name="gen_ai.client.operation.duration",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=DURATION_BUCKETS),
    )
    token_view = View(
        instrument_name="gen_ai.client.token.usage",
        aggregation=ExplicitBucketHistogramAggregation(boundaries=TOKEN_BUCKETS),
    )
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
        views=[duration_view, token_view],
    ))

    # Traceloop handles traces + auto-instruments OpenAI SDK.
    # block_instruments: prevents Traceloop's default Agents instrumentor from
    # running alongside the SDK's built-in trace processor (avoids duplicates).
    # We install the Agents instrumentor manually below with replace_existing_processors=True
    # to remove the SDK's processor that uploads to OpenAI's /v1/traces/ingest.
    Traceloop.init(
        app_name=service_name,
        exporter=OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"),
        metrics_exporter=metric_exporter,
        resource_attributes={"service.name": service_name},
        disable_batch=True,
        block_instruments={Instruments.OPENAI_AGENTS},
    )

    from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor(replace_existing_processors=True).instrument()
    log.info("status=openai_agents_instrumented replace_existing_processors=true")

    # Logs
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        SimpleLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
    )
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(
        LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    )
    LoggingInstrumentor().instrument(set_logging_format=False)

    FastAPIInstrumentor.instrument_app(app)
    log.info("status=openllmetry_initialized service=%s endpoint=%s", service_name, endpoint)
