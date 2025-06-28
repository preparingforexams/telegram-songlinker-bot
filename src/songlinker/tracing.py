import httpx
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor  # pyright: ignore
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import Decision, StaticSampler
from telegram.request import HTTPXRequest

from songlinker.config import Config


def setup_tracing(config: Config) -> None:
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

    AsyncioInstrumentor().instrument()


class InstrumentedHttpxRequest(HTTPXRequest):
    def _build_client(self) -> httpx.AsyncClient:
        client = super()._build_client()
        HTTPXClientInstrumentor().instrument_client(client)
        return client
