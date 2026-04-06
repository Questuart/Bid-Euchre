# Cash-A Deep Audit — Four Operator Bug Claims

**Date:** 2026-04-06
**Lane:** analyst-c (packet `a5a245aef26c`)
**Scope:** Investigation only. No implementation.
**Subject PR:** #2534 (`feat(strategy): Cash-A sure-winners + draw-trump lead fixes for Glutton`)
**Production state:** `cash_winners_on_lead=False` by default on both `GluttonStrategy` and `GluttonIsolatedStrategy`; operator has a temporary override in `web/ai_manager.py` (lines 141, 177) force-enabling the flag on the running server at `http://localhost:8000` for local proving.
**Strategy version:** `GLUTTON_STRATEGY_VERSION = "0.8.0"` (`src/bid_euchre/strategy/greedy.py:25`)

## 1. Executive Summary

| # | Claim | Verdict | Fix Location | Severity |
|---|---|---|---|---|
| 1 | `_draw_trump_lead()` burns LB on trick 2 when the second RB is still unaccounted for | **CONFIRMED BUG** | `src/bid_euchre/strategy/greedy.py` `_draw_trump_lead()` (both Glutton classes) | **HIGH** — fires on both Fix 1b (step 0.75) and Fix 2 (step 2) paths, directly reproduces operator's observed failure. Must fix before flag flip. |
| 2 | Cash-A step 0.5 `(suit_count, -card_value)` priority leads the shortest side-suit ace first, opening ruffing opportunities | **NOT A BUG** in Cash-A — but surfaces a **pre-existing** Step 1 behavior the operator may want to revisit separately | Pre-existing non-trump ace priority at `_choose_lead()` step 1 (line 366–381). Cash-A step 0.5 is correctly gated by `_is_sure_winner()` and does not fire in the scenario operator described. | LOW — Cash-A's sure-winner gating already prevents the described failure mode. |
| 3 | Cash-A hardcodes "lead aces tricks 1-4" instead of sequence-winner detection in high/low | **NOT A BUG** | None. Current behavior already matches the operator's expectation exactly. Driven entirely by `_is_sure_winner()` with **no** trick-number references anywhere in `greedy.py`. | NONE |
| 4 | Discard should dump A/K/Q/J in LOW (keep T) and T/J/Q/K in HIGH (keep A) | **NOT A BUG** | None. `_choose_discard()` already uses `min(..., key=card_value_for_dump)`, which via `rank_strength` inversion in LOW produces the exact order operator wants. | NONE |

**Recommended action:** Dispatch a single implementation packet for Claim 1 (`_draw_trump_lead()` sure-winner-first fallback). Claims 2, 3, and 4 need no code change. Claim 2's tie-break direction for non-trump ace leads (Step 1) is a long-standing design call; if the operator wants to change it, it should be a separate, clearly-scoped task tracking its own test impact and experiment rerun cost.

---

## 2. Per-Claim Walkthroughs

### Claim 1 — `_draw_trump_lead()` burns LB on trick 2 — **CONFIRMED BUG**

#### 2.1 Code lens

`_draw_trump_lead()` is shared by Cash-A Fix 1b (step 0.75, "draw trump first")
and Fix 2 (step 2, "draw trump from the top"). Current implementation:

```python
# src/bid_euchre/strategy/greedy.py:276-289  (GluttonStrategy)
def _draw_trump_lead(self, trump_indices: List[int], hand: List[Card]) -> int:
    """Lead the highest-ranking trump from the given indices.

    Shared by Cash-A Fix 1b (draw trump first) and Fix 2 (draw
    trump from the top). ``card_value_for_dump`` already ranks
    bowers above non-bower trump above non-trump, so ``max``
    naturally picks RB > LB > A > K > Q > ... > 10.
    """
    return max(
        trump_indices,
        key=lambda i: card_value_for_dump(
            hand[i], self._contract_type, self._trump_suit
        ),
    )
```

Mirror at `greedy.py:937-948` on `GluttonIsolatedStrategy`.

Relevant `card_value_for_dump` values for spade-trump (`src/bid_euchre/strategy/base.py:125-149`):

| card | base (rank_strength suit) | trump bonus | bower bonus | total |
|---|---:|---:|---:|---:|
| J♠ (RB) | 1 | +10 | +5 | **16** |
| J♣ (LB) | 1 | +10 | +4 | **15** |
| A♠ | 4 | +10 | 0 | **14** |
| K♠ | 3 | +10 | 0 | **13** |
| Q♠ | 2 | +10 | 0 | **12** |
| T♠ | 0 | +10 | 0 | **10** |

`max()` returns LB whenever LB is the only bower in hand and RB is not
present, regardless of whether LB is a sure winner.

#### 2.2 Operator's failure trace mapped onto the code

Observed state (6♠ contract, Ace declaring):

1. **Trick 1:** Ace leads J♠ (RB). Wins.
2. **Trick 2:** Ace leads J♣ (LB). Deuce covers with the second J♠ (RB). Wins for Deuce.

Walk through `_choose_lead()` for trick 2:

| Step | Condition | Fires? | Why |
|---|---|---|---|
| 0 (bowers+5+) | `has_right and has_left and trump_count >= 5` | No | RB already played — `has_right` False. |
| 0.5 (sure-winner cash) | `cash_winners_on_lead` AND any sure winner | No | LB's `cards_that_beat` set = `{J♠}`. `_seen_counts[J♠]=1`, `in_hand=0`, `remaining = 2-1-0 = 1 > 0`. LB **is not** a sure winner. Neither are A♠/K♠/Q♠ (same RB threat). Non-trump A♥/A♦ also not sure (all trump still out). `sure_winner_leads = []`. |
| 0.75 (Fix 1b, draw trump first) | `cash_winners_on_lead` AND `trump_indices` non-empty AND `_opponents_might_hold_trump` | **YES** | Opponents not yet inferred void in trump (trump_suit not in `_void_suits_by_seat[1]` or `[3]`). Step 0.75 fires → calls `_draw_trump_lead(trump_indices, hand)`. |
| → `_draw_trump_lead` returns `max(trump_indices, key=card_value_for_dump)` = **LB (15)**. |

The same `_draw_trump_lead` bug also fires via the Fix 2 path (step 2,
`trump_count >= 4 and not (has_right and has_left)` at `greedy.py:385-395`)
whenever opponents have been inferred void in trump — e.g., after a trump
round where both opponents ruffed offsuit or showed out.

**Bug is in `_draw_trump_lead()` itself**, not in the wiring. Both Fix 1b
and Fix 2 are correct about **when** to draw trump; they are wrong about
**which** trump to lead when no trump in hand is a sure winner.

#### 2.3 Deterministic repro

Run from the repo root:

```bash
uv run python - <<'PY'
from bid_euchre.core.cards import Card
from bid_euchre.strategy.greedy import GluttonStrategy

hand = [
    Card("S", "J"),  # RB
    Card("C", "J"),  # LB
    Card("S", "A"), Card("S", "K"), Card("S", "Q"),
    Card("H", "A"), Card("D", "A"),
    Card("C", "T"), Card("H", "T"), Card("D", "T"),
]
cash = GluttonStrategy(cash_winners_on_lead=True)
cash.on_hand_start(hand, "suit", "S", player_index=0)

# Trick 1: Ace leads RB (Step 0 fires, both bowers + 5+ trump).
idx1 = cash.choose_card(hand, [], "suit", "S", 0)
assert hand[idx1] == Card("S", "J"), hand[idx1]

# Simulate trick 1 plays: Ace RB, opponent low S, partner low S, opp2 low S.
trick1 = [(0, Card("S","J")), (1, Card("S","T")), (2, Card("S","T")), (3, Card("S","Q"))]
for i, (pi, c) in enumerate(trick1):
    cash.observe_play(pi, c, trick1[:i+1], "suit", "S")

# Trick 2 lead. Hand now has LB + AS, KS, AH, AD, TC, TH, TD.
hand_t2 = [Card("C","J"), Card("S","A"), Card("S","K"),
           Card("H","A"), Card("D","A"),
           Card("C","T"), Card("H","T"), Card("D","T")]
idx2 = cash.choose_card(hand_t2, [], "suit", "S", 0)
print("Cash-A trick 2 lead:", f"{hand_t2[idx2].rank}{hand_t2[idx2].suit}")
assert hand_t2[idx2] == Card("C", "J"), f"Expected LB burn, got {hand_t2[idx2]}"
print("CONFIRMED: Cash-A burns LB (J♣) on trick 2 while second RB is still out.")
PY
```

Output (captured during this audit):

```
Cash-A trick 2 lead: JC
CONFIRMED: Cash-A burns LB (J♣) on trick 2 while second RB is still out.
```

The same repro also confirms Fix 2 path — with `_void_suits_by_seat[1].add("S")`
and `[3].add("S")` (opponents inferred void in trump) and a 4-trump hand
`[C-J LB, S-A, S-K, S-Q, H-T]`, Cash-A picks `J♣` (LB) via step 2. Trace:

```
Cash-A (Fix 2 path, voids seeded) chose: JC
CONFIRMED: Fix 2 path also burns LB via _draw_trump_lead.
```

Both repros are lightweight Python snippets — no Playwright required, and
the failure is fully deterministic. These were run against this worktree's
HEAD (`origin/main` + branch `analyst/cash-a-deep-audit-2534`).

#### 2.4 Proposed fix

Concrete diff against `src/bid_euchre/strategy/greedy.py` for `GluttonStrategy`
(mirror identically onto `GluttonIsolatedStrategy` at `greedy.py:937-948`):

```diff
--- a/src/bid_euchre/strategy/greedy.py
+++ b/src/bid_euchre/strategy/greedy.py
@@ -276,14 +276,36 @@ class GluttonStrategy(Strategy):
     def _draw_trump_lead(self, trump_indices: List[int], hand: List[Card]) -> int:
-        """Lead the highest-ranking trump from the given indices.
-
-        Shared by Cash-A Fix 1b (draw trump first) and Fix 2 (draw
-        trump from the top). ``card_value_for_dump`` already ranks
-        bowers above non-bower trump above non-trump, so ``max``
-        naturally picks RB > LB > A > K > Q > ... > 10.
-        """
-        return max(
-            trump_indices,
-            key=lambda i: card_value_for_dump(
-                hand[i], self._contract_type, self._trump_suit
-            ),
-        )
+        """Lead trump: highest sure-winner trump if any, else lowest trump.
+
+        Shared by Cash-A Fix 1b (draw trump first) and Fix 2 (draw trump
+        from the top).  The previous implementation returned the highest
+        ``card_value_for_dump`` trump unconditionally, which burned the
+        left bower whenever the second right bower was still unaccounted
+        for — see ``plans/sessions/2026-04-06_cash_a_deep_audit.md``
+        §Claim 1.
+
+        New rule:
+        - If any trump in hand is a ``_is_sure_winner`` at lead position,
+          lead the highest-valued sure winner (cashes the master and keeps
+          pressure on opponents).
+        - Otherwise, lead the lowest-valued trump to feel out the shape
+          without burning a top card into the still-unaccounted master.
+        """
+        def value(i: int) -> int:
+            return card_value_for_dump(
+                hand[i], self._contract_type, self._trump_suit
+            )
+
+        sure_winner_trump = [
+            i for i in trump_indices if self._is_sure_winner(hand[i], [], hand)
+        ]
+        if sure_winner_trump:
+            return max(sure_winner_trump, key=value)
+        return min(trump_indices, key=value)
```

Apply the same change to `GluttonIsolatedStrategy._draw_trump_lead()`
(`greedy.py:937-948`).

**Why this preserves operator intent:**

| Scenario | Old behavior | New behavior |
|---|---|---|
| Have RB in hand, second RB unplayed | max → RB (16). RB is a sure winner (`cards_that_beat(RB) = {}`). | sure_winner_trump = [RB]. max → RB. **Same.** |
| Have RB in hand, second RB seen | RB is a sure winner. max → RB. | sure_winner_trump = [RB]. max → RB. **Same.** |
| Have LB + non-bower trump, both RB seen | max → LB (15). LB is a sure winner (no RB remaining). | sure_winner_trump = [LB, …]. max → LB. **Same.** |
| Have LB + non-bower trump, **one** RB still out | max → LB (15). **Bug: second RB covers LB.** | sure_winner_trump = [] (LB threatened by 1 remaining RB; A/K/Q/T also threatened). fallback → min → lowest trump (e.g. T♠). **Fix.** |
| Trump-dominant hand: A♠, K♠, Q♠, T♠, both J♠ seen, LB seen | All trump are sure winners. max → A♠ (14). | sure_winner_trump = [A♠, K♠, Q♠, T♠]. max → A♠. **Same.** |
| `_opponents_might_hold_trump=True`, hand = [K♠] only (test_draw_trump_first_on_suit scenario) | Only one trump → max=min=K♠. | sure_winner_trump = [] (RB/LB/A still out). fallback → K♠. **Same** (single-element list). |

The fallback "lowest trump" is the correct feeler lead because:

1. If the opponent covers with their master trump, we lose our cheapest
   card instead of LB/A.
2. If the opponent cannot cover, we still drew a round of trump — which
   is the whole point of Fix 1b/Fix 2.
3. The master trump stays in our hand until a future round when it
   becomes a sure winner (i.e., `_is_sure_winner` returns True).

#### 2.5 Test impact

| Test (`tests/unit/test_greedy.py`) | Current behavior | Effect of fix | Action needed |
|---|---|---|---|
| `test_draw_trump_first_on_suit` (line 262) | Hand `[K♠, A♥, Q♥, T♦]`. Single trump (K♠). Cash-A expects K♠. | Unchanged — `min([K♠]) = K♠`. | **None.** Test still passes. |
| `test_lead_highest_trump_when_drawing` (line 291) | Hand `[T♠, Q♠, K♠, J♣/LB, T♦]`, voids seeded. Cash-A expects LB (max = highest). | **Broken by fix.** None of these trumps are sure winners (RB, LB=in-hand, A♠ all need to be accounted for). Fallback → min → T♠. This is the same as baseline, so the test no longer demonstrates a Cash-A difference in this scenario. | **Rewrite:** keep as a regression test for the lowest-trump fallback (assert cash_choice == T♠, documenting the Claim-1 fix), and add a **new** test that exercises the sure-winner-first path (e.g., rig `_seen_counts` so the trump A is a sure winner and the test asserts Cash-A returns A♠, not min). |
| `test_isolated_strategy_cash_winners_on_lead_enabled` (line 369) | Hand `[K♠, A♥, Q♥, T♦]`. Same as `test_draw_trump_first_on_suit` but via `GluttonIsolatedStrategy`. | Unchanged — single trump. | **None.** |
| `test_sure_winner_lead_high_contract` (line 211) | High contract, no trump involvement. | Untouched. | **None.** |
| `test_sure_winner_lead_low_contract` (line 238) | Low contract, no trump involvement. | Untouched. | **None.** |
| `test_default_flag_preserves_baseline_behavior` (line 325) | Flag off — `_draw_trump_lead` not invoked. | Untouched. | **None.** |
| `test_isolated_strategy_flag_off_by_default` (line 349) | Flag off. | Untouched. | **None.** |
| `test_version_bumped_to_0_8_0` (line 387) | Checks the version constant. | Untouched. | **Version bump needed** — implementation packet should bump `GLUTTON_STRATEGY_VERSION` to `0.8.1` (PATCH per `docs/02_agent/STRATEGY_VERSIONING.md`: behavior change without config surface). Update this test to `"0.8.1"`. |

**New tests to add (implementation packet scope):**

1. `test_draw_trump_lowest_fallback_when_masters_unseen` — rebuild the
   operator's trick-2 scenario and assert the second lead is the lowest
   trump, not LB. Include both `GluttonStrategy` and `GluttonIsolatedStrategy`.
2. `test_draw_trump_prefers_sure_winner_when_masters_accounted` — rig
   `_seen_counts` with both RBs seen, hand contains LB + lower trump, and
   assert Cash-A leads LB (now a sure winner).
3. `test_draw_trump_trump_dominant_hand_cashes_top` — hand contains A♠ +
   lower trump with both RB + both LB seen; assert Cash-A leads A♠.

#### 2.6 Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Fallback "lowest trump" is suboptimal when opponents are void in trump and cannot cover | Low | Step 0.75 is gated on `_opponents_might_hold_trump=True`. If opponents are known void, Step 2 is reached via `trump_count >= 4`; in that branch if no sure winner exists we still prefer to save high trump. Operator may want to revisit Step 2 long-term, but the lowest-trump fallback is strictly better than burning LB into an unknown RB. |
| `_is_sure_winner` is O(cards_that_beat) per candidate; added call per trump lead | Low | Already called in step 0.5; this adds at most 4-6 extra calls per lead. No hot-path impact. |
| Fix regresses the operator-stated intent "lead highest trump when dominant" | Low | For dominant-trump hands (e.g., all top trump cards held, bowers accounted for) every trump in hand becomes a sure winner and `max(sure_winner_trump, key=value)` returns the highest trump — identical to old behavior. |
| Rewriting `test_lead_highest_trump_when_drawing` may mask an unintended behavior regression | Low | The rewrite splits the test into a "fallback" case and a "sure-winner-first" case, strictly widening coverage. Document in the PR body. |
| Version bump (0.8.0 → 0.8.1) invalidates in-flight experiment comparisons | Low | `cash_winners_on_lead=False` is still the production default, so on-disk experiment runs keyed to 0.8.0 remain valid for the baseline cohort. Only Cash-A cohort matches need re-running. |

---

### Claim 2 — Cash-A overplays established side-suit winners — **NOT A BUG**

#### 2.1 Operator's concern restated

Hand: A♠, A♠, A♦, trump = H. Operator believes Cash-A Step 0.5
(`(suit_count, -card_value)` priority) cashes A♦ first then A♠, A♠,
because D is a shorter suit than S. Operator claims A♠, A♦, A♠ would be
safer.

#### 2.2 Why Step 0.5 does not fire

`_is_sure_winner(A♠, [], hand)` at hand start with trump=H:

- `cards_that_beat(A♠, led_suit="S", trump="H", "suit")`
- Strength of A♠ as led suit: `(1, 4)` (non-trump led card, rank 4).
- Beating strength tuples: `(2, r)` for all H trump, `(3, _)` for bowers.
- **6 distinct card identities** beat A♠: `H-T, H-J(RB), H-Q, H-K, H-A, D-J(LB)`.
- For each, `remaining = 2 - seen(0) - in_hand(0) = 2`. Total = 12 unseen
  threats.
- `_is_sure_winner` returns `False` on the first threat it checks.

Same for A♦ and the second A♠. **No sure winners at hand start.**

So Step 0.5 `sure_winner_leads` is empty → falls through to Step 0.75
(draw trump first) or Step 1 (non-trump aces).

#### 2.3 What Cash-A actually does in this hand

Confirmed by deterministic repro (run during this audit):

```
Step 0 (both bowers + 5+ trump): skipped — we have 0 trump.
Step 0.5 sure_winner_leads = []
Step 0.75 (draw trump first): trump_indices=[] → empty → skipped.
Step 1 non-trump aces: ['AS', 'AS', 'AD']
suit_counts = {'S': 4, 'D': 2, 'C': 4}
  idx 0 AS: priority=(4, -4)
  idx 1 AS: priority=(4, -4)
  idx 2 AD: priority=(2, -4)
Cash-A chose: AD (idx 2)
```

The code path that fires for this scenario is **Step 1** (non-trump aces)
at `greedy.py:366-381`, **not** Cash-A Step 0.5. Step 1 is **pre-existing**
Glutton behavior — it predates Cash-A — and its `(suit_count, -card_value)`
priority was not added by PR #2534.

#### 2.4 Is the result bad?

The operator's observed behavior (A♦ led first, then A♠, then A♠) **is**
what Cash-A produces. But:

1. This ordering is decided by the **pre-existing Step 1**, not by Cash-A.
2. When any ace is still subject to ruff (still trump out), leading them in
   any order carries equal per-card ruff risk.
3. When all trump is drawn, all three aces are sure winners and order is
   strictly irrelevant to trick count.
4. The "interleave to hide shape" argument is a card-sense preference with
   marginal information-theoretic value in double-deck bid euchre — it is
   not an obvious trick-count win.

**Verdict:** The claim does not describe a Cash-A bug. It surfaces a
long-standing Step 1 tie-break direction (shortest-suit-first for non-trump
aces) that the operator may disagree with. Any change to that priority
should be:

- Filed as a separate issue with its own evidence and test coverage.
- Scoped against both `GluttonStrategy` and `GluttonIsolatedStrategy` so
  A/B isolation experiments stay symmetric.
- Accompanied by an experiment rerun plan (Arc D + baseline cohorts) to
  measure trick-count impact.

**No fix proposed for Claim 2.**

---

### Claim 3 — High/Low sequence-winner identification — **NOT A BUG**

#### 2.1 Operator scenario

Hand: (T, T, J, J, Q) all in one suit, LOW contract. Operator wants
the order `T, T, J, J, Q`. Also wants no hardcoded "tricks 1-4" rule.

#### 2.2 `_is_sure_winner` trace at hand start

LOW: `rank_strength` returns `{A:0, K:1, Q:2, J:3, T:4}`.

| Candidate | `cards_that_beat` (distinct card IDs) | In hand | Seen | Remaining | Sure winner? |
|---|---|---|---|---|---|
| T♠ | `{}` (T is highest in low) | — | — | 0 | **Yes** |
| J♠ | `{T♠}` (1 id) | 2 | 0 | 2 − 0 − 2 = 0 | **Yes** |
| Q♠ | `{T♠, J♠}` (2 ids) | 2 + 2 | 0 | 0 + 0 = 0 | **Yes** |

All five cards are sure winners immediately. `_choose_lead()` high/low
branch (`greedy.py:432-440`):

```python
if self.cash_winners_on_lead:
    sure_winner_leads = [idx for idx in legal_indices
                         if self._is_sure_winner(hand[idx], [], hand)]
    if sure_winner_leads:
        return max(sure_winner_leads, key=card_value)
```

`card_value` = `card_value_for_dump` = `rank_strength` in high/low.
`max` picks the highest rank first: **T** (rank 4) → **T** (rank 4) → **J**
(rank 3) → **J** → **Q**.

#### 2.3 Deterministic simulation

Confirmed by repro (this audit):

```
LOW  (T,T,J,J,Q in S): ['TS', 'TS', 'JS', 'JS', 'QS']
HIGH (A,A,K,K,Q in S): ['AS', 'AS', 'KS', 'KS', 'QS']
```

Exactly matches the operator's expectation in both directions.

#### 2.4 No hardcoded trick-number rule

Grep of `src/bid_euchre/strategy/greedy.py` for any identifier matching
`trick_number|trick_count|trick_index|trick_idx|trick_num` returns **zero
hits**. The lead logic is driven entirely by `_is_sure_winner()`, which
consults `_seen_counts` (updated by `observe_play`) and the candidate's
own hand — no trick counters, no per-trick special cases.

The earlier "leads aces on tricks 1-4" phrasing in
`plans/sessions/2026-04-06_ai_play_strategy_investigation.md` was an
informal description of the emergent behavior, not a statement about the
code. The code is already doing what the operator wants.

**Verdict: NOT A BUG. No fix needed.**

---

### Claim 4 — Discard behavior in low/high — **NOT A BUG**

#### 2.1 Code lens

`_choose_discard()` HIGH/LOW branch at `greedy.py:485-488`:

```python
else:
    # HIGH / LOW - no trump, so void creation has no benefit
    # Just discard the cheapest card (lowest value)
    return min(legal_indices, key=card_value)
```

`card_value` = `card_value_for_dump`, which for high/low returns
`rank_strength(card, contract_type)` directly (no trump bonus branch).

`rank_strength` inverts in low:
- HIGH: `T:0, J:1, Q:2, K:3, A:4`
- LOW:  `A:0, K:1, Q:2, J:3, T:4`

Therefore `min` dumps the lowest-strength (cheapest) card first:
- **LOW:** A → K → Q → J → T (keep T last)
- **HIGH:** T → J → Q → K → A (keep A last)

This is exactly what the operator wants.

#### 2.2 Deterministic repro

Confirmed by repro (this audit) against a single-suit hand
`[A♠, K♠, Q♠, J♠, T♠]`:

```
LOW hand [A,K,Q,J,T in S]:
  dump order: ['AS', 'KS', 'QS', 'JS', 'TS']
HIGH hand [A,K,Q,J,T in S]:
  dump order: ['TS', 'JS', 'QS', 'KS', 'AS']
```

#### 2.3 Suit contract non-trump discard

The suit contract branch at `greedy.py:465-483` dumps the cheapest non-trump
first, only falling back to trump when non-trump is empty. Repro:

```
SUIT trump=S, hand [A_D, T_C, T_H]:         dump order: ['TC', 'TH', 'AD']
SUIT trump=S, hand [A_D, A_H, T_C]:         dump order: ['TC', 'AD', 'AH']
SUIT trump=S, hand [T_S, Q_S, A_S]:         dump order: ['TS', 'QS', 'AS']
```

All match the operator's stated intent — aces are preserved over low
non-trump, lower trump is preserved over aces only when trump is forced.

**Verdict: NOT A BUG. No fix needed.**

---

## 3. Proposed Fix Diff Summary (Claim 1 Only)

### File: `src/bid_euchre/strategy/greedy.py`

**Two matching edits** — one on `GluttonStrategy._draw_trump_lead` (lines
276–289) and one on `GluttonIsolatedStrategy._draw_trump_lead` (lines
937–948). Both must be updated together because `GluttonIsolatedStrategy`
is a behavior-equivalent twin of `GluttonStrategy` and the comparator
experiment suites assume they agree on Cash-A paths.

See §2.4 above for the exact diff against `GluttonStrategy`. Apply the
identical body to `GluttonIsolatedStrategy._draw_trump_lead`.

### File: `src/bid_euchre/strategy/greedy.py` — version bump

```diff
-#   0.8.0 — Cash-A: sure-winner lead priority, draw-trump-first,
-#           draw trump from the top (behind ``cash_winners_on_lead``
-#           flag, default False). Category: MINOR.
-GLUTTON_STRATEGY_VERSION = "0.8.0"
+#   0.8.0 — Cash-A: sure-winner lead priority, draw-trump-first,
+#           draw trump from the top (behind ``cash_winners_on_lead``
+#           flag, default False). Category: MINOR.
+#   0.8.1 — Cash-A: _draw_trump_lead sure-winner-first fallback
+#           (prevents burning LB when second RB is still out).
+#           Category: PATCH.
+GLUTTON_STRATEGY_VERSION = "0.8.1"
```

### File: `tests/unit/test_greedy.py`

- **Rewrite** `test_lead_highest_trump_when_drawing` as a fallback
  regression guard (Cash-A now picks T♠, matching baseline in the
  current scenario). See §2.5 for rewrite notes.
- **Add** `test_draw_trump_lowest_fallback_when_masters_unseen` mirroring
  the operator's trick-2 scenario.
- **Add** `test_draw_trump_prefers_sure_winner_when_masters_accounted`
  rigging `_seen_counts` to make a trump ace a sure winner.
- **Add** `test_draw_trump_trump_dominant_hand_cashes_top` for the all-top-trump
  case.
- **Update** `test_version_bumped_to_0_8_0` → rename and assert `"0.8.1"`.
- **Mirror** all new tests onto `GluttonIsolatedStrategy` where
  existing symmetry tests exist.

---

## 4. Validation Plan for Implementation Packet

```bash
# Tier 1 — targeted tests during development
uv run python -m pytest tests/unit/test_greedy.py -v

# Tier 2 — full validation before PR (foreground, as per #2271)
make check-gated

# Optional smoke: seeded match-level experiment to confirm no regression
uv run python experiments/run_experiment.py \
  --seed 42 --config experiments/configs/quick_test.yaml
```

Expected delta: no change to baseline (flag off) cohort; measurable
improvement on Cash-A cohort whenever the fix avoids the LB burn.

---

## 5. Playwright Reproduction

Skipped per operator directive during this audit session. The deterministic
Python repros in §2.3 and the engine code path analysis (identical call
path: `MatchEngine._advance_ai` → `play_strategy.choose_card` at
`src/bid_euchre/hosted_play/engine.py:685`) are strictly stronger evidence
than a probabilistic live-game trace: they are reproducible in seconds,
seed-free, and directly exercise the class the web app consumes.

The running server at `http://localhost:8000` was confirmed up at the
start of this audit and the operator's override of
`web/ai_manager.py` (instantiating `GluttonStrategy()` on OLSa and Bud Bot
with `cash_winners_on_lead` force-enabled) is the same `GluttonStrategy`
instance whose `_draw_trump_lead` the deterministic repro exercises. No
evidence gap is introduced by skipping the live Playwright path.

---

## 6. Summary of Recommended Follow-Up

| Action | Owner | Priority |
|---|---|---|
| Dispatch implementation packet for Claim 1 fix (`_draw_trump_lead` sure-winner-first fallback + test updates + version bump 0.8.1) | orchestrator → author lane | **HIGH** (blocks Cash-A flag flip) |
| Close out Claims 2, 3, 4 as "investigated, no action needed" with link to this report | orchestrator | LOW |
| (Optional) Open a separate issue for Step 1 non-trump ace tie-break direction if operator wants to revisit it | operator / analyst | LOW |
| Revert the `web/ai_manager.py` override after the Claim-1 fix merges and a smoke-proving run passes | operator | MEDIUM (post-fix) |

## 7. Outcome

_To be filled after implementation packet ships and the Cash-A flag flip
is re-attempted._
