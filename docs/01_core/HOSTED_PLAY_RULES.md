# Hosted Play Rules

**Status:** Implementation contract for the browser-hosted play mode
**Governing plans:**
- V1 baseline: `plans/browser_game/governing_plan.md`
- Expansion: `plans/browser_game_expansion/governing_plan.md`
**Extends:** [RULES.md](./RULES.md) §6.5 (match scoring) and §7.2 (match termination)
**Last updated:** 2026-03-25

---

## 1. Scope

This document defines the hosted browser-play rules that extend the
hand-scoped rules in [RULES.md](./RULES.md).

Sections 1-10 define the **V1 baseline** that shipped with the original
browser game.  Sections 11-16 define **expansion rules** introduced by the
browser game expansion initiative.

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

## 5. AI Lineup (V1 Baseline)

- One bidding model is selected per match before the first hand.
- All three AI seats `(1, 2, 3)` use the same approved bidding model.
- All AI seats use `GluttonStrategy` for card play.
- The selected bidding model remains fixed for the entire match.
- See §11 for the expansion-wave model serving contract.

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

## 9. Private-Link Access (V1 Baseline)

- Each match is accessed through a UUID-style private link.
- There is no separate authentication in V1 beyond possessing the link.
- One private link corresponds to one human-controlled match series.
- See §15 for the expansion-wave invite-code access model.

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

---

## Expansion Rules (Browser Game Expansion Initiative)

The following sections extend the V1 baseline with moon/loner support,
updated model serving, improved game flow, and pilot access control.

## 11. Model Serving (Expansion)

- The browser-facing bidding roster contains exactly two options:
  - **OLSa**, backed by the Arc D v2 R3 `full_ols_av` artifact loaded
    through `ActionValueBidder`
  - **Bud Bot**, backed by the Arc D v2 R3 `gbt_av` artifact loaded
    through `GBTActionValueBidder`
- The previous `hybrid_olsa` (`HybridOLSaBidder`) is removed from the
  visible pilot roster because it only produces regular bids and is not
  moon/loner-capable.
- `heuristic` is not part of the browser-visible roster and must not be
  used as a silent browser fallback.
- All AI seats continue to use the same model and `GluttonStrategy` for
  card play (unchanged from §5).

## 12. Moon Bids (Expansion)

- A **moon bid** is a level-10 bid with `bid_type="moon"`.
- Moon overcalls any regular bid at any level, including level 10.
- Moon legality, overcall hierarchy, and auction integration must reuse
  canonical repo logic (`enumerate_legal_actions`, `BidAction.overcalls`).
- After a moon bid wins the auction, a **partner exchange** occurs before
  trick play: the declarer's partner gives their best cards to the declarer,
  who returns the same number of cards.  The exchange uses
  `perform_exchange()` from canonical repo logic.
- Moon scoring follows `compute_points()` with the moon bid type.

## 13. Loner Bids (Expansion)

- A **loner bid** is a level-10 bid with `bid_type="loner"`.
- Loner overcalls moon and all regular bids.
- After a loner bid wins the auction, the declarer's partner **sits out**
  for the entire hand.  Only three seats participate in trick play.
- The sit-out seat plays no cards and wins no tricks.
- Loner trick flow, active-seat determination, and scoring must reuse
  canonical repo logic.  The hosted-play engine must not re-implement
  loner seat skipping independently.
- Loner scoring follows `compute_points()` with the loner bid type.

## 14. Hand-End Pause and Next-Deal Flow (Expansion)

- After a hand completes (including redeals), the game enters a **hand-end
  pause** state.
- During the pause, the prior hand's result is visible: winning bid, tricks
  won, points awarded, and updated match scores.
- The next hand does not auto-start.  The human player must explicitly
  trigger the next deal (e.g., click "Next Deal").
- The pause state is persisted so that a browser refresh during the pause
  returns to the pause screen, not the next hand.

## 15. Invite-Code Access (Expansion)

- Pilot access uses **invite codes**, not passwords.
- A player reaches the game through a private link plus a valid invite code.
- On first successful access, the player may set a **display nickname**
  that is stored against the invited player record.
- The nickname is presentation state, not the authentication factor.
- Invalid or expired invite codes are rejected with a clear error.
- An admin workflow (CLI or script) exists for generating and distributing
  new invite codes without hand-editing the database.
- The invite-code model is intentionally lightweight: code + session +
  nickname.  Full account/password systems are out of scope.

## 16. Hand Sorting (Expansion, Amendment BGE-1)

- The human player's visible hand is auto-sorted by **printed suit** and
  then by **display rank** (`J > A > K > Q > 10`).
- Suit buckets stay strictly segregated by printed suit.  Left/right-bower
  effective-suit semantics do not affect the display sort order.
- Sorting applies to all browser surfaces showing the human hand: initial
  deal, refresh/resume, post-action rerender, and hand-end preview.
- Sorting is a presentation rule only.  Legal-play derivation, trick
  resolution, and bower effective-suit behavior remain governed by
  canonical rules code and must not be altered by the UI sort.
