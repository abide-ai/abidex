import os
os.environ['ABIDEX_AUTO'] = 'false'
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource

@pytest.fixture(scope='module')
def memory_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({'service.name': 'abidex-test'}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    try:
        yield exporter
    finally:
        trace.set_tracer_provider(previous)
        exporter.shutdown()

@pytest.fixture
def memory_exporter_cleared(memory_exporter):
    memory_exporter.clear()
    return memory_exporter