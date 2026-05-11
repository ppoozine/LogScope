"""Shared FastAPI dependencies / client singletons."""
from functools import lru_cache

import anthropic

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Singleton AsyncAnthropic client.

    Uses a placeholder api_key when ``ANTHROPIC_API_KEY`` is unset so endpoints
    can short-circuit gracefully (see chat_service / draft_service) instead of
    failing at construction time.
    """
    settings = get_settings()
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key or "placeholder"
    )
