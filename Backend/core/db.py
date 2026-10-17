"""Supabase database access for Dastak.

One data layer only: PostgreSQL via Supabase. ``MOCK_MODE`` affects WhatsApp
sends and LLM extraction, never storage. Environment separation (dev vs prod)
is handled by pointing ``SUPABASE_URL`` at a different project.

A second, dict-based store used to live here. It was removed because it had
different semantics from PostgreSQL (no foreign keys, no constraints, no
joins, ``eq()`` as its only filter), so the demo rehearsed code that was not
the code that shipped.
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger("dastak.db")

_supabase_client = None


class DbError(RuntimeError):
    """Raised when Supabase is misconfigured or a database call fails."""


def _create_client(url: str, key: str):
    """Import and construct the Supabase client lazily (keeps imports cheap)."""
    from supabase import create_client

    return create_client(url, key)


def get_db():
    """Return the shared Supabase client.

    Raises:
        DbError: if ``SUPABASE_URL`` or ``SUPABASE_SERVICE_KEY`` is missing.
            There is deliberately no fallback store: a missing configuration
            must fail loudly rather than silently change the data semantics.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise DbError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. "
            "Dastak has no in-memory fallback database."
        )

    try:
        _supabase_client = _create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as exc:  # pragma: no cover - depends on the client lib
        raise DbError(f"Could not create Supabase client for {SUPABASE_URL}: {exc}") from exc

    logger.info("Supabase client initialized: %s", SUPABASE_URL)
    return _supabase_client


def execute(query: Any):
    """Execute a Supabase query builder, translating failures to ``DbError``.

    Callers should let ``DbError`` propagate and decide how to degrade. The
    WhatsApp webhook in particular must always answer HTTP 200 — Meta retries
    any other status, which produces duplicate reports.
    """
    try:
        return query.execute()
    except DbError:
        raise
    except Exception as exc:
        raise DbError(f"Supabase query failed: {exc}") from exc
