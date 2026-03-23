import os
from abidex import core
from abidex.config import ABIDEX_AUTO
__all__ = ['init', 'patch_all_detected', 'ABIDEX_AUTO']

def init(auto_patch: bool=True) -> list[str]:
    return core.init(auto_patch=auto_patch)

def patch_all_detected() -> list[str]:
    return core.patch_all_detected()
if os.environ.get('ABIDEX_AUTO', 'true').lower() in ('true', '1', 'yes'):
    init()