"""OpenLLMetry setup for the OpenAI Agents metrics-gap experiment."""

import logging
import os

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry._logs import set_logger_provider
from traceloop.sdk import Traceloop
from traceloop.sdk.instruments import Instruments

log = logging.getLogger(__name__)


def _drop_openai_omit_attributes() -> None:
    """Drop OpenAI's Omit sentinel before OTel logs invalid attribute warnings."""
    try:
        from openai import Omit
        import opentelemetry.attributes as otel_attributes
    except Exception:
        log.exception("status=openai_omit_attribute_filter_unavailable")
        return

    if getattr(otel_attributes._clean_attribute, "_drops_openai_omit", False):
        return

    original_clean_attribute = otel_attributes._clean_attribute

    def clean_attribute_without_openai_omit(key, value, max_len):
        if isinstance(value, Omit):
            return None
        return original_clean_attribute(key, value, max_len)

    clean_attribute_without_openai_omit._drops_openai_omit = True
    otel_attributes._clean_attribute = clean_attribute_without_openai_omit
    log.info("status=openai_omit_attribute_filter_installed")


def init_instrumentation(app) -> None:
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    service_name = os.environ["OTEL_SERVICE_NAME"]
    resource = Resource.create({"service.name": service_name})

    _drop_openai_omit_attributes()

    Traceloop.init(
        app_name=service_name,
        exporter=OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"),
        metrics_exporter=OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
        resource_attributes={"service.name": service_name},
        disable_batch=True,
        # OpenAI Agents has its own built-in trace processor. Traceloop's default
        # OpenAIAgentsInstrumentor adds another processor next to it; for this
        # experiment we replace existing processors so only the OTel processor exports.
        block_instruments={Instruments.OPENAI_AGENTS},
    )

    try:
        from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

        OpenAIAgentsInstrumentor(replace_existing_processors=True).instrument()
        log.info("status=openai_agents_instrumented replace_existing_processors=true")
    except Exception:
        log.exception("status=openai_agents_instrumentation_failed")

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
