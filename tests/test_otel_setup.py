from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import ProxyTracerProvider

from abidex import otel_setup


class DummyExporter(SpanExporter):
    def export(self, spans):
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        return True


def test_init_otel_skips_when_sdk_provider_present(monkeypatch):
    provider = TracerProvider()
    monkeypatch.setattr(otel_setup, "_initialized", False)
    monkeypatch.setattr(otel_setup.trace, "get_tracer_provider", lambda: provider)

    set_calls = []

    def fake_set_tracer_provider(value):
        set_calls.append(value)

    monkeypatch.setattr(otel_setup.trace, "set_tracer_provider", fake_set_tracer_provider)

    otel_setup.init_otel()

    assert set_calls == []
    assert otel_setup._initialized is True


def test_init_otel_sets_provider_for_non_sdk_provider(monkeypatch):
    monkeypatch.setattr(otel_setup, "_initialized", False)
    monkeypatch.setattr(otel_setup.trace, "get_tracer_provider", lambda: object())
    monkeypatch.setattr(otel_setup, "ABIDEX_BUFFER_ENABLED", False)
    monkeypatch.setattr(otel_setup, "_get_exporter", lambda: DummyExporter())

    set_calls = []

    def fake_set_tracer_provider(value):
        set_calls.append(value)

    monkeypatch.setattr(otel_setup.trace, "set_tracer_provider", fake_set_tracer_provider)

    otel_setup.init_otel(service_name="test-service")

    assert len(set_calls) == 1
    assert isinstance(set_calls[0], TracerProvider)
    assert otel_setup._initialized is True


def test_init_otel_sets_provider_for_proxy_tracer_provider(monkeypatch):
    """Regression for #30: default global provider is ProxyTracerProvider, not NoOp."""
    monkeypatch.setattr(otel_setup, "_initialized", False)
    monkeypatch.setattr(otel_setup.trace, "get_tracer_provider", lambda: ProxyTracerProvider())
    monkeypatch.setattr(otel_setup, "ABIDEX_BUFFER_ENABLED", False)
    monkeypatch.setattr(otel_setup, "_get_exporter", lambda: DummyExporter())

    set_calls = []

    def fake_set_tracer_provider(value):
        set_calls.append(value)

    monkeypatch.setattr(otel_setup.trace, "set_tracer_provider", fake_set_tracer_provider)

    otel_setup.init_otel(service_name="test-service")

    assert len(set_calls) == 1
    assert isinstance(set_calls[0], TracerProvider)
    assert otel_setup._initialized is True
