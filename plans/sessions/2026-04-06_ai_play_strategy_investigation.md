# AI Play Strategy Investigation — "Won't Cash Winners"

> **Task:** analyst-b / packet `c98de2625cbd`
> **Issues:** #2502, #2504, #2506
> **Status:** Investigation complete — ready for orchestrator dispatch decision
> **Author:** analyst-b
> **Date:** 2026-04-06
> **Scope:** Investigation only, no implementation

## Problem Statement

Across all three contract types in live browser play, the AI opponents
(OLSa "Easy" and Bud Bot) hold guaranteed winning cards and play weaker
cards instead, often gifting tricks to opponents. Evidence cites three
distinct failure patterns:

1. **Low contracts (#2502):** AI dumps high cards (J, Q) correctly
   *relative to value-for-dump* but never leads its 10s to cash them
   as sure winners once opponents have exhausted the suit.
2. **High contracts (#2504):** AI holds aces across tricks 1–9 and
   only plays them at trick 10, wasting the guaranteed winner.
3. **Suit contracts (#2506):** After winning tricks 1–2 with the right
   bower and an ace, AI switches to non-winning off-suit leads (J♦)
   instead of continuing to cash the left bower or established side-suit
   winners still in hand.

All three patterns share a root cause: the play strategy has **no
"cash sure winners" logic**. It uses a "cheapest winner / longest suit
highest card" heuristic that is myopic (only looks at the provisional
trick in progress) and has no priority for established winners.

## Confirmed Delivery Surface

| Component | Role | File |
|-----------|------|------|
| Hosted AI roster | Instantiates AI opponents | `web/ai_manager.py` |
| Play strategy | `play_strategy=GluttonStrategy()` for **both** OLSa and Bud Bot | `web/ai_manager.py:141,177` |
| Card selection | `GluttonStrategy.choose_card()` | `src/bid_euchre/strategy/greedy.py:428–620` |
| Lead heuristic | `GluttonStrategy._choose_lead()` | `src/bid_euchre/strategy/greedy.py:229–328` |
| Discard heuristic | `GluttonStrategy._choose_discard()` | `src/bid_euchre/strategy/greedy.py:330–363` |
| Sure-winner check (exists, under-used) | `GluttonStrategy._is_sure_winner()` | `src/bid_euchre/strategy/greedy.py:177–211` |
| Feature-isolated twin | `GluttonIsolatedStrategy` | `src/bid_euchre/strategy/greedy.py:623–1077` |
| Card valuation | `card_value_for_dump()` (contract-aware, uses `rank_strength`) | `src/bid_euchre/strategy/base.py:125–149` |
| Rank ordering | `rank_strength()` — Low inverts (T > K > Q > J > A) | `src/bid_euchre/core/cards.py:145–165` |

**Important:** both hosted-play models (`olsa`, `bud_bot`) share
`GluttonStrategy()` as their play brain (`web/ai_manager.py:141,177`).
Only the bidder differs. Any fix to card play therefore fixes both AI
opponents in the live game simultaneously.

The sibling class `GluttonIsolatedStrategy` replicates the same lead /
discard heuristics behind feature flags, so any fix must land in both
locations (the two files are parallel — the investigation confirms the
divergence risk is contained to that one file, `greedy.py`).

## Evidence — Code-Level Root Cause

### Defect A — `_choose_lead` has no sure-winner priority (all contract types)

`_choose_lead()` (suit branch, `greedy.py:229–308`):

```python
# 0. Both bowers + 5+ trump  -> lead right bower
# 1. Non-trump aces          -> lead ace from *shortest* non-trump suit
# 2. ≥ 4 trumps, not both bowers -> lead LOWEST trump
# 3. Longest non-trump suit, highest card
# Fallback: highest value card overall
```

`_choose_lead()` (high/low branch, `greedy.py:310–328`):

```python
# longest_suit = max suit by count
# return max(longest_suit_indices, key=card_value)
# (card_value is contract-aware via rank_strength; in Low, T=4 beats A=0)
```

**Gap:** none of these steps consult `_is_sure_winner()`. After the AI
has run opponents out of a suit (voids inferred in `observe_play()` at
`greedy.py:141–158`), any remaining card in that suit with no surviving
higher ranks is a guaranteed winner. The lead heuristic ignores this
and continues to pick by local rules (longest suit / non-trump ace from
shortest suit / lowest trump). This is how Ace wins tricks 1–2 with aces
then switches away — the lead heuristic has no memory of "this suit
is now drained."

### Defect B — Step 2 leads the LOWEST trump (suit contract)

`greedy.py:287–293`:

```python
if trump_count >= 4 and trump_indices:
    if not (has_right and has_left):
        # Lead lowest trump to draw trump without burning top cards
        return min(trump_indices, key=card_value)
```

External best practice for drawing trump ([advinbridge.com](https://www.advinbridge.com/this-week-in-bridge/614),
[bridgemojo.com](https://bridgemojo.com/sites/default/files/BridgeWhiz/Lesson%207%20-%20When%20to%20Delay%20Drawing%20Trump%20Handout.pdf),
[pagat.com Bid Euchre](https://www.pagat.com/euchre/bideuch.html),
[bid-euchre.com](https://bid-euchre.com/how_to_play)):

> "If you plan to lead a trump, make sure it is high enough to take the
> trick or it will be wasted."
>
> "Draw trump from the top" — lead HIGH trump when you need to prevent
> opponents ruffing your side-suit winners.

The current logic leads lowest trump, which **works against** the goal
of clearing opponents. Concrete failure mode: Ace holds `J♠^RB` (already
played) + `J♣^LB` (unplayed) + small trump. He wins trick 1 with the
RB. On his next lead, step 2 fires ("≥ 4 trumps, NOT both bowers
anymore" — the RB is spent), and he leads the smallest trump instead of
the LB. Opponents can now win off-suit tricks by ruffing low while the
LB sits in hand. This is exactly the #2506 follow-up report:

> "Ace holds J♣ (Left Bower) but doesn't lead it until tricks 9–10.
> Opponents trump in on off-suit leads throughout the mid-game."

### Defect C — "Cheapest winner" following is myopic (not a sure-winner check)

`GluttonStrategy.choose_card()` (`greedy.py:597–608`):

```python
# If we have any card that is currently winning, play the cheapest winner
if winning_candidates:
    choice = min(winning_candidates, key=card_value)
```

`winning_candidates` is built by simulating `trick_winner(provisional_plays)`
for the trick as it stands **at the current player's point in play order**
(`greedy.py:483–494`). It does not verify the candidate will still win
after seats that play later have had their turn.

**Concrete 2nd-seat failure (exact #2504 trace, trick 4):**

- Trick state when Slim (seat 1, 2nd) plays: `[(You, 10♣)]`
- Slim's legal plays in clubs: `J♣`, `A♣`
- Provisional check: Play `J♣` → provisional winner = Slim ✓; Play `A♣` → provisional winner = Slim ✓
- `winning_candidates = [J♣, A♣]`
- `card_value(J♣)` in High = `rank_strength(J)` = **1**
- `card_value(A♣)` in High = `rank_strength(A)` = **4**
- `min(winning_candidates, key=card_value)` → `J♣`
- Slim plays `J♣`
- Ace (seat 2) plays `K♣` → K beats J → Ace now winning
- Deuce (seat 3) plays `10♦` → Ace wins the trick

Slim's `J♣` was a **false winner**. It won the provisional trick but
lost to the K that hadn't been played yet. Slim both lost the trick
**and** burned a mid-value card that might have won later. Meanwhile
the `A♣` — a true sure winner — was held to trick 10.

Classical bridge heuristic "2nd hand low, 3rd hand high" captures the
right principle: in 2nd seat, don't try to win with a non-sure card;
dump cheap and let partner decide in 3rd seat. The current logic does
the opposite.

`_is_sure_winner()` exists (`greedy.py:177–211`) and is contract-aware
via `cards_that_beat()` — but it is only used inside the narrow
`partner_vulnerable_cover` branch (`greedy.py:540–562`). It is **not
called** on the main "play cheapest winner" path.

### Defect D — Low contract behavior is less wrong than the issue implies

`card_value_for_dump()` **is** contract-aware: it calls `rank_strength(card, contract_type)`
which returns T=4, J=3, Q=2, K=1, A=0 for Low (`core/cards.py:155–165`).
So `min(..., key=card_value)` in `_choose_discard()` **correctly**
prefers to dump A, then K, then Q, then J, and preserves the T — the
opposite of what #2502's headline asserts.

The operator's correction comment on #2502 (trick 9: Ace plays J♣
while holding 10♠) is consistent with correct dump behavior: J (value
3) is cheaper than T (value 4), so the dump picks J. Preserving the T
in hand is the right local choice because the T is the highest rank
in Low.

**The real Low-contract bug is Defect A (lead heuristic never cashes
the preserved T).** Once the AI holds a T and opponents are out of
that suit, it should LEAD the T to cash it. The current lead heuristic
leads from "longest suit, highest card" — which will include the T
if its suit is the longest, but not otherwise. A T in a length-1 suit
is treated as a non-lead card forever, even after that suit is drained.

So #2502 and #2504 share the same surface manifestation (AI
holds a sure winner in a short suit until it's too late) and the same
root cause (no sure-winner priority in the lead heuristic).

### Defect E — `_choose_discard` trump-contract comment references #2300

`greedy.py:350–355` and `greedy.py:891–895`:

```python
# Dump the lowest-value non-trump card.  The previous
# void-suit sort tried to create voids by preferring
# shorter suits, but this caused Aces to be dumped from
# non-void suits while low cards in the "kept" suit were
# preserved — a net trick loss.  See #2300.
return min(non_trump_indices, key=card_value)
```

This is a recent correctness fix (#2300) that deliberately prioritizes
value-preservation over void creation. It is **correct** — it preserves
the ace that the sure-winner lead heuristic should eventually cash.
The bug is that the lead heuristic never cashes it. The discard logic
is the responsible upstream contributor; the lead logic is the
irresponsible downstream consumer.

## Why This Is A Distinct Investigation From Prior Glutton Work

The existing
`plans/sessions/2026-03-27_glutton-strategy-revamp-experiment-design.md`
(analyst-a, 2026-03-27, issue #1917) shaped a **bid-aware** GluttonV2
that threads `bid_amount` / `bidder_seat` / `bid_type` through
`on_hand_start()` and adjusts aggression per `tricks_needed`.

This investigation is **orthogonal** to that plan:

| Dimension | GluttonV2 (bid-aware) | This investigation |
|-----------|----------------------|--------------------|
| Input channel | New: bid context | No new inputs |
| Changes backward compat | Yes (new `on_hand_start` params) | No |
| Target defect | Play strategy ignores bid target | Play strategy ignores sure winners |
| Fixes #2502/#2504/#2506 | No — these bugs exist in bidless too | Yes |
| Can ship independently | Yes | Yes |
| Composes with other | Yes | Yes |

The two fix tracks are independently valuable and independently
deployable. GluttonV2 adds an *upward* layer (bid-awareness on top of
solid cashing). This investigation fixes the *downward* layer (cashing
itself). Shipping cash-winners first actually makes the GluttonV2
work easier to measure because the cashing baseline will be higher.

## Proposed Fix — "Cash Winners" Heuristic Bundle

Three targeted changes, all in `src/bid_euchre/strategy/greedy.py`,
replicated in both `GluttonStrategy` and `GluttonIsolatedStrategy`
(behind a new feature flag in the isolated class so the revamp
experiment harness can A/B test it).

### Fix 1 — `_choose_lead`: sure-winner priority (new step 0.5)

Insert a new priority layer between the existing step 0 (both-bowers
+ 5 trump) and step 1 (non-trump aces):

```python
# 0.5 NEW: Cash established sure winners first
#
# A "sure winner lead" is a card in our hand such that, if led,
# _is_sure_winner() returns True — i.e., no unaccounted-for card
# can beat it given the cards we've seen played + the cards still
# in our hand.
sure_winner_leads = [
    idx for idx in legal_indices
    if self._is_sure_winner(hand[idx], plays_so_far=[], hand=hand)
]
if sure_winner_leads:
    # Prefer sure winners from shortest established suit first
    # (frees up length for future leads), then highest value.
    def sure_lead_priority(idx: int) -> Tuple[int, int]:
        eff = effective_suit(hand[idx], self._trump_suit, self._contract_type)
        return (suit_counts.get(eff, 0), -card_value(idx))
    return min(sure_winner_leads, key=sure_lead_priority)
```

**Where it applies:** all contract types. `_is_sure_winner` is already
contract-aware via `cards_that_beat()` (`core/cards.py:221–265`), which
branches on `contract_type` for rank order, trump/bower handling.

**What it fixes:**
- **#2502 (Low):** Once opponents have played their T♠s (or the AI
  holds both T♠s), the AI's T♠ becomes a sure winner. The new step
  0.5 picks it up as a lead even if spades isn't the longest suit.
- **#2504 (High):** After clubs has been led once (Slim observes
  partner's `10♣` and maybe other clubs), Slim's A♣ may already be
  a sure winner. Even if not, once Slim's hand drops to 4 cards and
  he regains the lead, A♣ is trivially sure.
- **#2506 (Suit, both cases):** After running opponents out of clubs,
  remaining A♣/K♣ is a sure winner as a lead in clubs. Likewise after
  winning with RB, the LB becomes a sure winner when led as trump.

### Fix 2 — `_choose_lead` step 2: draw trump from the TOP

```python
# 2. Draw trump if holding >= 4 trumps and NOT holding both bowers
if trump_count >= 4 and trump_indices:
    if not (has_right and has_left):
        # FIX: lead highest trump to clear opponents' top trump
        # (see bid-euchre.com, pagat.com, and bridge "draw trump
        # from the top" principle). The previous behavior leading
        # the lowest trump left master cards unplayed until too
        # late (#2506).
        return max(trump_indices, key=card_value)
```

**What it fixes:** the left-bower-held-to-trick-9 failure mode in
#2506 second trace. `card_value` correctly ranks `J♣^LB` higher than
other trumps (`card_value_for_dump` adds +10 for trump and +4 for LB),
so `max` picks the LB first, then RB (if present), then K, Q, and
down.

**Interaction with Fix 1:** Fix 1 fires *before* step 2, so when the
LB is a sure winner (all RBs accounted for), Fix 1 cashes it. Step 2
only fires when trump >= 4 and we're in a weaker draw-trump state.
Leading max in that state is still correct.

**Subtlety:** an argument can be made for "lead from the top of a
sequence, not the absolute top" — e.g., don't burn an RB if the
opponents' last trump is only a 10. This is a refinement for a
future PR and should not block the first fix. The current behavior
(`min`) is unambiguously wrong in the common case. (Document this
in the fix PR as a known follow-up.)

### Fix 3 — Following: refine "cheapest winner" to prefer sure winners, then fall back to 2nd-hand-low

```python
# Standard winning logic (currently in choose_card lines 597-608)
if winning_candidates:
    # NEW: split winners into sure winners and provisional winners.
    sure_winning_candidates = [
        idx for idx in winning_candidates
        if self._is_sure_winner(hand[idx], plays_so_far, hand)
    ]
    if sure_winning_candidates:
        # Play cheapest card that is actually guaranteed to win
        return min(sure_winning_candidates, key=card_value)

    # NEW: 2nd-hand-low fallback — if my best winner is only a
    # provisional winner (can still be beaten), and I'm in 2nd
    # seat, dump low instead of burning a mid-card as a false winner.
    pos = len(plays_so_far)
    if pos == 1:  # 2nd seat
        return self._choose_discard(hand, legal_indices)

    # 3rd and 4th seat: retain current behavior (play cheapest
    # provisional winner). 3rd seat should attempt to win; 4th
    # seat has perfect info so provisional == actual.
    return min(winning_candidates, key=card_value)
```

**What it fixes:** Defect C exactly — Slim no longer burns J♣ as a
false 2nd-seat winner when the true sure winner (A♣) is still in
hand. Slim dumps a low card in 2nd seat. Partner (Deuce) gets to
decide in 4th seat with full information.

**Interaction with partner awareness:** Fix 3 sits inside the main
`if winning_candidates:` branch, which executes **after** the
partner-winning branch (`greedy.py:540–595`). Partner awareness is
unaffected.

**Subtlety — 2nd-seat exceptions:** "2nd hand low" has known
exceptions (e.g., covering an honor, forcing a split). These are
not implemented here; the fix is intentionally minimal. A conservative
refinement would be to also play high in 2nd seat if the card is a
*sure winner*, which is exactly what the first branch of Fix 3
already does.

## Acceptance Criteria

1. **Code:** all three fixes landed in `GluttonStrategy`, and
   `GluttonIsolatedStrategy` exposes **two independent feature flags**
   so Cash-A and Cash-B can be isolated in A/B experiments even after
   both PRs ship:
   - `cash_winners_on_lead` — gates Fix 1 (sure-winner lead priority)
     and Fix 2 (draw trump from the top). Shipped by Cash-A.
   - `cash_winners_on_follow` — gates Fix 3 (sure-winner follow +
     2nd-hand-low fallback). Shipped by Cash-B.

   Both default to `True` on `GluttonStrategy` (production behavior)
   and default to `False` on `GluttonIsolatedStrategy` (baseline
   behavior, overridable per experiment). This lets the experiment
   matrix enumerate all four combinations:
   `(lead=False, follow=False)`, `(lead=True, follow=False)`,
   `(lead=False, follow=True)`, `(lead=True, follow=True)`.
2. **Unit tests:**
   - New tests in `tests/unit/test_greedy.py`:
     - Low contract: AI leads preserved T once opponents void.
     - High contract: 2nd-seat Slim dumps low instead of burning J
       when A is still held.
     - Suit contract: AI leads LB immediately after cashing RB in a
       4+ trump hand.
     - Suit contract: AI cashes remaining side-suit A after running
       opponents out (two-lead sequence).
     - Equivalence test for `GluttonIsolatedStrategy` with
       `cash_winners_on_lead=False` and
       `cash_winners_on_follow=False`: identical behavior to pre-fix
       snapshot.
     - A/B isolation test: with only `cash_winners_on_lead=True`,
       Cash-A behaviors fire but Cash-B does not (and vice versa).
3. **Regression test:** existing strategy test files pass unchanged:
   `tests/unit/test_greedy.py`, `tests/unit/test_glutton.py`,
   `tests/unit/test_strategy.py`, `tests/unit/test_strategy_correctness.py`,
   and `tests/unit/test_strategy_registry.py`.
4. **Statistical proving (Tier 2 experiment):** a seeded
   head-to-head run with pre-fix `GluttonIsolatedStrategy`
   (both cash flags `False`) and post-fix `GluttonStrategy`
   (both cash flags `True`) seated opposite each other on the
   **same deals**, using the canonical runner in
   `head_to_head_matrix` mode (the mode used by
   `scripts/internal/run_arc_d_h2h_battery.py`), 50,000 deals
   across the 6 contract × trump scenarios reused from
   `plans/sessions/2026-03-27_glutton-strategy-revamp-experiment-design.md`
   §Phase 1A. Because both strategies play the same matched deals,
   post-hand analysis must compute **paired deltas** via
   `bid_euchre.analysis.paired.compute_paired_deltas` +
   `bid_euchre.analysis.stats.paired_t_ci`. Post-fix must win or tie
   on `avg_tricks_team0` (paired bootstrap, p < 0.05, 95% CI lower
   bound ≥ 0).

## Validation Commands

```bash
# Tier 1 (during implementation)
uv run python -m pytest tests/unit/test_greedy.py -x

# Tier 2 (before PR)
make check-gated

# Tier 2 statistical proving — paired H2H matrix on matched deals.
# Cash-A creates a new experiment config under experiments/configs/
# (proposed filename stem: "glutton_sure_winner_h2h") that declares
# both strategies seated across the 6 contract x trump scenarios and
# sets mode: head_to_head_matrix. Replace <CONFIG_PATH> below:
#
# uv run python experiments/run_experiment.py \
#   --config <CONFIG_PATH> \
#   --seed 42 --n_per 50000
#
# After the run completes, compute the paired bootstrap gate from
# the emitted JSONL hand records (not from rollup.json):
#
# uv run python -c "
# from bid_euchre.analysis.paired import (
#     load_paired_data, compute_paired_deltas,
# )
# from bid_euchre.analysis.stats import paired_t_ci
# run_dir = 'data/runs/<RUN_ID>'
# data = load_paired_data(run_dir,
#     ['glutton_isolated_baseline', 'glutton_cash_winners'])
# deltas = compute_paired_deltas(data, metric='team0_tricks')
# mean_d, lo, hi = paired_t_ci(deltas.tolist())
# assert lo >= 0, f'Paired gate failed: CI=[{lo:.3f}, {hi:.3f}]'
# print(f'mean_delta={mean_d:+.3f} 95% CI=[{lo:+.3f}, {hi:+.3f}]')
# "
#
# NOTE: scripts/compare_runs.py is NOT suitable for this gate -- it
# compares two independently-sampled runs on bootstrap distributions,
# not paired per-deal deltas. Use the analysis.paired module instead.

# Tier 2 browser smoke (operator validation)
# Manual playtest via the hosted game: play one Low, one High, and
# one Suit contract against the AI and observe cash-winner behavior.
# Target: AI leads its sure winners rather than holding them.
```

## Risk Register

| Risk | Severity | Mitigation |
|------|---------|-----------|
| Sure-winner detection is expensive (O(hand × deck)) | LOW | `_is_sure_winner()` already exists and is called in partner-cover path without perf issue. Lead phase is called once per trick per player (≤ 40 calls/hand). |
| Fix 2 (draw trump high) hurts strategies relying on low-trump draws | MEDIUM | Gate behind `GluttonIsolatedStrategy` flag and run feature isolation experiment (Phase 3C template in analyst-a's 2026-03-27 plan). |
| Fix 3 (2nd-hand-low) regresses on hands where forced winning is correct | MEDIUM | Only applies when no sure winner exists among candidates; sure winners still win aggressively. Verify with feature isolation. |
| Cascading effect on bidder-play pairs (OLSa/Bud Bot) | MEDIUM | Both browser models share GluttonStrategy — the fix uniformly lifts both. A/B via experiment config comparing pre/post for each bidder. |
| Post-merge review may flag "why two files" for duplicated fix in `GluttonIsolatedStrategy` | LOW | Existing convention: `GluttonIsolatedStrategy` is a deliberate feature-flag twin. Follow-up refactor to share helpers is out of scope. |
| Interaction with future GluttonV2 (bid-aware) work | LOW | Changes are additive and do not touch `on_hand_start()` signature; GluttonV2 can layer bid-aware logic on top. |
| #2502 headline claim is inaccurate (Defect D above) | LOW | Explain in PR description; fix still addresses the real underlying bug (no cash-winners). |
| Ties-broken-by-seat-order in double deck may affect tests | LOW | Use fixtures where winners are unambiguous (use distinct ranks); don't rely on seat tiebreakers. |

## Recommended PR Decomposition

**Track:** single author lane, 2 sequential PRs.

| PR | Scope | Size | Validation | Depends on |
|----|-------|------|-----------|-----------|
| **Cash-A:** Sure-winner lead + draw trump high in `GluttonStrategy` + `GluttonIsolatedStrategy` (behind `cash_winners_on_lead` flag) | `src/bid_euchre/strategy/greedy.py`, `tests/unit/test_greedy.py`, new `experiments/configs/` H2H YAML | ~150–250 LoC + ~20 test cases | `make check-gated`; unit tests; paired H2H on matched deals via `analysis.paired` | none |
| **Cash-B:** 2nd-hand-low / prefer-sure-winners in the follow phase (both classes, behind `cash_winners_on_follow` flag) | `src/bid_euchre/strategy/greedy.py`, `tests/unit/test_greedy.py` | ~60–120 LoC + ~10 test cases | same as Cash-A + explicit 2nd-seat scenario tests; paired H2H reusing Cash-A config | Cash-A |

Both PRs deliberately keep the scope to `greedy.py` and its tests.
Neither PR touches `web/`, the hosted_play engine, the bidding
policies, or the experiment runner itself (only adds a new experiment
YAML config).

**Why two PRs, not one:**
- Cash-A fixes the lead phase defects (A, B) which are independently
  testable and independently shippable.
- Cash-B fixes the follow-phase defect (C) which has a different
  surface (`choose_card` main path vs `_choose_lead`) and a different
  risk profile (2nd-hand-low rule is more contestable than
  cash-established-winners).
- Decomposition lets the measurement-integrity review separate
  lead-phase and follow-phase effects in bootstrap CIs.

**Out of scope for these two PRs** (explicit):
- Bid-aware aggression (that is GluttonV2 — see 2026-03-27 plan)
- Per-suit length-based sure-winner sequencing refinements
- Moon / loner play adjustments
- 3rd-seat / 4th-seat exception handling beyond current Glutton logic
- Refactor to share helpers between `GluttonStrategy` and
  `GluttonIsolatedStrategy`
- Retraining any artifact-backed bidder (OLSa, Bud Bot) — play
  strategy changes do not invalidate bidder artifacts

## Complexity & Risk Estimate

- **Implementation complexity:** **Medium.** ~200–400 LoC total,
  localized to one file, reusing existing utilities (`_is_sure_winner`,
  `cards_that_beat`). No new dependencies. No schema changes.
- **Test complexity:** **Medium.** ~30 new unit tests covering the
  three bug scenarios × three contract types × edge cases. Fixtures
  are straightforward (construct hand + plays_so_far + assert chosen
  card).
- **Review complexity:** **Medium.** Correctness reasoning requires
  thinking through trick-play states and double-deck sure-winner
  semantics. Codex review should catch any rank-inversion mistakes.
- **Experimental complexity:** **Medium.** ~5 min per 50K deals
  H2H × 3 matchups × 2 conditions ≈ 30 min compute. The paired
  analysis stack (`bid_euchre.analysis.paired.compute_paired_deltas`
  + `bid_euchre.analysis.stats.paired_t_ci`) is already scaffolded
  and is the correct path for matched-deal comparison.
  `scripts/compare_runs.py` is **not** suitable — it compares two
  independently-sampled runs, not paired deltas.
- **Live-game risk:** **LOW–MEDIUM.** The browser game is post
  go-live with real players. The fix is a strict improvement in
  expected play quality (cashing winners is universally better
  than burning them). But any change to `GluttonStrategy` affects
  every datapoint collected during the pilot; note this in release
  notes and preserve the pre-fix baseline in `data/runs/` for
  pre/post comparison.
- **Rollback plan:** Git revert of the two PRs. No migrations, no
  schema changes, no external state.

## Smoke Test / User Validation Boundary

After both PRs land, the operator should run the following manual
smoke tests in the live hosted game:

1. **Low contract smoke:** Open a hand where the AI is dealt a
   monster in Low (multiple 10s). Bid Low as the human. Verify the
   AI leads its 10s aggressively (not on trick 9–10).
2. **High contract smoke:** Play a hand where the AI is not declarer
   but holds an ace. Verify that when the AI gets the lead, it
   cashes the ace at its first opportunity rather than holding it.
3. **Suit contract smoke:** Play a hand where the AI is declarer
   with both bowers + one extra trump. Verify it leads RB then LB
   in sequence rather than going RB → small trump → LB deferred.
4. **Regression smoke:** Play three additional hands of mixed
   contracts. Verify no new obvious misplays (e.g., AI not leading
   worthless junk when sure winners are held).

The smoke tests should happen post-merge, with a dedicated issue
(`needs-verification` label) tracking completion per
`.claude/rules/deferred/55_issue_closure.md` Tier 2.

## Known Risks & Scope Traps

- **Do not expand scope to bid-aware logic.** That is GluttonV2 (issue
  #1917 / 2026-03-27 plan). This fix is strictly about mechanical
  card selection and must stay orthogonal.
- **Do not retire `GluttonIsolatedStrategy`.** It is actively used in
  feature isolation experiments. Add the two independent flags
  `cash_winners_on_lead` and `cash_winners_on_follow` as described in
  §Acceptance Criteria item 1; do not fold the two classes together
  and do not collapse the flags into one.
- **Do not change `card_value_for_dump` or `rank_strength`.** Those
  utilities are correct; the bug is in the strategy logic that
  consumes them.
- **Do not touch `cards_that_beat` or `card_strength_in_trick`.** The
  core comparators are contract-aware and correct.
- **Do not change `on_hand_start()` / `observe_play()` signatures.**
  Those are the GluttonV2 extension surface and must remain stable.
- **Double-deck tiebreakers.** If two sure winners exist (one
  already-played copy and one in hand), use fixtures that avoid
  ambiguous tiebreakers in tests.

## Issue Linkage

Open after implementation — use `Refs #2502`, `Refs #2504`, `Refs #2506`
on both PRs. Per `.claude/rules/deferred/55_issue_closure.md` Tier 2,
add `needs-verification` label after merge and close the three issues
only after operator smoke validation.

## References

### Repository code
- `src/bid_euchre/strategy/greedy.py:78–620` — `GluttonStrategy`
- `src/bid_euchre/strategy/greedy.py:623–1077` — `GluttonIsolatedStrategy`
- `src/bid_euchre/strategy/base.py:125–149` — `card_value_for_dump`
- `src/bid_euchre/core/cards.py:145–265` — `rank_strength`,
  `card_strength_in_trick`, `cards_that_beat`
- `web/ai_manager.py:141,177` — hosted-play strategy wiring

### Prior work
- `plans/sessions/2026-03-27_glutton-strategy-revamp-experiment-design.md`
  — analyst-a's GluttonV2 bid-aware plan (orthogonal, complementary)
- PR #2300 — discard logic void-creation regression fix (preserves
  the value this investigation teaches the lead phase to cash)
- Issues #2502, #2504, #2506 — operator bug reports

### External research
- [Bid Euchre - Pagat](https://www.pagat.com/euchre/bideuch.html)
- [How To Play - Bid Euchre](https://bid-euchre.com/how_to_play)
- [Adventures in Bridge — Fundamentals of Trick Taking](https://www.advinbridge.com/this-week-in-bridge/614)
- [Bridge Mojo — When to Delay Drawing Trump](https://bridgemojo.com/sites/default/files/BridgeWhiz/Lesson%207%20-%20When%20to%20Delay%20Drawing%20Trump%20Handout.pdf)
- [World of Card Games — Hearts AI Rule Set](https://worldofcardgames.com/blog/2025/07/when-ai-learned-to-play-hearts-study)
- [bid and made — Draw trumps first unless you have a good reason not to](http://www.bidandmade.com/bridge_bid_and_play/Bridge_Play_1312_Draw_trumps_first_unless_you_have_a_good_reason_not_to.php)

## Orchestrator Handoff

**Dispatch recommendation:** dispatch Cash-A and Cash-B sequentially
to a single author lane (author-a or author-b). Each PR is a
1–3 hour unit.

**Required execution sequence (AGENTS.md §12.4):** The receiving author
lane must, for each task packet, do the following in order before
writing any production code:

1. Refresh this plan plus the relevant governing-plan context
   (browser game expansion + any active GluttonV2 notes).
2. Draft or refine a concrete execution plan inline in the task
   (scope, file list, test list, H2H config shape, acceptance gate).
3. Spawn at least one reviewer agent to review that execution plan
   before making substantive edits to `greedy.py`.
4. Create a TUI task list covering implementation, unit tests, Tier 2
   paired H2H run, paired-bootstrap gate, and PR shipment.
5. Assess the work for safe parallelism — Cash-A and Cash-B are
   sequential (B is blocked by A); within each PR the unit tests and
   experiment config work on disjoint files and can run in parallel.
6. Execute the work end to end autonomously: implement → unit tests →
   `make check-gated` → H2H run → paired bootstrap → commit → open PR
   → include `Validation Performed` evidence (paired mean delta and
   95% CI per scenario, unit test output, `make check-gated` summary)
   in the PR body.

Handoffs that skip any of these steps are incomplete per AGENTS.md
§12.4.

**Task packet skeletons:**

1. **Cash-A:** *Sure-winner lead priority + draw trump from the top*
   - `scope_declared`: `src/bid_euchre/strategy/greedy.py`,
     `tests/unit/test_greedy.py`,
     and a new paired H2H experiment YAML under
     `experiments/configs/` (proposed filename stem
     "glutton_sure_winner_h2h" — Cash-A creates it, using
     `mode: head_to_head_matrix` so both strategies play matched deals)
   - `validation`: `make check-gated` then the H2H run and paired
     bootstrap gate described in §Acceptance Criteria item 4 and
     §Validation Commands. **Do not** use `scripts/compare_runs.py`
     for the acceptance gate — it compares independent runs, not
     paired per-deal deltas. Use
     `bid_euchre.analysis.paired.compute_paired_deltas` +
     `bid_euchre.analysis.stats.paired_t_ci` on the emitted JSONL
     hand records.
   - Reference: this doc §Fix 1, §Fix 2

2. **Cash-B:** *Sure-winner follow + 2nd-hand-low fallback*
   - `scope_declared`: `src/bid_euchre/strategy/greedy.py`,
     `tests/unit/test_greedy.py`
   - `validation`: `make check-gated` + unit tests covering 2nd-seat
     false-winner scenario; regression paired H2H reusing Cash-A
     config (same `analysis.paired` gate)
   - Reference: this doc §Fix 3
   - **Blocked by:** Cash-A merged

**Author lane guidance:** use `planning-code-first` skill to read
the actual `_choose_lead` / `choose_card` signatures before
implementing. Do not guess; the file is dense and the
feature-flag twin adds surface area.

**Do not dispatch** until operator decides whether to:
(a) Ship these fixes as standalone PRs now (recommended — low risk,
    high live-game impact), or
(b) Bundle them into the larger GluttonV2 initiative (delays live-game
    fix for ≥ 3 PRs of additional work).

Given the task packet note ("We are post go-live with real players.
The AI bugs are noticeable but not blocking. We want to understand
the fix scope before committing to it."), the recommendation is
**(a) — ship standalone**. The scope is bounded, the fix is a strict
improvement, and the orthogonality to GluttonV2 is preserved.

## Outcome

*(To be filled after implementation)*
