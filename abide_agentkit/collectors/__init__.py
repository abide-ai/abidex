"""
Collectors for gathering telemetry data from external sources.
"""

from .http_collector import HTTPCollector, create_collector_app

__all__ = [
    "HTTPCollector",
    "create_collector_app"
]
