from functools import lru_cache

from gatehouse.config import settings
from gatehouse.jev.base import ChoiceAnswer, JevAdapter, JevResult, JevUnavailable

__all__ = ["ChoiceAnswer", "JevAdapter", "JevResult", "JevUnavailable", "get_jev_adapter"]


@lru_cache(maxsize=1)
def get_jev_adapter() -> JevAdapter:
    """Single cached adapter instance for the process lifetime — real or mock is
    chosen once from settings.jev_adapter, never mixed within a run.
    """
    if settings.jev_adapter == "real":
        from gatehouse.jev.real import RealJevAdapter

        return RealJevAdapter()
    from gatehouse.jev.mock import MockJevAdapter

    return MockJevAdapter()
