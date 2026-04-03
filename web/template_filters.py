"""Custom Jinja2 template filters for the browser game.

Filters are registered on the Jinja2 environment in :func:`web.app.lifespan`
and in test fixtures that render templates directly.
"""

from __future__ import annotations

from typing import Optional

from bid_euchre.core.cards import Card
from bid_euchre.core.cards import effective_suit as _effective_suit
from bid_euchre.core.cards import is_left_bower as _is_left_bower
from bid_euchre.core.cards import is_right_bower as _is_right_bower


def display_rank(rank: str) -> str:
    """Convert internal single-char rank to display string.

    The core card model uses ``'T'`` for tens.  Users expect ``'10'``.
    All other ranks (``J``, ``Q``, ``K``, ``A``) pass through unchanged.
    """
    return "10" if rank == "T" else rank


def effective_suit(
    card: list[str],
    trump: Optional[str] = None,
    contract_type: Optional[str] = None,
) -> str:
    """Return the effective suit of a card given the current contract.

    In suit contracts, bowers belong to the trump suit regardless of their
    printed suit.  The left bower (J of the same-colour off-suit) is the
    most visible case: e.g. J♠ in a clubs contract effectively belongs to
    clubs.

    Usage in Jinja2::

        {{ card|effective_suit(trump, contract_type) }}

    where *card* is a ``[suit, rank]`` list as stored in the play tuples.
    """
    suit, rank = card[0], card[1]
    return _effective_suit(Card(suit, rank), trump, contract_type or "suit")


def is_bower(
    card: list[str],
    trump: Optional[str] = None,
    contract_type: Optional[str] = None,
) -> str:
    """Return ``'left'``, ``'right'``, or ``''`` indicating bower status.

    In suit contracts, the right bower is the J of trump, and the left bower
    is the J of the same-colour off-suit.  Returns an empty string for
    non-bower cards or non-suit contracts.

    Usage in Jinja2::

        {% set bower = card|is_bower(trump, contract_type) %}
        {% if bower %}...{% endif %}
    """
    if not trump or (contract_type or "suit") != "suit":
        return ""
    suit, rank = card[0], card[1]
    c = Card(suit, rank)
    if _is_right_bower(c, trump):
        return "right"
    if _is_left_bower(c, trump):
        return "left"
    return ""
