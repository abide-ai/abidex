"""
Collectors for gathering telemetry data from external sources.
"""

try:
    from .http_collector import HTTPCollector, create_collector_app
    __all__ = [
        "HTTPCollector",
        "create_collector_app"
    ]
except (ImportError, NameError):
    # FastAPI or dependencies not available
    __all__ = []
