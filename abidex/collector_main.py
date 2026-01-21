"""
Collector CLI entry point for Abide AgentKit.
"""

import argparse
import sys

try:
    import uvicorn
    UVICORN_AVAILABLE = True
except ImportError:
    UVICORN_AVAILABLE = False

try:
    from .collectors import create_collector_app
    COLLECTOR_AVAILABLE = True
except ImportError:
    COLLECTOR_AVAILABLE = False

from .client import TelemetryClient
from .config import resolve_collector_settings
from .sinks import JSONLSink, HTTPSink


def collector_main(args=None):
    """
    Main entry point for the collector CLI.

    Args:
        args: Parsed arguments (Namespace object). If None, will parse from sys.argv.
    """
    if not COLLECTOR_AVAILABLE:
        print("Error: Collector is not available. Install with: pip install abidex[collector]")
        sys.exit(1)

    # If args not provided, parse them (for standalone usage)
    if args is None:
        parser = argparse.ArgumentParser(
            description="Abide AgentKit Telemetry Collector",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )

        parser.add_argument(
            "--host",
            default=None,
            help="Host to bind the collector to (default: 127.0.0.1 or ABIDEX_COLLECTOR_HOST/config)"
        )

        parser.add_argument(
            "--port",
            type=int,
            default=None,
            help="Port to bind the collector to (default: 8000 or ABIDEX_COLLECTOR_PORT/config)"
        )

        parser.add_argument(
            "--auth-token",
            help="Authentication token for API requests"
        )

        parser.add_argument(
            "--cors-origins",
            nargs="*",
            default=["*"],
            help="Allowed CORS origins"
        )

        parser.add_argument(
            "--max-batch-size",
            type=int,
            default=1000,
            help="Maximum batch size for event processing"
        )

        parser.add_argument(
            "--output-file",
            help="Output file for JSONL sink (optional)"
        )

        parser.add_argument(
            "--forward-url",
            help="HTTP URL to forward events to (optional)"
        )

        parser.add_argument(
            "--log-level",
            choices=["debug", "info", "warning", "error"],
            default="info",
            help="Log level"
        )

        parser.add_argument(
            "--reload",
            action="store_true",
            help="Enable auto-reload for development"
        )

        args = parser.parse_args()

    if not UVICORN_AVAILABLE:
        print("Error: uvicorn is required to run the collector. Install with: pip install abidex[collector]")
        sys.exit(1)

    defaults = resolve_collector_settings(args.host, args.port)
    args.host = defaults.host
    args.port = defaults.port

    # Set up telemetry client with optional sinks
    client = TelemetryClient()

    if args.output_file:
        client.add_sink(JSONLSink(args.output_file))
        print(f"Added JSONL sink: {args.output_file}")

    if args.forward_url:
        client.add_sink(HTTPSink(args.forward_url))
        print(f"Added HTTP sink: {args.forward_url}")

    # Create collector app
    app = create_collector_app(
        client=client,
        auth_token=args.auth_token,
        cors_origins=args.cors_origins,
        max_batch_size=args.max_batch_size
    )

    print(f"Starting Abide AgentKit Collector on {args.host}:{args.port}")
    if args.auth_token:
        print("Authentication enabled")
    else:
        print("WARNING: No authentication token set - collector is open to all requests")

    # Run with uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload
    )
