import json

from abidex.log_patterns import load_log_pattern_config, resolve_log_patterns


def test_load_log_pattern_config_reads_logs_section(tmp_path, monkeypatch):
    config_path = tmp_path / "abidex.json"
    config_path.write_text(
        json.dumps(
            {
                "logs": {
                    "patterns": ["alpha_logs_*.jsonl", "beta_logs_*.jsonl"],
                    "auto_detect": False,
                }
            }
        )
    )

    monkeypatch.setenv("ABIDEX_CONFIG", str(config_path))

    config = load_log_pattern_config()

    assert config.patterns == ["alpha_logs_*.jsonl", "beta_logs_*.jsonl"]
    assert config.auto_detect is False
    assert config.source == config_path


def test_resolve_log_patterns_explicit_overrides_config(tmp_path, monkeypatch):
    config_path = tmp_path / "abidex.json"
    config_path.write_text(
        json.dumps(
            {
                "logs": {
                    "patterns": ["ignored.jsonl"],
                    "auto_detect": False,
                }
            }
        )
    )

    monkeypatch.setenv("ABIDEX_CONFIG", str(config_path))

    patterns = resolve_log_patterns("foo_logs_*.jsonl,bar_logs_*.jsonl")

    assert patterns == ["foo_logs_*.jsonl", "bar_logs_*.jsonl"]


def test_resolve_log_patterns_auto_detects(tmp_path, monkeypatch):
    config_path = tmp_path / "abidex.json"
    config_path.write_text(
        json.dumps(
            {
                "logs": {
                    "patterns": [],
                    "auto_detect": True,
                }
            }
        )
    )

    (tmp_path / "alpha_logs_20230101.jsonl").write_text("")
    (tmp_path / "beta_telemetry_001.jsonl").write_text("")
    (tmp_path / "misc.jsonl").write_text("")

    monkeypatch.setenv("ABIDEX_CONFIG", str(config_path))

    patterns = resolve_log_patterns(search_dir=tmp_path)

    assert "alpha_logs_*.jsonl" in patterns
    assert "beta_telemetry_*.jsonl" in patterns
    assert "misc.jsonl" in patterns
