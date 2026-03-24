# Contributing to Abidex

Thanks for your interest in contributing. Abidex is Phase 1: zero-code OpenTelemetry tracing for agentic AI workflows (CrewAI, LangGraph, Pydantic AI, and more).

## Getting started

1. **Fork and clone** the repo.
2. **Install in dev mode** with optional dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

3. **Run tests:**

   ```bash
   pytest
   ```

4. **Lint and type-check:**

   ```bash
   ruff check src/ tests/
   mypy src/
   ```

## Code style

- Use **Ruff** for formatting and linting (see `[tool.ruff]` in `pyproject.toml`).
- Type hints preferred for public APIs and new code.
- Keep patches in `src/abidex/patches/` minimal and idempotent (use a `_patched` flag to avoid double-patching).

## Adding a new framework patch

1. Add a new module under `src/abidex/patches/`, e.g. `src/abidex/patches/my_framework.py`.
2. Implement `apply_my_framework_patch() -> bool` that:
   - Imports the framework (so it’s optional).
   - Wraps the relevant entry points (e.g. `run`, `invoke`) with `get_tracer("my_framework")` and span creation.
   - Sets GenAI semantic attributes where possible (`gen_ai.agent.name`, `gen_ai.workflow.name`, etc.).
   - Returns `True` if patching succeeded, `False` otherwise.
3. Register the framework in `src/abidex/core.py` by adding it to `_FRAMEWORKS` and ensuring the patch module is loaded in `patch_all_detected()`.
4. Add tests (e.g. in `tests/`) that run with a mock or in-memory exporter and assert span names/attributes.

## Pull requests

- Open a PR against `main` with a clear description of the change.
- Ensure `pytest` and `ruff check` pass.
- For new features (e.g. a new framework), add to [docs/frameworks.md](docs/frameworks.md) and, if useful, an example in `examples/`.

## Bugs and feature ideas

- **Bugs and feature requests:** [GitHub Issues](https://github.com/abide-ai/abidex/issues).
- For “no spans” or “wrong attributes,” include: framework name and version, import order, and whether `ABIDEX_VERBOSE=true` was set.

## Scope

We’re focused on **Phase 1: execution observability**—workflow/agent/task spans and GenAI attributes. Deeper instrumentation (e.g. LLM call spans, token counts) and more frameworks are on the roadmap. If you’re unsure whether a change fits, open an issue first.

---

For usage, see the [README](README.md) and [docs/](docs/).
