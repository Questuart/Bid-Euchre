# Bid Euchre Rules

This document is the authoritative ruleset for **Bid Euchre (Double-Deck, 10–A)** as implemented (or to be implemented) in this repository.
If there is any conflict between code and this document, **this document wins** unless an ADR explicitly states otherwise.

## Status

- Deck / dealing / trick rules: **Specified**
- Bidding (single-round auction): **Specified**
- Scoring (per-hand, independent hands): **Specified**
- Edge cases / determinism: **Specified where known; TBD otherwise**

---

## 1. Glossary

- **Seat**: One of 4 players. Indexing convention: `0..3` (clockwise).
- **Partnerships**: Seats `(0,2)` vs `(1,3)` unless otherwise stated.
- **Hand**: A full deal from auction through trick play and scoring, or an **auction-only redeal event** if all players pass.
- **Trick**: One card played by each seat (4 cards total).
- **Trump**: The suit that beats non-trump cards (suit contracts only).
- **Led suit (effective)**: The **effective suit** of the first card played in a trick (see Section 4.3). In suit contracts, the Left Bower counts as trump. In high/low contracts, effective suit equals printed suit.
- **Legal play**: A card play permitted by the rules given the player's hand and current trick context.
- **Bid / Contract**: The declarer's commitment: **take at least N tricks**, and the declared contract type (and trump suit for SUIT contracts).
- **Declarer**: The seat that wins the auction by making the highest bid (largest `tricks_bid`). The declarer's team is the declaring team and must satisfy the contract.

### Implementation Notes

**Rank representation:**
- This document shows ranks as `10, J, Q, K, A` for readability
- In code, the rank "10" is represented as `T` (Ten)
- Example: `A♠` in this doc is `Card(suit="S", rank="A")` in code

**Suit representation:**
- This document uses Unicode symbols ♠♥♦♣ for readability
- In code, suits are represented by single letters: `S, H, D, C`
- Mapping: **♠ = S** (Spades), **♥ = H** (Hearts), **♦ = D** (Diamonds), **♣ = C** (Clubs)
- Example: `J♠` in this doc is `Card(suit="S", rank="J")` in code

**Contract type representation:**
- This document uses lowercase strings: `"suit"`, `"high"`, `"low"`
- These are the actual string values used in code for `contract_type`
- Example: A suit contract in clubs has `contract_type="suit"` and `trump="C"`

---

## 2. Deck and Dealing

### 2.1 Deck composition

- **Double-deck euchre-like deck**:
  - Ranks: `10, J, Q, K, A`
  - Suits: `♠, ♥, ♦, ♣`
  - **Two copies of each card** (double deck)
- Total cards: `5 ranks * 4 suits * 2 copies = 40 cards`

### 2.2 Hand size and tricks

- Cards per player: **10**
- Total tricks per hand: **10**

### 2.3 Shuffle and determinism

- Shuffling is driven by a PRNG seeded by the experiment seed + deal_id (see `REPRODUCIBILITY.md`).
- The same `(seed, deal_id, config)` must generate identical deals.

### 2.4 Dealer and deal procedure

- Dealer rotates each hand: `dealer = (dealer + 1) mod 4`
- Deal order: clockwise starting left of dealer.
- Dealing pattern is not strategically relevant if shuffle is uniform; the engine may deal in a single step.

---

## 3. Bidding Phase: Single-Round Auction (Contract Selection)

This repo uses a **single-round auction variant**: each seat acts **exactly once** in a fixed order starting left of the dealer.

### 3.1 Bid order (exact)

Let `D` be the dealer seat index.

Bidding order is:
1. **Left of dealer**: `(D + 1) mod 4`
2. **Dealer's partner** (opposite): `(D + 2) mod 4`
3. **Right of dealer**: `(D + 3) mod 4`
4. **Dealer**: `D`

After the dealer acts, the auction is complete.

### 3.2 Bid format (contract type + trump)

A bid selects a **contract type** and declares a trick target.

This repo supports three contract types:

- **"suit"** (standard): a trump suit is declared; bowers are active (Section 4).
- **"high"** (no-trump): no trump suit; highest cards win by base rank order (Section 4.1). Bowers are not active.
- **"low"** (no-trump): no trump suit; lowest cards win by inverted rank order (Section 3.2.2). Bowers are not active.

#### 3.2.1 Bid encoding

A bid is a tuple:

- `tricks_bid`: integer in `[0..10]`
- `contract_type`: one of `{"suit", "high", "low"}`
- `trump`: one of `♠ ♥ ♦ ♣` **only if** `contract_type = "suit"` (otherwise null)

Where:
- `tricks_bid = 0` means **PASS** (and `contract_type`/`trump` are null).
- A **bid** must have `tricks_bid >= 1`.
- If `contract_type = "suit"`, `trump` must be provided.
- If `contract_type ∈ {"high", "low"}`, `trump` must be null.

> "No minimum bid" means the first player may pass, and the first non-pass bid may be as low as **1**.

#### 3.2.2 Rank ordering for high/low contracts

- **"high"** (no-trump): within any suit, rank order is base order:
  - `A > K > Q > J > 10`
- **"low"** (no-trump): within any suit, rank order is inverted:
  - `10 > J > Q > K > A`

In both "high" and "low":
- There is no trump suit.
- Bowers are inactive; all jacks behave as normal jacks in their printed suits.

#### 3.2.3 Note on bidding strategies

The auction system supports all three contract types, but current bidding strategies may prioritize "suit" contracts. If "high"/"low" are enabled, strategy implementations must explicitly handle them.

### 3.3 Legal bids (strictly increasing)

Bidding is **strictly increasing**.

Let `current_high` be the highest `tricks_bid` made so far (initially `0`).

On a player's turn:
- They may **PASS** (`tricks_bid = 0`) at any time.
- Or they may bid `(tricks_bid, contract_type, trump)` only if `tricks_bid > current_high`.

Notes:
- `contract_type` does not affect bid ordering; only `tricks_bid` determines whether a bid is higher.
- Because `tricks_bid` must strictly increase, ties are impossible.

### 3.4 Auction result (declarer + contract)

After the 4 bids/passes:
- If at least one bid was made (`tricks_bid >= 1`), the seat that made the **highest bid** is the **declarer**.
- The declarer's partnership is the **declaring team**.
- The winning bid defines the **contract**:
  - `contract_tricks = tricks_bid`
  - `contract_type` (one of `{"suit", "high", "low"}`)
  - `contract_trump` (null unless `contract_type = "suit"`)

If all four seats pass (no bids), there is **no declarer** and the outcome is an **all-pass redeal event** (Section 3.5).

### 3.5 All-pass behavior (redeal)

If all four seats pass (no `tricks_bid >= 1`):
- The current deal is recorded as an **all-pass redeal event** (auction only; no tricks).
- Dealer advances by rotation for the *next* deal.
- The next deal is a fresh hand with a new `hand_id` and new `deal_id`.

This redeal event must be logged explicitly (see Section 8).

---

## 4. Trump, Bowers, and Card Ordering

### 4.1 Rank ordering (base)

Within a suit when no trump/bower rules apply:

`A > K > Q > J > 10`

### 4.2 Bowers (suit contracts only)

Bowers apply only to **"suit"** contracts. For **"high"** and **"low"** contracts, bowers are inactive and all jacks are treated as normal cards in their printed suits.

For "suit" contracts, this repo uses **bowers** by default:

- **Right bower**: the `J` of the trump suit
- **Left bower**: the `J` of the suit of the same color as trump (the "next" suit)

Same-color mapping (explicit):
- Trump **♠** ⇒ Left Bower **J♣**
- Trump **♣** ⇒ Left Bower **J♠**
- Trump **♥** ⇒ Left Bower **J♦**
- Trump **♦** ⇒ Left Bower **J♥**

Because the deck is **double**, each printed card exists twice:
- There are **two** `J` of trump (two Right Bowers)
- There are **two** `J` of the same-color suit (two Left Bowers)

Clarification:
- Only those two jack ranks (trump jack and same-color jack) function as bowers **for the chosen trump that hand**.
- The other two jacks are ordinary jacks in their printed suits.

### 4.3 Effective suit (contract-type aware)

Define `effective_suit(card, contract_type, trump)`:

- If `contract_type != "suit"`: effective suit = printed suit (bowers inactive).
- If `contract_type = "suit"`:
- If card is the **Right Bower** (`J` of trump): effective suit = `trump`
- If card is the **Left Bower** (`J` of same-color suit): effective suit = `trump`
- Otherwise: effective suit = printed suit

Important implication ("suit" contracts):
- The Left Bower is considered **trump for all purposes**:
- following suit
- determining the led suit (effective)
- determining trick winner

### 4.4 Trump ordering (suit contracts only, with bowers)

When comparing trump cards for trick-taking in "suit" contracts, trump ordering is:

1. **Right Bower** (highest trump)
2. **Left Bower**
3. Remaining trump cards (non-bower trumps) in base rank order:
   - `A(trump) > K(trump) > Q(trump) > 10(trump)`
   - Note: `J(trump)` is the Right Bower (covered above)

Clarification on all Jacks ("suit" contracts):
- `J` of trump suit → **Right Bower** (highest trump)
- `J` of same-color suit → **Left Bower** (second-highest trump)
- `J` of the two other suits → **Normal Jacks** in their printed suits (not trump)

### 4.5 Duplicate cards (double deck)

Because the deck contains duplicates (e.g., two `A♠`), identical cards may appear in the same trick.

Deterministic tie-break rule:
- **Earlier play wins** among identical cards.
  - Example: `A♠` played by seat 1 then `A♠` played by seat 3 → seat 1's `A♠` is higher for that trick.
- This also applies to duplicate bowers:
  - If two identical Right Bowers are played in the same trick, the earlier one wins.

This is a required invariant.

---

## 5. Trick-Taking Rules (Contract-Type Aware)

### 5.1 First lead (critical)

- **The declarer leads the first trick**.

### 5.2 Leading subsequent tricks

- The winner of the previous trick leads the next trick.

### 5.3 Following suit (effective suit)

Suit-following is based on **effective suit** (Section 4.3), not printed suit.

- Let `led_effective_suit` be the effective suit of the first card played in the trick.
- If a player holds at least one card whose effective suit equals `led_effective_suit`, they **must** play a card whose effective suit equals `led_effective_suit`.
- Otherwise, they may play any card.

Example ("suit" contract, trump = ♠):
- Trick led with `J♣` is the Left Bower ⇒ effective suit **♠** ⇒ players must follow **trump** if able.

### 5.4 Determining the trick winner (contract-type aware)

Given the four played cards in order:

1. Compute each card’s `effective_suit(card, contract_type, contract_trump)` (Section 4.3).
2. Let `led_effective_suit` be the effective suit of the first card played.

Then determine the winner:

#### suit contract
If `contract_type = "suit"`:
- If any played card has effective suit = `contract_trump`, the highest card by **trump ordering with bowers** wins (Section 4.4).
- Otherwise, the highest card of `led_effective_suit` wins using base ordering (Section 4.1).

#### high contract (no-trump)
If `contract_type = "high"`:
- Only cards of `led_effective_suit` are eligible to win the trick; off-suit cards can never win.
- The highest card of `led_effective_suit` wins using base ordering (Section 4.1).

#### low contract (no-trump)
If `contract_type = "low"`:
- Only cards of `led_effective_suit` are eligible to win the trick; off-suit cards can never win.
- The **lowest** card of `led_effective_suit` wins using low ordering (Section 3.2.2).

Tie-break:
- If there are identical highest/lowest cards (possible with duplicates), **earlier play wins** (Section 4.5).

### 5.5 Illegal plays

An illegal play occurs if a player fails to follow `led_effective_suit` despite holding at least one card with that effective suit.

Illegal plays MUST be prevented by the engine:
- The engine exposes `legal_actions(state, seat)` and rejects illegal actions.
- Policies must never be able to force an illegal action.

---

## 6. Scoring (Per-Hand, Independent Hands)

Scoring is computed **per hand** only. Hands are simulated independently; there is no running match score at this stage.

### 6.1 Definitions

Track tricks won per partnership per hand:
- `tricks_team_0` for seats `(0,2)`
- `tricks_team_1` for seats `(1,3)`

Let:
- `declarer_seat` be the seat that won the auction (Section 3.4)
- `declaring_team` be the partnership containing `declarer_seat`
- `defending_team` be the opposing partnership
- `bid_tricks` be the declarer's `contract_tricks`
- `contract_type` be the declarer’s chosen contract type
- `tricks_declaring` be tricks won by `declaring_team` (0–10)
- `tricks_defending` be tricks won by `defending_team` (0–10)

Invariant:
- `tricks_declaring + tricks_defending = 10`

### 6.2 Making the bid (contract success)

The declaring team **makes the bid** if:
- `tricks_declaring >= bid_tricks`

### 6.3 Points awarded (authoritative, per-hand)

Points are awarded per hand as follows:

- The **defending team** always scores points equal to the number of tricks they won.
- The **declaring team** scores:
  - If they **make** the bid: points equal to the number of tricks they won (including overtricks).
  - If they **fail** the bid: points equal to **negative** the number of tricks they bid, and they receive **no additional points**.

#### 6.3.1 Defending team points (always)

- `points_defending_team = tricks_defending`

#### 6.3.2 Declaring team points (conditional)

- If `tricks_declaring >= bid_tricks` (make):
  - `points_declaring_team = tricks_declaring`
- If `tricks_declaring < bid_tricks` (set):
  - `points_declaring_team = -bid_tricks`

#### 6.3.3 Expanded summary

- If make (`tricks_declaring >= bid_tricks`):
  - `points_declaring_team = tricks_declaring`
  - `points_defending_team = tricks_defending`
- If set (`tricks_declaring < bid_tricks`):
  - `points_declaring_team = -bid_tricks`
  - `points_defending_team = tricks_defending`

### 6.4 Moon and loner bid scoring

Moon and loner bids are special bid types that require winning **all 10 tricks** to make.
The `bid_type` field on a bid action distinguishes these from regular bids.

#### 6.4.1 Moon bid (`bid_type="moon"`)

- **Make** (`tricks_declaring == 10`): `points_declaring_team = +20`
- **Fail** (`tricks_declaring < 10`): `points_declaring_team = -20`
- **Defending team** always scores `tricks_defending` (same as regular bids)

#### 6.4.2 Loner bid (`bid_type="loner"`)

- **Make** (`tricks_declaring == 10`): `points_declaring_team = +40`
- **Fail** (`tricks_declaring < 10`): `points_declaring_team = -40`
- **Defending team** always scores `tricks_defending` (same as regular bids)

#### 6.4.3 Summary table

| Bid type | Make condition | Make points | Fail points | Defending points |
|----------|---------------|-------------|-------------|------------------|
| regular  | tricks >= bid | tricks won  | -bid        | tricks won       |
| moon     | tricks == 10  | +20         | -20         | tricks won       |
| loner    | tricks == 10  | +40         | -40         | tricks won       |

### 6.5 All-pass redeal events

If the auction results in an all-pass redeal event (Section 3.5):
- No tricks are played
- No points are awarded
- Declarer/contract fields are null

### 6.6 Placeholder: match scoring (future)

A future experiment mode may aggregate per-hand points into a running match score (e.g., first to target points, fixed number of hands). This is intentionally out of scope for the current phase.

---

## 7. Hand and Experiment Termination

### 7.1 End of hand

A hand ends when one of the following occurs:

- **Normal hand:** 10 tricks are completed.
- **All-pass redeal event:** all four seats pass in the auction (Section 3.5). In this case, no tricks are played.

Per-hand outcomes (tricks, make-bid, points) are computed once at the end of the hand, **only for normal hands**.

### 7.2 End of experiment (future)

At this stage, experiments simulate **independent hands** (no running match score).

A future experiment mode may define a "match" as:
- Fixed number of hands `N`
- First to `target_score`
- Compute budget / time budget

This is specified by experiment config (see `EXPERIMENTS.md`) and is intentionally out of scope for current phase.

---

## 8. Required Logging Events (Rules-Relevant)

Every attempted hand MUST log enough information to:
1) replay the hand deterministically, and
2) recompute legality, trick winners, and scoring exactly as defined in Sections 3–6.

Exact schemas live in `DATA_CONTRACT.md`.

### 8.1 Deal identity

Log:
- `seed`
- `deal_id`
- `hand_id`
- `dealer_seat` (0-3; may appear as `dealer_position` or `dealer_index` in code)

Redeal identity convention:
- An **all-pass redeal** is logged as its own **hand record** with `redeal_flag=true` and no trick data.
- The subsequent redealt deal is a **new** `hand_id` and **new** `deal_id` (with the dealer advanced).

Also log a reproducible representation of the deal for normal hands:
- either full hands dealt per seat, OR
- a deal hash plus a guaranteed reconstruction method (seed + shuffler + dealing algorithm + config hash)

### 8.2 Single-round auction transcript (always 4 actions)

Because the auction is exactly one round (Section 3.1), always log 4 actions in order.

For each of the 4 auction turns:
- `seat`
- `action`: `PASS` or `BID`
- if `BID`: `tricks_bid`, `contract_type`, `trump` (null unless `contract_type = "suit"`)
- `current_high_tricks` after the action (or ensure it is derivable)

Also log:
- `declarer_seat` (null if redeal; may appear as `bidder_position` in code)
- `contract_tricks` (null if redeal)
- `contract_type` (null if redeal; one of `{"suit", "high", "low"}`)
- `contract_trump` (null unless `contract_type = "suit"`; null if redeal)
- `redeal_flag` (true if all-pass redeal event)

### 8.3 Trump and effective-suit context (contract-type aware)

Logs MUST allow reconstruction of `effective_suit(card, contract_type, contract_trump)` (Section 4.3):

- Log `contract_type` (required for normal hands; one of `{"suit", "high", "low"}`)
- Log `contract_trump` (required iff `contract_type = "suit"`)
- For each played card log:
  - `card_instance_id` (stable within the hand; distinguishes duplicates)
  - `rank`
  - `printed_suit`

**⚠️ Implementation status:** `card_instance_id` is recommended for future implementation but not yet implemented in the current codebase. This means:
- Duplicate cards (e.g., both A♠) in the same trick cannot be distinguished in logs
- The "earlier play wins" tie-break rule (Section 4.5) cannot be audited from logs alone
- Hand replay with duplicate cards may be ambiguous
- Future implementation should assign unique instance IDs when cards are dealt

Optional (recommended for debugging, but derivable):
- `effective_suit` at time of play

### 8.4 Trick play-by-play

For each trick `trick_index` in `0..9`, log:
- `trick_index`
- `leader_seat`
  - For trick 0, `leader_seat = declarer_seat` (Section 5.1)
- ordered plays (in play order): `(seat, card_instance_id, rank, printed_suit)`
- `trick_winner_seat`

### 8.5 Outcomes (per-hand)

For normal hands (non-redeal), log:
- `tricks_team_0`, `tricks_team_1`
- `made_bid` boolean (true iff declaring team tricks ≥ `contract_tricks`)
- `points_team_0`, `points_team_1` computed per Section 6

Optional derived fields (must be derivable from logged data):
- `tricks_declaring`, `tricks_defending`
- `points_declaring_team`, `points_defending_team`

For redeal events, log:
- `redeal_flag = true`
- `declarer_seat = null`
- `contract_tricks = null`
- `contract_type = null`
- `contract_trump = null`
- and set outcomes to null or omit them consistently per `DATA_CONTRACT.md`

---

## 9. Edge Cases and Determinism Invariants

These are required invariants:

1. **Duplicate-card tie break:** If identical cards compete in a trick (including duplicate bowers), **earlier play wins** (Section 4.5).
2. **Legality enforcement:** Legal actions are enforced by the engine; policies cannot force illegal plays (Section 5.5).
3. **Deterministic randomness:** All randomness derives from seeded PRNG and is replayable (Section 2.3).
4. **Strict bidding:** Bids are strictly increasing by `tricks_bid` only (Section 3.3); ties cannot occur.
5. **Single-round auction:** The auction is exactly 4 actions (one per seat), then ends (Section 3.1).
6. **All-pass redeal:** If all four pass, the result is a redeal event and must be logged as such (Section 3.5, 8.1).
7. **First lead:** Declarer leads the first trick (Section 5.1).
8. **Effective-suit following:** Suit-following uses **effective suit** (Section 5.3); in "suit" contracts, the Left Bower is trump for legality and trick resolution.

---

## Appendix A: Open Decisions (TBD)

- Optional variants beyond {"suit", "high", "low"} — only via config + explicit spec
- Match-level scoring / match termination rules (Section 7.2) — intentionally out of scope for current phase
