"""Custom Jinja2 template filters for the browser game.

Filters are registered on the Jinja2 environment in :func:`web.app.lifespan`
and in test fixtures that render templates directly.
"""

from __future__ import annotations


def display_rank(rank: str) -> str:
    """Convert internal single-char rank to display string.

    The core card model uses ``'T'`` for tens.  Users expect ``'10'``.
    All other ranks (``J``, ``Q``, ``K``, ``A``) pass through unchanged.
    """
    return "10" if rank == "T" else rank
