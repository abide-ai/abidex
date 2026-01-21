import json

from abidex.config import (
    resolve_collector_settings,
    resolve_otlp_settings,
)


def test_resolve_collector_settings_defaults(monkeypatch):
    monkeypatch.delenv("ABIDEX_COLLECTOR_HOST", raising=False)
    monkeypatch.delenv("ABIDEX_COLLECTOR_PORT", raising=False)
    monkeypatch.delenv("ABIDEX_CONFIG", raising=False)

    settings = resolve_collector_settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_resolve_collector_settings_env_overrides_config(tmp_path, monkeypatch):
    config_path = tmp_path / "abidex.json"
    config_path.write_text(
        json.dumps(
            {
                "collector": {
                    "host": "0.0.0.0",
                    "port": 9000,
                }
            }
        )
    )

    monkeypatch.setenv("ABIDEX_CONFIG", str(config_path))
    monkeypatch.setenv("ABIDEX_COLLECTOR_HOST", "127.0.0.2")
    monkeypatch.setenv("ABIDEX_COLLECTOR_PORT", "9100")

    settings = resolve_collector_settings()

    assert settings.host == "127.0.0.2"
    assert settings.port == 9100


def test_resolve_otlp_settings_accepts_full_traces_endpoint(tmp_path, monkeypatch):
    config_path = tmp_path / "abidex.json"
    config_path.write_text(
        json.dumps(
            {
                "otel": {
                    "endpoint": "http://localhost:4318/v1/traces",
                }
            }
        )
    )

    monkeypatch.setenv("ABIDEX_CONFIG", str(config_path))
    monkeypatch.delenv("ABIDEX_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("ABIDEX_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("ABIDEX_OTLP_METRICS_ENDPOINT", raising=False)

    settings = resolve_otlp_settings()

    assert settings.traces_endpoint == "http://localhost:4318/v1/traces"
    assert settings.metrics_endpoint == "http://localhost:4318/v1/metrics"


def test_resolve_otlp_settings_parses_headers_env(monkeypatch):
    monkeypatch.delenv("ABIDEX_CONFIG", raising=False)
    monkeypatch.delenv("ABIDEX_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("ABIDEX_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("ABIDEX_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.setenv("ABIDEX_OTLP_HEADERS", "api-key=secret,env=prod")

    settings = resolve_otlp_settings()

    assert settings.headers == {"api-key": "secret", "env": "prod"}
