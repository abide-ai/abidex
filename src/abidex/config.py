import os
from typing import Optional

def _env_auto() -> bool:
    raw = os.environ.get('ABIDEX_AUTO', 'true').strip().lower()
    return raw in ('true', '1', 'yes')

def _env_bool(key: str, default: bool=True) -> bool:
    raw = os.environ.get(key, '').strip().lower()
    if not raw:
        return default
    return raw in ('true', '1', 'yes')
ABIDEX_AUTO: bool = _env_auto()
ABIDEX_VERBOSE: bool = _env_bool('ABIDEX_VERBOSE', False)
ABIDEX_BUFFER_ENABLED: bool = _env_bool('ABIDEX_BUFFER_ENABLED', False)

def get_service_name() -> Optional[str]:
    return os.environ.get('OTEL_SERVICE_NAME')