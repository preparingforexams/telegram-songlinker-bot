import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import Decision, StaticSampler
from telegram.request import HTTPXRequest

if TYPE_CHECKING:
    import httpx

    from songlinker.config import Config


def setup_telemetry(config: Config) -> None:
    resource = Resource(attributes={SERVICE_NAME: "telegram-songlinker-bot"})

    trace_provider = TracerProvider(
        resource=resource,
        sampler=StaticSampler(Decision.RECORD_AND_SAMPLE),
    )

    if config.enable_telemetry:
        exporter = OTLPSpanExporter()
        processor = BatchSpanProcessor(exporter)
        trace_provider.add_span_processor(processor)

    trace.set_tracer_provider(trace_provider)

    if config.enable_telemetry:
        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)
        log_exporter = OTLPLogExporter()
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        handler = LoggingHandler(logger_provider=logger_provider)
        logging.root.addHandler(handler)

    AsyncioInstrumentor().instrument()
    LoggingInstrumentor().instrument()


class InstrumentedHttpxRequest(HTTPXRequest):
    def _build_client(self) -> httpx.AsyncClient:
        client = super()._build_client()
        HTTPXClientInstrumentor().instrument_client(client)
        return client
