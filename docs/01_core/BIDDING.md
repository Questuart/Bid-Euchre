# Bidding Contract (v1)

## Overview

Bid Euchre bidding mechanics define how players select contracts for each hand. This document specifies the bidding protocol, observation contract, and default behaviors.

## Bidding Protocol

### Round Structure
- **Single round**: One bidding round starting left of dealer
- **Simultaneous action**: All players bid `(n, contract)` simultaneously
- **Bid values**: `n` ranges from 0–10 where `0` = pass
- **Strictly increasing**: `n` must be `> current_high_bid` else treated as pass
- **Redeal condition**: All players pass (bid 0) → redeal

### Contracts
- **Suit contracts**: `C`, `D`, `H`, `S` (Clubs, Diamonds, Hearts, Spades)
- **Special contracts**: `HIGH`, `LOW`
  - No trump suit applies
  - Only rank order determines winners (A > K > Q > J > 10)

## Observation Contract (v1)

Bidding observations provide minimal context for decision-making:

- **Hand**: Player's 5 cards
- **Seat**: Player's position (0-3)
- **Dealer seat**: Dealer's position (0-3)
- **Current high bid**: Highest `n` bid so far in this round

**Note**: Bidding history not included (planned for v2)

## Default Behavior

### Auction Configurations
- **Required**: Bidding policy must be specified
- **Fail fast**: Missing bidding policy → immediate error

### Non-Auction Configurations
- **No bidding**: Skip bidding phase entirely
- **Deterministic selection**: Use existing non-auction contract selection path
- **Randomness**: Via repo's seeded RNG sources (deterministic by default)