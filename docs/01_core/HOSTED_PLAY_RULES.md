# Hosted Play Rules

**Status:** Draft implementation contract for the browser-hosted play mode
**Governing plan:** `plans/browser_game/governing_plan.md`
**Extends:** [RULES.md](./RULES.md) §6.5 (match scoring) and §7.2 (match termination)

---

## 1. Scope

This document defines the hosted browser-play rules that extend the
hand-scoped rules in [RULES.md](./RULES.md) for the V1 product.

Unless explicitly overridden here, the rules in [RULES.md](./RULES.md) remain
authoritative for deck composition, bidding legality, effective suit, trick
resolution, and per-hand scoring.

## 2. Match Scoring

Hosted play adds cumulative match scoring on top of the per-hand scoring
defined in [RULES.md](./RULES.md) §6.

- Each hand's `points_team0` and `points_team1` are computed using
  `compute_points(winning_bid, bidder_position, tricks_team0, tricks_team1)`.
- Those hand points are added to running match totals.
- The human team is seats `(0, 2)`.
- The opposing AI team is seats `(1, 3)`.

## 3. Match Termination

The match ends when the human team's cumulative score reaches either bound:

- Win condition: `score_human >= 52`
- Loss condition: `score_human <= -52`

Per-hand scoring rules are otherwise unchanged.

## 4. Human Seat

- The human player is always seat `0`.
- The human participates in both bidding and card play.
- Seat `2` remains the human player's AI partner.

## 5. AI Lineup

- One bidding model is selected per match before the first hand.
- All three AI seats `(1, 2, 3)` use the same approved bidding model.
- All AI seats use `GluttonStrategy` for card play.
- The selected bidding model remains fixed for the entire match.

## 6. Dealer Rotation and Bid Order

- Dealer rotation is standard: `dealer = (dealer + 1) % 4` each hand.
- The first dealer is deterministic from the match seed.
- Bid order remains `[D+1, D+2, D+3, D] mod 4` as defined in
  [RULES.md](./RULES.md) §3.1.

## 7. All-Pass Redeals

- An all-pass auction remains a redeal event.
- No points are awarded for a redeal hand.
- Dealer advances and a new hand is dealt automatically.
- The UI may briefly show the redeal result before advancing.

## 8. Async Resume and Idempotency

- Match state is persisted after every bid and every played card.
- Browser refresh resumes from the persisted state.
- Action submissions are idempotent.
- Resubmitting an already-processed turn returns the current state without
  applying the action a second time.
- Each persisted hand state records `current_seat` and `turn_number`.

## 9. Private-Link Access

- Each match is accessed through a UUID-style private link.
- There is no separate authentication in V1 beyond possessing the link.
- One private link corresponds to one human-controlled match series.

## 10. Decision Logging

Decision logging is on by default for hosted play.

Every bid and card-play decision must persist:

- actor type (`human` or AI model identifier)
- match, hand, and turn identifiers
- enough game state to replay the decision context
- legal alternatives
- chosen action

The stored data must be sufficient to support deterministic replay and later
training-data export.
