# strategy/ — Bot Policies

Bidding and play strategies for AI players.

## Key Files

| File | Purpose |
|------|---------|
| `base.py` | `Strategy` ABC, shared utilities (`card_value_for_dump`) |
| `baselines.py` | Simple strategies: `BasicStrategy`, `RandomLegalStrategy`, `AlwaysLowest/HighestLegalStrategy` |
| `glutton.py` | `GreedyStrategy`, `GluttonStrategy` — 1-trick lookahead |
| `bidding.py` | Bidding policies: `RanktheTank`, `StrictRaiserBidder`, `ArtifactBidder`, etc. |
| `artifact_strategy.py` | Artifact-based strategy loading |

## Available Strategies

**Play Strategies:**
- `BasicStrategy` — Simple rule-based
- `RandomLegalStrategy` — Random legal card
- `GreedyStrategy` / `GluttonStrategy` — 1-trick lookahead

**Bidding Policies:**
- `AlwaysPassBidder`, `FixedBidder` — Testing/baseline
- `RanktheTank`, `StrictRaiserBidder` — Rule-based
- `ArtifactBidder` — ML model-based

## Adding a New Strategy
1. Implement in new file or extend existing (inherit from `Strategy` or `BiddingPolicy`)
2. Export in `__init__.py`
3. Register in `src/bid_euchre/experiments/config.py` (`StrategyConfig.create_strategy`)
4. Add tests in `tests/unit/`

## Contract
- See [docs/02_agent/AGENTS.md](../../../docs/02_agent/AGENTS.md) Section 10 for recipes
