# Bidding Contract (v1)

## Overview

Bid Euchre bidding mechanics define how players select contracts for each hand. This document specifies the bidding protocol, observation contract, and default behaviors.

## Bidding Protocol

### Round Structure
- **Single round**: One bidding round starting left of dealer
- **Sequential action**: Players bid `(n, contract)` in order: LOD → partner → ROD → dealer (clockwise from dealer)
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

- **Hand**: Player's 10 cards
- **Seat**: Player's position (0-3)
- **Dealer seat**: Dealer's position (0-3)
- **Current high bid**: Highest `n` bid so far in this round
- **Allowed contracts**: Tuple of contract types the player may bid (`C`, `D`, `H`, `S`, `HIGH`, `LOW` by default)

**Note**: Full bidding history is now captured in game logs via the `auction_transcript` field (schema v7). The observation contract itself still provides only the current high bid, not the full history.

## Default Behavior

### Auction Configurations
- **Required**: Bidding policy must be specified
- **Fail fast**: Missing bidding policy → immediate error

### Non-Auction Configurations
- **No bidding**: Skip bidding phase entirely
- **Deterministic selection**: Use existing non-auction contract selection path
- **Randomness**: Via repo's seeded RNG sources (deterministic by default)
