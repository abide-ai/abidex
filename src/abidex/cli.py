import json
import os
import runpy
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

SIGNOZ_DIR = Path.home() / ".abidex" / "signoz"
SIGNOZ_DEPLOY = SIGNOZ_DIR / "deploy" / "docker"
SIGNOZ_UI_URL = "http://localhost:8080"
OTLP_GRPC_PORT = 4317
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box
from abidex import core
from abidex.config import ABIDEX_AUTO, ABIDEX_BUFFER_ENABLED, ABIDEX_LOGS_ENABLED, get_service_name
from abidex import otel_setup
from abidex import trace_buffer
from abidex import log_buffer
app = typer.Typer(name='abidex', help='[bold]Abidex[/bold] – zero-code OpenTelemetry tracing for AI agents (CrewAI, LangGraph, Pydantic AI, LlamaIndex, n8n).\n\n[dim]Usage:[/dim] Import [cyan]abidex[/cyan] before your crew/graph; traces are created automatically.\nFor a persistent UI: set [cyan]OTEL_EXPORTER_OTLP_ENDPOINT[/cyan] (e.g. http://localhost:4317) and [cyan]pip install abidex[otlp][/cyan].\n', rich_markup_mode='rich')
console = Console()
TRUNCATE_LEN = 50
def _trunc(s: str | None, max_len: int=TRUNCATE_LEN) -> str:
    if s is None:
        return '—'
    t = str(s).strip()
    return t[:max_len] + '…' if len(t) > max_len else t
def _status_display(span: dict) -> str:
    status_val = str(span.get('status') or '')
    if 'error' in status_val.lower() or status_val == 'StatusCode.ERROR':
        return '[red]✗ ERROR[/red]'
    return '[green]✓ OK[/green]'
def _get_patched_frameworks() -> list[str]:
    try:
        return core.patch_all_detected()
    except Exception:
        return []
def _filter_spans(spans: list[dict], filter_expr: str | None) -> list[dict]:
    if not filter_expr:
        return spans
    filter_str = filter_expr.strip().lower()
    if '=' in filter_expr:
        key, _, value = filter_expr.partition('=')
        key, value = (key.strip().lower(), value.strip().lower())
        out = []
        for s in spans:
            attrs = s.get('attributes') or {}
            for k, v in attrs.items():
                if key in k.lower() and value in str(v).lower():
                    out.append(s)
                    break
        return out
    return [s for s in spans if filter_str in str(s.get('attributes') or {}).lower()]
@app.command()
def status(verbose: bool=typer.Option(False, '--verbose', '-v', help='Show extra detail')) -> None:
    otel_endpoint_raw = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT')
    current_exporter = otel_endpoint_raw or 'console'
    service = get_service_name() or '(default: abidex)'
    patched = _get_patched_frameworks()
    table = Table(box=box.ROUNDED, show_header=True, header_style='bold blue')
    table.add_column('Setting', style='cyan')
    table.add_column('Value', style='green')
    table.add_row('ABIDEX_AUTO', f"{('✅ true' if ABIDEX_AUTO else 'false')}")
    table.add_row('OTEL_SERVICE_NAME', service)
    table.add_row('OTEL_EXPORTER_OTLP_ENDPOINT', otel_endpoint_raw or '[dim](not set → console)[/dim]')
    table.add_row('Patched frameworks', ', '.join(patched) if patched else '[dim]none (run agent code first)[/dim]')
    table.add_row('Buffer enabled', f"{('✅' if ABIDEX_BUFFER_ENABLED else '—')} {str(ABIDEX_BUFFER_ENABLED)}")
    table.add_row('Logs enabled', f"{('✅' if ABIDEX_LOGS_ENABLED else '—')} {str(ABIDEX_LOGS_ENABLED)}")
    if ABIDEX_BUFFER_ENABLED:
        n = trace_buffer.buffer_len()
        table.add_row('Trace buffer', f'⏱️ {n} span(s)')
    if ABIDEX_LOGS_ENABLED:
        ln = log_buffer.buffer_len()
        table.add_row('Log buffer', f'📋 {ln} log(s)')
        if n > 0 and verbose:
            spans = trace_buffer.get_recent_spans(1)
            if spans and spans[0].get('end_time_ns'):
                ns = spans[0]['end_time_ns']
                try:
                    sec = ns / 1000000000.0
                    table.add_row('Last span (approx)', datetime.fromtimestamp(sec).isoformat()[:19] + 'Z')
                except Exception:
                    pass
    console.print(Panel(table, title='[bold] abidex status [/bold]', border_style='blue', padding=(0, 1)))
    console.print()
    console.print(f'Current OTEL exporter: [cyan]{current_exporter}[/cyan]')
    if not otel_endpoint_raw:
        console.print('[yellow]Tip:[/yellow] Run [cyan]abidex backend start[/cyan] to start SigNoz and open the UI, then set [cyan]OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317[/cyan]. Or use [cyan]abidex init[/cyan] for manual Docker commands.')
    console.print('[dim]For persistent traces + UI:[/dim]')
    console.print('  [dim]SigNoz[/dim] → docker-compose from signoz repo → [cyan]http://localhost:4317[/cyan]')
    console.print('  [dim]Uptrace[/dim] → docker run uptrace/uptrace → [cyan]http://localhost:14317[/cyan]')
DEFAULT_SPANS_FILE = Path("spans.ndjson")
DEFAULT_TRACES_DIR = Path("traces")
DEFAULT_LOGS_DIR = Path("logs")


def _find_latest_spans_file() -> Path | None:
    """Find spans: spans.ndjson, or latest traces/spans_*.ndjson."""
    if DEFAULT_SPANS_FILE.exists():
        return DEFAULT_SPANS_FILE
    traces_dir = Path.cwd() / DEFAULT_TRACES_DIR
    if traces_dir.exists():
        candidates = sorted(traces_dir.glob("spans_*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0]
    return None


def _find_latest_logs_file() -> Path | None:
    """Find logs: latest logs/logs_*.ndjson (prefer) or logs/logs.ndjson."""
    logs_dir = Path.cwd() / DEFAULT_LOGS_DIR
    if logs_dir.exists():
        candidates = sorted(logs_dir.glob("logs_*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0]
        if (logs_dir / "logs.ndjson").exists():
            return logs_dir / "logs.ndjson"
    return None


def _list_span_files() -> None:
    """Print span files with relative path and position (newest first)."""
    cwd = Path.cwd()
    files = []
    if DEFAULT_SPANS_FILE.exists():
        files.append((DEFAULT_SPANS_FILE, DEFAULT_SPANS_FILE.stat().st_mtime))
    traces_dir = cwd / DEFAULT_TRACES_DIR
    if traces_dir.exists():
        for p in traces_dir.glob("spans_*.ndjson"):
            files.append((p, p.stat().st_mtime))
    files.sort(key=lambda x: x[1], reverse=True)
    if not files:
        console.print(f'[yellow]⚠️ No span files.[/yellow] Expected [cyan]{DEFAULT_TRACES_DIR}/spans_*.ndjson[/cyan] or [cyan]{DEFAULT_SPANS_FILE}[/cyan]')
        return
    table = Table(box=box.ROUNDED, header_style='bold blue', title='Trace span files (newest first)')
    table.add_column('#', justify='right', style='dim', width=4)
    table.add_column('Relative path', style='cyan')
    table.add_column('Filename', style='green')
    for i, (path, _) in enumerate(files, 1):
        try:
            rel = path.relative_to(cwd)
        except ValueError:
            rel = path
        table.add_row(str(i), str(rel), path.name)
    console.print(table)


def _count_logs_in_latest() -> tuple[int, Path | None]:
    """Return (total_log_count, latest_log_path or None)."""
    latest = _find_latest_logs_file()
    if not latest or not latest.exists():
        return (0, None)
    lines = [l for l in latest.read_text().strip().splitlines() if l.strip()]
    return (len(lines), latest)


def _list_log_files() -> None:
    """Print log files with relative path and position (newest first)."""
    cwd = Path.cwd()
    logs_dir = cwd / DEFAULT_LOGS_DIR
    files = []
    if logs_dir.exists():
        files = sorted(logs_dir.glob("*.ndjson"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        console.print(f'[yellow]⚠️ No log files.[/yellow] Expected [cyan]{DEFAULT_LOGS_DIR}/logs_*.ndjson[/cyan]')
        return
    table = Table(box=box.ROUNDED, header_style='bold blue', title='Log files (newest first)')
    table.add_column('#', justify='right', style='dim', width=4)
    table.add_column('Relative path', style='cyan')
    table.add_column('Filename', style='green')
    for i, path in enumerate(files, 1):
        try:
            rel = path.relative_to(cwd)
        except ValueError:
            rel = path
        table.add_row(str(i), str(rel), path.name)
    console.print(table)


def _load_spans_from_buffer_or_file(file_path: Path | None) -> tuple[list[dict], Path | None]:
    """Return (spans, source_file or None if from buffer)."""
    if file_path is not None:
        if not file_path.exists():
            return ([], file_path)
        raw = file_path.read_text().strip().splitlines()
        spans = [json.loads(line) for line in raw if line.strip()]
        return (spans, file_path)
    spans = trace_buffer.get_recent_spans(trace_buffer.BUFFER_MAX)
    if spans:
        return (spans, None)
    # Fallback: buffer empty, try default files
    latest = _find_latest_spans_file()
    if latest:
        raw = latest.read_text().strip().splitlines()
        spans = [json.loads(line) for line in raw if line.strip()]
        return (spans, latest)
    return ([], None)


def _render_spans_table(spans: list[dict], n: int, filter_attr: str | None, verbose: bool) -> None:
    """Render spans as a table (shared by trace last and run)."""
    spans = list(reversed(spans))[:n * 3]
    spans = _filter_spans(spans, filter_attr)[:n]
    if not spans:
        console.print('[yellow]⚠️ No spans match filter.[/yellow]')
        return
    table = Table(box=box.ROUNDED, header_style='bold blue', title=f'Last {len(spans)} span(s)')
    table.add_column('Name', style='bold blue', max_width=40, overflow='ellipsis')
    table.add_column('Duration', justify='right', style='green')
    table.add_column('Status', justify='center')
    table.add_column('Role / Goal', max_width=TRUNCATE_LEN + 2, overflow='ellipsis')
    table.add_column('Start', style='dim')
    for s in reversed(spans):
        name = s.get('name', '?')
        attrs = s.get('attributes') or {}
        start_ns = s.get('start_time_ns')
        end_ns = s.get('end_time_ns')
        duration_ms = (end_ns - start_ns) / 1000000.0 if start_ns and end_ns else None
        if duration_ms is not None:
            dur_style = 'yellow' if duration_ms > 1000 else 'green'
            dur_str = f'{duration_ms:.0f} ms'
        else:
            dur_style = 'dim'
            dur_str = '—'
        role = _trunc(attrs.get('gen_ai.agent.role') or attrs.get('gen_ai.agent.name'))
        goal = _trunc(attrs.get('gen_ai.agent.goal') or attrs.get('gen_ai.task.goal'))
        role_goal = role if role != '—' else goal
        if start_ns:
            try:
                start_str = datetime.fromtimestamp(start_ns / 1000000000.0).strftime('%H:%M:%S')
            except Exception:
                start_str = str(start_ns)[:12]
        else:
            start_str = '—'
        table.add_row(name, f'[{dur_style}]{dur_str}[/{dur_style}]', _status_display(s), role_goal, start_str)
    console.print(table)
    if verbose:
        for i, s in enumerate(reversed(spans), 1):
            console.print(Panel(json.dumps(s.get('attributes') or {}, indent=2)[:500], title=f'Span {i} attributes', border_style='dim'))


trace_app = typer.Typer(help='Inspect or export trace spans.', invoke_without_command=True)


@trace_app.callback()
def trace_callback(ctx: typer.Context) -> None:
    """When no subcommand: list span files with relative paths (newest first)."""
    if ctx.invoked_subcommand is not None:
        return
    _list_span_files()
    raise typer.Exit(0)


@trace_app.command('last')
def trace_last(n: int=typer.Argument(10, help='Number of spans to show'), filter_attr: str | None=typer.Option(None, '--filter', '-f', help='Filter by attribute, e.g. "role=Researcher"'), file_path: Path | None=typer.Option(None, '--file', help='Read from JSONL file instead of buffer (default: spans.ndjson if buffer empty)'), verbose: bool=typer.Option(False, '--verbose', '-v', help='Show full attributes')) -> None:
    spans, source = _load_spans_from_buffer_or_file(file_path)
    if source is not None and not spans:
        if not source.exists():
            console.print(f'[red]⚠️ File not found: {source}[/red]')
            raise typer.Exit(1)
        console.print(f'[yellow]⚠️ No spans in file.[/yellow] File [cyan]{source}[/cyan] is empty or has no valid JSONL spans.')
        raise typer.Exit(0)
    if not spans:
        console.print('[yellow]⚠️ No spans in buffer.[/yellow] Run [cyan]abidex run main.py[/cyan] or a traced workflow (set ABIDEX_BUFFER_ENABLED=true), or use [cyan]--file[/cyan] with an exported JSONL file.')
        raise typer.Exit(0)
    _render_spans_table(spans, n, filter_attr, verbose)
@trace_app.command('export')
def trace_export(format: str=typer.Option('jsonl', '--format', '-f', help='Output format: jsonl or pretty'), output: Path | None=typer.Option(None, '--output', '-o', help='Output file (required for jsonl)'), last: int | None=typer.Option(None, '--last', '-n', help='Limit to last N spans (default for pretty: 10)'), verbose: bool=typer.Option(False, '--verbose', '-v')) -> None:
    n = last if last is not None else 10 if format == 'pretty' else trace_buffer.BUFFER_MAX
    with console.status('[bold blue]Fetching recent traces...', spinner='dots'):
        spans = trace_buffer.get_recent_spans(n)
    if not spans:
        console.print('[yellow]⚠️ No spans in buffer.[/yellow]')
        raise typer.Exit(0)
    if format == 'jsonl':
        if output is None:
            console.print('[red]⚠️ --output required for jsonl.[/red]')
            raise typer.Exit(1)
        trace_buffer.export_to_jsonl(str(output), n)
        console.print(f'[green]✅ Exported {len(spans)} span(s) to [bold]{output}[/bold][/green]')
    elif format == 'pretty':
        console.print_json(data=spans, indent=2)
    else:
        console.print(f'[red]Unknown format: {format}. Use jsonl or pretty.[/red]')
        raise typer.Exit(1)
app.add_typer(trace_app, name='trace')
app.add_typer(trace_app, name='spans')

logs_app = typer.Typer(help='Inspect or export logs (OTel logs enriched with gen_ai.* from spans).', invoke_without_command=True)


@logs_app.callback()
def logs_callback(ctx: typer.Context) -> None:
    """When no subcommand: list log files with relative paths (newest first)."""
    if ctx.invoked_subcommand is not None:
        return
    _list_log_files()
    raise typer.Exit(0)


@logs_app.command('last')
def logs_last(
    n: int = typer.Argument(10, help='Number of logs to show'),
    file_path: Path | None = typer.Option(None, '--file', help='Read from JSONL file'),
) -> None:
    """Show last N logs. Uses buffer if non-empty, else logs/logs.ndjson."""
    if file_path is not None:
        if not file_path.exists():
            console.print(f'[red]⚠️ File not found: {file_path}[/red]')
            raise typer.Exit(1)
        logs = [json.loads(line) for line in file_path.read_text().strip().splitlines() if line.strip()]
    else:
        logs = log_buffer.get_recent_logs(log_buffer.BUFFER_MAX)
        if not logs:
            latest = _find_latest_logs_file()
            if latest:
                logs = [json.loads(line) for line in latest.read_text().strip().splitlines() if line.strip()]
    if not logs:
        console.print('[yellow]⚠️ No logs.[/yellow] Run a traced workflow with logging; logs are enriched with gen_ai.* from active spans.')
        raise typer.Exit(0)
    logs = list(reversed(logs))[-n:]
    table = Table(box=box.ROUNDED, header_style='bold blue', title=f'Last {len(logs)} log(s)')
    table.add_column('Time', style='dim', max_width=12)
    table.add_column('Severity', style='cyan', max_width=8)
    table.add_column('Body', style='green', max_width=50, overflow='ellipsis')
    table.add_column('Workflow / Agent', max_width=30, overflow='ellipsis')
    for log in reversed(logs):
        ts = log.get('timestamp_ns')
        time_str = datetime.fromtimestamp(ts / 1e9).strftime('%H:%M:%S') if ts else '—'
        sev = log.get('severity_text') or '—'
        body = _trunc(str(log.get('body') or '—'), 50)
        attrs = log.get('attributes') or {}
        wf = attrs.get('gen_ai.workflow.name') or attrs.get('gen_ai.agent.role') or '—'
        table.add_row(time_str, sev, body, _trunc(str(wf), 30))
    console.print(table)


@logs_app.command('export')
def logs_export(
    output: Path = typer.Option(None, '--output', '-o', help='Output path (default: logs/logs.ndjson)'),
    n: int = typer.Option(log_buffer.BUFFER_MAX, '--last', '-n', help='Limit to last N logs'),
) -> None:
    """Export logs to JSONL (default: logs/logs.ndjson)."""
    logs = log_buffer.get_recent_logs(n)
    if not logs:
        console.print('[yellow]⚠️ No logs in buffer.[/yellow]')
        raise typer.Exit(0)
    out = output or (log_buffer.DEFAULT_LOGS_DIR / "logs.ndjson")
    log_buffer.export_to_jsonl(out, n)
    console.print(f'[green]✅ Exported {len(logs)} log(s) to [bold]{out}[/bold][/green]')


app.add_typer(logs_app, name='logs')


def _parse_date_to_ns(s: str, end_of_day: bool = False) -> int | None:
    """Parse date string (YYYY-MM-DD only) to timestamp_ns. Blank returns None. end_of_day=True uses 23:59:59.999999999."""
    s = s.strip()
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999_999)
        return int(dt.timestamp() * 1e9)
    except ValueError:
        return None


def _create_abidex_notebook(log_path: Path, from_date: str | None, to_date: str | None, nb_path: Path) -> None:
    """Create a Jupyter notebook with imports and logs filtered by date range (YYYY-MM-DD)."""
    abs_path = str(log_path.resolve())
    import_lines = [
        "import ast",
        "import re",
        "import numpy as np",
        "import pandas as pd",
        "import matplotlib.pyplot as plt",
        "import requests",
        "import os",
    ]
    load_lines = [
        "# Load logs from abidex (filter by date)",
        f"log_path = {repr(abs_path)}",
        "df = pd.read_json(log_path, lines=True)",
        "df['timestamp_ns'] = df['timestamp_ns'].astype('int64')",
        "df['date'] = pd.to_datetime(df['timestamp_ns'], unit='ns').dt.date",
        "# Expand dict-like body and attributes into columns",
        "def _extract_dict(x):",
        "    if isinstance(x, dict): return x",
        "    if pd.isna(x) or not isinstance(x, str): return {}",
        "    m = re.search(r'[{][^{}]*[}]', str(x))",
        "    if not m: return {}",
        "    try: return ast.literal_eval(m.group())",
        "    except (ValueError, SyntaxError): return {}",
        "body_expanded = pd.json_normalize(df['body'].apply(_extract_dict)).add_prefix('body_')",
        "attrs_expanded = pd.json_normalize(df['attributes'].apply(_extract_dict)).add_prefix('attr_')",
        "df = pd.concat([df.reset_index(drop=True), body_expanded.reset_index(drop=True), attrs_expanded.reset_index(drop=True)], axis=1)",
    ]
    if from_date is not None:
        load_lines.append(f"df = df[df['date'] >= pd.to_datetime({repr(from_date)}).date()]")
    if to_date is not None:
        load_lines.append(f"df = df[df['date'] <= pd.to_datetime({repr(to_date)}).date()]")
    load_lines.append("df")

    def to_source(lines: list[str]) -> list[str]:
        return [line + "\n" for line in lines]

    nb = {
        "cells": [
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": to_source(import_lines)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": to_source(load_lines)},
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path.parent.mkdir(parents=True, exist_ok=True)
    nb_path.write_text(json.dumps(nb, indent=1), encoding="utf-8")


@app.command("notebook")
def notebook_cmd() -> None:
    """Launch Jupyter notebook with logs as pandas DataFrame. Prompts for from/to date range (timestamp_ns). Saves to notebooks/."""
    total, latest = _count_logs_in_latest()
    if not latest:
        console.print('[yellow]⚠️ No log files.[/yellow] Run a traced workflow first (e.g. [cyan]abidex run main.py[/cyan]).')
        raise typer.Exit(1)
    console.print(f"[bold]You have {total} log(s)[/bold] in [cyan]{latest.name}[/cyan].")
    console.print("[dim]Enter date range (YYYY-MM-DD, blank = no limit):[/dim]")
    try:
        from_str = input("From date: ").strip()
        to_str = input("To date: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    from_date = from_str if from_str and _parse_date_to_ns(from_str) is not None else None
    to_date = to_str if to_str and _parse_date_to_ns(to_str) is not None else None
    if from_str and from_date is None:
        console.print(f'[red]⚠️ Could not parse from date: {from_str}[/red]')
        raise typer.Exit(1)
    if to_str and to_date is None:
        console.print(f'[red]⚠️ Could not parse to date: {to_str}[/red]')
        raise typer.Exit(1)
    nb_dir = Path.cwd() / "notebooks"
    nb_path = nb_dir / "abidex_logs.ipynb"
    _create_abidex_notebook(latest, from_date, to_date, nb_path)
    console.print(f'[green]✅ Created [bold]{nb_path}[/bold][/green]')
    try:
        subprocess.run([sys.executable, "-m", "jupyter", "notebook", str(nb_path)], check=False)
    except FileNotFoundError:
        console.print('[yellow]⚠️ Jupyter not found.[/yellow] Reinstall abidex: [cyan]pip install abidex[/cyan]')
        raise typer.Exit(1)


@app.command("run")
def run_cmd(
    script: Path = typer.Argument(..., help='Python script to run (e.g. main.py)'),
    n: int = typer.Option(10, '--last', '-n', help='Number of spans to show after run'),
) -> None:
    """Run a script with buffer enabled, then show trace last. One command does it all."""
    if not script.exists():
        console.print(f'[red]⚠️ Script not found: {script}[/red]')
        raise typer.Exit(1)
    script_dir = script.resolve().parent
    env = dict(os.environ)
    env['ABIDEX_BUFFER_ENABLED'] = 'true'
    env['ABIDEX_RUN_MODE'] = '1'
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script_dir),
        env=env,
    )
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
    # Show trace last from exported file (traces/ or spans.ndjson)
    spans, source = _load_spans_from_buffer_or_file(None)
    if spans:
        console.print()
        _render_spans_table(spans, n, None, False)
    else:
        console.print('[yellow]⚠️ No spans.[/yellow] Ensure the script imports abidex, runs a traced workflow, and calls trace_buffer.export_with_timestamp("traces") before exit.')


backend_app = typer.Typer(help="Start, stop, or check SigNoz backend (requires pip install abidex[otlp])")


def _check_backend(host: str = "localhost", ui_port: int = 8080) -> bool:
    """Return True if SigNoz UI is reachable."""
    try:
        import urllib.request
        urllib.request.urlopen(f"http://{host}:{ui_port}", timeout=3)
        return True
    except Exception:
        return False


@backend_app.command("start")
def backend_start(no_browser: bool = typer.Option(False, "--no-browser", help="Don't open the UI in browser")) -> None:
    """Clone SigNoz (if needed), start Docker Compose, and open the UI."""
    if not SIGNOZ_DEPLOY.exists():
        console.print("[dim]Cloning SigNoz (first run)...[/dim]")
        SIGNOZ_DIR.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/SigNoz/signoz.git", str(SIGNOZ_DIR)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            console.print(f"[red]⚠️ git clone failed: {r.stderr}[/red]")
            raise typer.Exit(1)
        console.print("[green]✅ SigNoz cloned[/green]")
    r = subprocess.run(
        ["docker", "compose", "up", "-d", "--remove-orphans"],
        cwd=str(SIGNOZ_DEPLOY),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        console.print(f"[red]⚠️ docker compose failed: {r.stderr}[/red]")
        raise typer.Exit(1)
    console.print("[green]✅ SigNoz started[/green]")
    # Wait for UI to be ready
    with console.status("[bold blue]Waiting for SigNoz UI...", spinner="dots"):
        for _ in range(45):
            time.sleep(2)
            if _check_backend():
                break
        else:
            console.print(f"[yellow]⚠️ UI not ready yet. Open {SIGNOZ_UI_URL} manually.[/yellow]")
    if not no_browser:
        webbrowser.open(SIGNOZ_UI_URL)
        console.print(f"[dim]Opened {SIGNOZ_UI_URL}[/dim]")
    console.print()
    console.print(f"[bold]Next:[/bold] export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:{OTLP_GRPC_PORT}")
    console.print(f"  Then run your agent. Traces will appear in [cyan]{SIGNOZ_UI_URL}[/cyan]")


@backend_app.command("stop")
def backend_stop() -> None:
    """Stop SigNoz Docker Compose."""
    if not SIGNOZ_DEPLOY.exists():
        console.print("[yellow]⚠️ SigNoz not installed. Run [cyan]abidex backend start[/cyan] first.[/yellow]")
        raise typer.Exit(0)
    r = subprocess.run(
        ["docker", "compose", "down"],
        cwd=str(SIGNOZ_DEPLOY),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        console.print(f"[red]⚠️ docker compose down failed: {r.stderr}[/red]")
        raise typer.Exit(1)
    console.print("[green]✅ SigNoz stopped[/green]")


@backend_app.command("status")
def backend_status() -> None:
    """Check if SigNoz backend is reachable."""
    if _check_backend():
        console.print("[green]✅ SigNoz is running[/green]")
        console.print(f"  UI: [cyan]{SIGNOZ_UI_URL}[/cyan]")
        console.print(f"  OTLP gRPC: [cyan]http://localhost:{OTLP_GRPC_PORT}[/cyan]")
    else:
        console.print("[yellow]⚠️ SigNoz is not reachable[/yellow]")
        console.print("  Run [cyan]abidex backend start[/cyan] to start it.")
        raise typer.Exit(1)


app.add_typer(backend_app, name="backend")


@app.command('init')
def init_cmd() -> None:
    """Print .env template and docker run commands for SigNoz and Uptrace."""
    env_lines = [
        "# Abidex – Phase 1",
        "ABIDEX_AUTO=true",
        "OTEL_SERVICE_NAME=my-agent-app",
        "# Uncomment for persistent traces:",
        "# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317",
    ]
    env_path = Path('.env')
    if env_path.exists():
        console.print('[yellow]⚠️ .env exists; not overwriting.[/yellow]')
    else:
        env_path.write_text('\n'.join(env_lines) + '\n')
        console.print(f'[green]✅ Wrote [bold].env[/bold][/green]')
    console.print()
    table = Table(box=box.ROUNDED, header_style='bold blue', title='Docker one-liners')
    table.add_column('Backend', style='cyan')
    table.add_column('Command', style='green')
    table.add_row('SigNoz', 'git clone https://github.com/signoz/signoz.git && cd signoz/deploy/docker && docker compose up -d --remove-orphans')
    table.add_row('', 'UI: http://localhost:8080  →  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317')
    table.add_row('Uptrace', 'docker run -d -p 14317:4317 -p 14318:4318 --name uptrace -e UPTRACE_DSN=postgres://uptrace:uptrace@host.docker.internal:5432/uptrace uptrace/uptrace:latest')
    table.add_row('', 'UI: http://localhost:14318  →  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317')
    console.print(Panel(table, border_style='blue', padding=(0, 1)))
    console.print('[dim]Copy-paste commands (no table chars):[/dim]')
    console.print('[cyan]SigNoz:[/cyan] git clone https://github.com/signoz/signoz.git && cd signoz/deploy/docker && docker compose up -d --remove-orphans')
    console.print('[cyan]Uptrace:[/cyan] docker run -d -p 14317:4317 -p 14318:4318 --name uptrace -e UPTRACE_DSN=sqlite3:///tmp/uptrace.sqlite?mode=memory uptrace/uptrace:latest')
@app.command()
def summary(verbose: bool=typer.Option(False, '--verbose', '-v')) -> None:
    with console.status('[bold blue]Fetching recent traces...', spinner='dots'):
        spans = trace_buffer.get_recent_spans(trace_buffer.BUFFER_MAX)
    if not spans:
        console.print('[yellow]⚠️ No spans in buffer.[/yellow]')
        raise typer.Exit(0)
    by_name: dict[str, list[dict]] = {}
    errors = 0
    total_duration_ns = 0
    count_with_duration = 0
    total_tokens = 0
    for s in spans:
        name = s.get('name', '?')
        by_name.setdefault(name, []).append(s)
        if str(s.get('status', '')).lower().find('error') >= 0:
            errors += 1
        start, end = (s.get('start_time_ns'), s.get('end_time_ns'))
        if start and end:
            total_duration_ns += end - start
            count_with_duration += 1
        attrs = s.get('attributes') or {}
        for k, v in attrs.items():
            if 'token' in k.lower():
                try:
                    total_tokens += int(v)
                except (TypeError, ValueError):
                    pass
    table = Table(box=box.ROUNDED, header_style='bold blue', title='⏱️ Span summary')
    table.add_column('Name', style='blue', max_width=45, overflow='ellipsis')
    table.add_column('Count', justify='right', style='green')
    table.add_column('Avg duration (ms)', justify='right', style='yellow')
    for name, group in sorted(by_name.items(), key=lambda x: -len(x[1])):
        durs = [g.get('end_time_ns', 0) - g.get('start_time_ns', 0) for g in group if g.get('start_time_ns') and g.get('end_time_ns')]
        avg_ms = sum(durs) / len(durs) / 1000000.0 if durs else None
        table.add_row(name, str(len(group)), f'{avg_ms:.2f}' if avg_ms is not None else '—')
    console.print(table)
    avg_all = total_duration_ns / count_with_duration / 1000000.0 if count_with_duration else None
    console.print()
    console.print(f'  [bold]Total spans:[/bold] {len(spans)}  [bold]With duration:[/bold] {count_with_duration}  [bold]Avg (all):[/bold] {avg_all:.2f} ms' if avg_all else f'  [bold]Total spans:[/bold] {len(spans)}')
    if total_tokens:
        console.print(f'  [bold]Total tokens:[/bold] {total_tokens}')
    if errors:
        console.print(f'  [red]⚠️ Spans with error status: {errors}[/red]')
    else:
        console.print('  [green]✅ No errors in spans[/green]')
if __name__ == '__main__':
    app()