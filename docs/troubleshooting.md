# Troubleshooting

| Issue | Fix |
|-------|-----|
| **No spans** | Import `abidex` **before** CrewAI/LangGraph/Pydantic AI. |
| **Spans only in console** | Set `OTEL_EXPORTER_OTLP_ENDPOINT`, install `abidex[otlp]`, run `abidex backend start` or your own backend. |
| **CLI says "No spans in buffer"** | Buffer is per-process. Call `trace_buffer.export_to_jsonl("spans.ndjson", 100)` in your script, then `abidex trace last` (or use `abidex run main.py`). |
| **Wrong or missing attributes** | Run with `ABIDEX_VERBOSE=true`. Check you're using standard entry points (e.g. `crew.kickoff`, `compiled.invoke`). |
| **Tests failing / double traces** | Set `ABIDEX_AUTO=false` in tests. |
