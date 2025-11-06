"""
Adapters for integrating with various AI frameworks and platforms.
"""

from .claude_adapter import ClaudeAdapter
from .crew_adapter import CrewAdapter
from .n8n_adapter import N8NAdapter

__all__ = [
    "ClaudeAdapter",
    "CrewAdapter",
    "N8NAdapter"
]
