import json
import os
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from abidex import core
from abidex.config import ABIDEX_AUTO, ABIDEX_BUFFER_ENABLED, get_service_name
from abidex import otel_setup
from abidex import trace_buffer

app = typer.Typer(
    name="abidex",
    help="""[bold]Abidex[/bold] – zero-code OpenTelemetry tracing for AI agents (CrewAI, LangGraph, Pydantic AI, LlamaIndex, n8n).

[dim]Usage:[/dim] Import [cyan]abidex[/cyan] before your crew/graph; traces are created automatically.
For a persistent UI: set [cyan]OTEL_EXPORTER_OTLP_ENDPOINT[/cyan] (e.g. http://localhost:4317) and [cyan]pip install abidex[otlp][/cyan].
""",
    rich_markup_mode="rich",
)
console = Console()
TRUNCATE_LEN = 50


def _trunc(s: str | None, max_len: int = TRUNCATE_LEN) -> str:
    if s is None:
        return "—"
    t = str(s).strip()
    return (t[:max_len] + "…") if len(t) > max_len else t


def _status_display(span: dict) -> str:
    status_val = str(span.get("status") or "")
    if "error" in status_val.lower() or status_val == "StatusCode.ERROR":
        return "[red]✗ ERROR[/red]"
    return "[green]✓ OK[/green]"


def _get_patched_frameworks() -> list[str]:
    try:
        return core.patch_all_detected()
    except Exception:
        return []


def _filter_spans(spans: list[dict], filter_expr: str | None) -> list[dict]:
    if not filter_expr:
        return spans
    filter_str = filter_expr.strip().lower()
    if "=" in filter_expr:
        key, _, value = filter_expr.partition("=")
        key, value = key.strip().lower(), value.strip().lower()
        out = []
        for s in spans:
            attrs = s.get("attributes") or {}
            for k, v in attrs.items():
                if key in k.lower() and value in str(v).lower():
                    out.append(s)
                    break
        return out
    return [s for s in spans if filter_str in str(s.get("attributes") or {}).lower()]


@app.command()
def status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show extra detail"),
) -> None:
    """Show config: ABIDEX_AUTO, OTEL endpoint, patched frameworks, last run hint."""
    otel_endpoint_raw = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    current_exporter = otel_endpoint_raw or "console"
    service = get_service_name() or "(default: abidex)"
    patched = _get_patched_frameworks()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold blue")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("ABIDEX_AUTO", f"{'✅ true' if ABIDEX_AUTO else 'false'}")
    table.add_row("OTEL_SERVICE_NAME", service)
    table.add_row("OTEL_EXPORTER_OTLP_ENDPOINT", otel_endpoint_raw or "[dim](not set → console)[/dim]")
    table.add_row("Patched frameworks", ", ".join(patched) if patched else "[dim]none (run agent code first)[/dim]")
    table.add_row("Buffer enabled", f"{'✅' if ABIDEX_BUFFER_ENABLED else '—'} {str(ABIDEX_BUFFER_ENABLED)}")

    if ABIDEX_BUFFER_ENABLED:
        n = trace_buffer.buffer_len()
        table.add_row("Trace buffer", f"⏱️ {n} span(s)")
        if n > 0 and verbose:
            spans = trace_buffer.get_recent_spans(1)
            if spans and spans[0].get("end_time_ns"):
                ns = spans[0]["end_time_ns"]
                try:
                    sec = ns / 1e9
                    table.add_row("Last span (approx)", datetime.fromtimestamp(sec).isoformat()[:19] + "Z")
                except Exception:
                    pass

    console.print(Panel(table, title="[bold] abidex status [/bold]", border_style="blue", padding=(0, 1)))
    console.print()
    console.print(f"Current OTEL exporter: [cyan]{current_exporter}[/cyan]")
    if not otel_endpoint_raw:
        console.print("[yellow]Tip:[/yellow] To see persistent traces, start SigNoz or Uptrace and set [cyan]OTEL_EXPORTER_OTLP_ENDPOINT[/cyan] (e.g. http://localhost:4317). Run [cyan]abidex init[/cyan] for Docker commands.")
    console.print("[dim]For persistent traces + UI:[/dim]")
    console.print("  [dim]SigNoz[/dim] → docker-compose from signoz repo → [cyan]http://localhost:4317[/cyan]")
    console.print("  [dim]Uptrace[/dim] → docker run uptrace/uptrace → [cyan]http://localhost:14317[/cyan]")


trace_app = typer.Typer(help="Inspect or export trace spans.")

@trace_app.command("last")
def trace_last(
    n: int = typer.Argument(10, help="Number of spans to show"),
    filter_attr: str | None = typer.Option(None, "--filter", "-f", help='Filter by attribute, e.g. "role=Researcher"'),
    file_path: Path | None = typer.Option(None, "--file", help="Read from JSONL file instead of buffer"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full attributes"),
) -> None:
    """Pretty table of last N spans: name, duration, role/goal, start time.

    After running your agent (with ABIDEX_BUFFER_ENABLED=true or --file), use this to view recent spans.
    """
    if file_path is not None:
        if not file_path.exists():
            console.print(f"[red]⚠️ File not found: {file_path}[/red]")
            raise typer.Exit(1)
        spans = [json.loads(line) for line in file_path.read_text().strip().splitlines() if line.strip()]
    else:
        with console.status("[bold blue]Fetching recent traces...", spinner="dots"):
            spans = trace_buffer.get_recent_spans(trace_buffer.BUFFER_MAX)

    if not spans:
        console.print("[yellow]⚠️ No spans in buffer.[/yellow] Run a traced workflow (set ABIDEX_BUFFER_ENABLED=true) or use [cyan]--file[/cyan].")
        raise typer.Exit(0)

    spans = list(reversed(spans))[: n * 3]
    spans = _filter_spans(spans, filter_attr)[:n]

    if not spans:
        console.print("[yellow]⚠️ No spans match filter.[/yellow]")
        raise typer.Exit(0)

    table = Table(box=box.ROUNDED, header_style="bold blue", title=f"Last {len(spans)} span(s)")
    table.add_column("Name", style="bold blue", max_width=40, overflow="ellipsis")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Role / Goal", max_width=TRUNCATE_LEN + 2, overflow="ellipsis")
    table.add_column("Start", style="dim")

    for s in reversed(spans):
        name = s.get("name", "?")
        attrs = s.get("attributes") or {}
        start_ns = s.get("start_time_ns")
        end_ns = s.get("end_time_ns")
        duration_ms = (end_ns - start_ns) / 1e6 if (start_ns and end_ns) else None
        if duration_ms is not None:
            dur_style = "yellow" if duration_ms > 1000 else "green"
            dur_str = f"{duration_ms:.0f} ms"
        else:
            dur_style = "dim"
            dur_str = "—"
        role = _trunc(attrs.get("gen_ai.agent.role") or attrs.get("gen_ai.agent.name"))
        goal = _trunc(attrs.get("gen_ai.agent.goal") or attrs.get("gen_ai.task.goal"))
        role_goal = role if role != "—" else goal
        if start_ns:
            try:
                start_str = datetime.fromtimestamp(start_ns / 1e9).strftime("%H:%M:%S")
            except Exception:
                start_str = str(start_ns)[:12]
        else:
            start_str = "—"
        table.add_row(name, f"[{dur_style}]{dur_str}[/{dur_style}]", _status_display(s), role_goal, start_str)

    console.print(table)
    if verbose:
        for i, s in enumerate(reversed(spans), 1):
            console.print(Panel(json.dumps(s.get("attributes") or {}, indent=2)[:500], title=f"Span {i} attributes", border_style="dim"))


@trace_app.command("export")
def trace_export(
    format: str = typer.Option("jsonl", "--format", "-f", help="Output format: jsonl or pretty"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file (required for jsonl)"),
    last: int | None = typer.Option(None, "--last", "-n", help="Limit to last N spans (default for pretty: 10)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Export recent spans: jsonl to file or pretty (colored JSON) to terminal."""
    n = last if last is not None else (10 if format == "pretty" else trace_buffer.BUFFER_MAX)
    with console.status("[bold blue]Fetching recent traces...", spinner="dots"):
        spans = trace_buffer.get_recent_spans(n)

    if not spans:
        console.print("[yellow]⚠️ No spans in buffer.[/yellow]")
        raise typer.Exit(0)

    if format == "jsonl":
        if output is None:
            console.print("[red]⚠️ --output required for jsonl.[/red]")
            raise typer.Exit(1)
        trace_buffer.export_to_jsonl(str(output), n)
        console.print(f"[green]✅ Exported {len(spans)} span(s) to [bold]{output}[/bold][/green]")
    elif format == "pretty":
        console.print_json(data=spans, indent=2)
    else:
        console.print(f"[red]Unknown format: {format}. Use jsonl or pretty.[/red]")
        raise typer.Exit(1)


app.add_typer(trace_app, name="trace")


@app.command("init")
def init_cmd() -> None:
    """Print .env template and docker run commands for SigNoz and Uptrace."""
    env_lines = [
        "# Abidex – Phase 1",
        "ABIDEX_AUTO=true",
        "OTEL_SERVICE_NAME=my-agent-app",
        "# Uncomment for persistent traces:",
        "# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317",
    ]
    env_path = Path(".env")
    if env_path.exists():
        console.print("[yellow]⚠️ .env exists; not overwriting.[/yellow]")
    else:
        env_path.write_text("\n".join(env_lines) + "\n")
        console.print(f"[green]✅ Wrote [bold].env[/bold][/green]")

    console.print()
    table = Table(box=box.ROUNDED, header_style="bold blue", title="Docker one-liners")
    table.add_column("Backend", style="cyan")
    table.add_column("Command", style="green")
    table.add_row("SigNoz", "git clone https://github.com/signoz/signoz.git && cd signoz/deploy && docker compose -f docker/clickhouse-setup/docker-compose.yaml up -d")
    table.add_row("", "UI: http://localhost:3301  →  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317")
    table.add_row("Uptrace", "docker run -d -p 14317:4317 -p 14318:4318 --name uptrace -e UPTRACE_DSN=postgres://uptrace:uptrace@host.docker.internal:5432/uptrace uptrace/uptrace:latest")
    table.add_row("", "UI: http://localhost:14318  →  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317")
    console.print(Panel(table, border_style="blue", padding=(0, 1)))


@app.command()
def summary(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Simple stats: avg latency per agent/role, total spans, error count."""
    with console.status("[bold blue]Fetching recent traces...", spinner="dots"):
        spans = trace_buffer.get_recent_spans(trace_buffer.BUFFER_MAX)

    if not spans:
        console.print("[yellow]⚠️ No spans in buffer.[/yellow]")
        raise typer.Exit(0)

    by_name: dict[str, list[dict]] = {}
    errors = 0
    total_duration_ns = 0
    count_with_duration = 0
    total_tokens = 0

    for s in spans:
        name = s.get("name", "?")
        by_name.setdefault(name, []).append(s)
        if str(s.get("status", "")).lower().find("error") >= 0:
            errors += 1
        start, end = s.get("start_time_ns"), s.get("end_time_ns")
        if start and end:
            total_duration_ns += end - start
            count_with_duration += 1
        attrs = s.get("attributes") or {}
        for k, v in attrs.items():
            if "token" in k.lower():
                try:
                    total_tokens += int(v)
                except (TypeError, ValueError):
                    pass

    table = Table(box=box.ROUNDED, header_style="bold blue", title="⏱️ Span summary")
    table.add_column("Name", style="blue", max_width=45, overflow="ellipsis")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Avg duration (ms)", justify="right", style="yellow")
    for name, group in sorted(by_name.items(), key=lambda x: -len(x[1])):
        durs = [g.get("end_time_ns", 0) - g.get("start_time_ns", 0) for g in group if g.get("start_time_ns") and g.get("end_time_ns")]
        avg_ms = (sum(durs) / len(durs)) / 1e6 if durs else None
        table.add_row(name, str(len(group)), f"{avg_ms:.2f}" if avg_ms is not None else "—")

    console.print(table)
    avg_all = (total_duration_ns / count_with_duration) / 1e6 if count_with_duration else None
    console.print()
    console.print(f"  [bold]Total spans:[/bold] {len(spans)}  [bold]With duration:[/bold] {count_with_duration}  [bold]Avg (all):[/bold] {avg_all:.2f} ms" if avg_all else f"  [bold]Total spans:[/bold] {len(spans)}")
    if total_tokens:
        console.print(f"  [bold]Total tokens:[/bold] {total_tokens}")
    if errors:
        console.print(f"  [red]⚠️ Spans with error status: {errors}[/red]")
    else:
        console.print("  [green]✅ No errors in spans[/green]")


if __name__ == "__main__":
    app()
