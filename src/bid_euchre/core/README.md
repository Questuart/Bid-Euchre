# core/ — Game Mechanics

Card primitives, rules, and trick resolution. This is the **source of truth** for game logic.

## Key Files

| File | Purpose |
|------|---------|
| `cards.py` | `Card` class, deck creation, suit/rank logic, `effective_suit()` |
| `rules.py` | `get_legal_indices()`, `trick_winner()` |

## Exports (via `__init__.py`)
```python
Card, create_deck, shuffle_deck, deal_hands
effective_suit, rank_strength
trick_winner, get_legal_indices
```

## Dependencies
**None** — This is a leaf module. Does not import from other `bid_euchre` modules.

## Contract
- Changes here require unit tests in `tests/unit/test_cards.py`, `tests/unit/test_rules.py`
- See [docs/01_core/RULES.md](../../../docs/01_core/RULES.md) for game rule specifications
- Bower handling (left/right jack) is critical — test thoroughly
