# Glutton + GBT Bidder Implementation Plan

> **Task:** analyst-a / packet `8406142dcdfc`
> **Date:** 2026-04-06
> **Status:** Plan only — no implementation in this PR
> **Author:** analyst-a
> **Inputs read:** `plans/sessions/2026-04-06_cash_a_deep_audit.md`
> (analyst-c), `plans/sessions/2026-04-06_strategy_versioning_plan.md`
> (analyst-b), `docs/02_agent/STRATEGY_VERSIONING.md`,
> `src/bid_euchre/strategy/greedy.py`,
> `src/bid_euchre/strategy/bidding.py`, `web/ai_manager.py`,
> `tests/unit/test_greedy.py`.
>
> **Inputs deferred:** the analyst-d quick-sim experiment doc
> (filename 2026-04-06_glutton_gbt_quicksim_experiment.md, intended
> location `plans/sessions/`) — **not yet landed** at the time of
> writing. The GBT
> Enhancement A and B sections (§3, §4) are written as **stubs with a
> defined fill-in protocol** so they can be completed in a single
> follow-up edit once analyst-d's experiment design + filter specs
> arrive.

## 0. Purpose

Produce a dispatch-ready implementation roadmap for two parallel tracks
of Glutton / GBT-bidder improvements:

1. **Track 1 — Cash-A.1 (Claim 1 fix from analyst-c's audit).** A
   confirmed bug in `_draw_trump_lead()` that burns the left bower on
   trick 2 whenever the second right bower is still unaccounted for.
   Blocks the production flag flip of `cash_winners_on_lead`.
2. **Track 2 — GBT bidder post-model filters.** Two narrow behavioral
   filters layered onto `GBTActionValueBidder.choose_bid()` (and likely
   `ActionValueBidder.choose_bid()` for symmetry):
   - **Enhancement A** — "don't overbid as last bidder."
   - **Enhancement B** — "don't bump partner's bid by +1 in same suit
     as last bidder."

After reading this plan, the operator should be able to say:

> "Dispatch the Cash-A.1 packet to author-a now, run analyst-d's
> experiment tomorrow, decide on Enhancements A+B after seeing results."

…without any re-derivation. The orchestrator can paste each packet's
`task create` block from §2.7, §3.7, §4.7, and §5.4 with at most a
trivial edit (lane name + priority).

## 1. Executive Summary

| Wave | Track | Deliverable | Auto-merge OK? | Blocks |
|---|---|---|---|---|
| 1a | Cash-A.1 | `_draw_trump_lead` sure-winner-first fallback (PATCH 0.8.0 → 0.8.1) | **YES** (pure bug fix, test-covered, feature-flag-gated) | Wave 2, Wave 1b |
| 1b | Cash-A flag flip | Set `cash_winners_on_lead=True` on `web/ai_manager.py` lines 141 + 177 | **NO** (production behavior change, needs operator smoke) | Wave 6 |
| 2  | Quick-sim experiment | analyst-d's experiment runs against post-1a state | n/a (run, not PR) | Wave 3 |
| 3  | Operator review | Decide whether Enhancements A+B clear the gate | n/a (review) | Wave 4 |
| 4a | GBT Enhancement A | "don't overbid as last bidder" filter | **NO** (AI behavior, needs operator proving) | Wave 5 |
| 4b | GBT Enhancement B | "don't bump partner +1 same suit" filter | **NO** (AI behavior, needs operator proving) | Wave 5 |
| 5  | Operator proving (local) | Browser smoke + targeted scenarios for new bidder filters | n/a (proving) | Wave 6 |
| 6  | Render deploy | Roll the full stack (1a + 1b + 4a + 4b) to production | n/a (deploy) | — |

The dependency graph is **strictly serial across waves**, but **parallel
within Wave 1** (1a and 1b can be drafted in parallel — author lane for
1a, operator-owned 1b — though 1b must NOT merge before 1a) and
**parallel within Wave 4** (4a and 4b are independent if no shared
filter module; serial if they share a new bidding_filters module
under `src/bid_euchre/strategy/`).

The single-file rollback for everything Cash-A is the **flag-flip
revert** (Wave 1b inverse): change `cash_winners_on_lead=True` back to
the default `False`. This is documented per-packet in §6 (Risk
register).

## 2. Cash-A.1 — Claim 1 Fix Implementation Packet (READY TO DISPATCH)

> **Source of truth:** `plans/sessions/2026-04-06_cash_a_deep_audit.md`
> §2.4 (proposed fix), §2.5 (test impact table), §2.6 (risk register).
> Everything below is transcribed from that audit; if the audit and
> this packet ever diverge, the audit is authoritative.

### 2.1 Context

`_draw_trump_lead()` is shared by Cash-A Fix 1b (step 0.75, "draw
trump first") and Fix 2 (step 2, "draw trump from the top"). Current
implementation (`src/bid_euchre/strategy/greedy.py` lines 276–289 on
`GluttonStrategy` and lines 937–948 on `GluttonIsolatedStrategy`) calls
`max(trump_indices, key=card_value_for_dump)`, which returns the **left
bower** whenever LB is in hand and the second RB has not yet been
played. The deterministic repro in the audit (§2.3) confirms the
operator's observed failure exactly.

### 2.2 Target lane

**Recommended:** `author-a` or `author-b` (platform pool).

The change touches `src/bid_euchre/` and `tests/unit/`, which are
platform-pool concerns. Either of `author-a` / `author-b` is fine —
prefer whichever lane has the lightest in-flight queue at dispatch
time. Do **not** route to the browser-game pool (`brws-author-*`) —
the change is in core strategy code, not in `web/`.

### 2.3 Scope declared

```
src/bid_euchre/strategy/greedy.py
tests/unit/test_greedy.py
```

(Optional, not required by the fix itself: `docs/02_agent/STRATEGY_VERSIONING.md`
docstring touch-up to add the 0.8.1 line — only if the implementer wants
to keep the changelog block in greedy.py and the doc in lockstep.)

**Files explicitly NOT in scope:**
- `web/ai_manager.py` — the flag flip is a separate Wave 1b PR (§5).
- `src/bid_euchre/strategy/base.py` — `card_value_for_dump` is unchanged.
- Any `experiments/configs/*.yaml` — the existing
  glutton_cash_winners_paired YAML (if present in
  `experiments/configs/`) is unaffected.
- Any browser-side template, CSS, or route handler.

### 2.4 The exact diff (transcribed from analyst-c §2.4)

Apply this diff to **both** the `_draw_trump_lead` method on
`GluttonStrategy` (`src/bid_euchre/strategy/greedy.py` lines 276–289)
and the same-named method on `GluttonIsolatedStrategy`
(`src/bid_euchre/strategy/greedy.py` lines 937–948). The two
implementations must remain behavior-equivalent because the
comparator experiment suites assume they agree on Cash-A paths.

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

Mirror onto the `_draw_trump_lead` method on
`GluttonIsolatedStrategy` (`src/bid_euchre/strategy/greedy.py` lines
937–948).

### 2.5 Version bump (REQUIRED)

`GLUTTON_STRATEGY_VERSION` bumps **0.8.0 → 0.8.1** per
`docs/02_agent/STRATEGY_VERSIONING.md`:

> **PATCH** — Bug fix that changes which card is played in a *narrow*
> class of states.

The change qualifies as PATCH (not MINOR) because:

- It does not introduce a new behavioral priority — the priorities
  added by Cash-A (steps 0.5, 0.75, 2 with `cash_winners_on_lead`) are
  unchanged.
- It corrects the *implementation* of one helper (`_draw_trump_lead`)
  that those priorities call.
- It fires only when the cohort flag `cash_winners_on_lead=True` is
  set — pre-flag baseline cohort is unaffected.

Diff for the changelog block in `src/bid_euchre/strategy/greedy.py`:

```diff
 # Changelog:
 #   0.7.0 — Initial versioned baseline (PR #2529)
 #   0.8.0 — Cash-A: sure-winner lead priority, draw-trump-first,
 #           draw trump from the top (behind ``cash_winners_on_lead``
 #           flag, default False). Category: MINOR.
+#   0.8.1 — Cash-A: _draw_trump_lead sure-winner-first fallback
+#           (prevents burning LB when second RB is still out).
+#           Category: PATCH.
-GLUTTON_STRATEGY_VERSION = "0.8.0"
+GLUTTON_STRATEGY_VERSION = "0.8.1"
```

> **Versioning conflict watch:** the strategy versioning plan §1.5
> projects 0.8.1 for "Cash-B" (sure-winner follow + 2nd-hand-low
> fallback). Cash-B is **not** part of this implementation plan and
> has not been dispatched. The Claim 1 fix takes 0.8.1 because it
> ships first. When Cash-B is eventually packaged, it bumps to 0.8.2
> (still PATCH if scoped narrowly, MINOR if it adds a new follow
> priority). Update `docs/02_agent/STRATEGY_VERSIONING.md` and the
> Cash-B dispatch packet to reflect this when Cash-B is queued.

### 2.6 Test impact (transcribed from analyst-c §2.5)

| Test (`tests/unit/test_greedy.py`) | Action |
|---|---|
| `test_draw_trump_first_on_suit` (line 262) | **None.** Single-trump hand → `min([K♠]) = K♠`, unchanged. |
| `test_lead_highest_trump_when_drawing` (line 291) | **Rewrite.** None of the trump in this scenario are sure winners; fallback → min → `T♠`. Keep as a regression test for the lowest-trump fallback (assert Cash-A returns `T♠`, document the Claim-1 fix in the test docstring), and split out a new test that exercises the sure-winner-first path (see new test #2 below). |
| `test_isolated_strategy_cash_winners_on_lead_enabled` (line 369) | **None.** Single-trump hand. |
| `test_sure_winner_lead_high_contract` (line 211) | **None.** No trump involvement. |
| `test_sure_winner_lead_low_contract` (line 238) | **None.** No trump involvement. |
| `test_default_flag_preserves_baseline_behavior` (line 325) | **None.** Flag off — `_draw_trump_lead` not invoked. |
| `test_isolated_strategy_flag_off_by_default` (line 349) | **None.** Flag off. |
| `test_version_bumped_to_0_8_0` (line 387) | **Rename + retarget** to `test_version_bumped_to_0_8_1`. Assert `GLUTTON_STRATEGY_VERSION == "0.8.1"`, `GluttonStrategy.VERSION == "0.8.1"`, `GluttonIsolatedStrategy.VERSION == "0.8.1"`. |

**New tests to add:**

1. `test_draw_trump_lowest_fallback_when_masters_unseen` — rebuild the
   operator's trick-2 scenario (hand has LB + non-bower trump, second
   RB still unaccounted) and assert the second lead is the lowest
   trump, not LB. Mirror onto both `GluttonStrategy` and
   `GluttonIsolatedStrategy`.
2. `test_draw_trump_prefers_sure_winner_when_masters_accounted` — rig
   `_seen_counts` so both RBs are seen, hand contains LB + lower trump,
   assert Cash-A leads LB (now a sure winner). Mirror onto both
   classes.
3. `test_draw_trump_trump_dominant_hand_cashes_top` — hand contains A♠
   + lower trump with both RB + both LB seen; assert Cash-A leads A♠
   (highest sure winner). Mirror onto both classes.

### 2.7 Dispatch packet (orchestrator paste-in)

```bash
uv run python scripts/internal/ops.py task create \
  --title "Implement Cash-A.1: _draw_trump_lead sure-winner-first fallback" \
  --owner author-a \
  --priority high \
  --domain platform \
  --scope "src/bid_euchre/strategy/greedy.py" \
  --scope "tests/unit/test_greedy.py" \
  --validation "uv run python -m pytest tests/unit/test_greedy.py -v" \
  --validation "make check-gated" \
  --description "$(cat <<'DESC'
Apply the Claim 1 fix from
plans/sessions/2026-04-06_cash_a_deep_audit.md §2.4 to BOTH
GluttonStrategy._draw_trump_lead (greedy.py:276-289) and
GluttonIsolatedStrategy._draw_trump_lead (greedy.py:937-948).

## Code change

Replace the unconditional `max(trump_indices, key=card_value_for_dump)`
with the sure-winner-first fallback documented in §2.4. Both classes
must update together — they are behavior-equivalent twins.

## Version bump

GLUTTON_STRATEGY_VERSION: "0.8.0" → "0.8.1" (PATCH per
docs/02_agent/STRATEGY_VERSIONING.md). Update the changelog block in
greedy.py to add the 0.8.1 line.

## Test changes

- Rewrite `test_lead_highest_trump_when_drawing` to assert lowest-trump
  fallback (T♠).
- Rename `test_version_bumped_to_0_8_0` → `test_version_bumped_to_0_8_1`
  and assert the new version on both Glutton classes.
- Add three new tests (mirrored on both GluttonStrategy and
  GluttonIsolatedStrategy):
  1. `test_draw_trump_lowest_fallback_when_masters_unseen`
  2. `test_draw_trump_prefers_sure_winner_when_masters_accounted`
  3. `test_draw_trump_trump_dominant_hand_cashes_top`

See plans/sessions/2026-04-06_glutton_gbt_implementation_plan.md §2.6
for the full test impact table.

## PR title

fix(strategy): _draw_trump_lead sure-winner-first fallback (Cash-A.1)

## PR body must include

- Strategy Version block (per docs/02_agent/STRATEGY_VERSIONING.md):
    | Field | Value |
    |-------|-------|
    | Old version | "0.8.0" |
    | New version | "0.8.1" |
    | Bump category | PATCH (Claim 1 fix to _draw_trump_lead) |
    | Behavior delta | When `cash_winners_on_lead=True`, the
                       draw-trump helper now leads the highest-valued
                       sure-winner trump if any, else the lowest-valued
                       trump. Fixes the "burn LB while second RB is
                       still out" trace from operator's bug report. |
    | Affected functions | `_draw_trump_lead` (both Glutton classes) |
    | Unaffected functions | `_choose_lead`, `_choose_discard`,
                              `choose_card`, `_is_sure_winner` |

- Validation Performed section listing:
  - `uv run python -m pytest tests/unit/test_greedy.py -v` (all green)
  - `make check-gated` (all green)
  - Optional smoke: `experiments/run_experiment.py` invocation with --seed 42 against `experiments/configs/quick_test.yaml`

## Acceptance criteria

1. Both GluttonStrategy._draw_trump_lead and
   GluttonIsolatedStrategy._draw_trump_lead use the sure-winner-first
   fallback rule from §2.4.
2. GLUTTON_STRATEGY_VERSION == "0.8.1" and both class VERSION attrs
   equal "0.8.1".
3. All Tier 1 targeted tests pass.
4. `make check-gated` passes.
5. Operator-trace repro from §2.3 of the audit, when run against the
   new code, no longer prints "CONFIRMED: Cash-A burns LB" — instead
   it should print the lowest-trump fallback (T♠ or equivalent).
6. PR body includes the Strategy Version block above.

## Auto-merge policy

AUTO-MERGE OK once the autonomous review loop returns `passed`.
Rationale: pure bug fix, test-covered (3 new tests + 1 rewritten),
feature-flag-gated (only fires when `cash_winners_on_lead=True`,
which is still False by default in production), no contract surface
change.
DESC
)"
```

### 2.8 Validation summary

| Tier | Command | Expected |
|---|---|---|
| Tier 1 — during dev | `uv run python -m pytest tests/unit/test_greedy.py -v` | All green; new tests assert the new behavior. |
| Tier 2 — pre-PR | `make check-gated` | All green. |
| Optional smoke | `experiments/run_experiment.py` with --seed 42 against `experiments/configs/quick_test.yaml` | Same delta as today (flag is still off in production). |
| Operator deterministic repro | The Python snippet in audit §2.3 against the post-fix tree | Output should NOT print "CONFIRMED: burns LB"; should print the lowest-trump fallback (e.g., `Cash-A trick 2 lead: TC` or `TS`). |

### 2.9 Risk register (transcribed from analyst-c §2.6)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Fallback "lowest trump" is suboptimal when opponents are void in trump and cannot cover | Low | Step 0.75 is gated on `_opponents_might_hold_trump=True`. The lowest-trump fallback is strictly better than burning LB into an unknown RB. Operator may want to revisit Step 2 long-term, but that is a separate task. |
| `_is_sure_winner` is O(cards_that_beat) per candidate; added call per trump lead | Low | Already called in step 0.5. Adds at most 4–6 extra calls per lead. No hot-path impact. |
| Fix regresses operator-stated intent "lead highest trump when dominant" | Low | For dominant-trump hands every trump becomes a sure winner; `max(sure_winner_trump, key=value)` returns the highest. Behavior preserved. |
| Rewriting `test_lead_highest_trump_when_drawing` may mask an unintended behavior regression | Low | The rewrite splits the test into "fallback" and "sure-winner-first" cases — strictly widens coverage. Document the rationale in the PR body. |
| Version bump (0.8.0 → 0.8.1) invalidates in-flight experiment comparisons | Low | `cash_winners_on_lead=False` is still the production default; on-disk experiment runs keyed to 0.8.0 remain valid for the baseline cohort. Only Cash-A cohort matches need re-running. |
| Cash-B (future) collides on 0.8.1 | Medium (procedural) | This plan re-targets Cash-B to 0.8.2. Update the strategy versioning plan §1.5 + STRATEGY_VERSIONING.md when Cash-B is dispatched. |

### 2.10 Rollback plan

- **Code rollback:** revert the Claim 1 fix PR. Trivial — no migrations,
  no schema changes.
- **Production behavior rollback:** flip `cash_winners_on_lead` back
  to default `False` in `web/ai_manager.py` (Wave 1b reverse). Even
  faster than reverting the Claim 1 fix because it does not need a
  re-deploy of the strategy module — only of `web/ai_manager.py`.
- **Cohort cleanup:** mark the 0.8.1 cohort as quarantined in
  analysis driven by the `play_strategy_version` column on `matches`
  (no code change, just an analysis-time filter). The cohort boundary
  is honest because the version constant captured the change.

## 3. GBT Enhancement A — "Don't overbid as last bidder" (STUB — pending analyst-d)

> **Status:** Skeleton only. analyst-d's experiment design and the
> precise filter spec live in the analyst-d quick-sim experiment doc
> (filename 2026-04-06_glutton_gbt_quicksim_experiment.md, intended
> location `plans/sessions/`), which has **not yet landed** at the
> time of writing. The fields
> marked **TODO(analyst-d)** must be filled in by the operator or by a
> follow-up analyst-a edit once that file lands. The skeleton is
> structured so the only edits needed are populating those fields and
> running `make check-gated` on the resulting packet.

### 3.1 Behavioral intent (operator-stated)

The GBT bidder should not raise a bid when:
- it is the **last bidder** in the auction (i.e., the dealer's seat
  has bid or passed and the current bidder is the dealer, OR all
  three other seats have already passed),
- the current high bid is one its partner can already make,
- AND the GBT model's predicted EV ranks the raise above the pass by
  only a small margin (i.e., the raise is a marginal call that the
  filter should override).

The exact gate ("only a small margin") is what analyst-d's quick-sim
is supposed to calibrate. Until that's known, the filter spec is
"reject any raise as last bidder if the EV delta vs. pass is below
threshold T", with T = TODO(analyst-d).

### 3.2 Target lane

**Recommended:** `author-b` or `author-c` (platform pool).

The change touches `src/bid_euchre/strategy/bidding.py` (and may also
add a new bidding_filters module under `src/bid_euchre/strategy/`).
Same pool as Cash-A.1 — but use a **different lane** to keep the two
in flight in parallel without scope-lock contention.

### 3.3 Scope declared (provisional)

```
src/bid_euchre/strategy/bidding.py
src/bid_euchre/strategy/bidding_filters.py        # NEW (if generic)
tests/unit/test_bidding.py
tests/unit/test_bidding_filters.py                # NEW (if generic)
```

If analyst-d's spec turns out to be small enough to inline directly
into `GBTActionValueBidder.choose_bid()`, drop the proposed
bidding_filters files from scope and inline. Decision happens at
fill-in time, not at packet-creation time.

**Files explicitly NOT in scope:**
- Any GBT model artifact (`*.joblib`, `*.json`). These are
  **post-model filters** — they reshape the bidder's choice **after**
  inference. The artifacts and `gbt_models` dict are unchanged.
- `web/ai_manager.py` — Bud Bot is instantiated with
  `GBTActionValueBidder(...)`; the filter ships inside the class and
  takes effect on the next deploy automatically.
- `src/bid_euchre/features/` — no new features extracted from the
  observation.

### 3.4 Implementation seam (read from `src/bid_euchre/strategy/bidding.py`)

`GBTActionValueBidder.choose_bid()` lives at `src/bid_euchre/strategy/bidding.py` lines 2515-2550.
Today the method:

1. Enumerates legal actions via `enumerate_legal_actions(obs, …)`.
2. For each action, computes `value` from the appropriate GBT model.
3. Returns `BidAction` with the highest predicted `value`.

The filter slots in **between step 2 (gathering all candidate values)
and step 3 (returning the argmax)**. Concretely, after the loop builds
a list of `(action, value)` pairs, apply a filter that:

1. Detects "last bidder" via the `auction_transcript` and `dealer_seat`
   fields on `BiddingObservation` (`src/bid_euchre/strategy/bidding.py` lines 227-246).
2. Computes the raise candidates and the pass candidate.
3. For each raise candidate, if the raise's value minus the pass
   value is below threshold T, demote the raise (e.g., set its
   effective value to `-inf`).
4. Re-runs the argmax on the filtered list.

This keeps the GBT model untouched and the filter mechanically obvious
in code review. The filter is **purely** behavioral — no retraining,
no artifact bump.

A symmetric filter on `ActionValueBidder.choose_bid()` (line 2310) is
**recommended for parity** so the OLSa cohort also benefits and the
A/B comparator stays meaningful. This is a TODO(analyst-d) decision —
the experiment may indicate the filter is GBT-specific.

### 3.5 STRATEGY_VERSION analog (operator question)

`GLUTTON_STRATEGY_VERSION` exists for the play strategy. The bidder
classes (`ActionValueBidder`, `GBTActionValueBidder`) currently have
**no analog** — the bidder is implicitly versioned by its on-disk
artifact filename (the hybrid_r3 model file, the gbt_action_value model file, etc.)
plus the schema version inside the artifact.

A behavioral filter that fires *outside* the model invalidates this
implicit versioning: the same artifact file produces different bids
before vs. after the filter ships. Operator-facing question for the
implementation packet:

- **Option A:** Add `BIDDING_POLICY_VERSION` constant to
  `src/bid_euchre/strategy/bidding.py`, expose as `VERSION` on `GBTActionValueBidder` (and
  `ActionValueBidder`), and capture it on the `Match` row analogously
  to `play_strategy_version`. Schema change: `bidding_policy_version
  TEXT NULL` on `matches`. Migration: in-process `ALTER TABLE` per
  the strategy versioning plan §1.2 pattern.
- **Option B:** Append the filter spec hash (e.g., the threshold T)
  to the bidder name string and let the existing `ai_model` column on
  `matches` carry it. Cheap, ugly, breaks the clean cohort boundary.
- **Option C:** Don't version. Rely on git history + deploy timestamps.
  This is the "pre-versioning" anti-pattern the strategy versioning
  plan was written to escape — **not recommended**.

**Recommendation:** Option A. The cost is one schema column + one
constant + one PR; the benefit is the same clean cohort boundaries we
just paid to set up for the play strategy. **TODO(analyst-d):**
confirm the operator wants this scope-expanded into the Enhancement A
PR or split into a precursor PR.

### 3.6 Acceptance criteria (skeleton)

For each scenario in the table below, the filter must produce the
specified bid. The exact thresholds and additional scenarios come
from analyst-d's spec.

| Scenario | Pre-filter behavior | Post-filter behavior |
|---|---|---|
| Last bidder (dealer), opponents passed, partner bid 5H, hand could marginally bid 6S | GBT predicts 6S has highest EV by ε margin | **Pass** (filter demotes the marginal raise) |
| Last bidder (dealer), partner bid 4S, our hand strongly supports 5S (large EV margin) | GBT predicts 5S strongly | **5S** (filter does NOT fire — margin above T) |
| Not last bidder (3 seats remaining), GBT predicts 5H marginally | GBT predicts 5H | **5H** (filter does NOT fire — only fires last) |
| Last bidder, partner has not bid (all passes ahead of dealer), GBT predicts 3D opening | GBT predicts 3D | **3D** (filter only fires when partner has a live bid we can rely on) |
| **TODO(analyst-d):** add the precise scenarios from the experiment doc | | |

### 3.7 Dispatch packet (skeleton — DO NOT DISPATCH UNTIL FILLED IN)

```bash
# !! STUB — fill in the TODO(analyst-d) fields before dispatching !!
uv run python scripts/internal/ops.py task create \
  --title "Implement GBT Enhancement A: don't overbid as last bidder" \
  --owner author-b \
  --priority normal \
  --domain platform \
  --scope "src/bid_euchre/strategy/bidding.py" \
  --scope "src/bid_euchre/strategy/bidding_filters.py" \
  --scope "tests/unit/test_bidding.py" \
  --scope "tests/unit/test_bidding_filters.py" \
  --validation "uv run python -m pytest tests/unit/test_bidding.py tests/unit/test_bidding_filters.py -v" \
  --validation "make check-gated" \
  --validation "uv run python experiments/run_experiment.py --seed 42 --config TODO(analyst-d-quicksim-config).yaml" \
  --description "$(cat <<'DESC'
Implement Enhancement A from
plans/sessions/2026-04-06_glutton_gbt_quicksim_experiment.md (analyst-d)
and plans/sessions/2026-04-06_glutton_gbt_implementation_plan.md §3
(analyst-a).

## Behavior

When GBTActionValueBidder.choose_bid() runs as the last bidder
(dealer seat with all preceding seats having bid/passed) AND the
highest-EV raise candidate is within threshold T of the pass EV, the
filter overrides the raise and selects pass instead.

T = TODO(analyst-d) — derived from the quick-sim calibration in
analyst-d's experiment doc.

## Implementation seam

bidding.py:2515-2550 (GBTActionValueBidder.choose_bid). Insert the
filter between the value-collection loop and the argmax return. See
analyst-a's plan §3.4 for the seam description and §3.5 for the
versioning question.

## Symmetry decision

TODO(analyst-d): mirror the filter onto ActionValueBidder.choose_bid()
(bidding.py:2310-2344) so OLSa benefits too. Default: yes, mirror —
keeps the A/B comparator meaningful.

## Versioning question

TODO(analyst-d): Option A (BIDDING_POLICY_VERSION + matches.bidding_policy_version)
vs. Option B (name string append) vs. Option C (skip). Default: Option A.

## Acceptance criteria

See plan §3.6.

## Validation

- Unit tests: TODO(analyst-d) — list per-scenario test names.
- Tier 2: `make check-gated`.
- Quick-sim from analyst-d's experiment doc with --seed 42 against
  the TODO(analyst-d-quicksim-config).yaml.

## Auto-merge policy

NO. Behavior change to the AI bidder. Requires operator local proving
in the browser before deploy. After autonomous review returns
`passed`, leave the PR open and notify the operator.
DESC
)"
```

### 3.8 Fill-in protocol (when analyst-d's file lands)

1. Read analyst-d's quick-sim doc (filename
   2026-04-06_glutton_gbt_quicksim_experiment.md, intended location
   `plans/sessions/`), §"Enhancement A spec" (or equivalently named
   section).
2. Replace every TODO(analyst-d) token in §3.1, §3.4, §3.6, and §3.7
   above with the concrete value from analyst-d's doc.
3. Replace the TODO(analyst-d-quicksim-config) YAML placeholder with
   the actual experiment config path (likely a
   glutton_gbt_quicksim YAML under `experiments/configs/` or similar).
4. Re-audit the §3.6 scenario table for completeness against
   analyst-d's spec; add any missing rows.
5. Decide the symmetry question (mirror to OLSa's `ActionValueBidder`?
   Default yes) and update §3.4 accordingly.
6. Decide the versioning question (Option A/B/C from §3.5) and update
   §3.5 accordingly.
7. Commit the fill-in as a follow-up PR titled
   `docs(analyst): fill in GBT Enhancement A/B specs after quick-sim doc`.
8. Mark this section's status banner as "READY TO DISPATCH".

## 4. GBT Enhancement B — "Don't bump partner +1 same suit as last bidder" (STUB — pending analyst-d)

> **Status:** Same as §3 — skeleton only, fill-in protocol at §4.8.

### 4.1 Behavioral intent (operator-stated)

The GBT bidder should not raise its partner's bid by exactly +1 in
the same suit when:
- it is the last bidder (same trigger as Enhancement A),
- AND the partner's existing bid is a suit contract,
- AND the proposed raise is `partner_bid_n + 1` in the same suit.

Rationale: in this position, the +1 same-suit bump is almost always a
soft over-commit — partner was the high bidder for a reason, and
bumping by 1 in the same suit usually means the bidder is hedging
against partner's actual capability rather than adding real value.

### 4.2 Target lane

**Recommended:** `author-b` or `author-c`. **Serial dependency** on
Enhancement A *iff* both share the proposed bidding_filters module. If
Enhancement A inlines into `choose_bid()` (no shared module), then
Enhancement B can ship in parallel on a different lane.

| Decision | Author lane | Sequencing |
|---|---|---|
| Shared bidding_filters module | Same lane as Enhancement A (e.g., `author-b`) | Serial: A merges first, B rebases onto post-A main |
| Inlined per-class | Different lane from Enhancement A | Parallel — independent scope |

The default in this plan is **shared module → serial**. This is the
safer choice because both filters touch the same `choose_bid` body in
the inlined case, and a parallel-scope conflict between two author
lanes is the worst kind of merge accident.

### 4.3 Scope declared (provisional)

Same as §3.3 — same files, same NOT-in-scope list. If serial on
Enhancement A, the scope is identical and the diff is purely additive
(new filter function in the bidding_filters module, new wire-up in
`choose_bid()`).

### 4.4 Implementation seam

Same as §3.4 — `GBTActionValueBidder.choose_bid()` (and optionally
mirror to `ActionValueBidder.choose_bid()`). The filter stacks **after**
Enhancement A's filter in the same post-model filter chain. Order
matters only if both filters could fire on the same candidate; in
practice, Enhancement A is "demote marginal raises", Enhancement B is
"demote +1 same-suit raises", so they target overlapping but
distinguishable candidates. Run order: A first, then B (the marginal-EV
gate is the more permissive of the two; B is the structural override).

### 4.5 STRATEGY_VERSION analog

If §3.5 chooses Option A (BIDDING_POLICY_VERSION), Enhancement B bumps
the constant by another PATCH:

- Enhancement A: 0.0.0 → 0.1.0 (MINOR — first behavioral filter added).
- Enhancement B: 0.1.0 → 0.1.1 (PATCH — second filter, same module).

If §3.5 chooses Option B or C, no version bump is needed.

### 4.6 Acceptance criteria (skeleton)

| Scenario | Pre-filter behavior | Post-filter behavior |
|---|---|---|
| Last bidder, partner bid 4S, our hand has marginal 5S support | GBT predicts 5S marginally | **Pass** (Enhancement B fires: same-suit +1 bump) |
| Last bidder, partner bid 4S, our hand strongly supports 5S | GBT predicts 5S strongly | **TODO(analyst-d):** does Enhancement B fire on strong support, or only on marginal? Default: fire regardless — the structural rule is "no +1 same-suit bumps as last bidder". |
| Last bidder, partner bid 4S, our hand has 6H | GBT predicts 6H | **6H** (different suit, filter does NOT fire) |
| Last bidder, partner bid 4S, our hand has 5H | GBT predicts 5H | **5H** (different suit, filter does NOT fire — even though it's a +1 in tricks) |
| Last bidder, partner bid 4S, our hand has 5S but partner is 60+ tricks ahead this match (game-state context) | GBT predicts 5S | **TODO(analyst-d):** does game state override? Default: no — the filter is stateless w.r.t. score. |
| Not last bidder, partner bid 4S, our hand has 5S | GBT predicts 5S | **5S** (filter only fires last) |
| **TODO(analyst-d):** add the precise scenarios from the experiment doc | | |

### 4.7 Dispatch packet (skeleton — DO NOT DISPATCH UNTIL FILLED IN)

```bash
# !! STUB — fill in the TODO(analyst-d) fields before dispatching !!
# !! And confirm the serial-vs-parallel decision vs. Enhancement A !!
uv run python scripts/internal/ops.py task create \
  --title "Implement GBT Enhancement B: don't bump partner +1 same suit as last bidder" \
  --owner author-b \
  --priority normal \
  --domain platform \
  --scope "src/bid_euchre/strategy/bidding.py" \
  --scope "src/bid_euchre/strategy/bidding_filters.py" \
  --scope "tests/unit/test_bidding.py" \
  --scope "tests/unit/test_bidding_filters.py" \
  --validation "uv run python -m pytest tests/unit/test_bidding.py tests/unit/test_bidding_filters.py -v" \
  --validation "make check-gated" \
  --validation "uv run python experiments/run_experiment.py --seed 42 --config TODO(analyst-d-quicksim-config).yaml" \
  --description "$(cat <<'DESC'
Implement Enhancement B from
plans/sessions/2026-04-06_glutton_gbt_quicksim_experiment.md (analyst-d)
and plans/sessions/2026-04-06_glutton_gbt_implementation_plan.md §4
(analyst-a).

## Behavior

When GBTActionValueBidder.choose_bid() runs as the last bidder AND
the highest-EV raise candidate is exactly +1 in the same suit as the
partner's bid, the filter overrides it and selects pass instead.

## Dependency

DEPENDS ON Enhancement A (Wave 4a) merging first IF the
bidding_filters.py module is shared. Confirm sequencing with the
operator before dispatch.

## Implementation seam

Same as Enhancement A — see analyst-a's plan §3.4 and §4.4.

## Acceptance criteria

See plan §4.6.

## Validation

- Unit tests: TODO(analyst-d).
- Tier 2: `make check-gated`.
- Quick-sim with --seed 42 against TODO(analyst-d-quicksim-config).yaml.

## Auto-merge policy

NO. Behavior change to the AI bidder. Operator proving required.
DESC
)"
```

### 4.8 Fill-in protocol

Identical to §3.8, scoped to Enhancement B's section of analyst-d's
doc. Both fill-ins should ship in **one** follow-up edit to this plan
to keep the diff reviewable.

## 5. Cash-A Flag-Flip PR (Wave 1b)

### 5.1 Purpose

Set `cash_winners_on_lead=True` on the production `GluttonStrategy`
instances so the Cash-A behavior (now bug-free post-Wave 1a) actually
fires for hosted matches. This is the PR that **enables** Cash-A in
production. It is a separate, narrow PR — keep it separate to make
the cohort boundary in the hosted DB unambiguous (the
`play_strategy_version` column will jump from 0.8.0 → 0.8.1 at the
1a merge, then the *behavior* changes at the 1b merge while the
version stays at 0.8.1; the `created_at` timestamp + the diff between
1a and 1b deploy times disambiguates the two cohorts).

### 5.2 Scope

Two single-line edits in `web/ai_manager.py`:

- **Line 141** (OLSa instantiation): change
  `play_strategy=GluttonStrategy(),` →
  `play_strategy=GluttonStrategy(cash_winners_on_lead=True),`
- **Line 177** (Bud Bot instantiation): same change.

That's the entire diff. No other files. No new tests (the existing
hosted-play tests cover model construction).

> **Audit clarification:** the audit doc mentions a "temporary
> override" the operator was running locally on `lines 141 and 177`.
> Inspection of the current `web/ai_manager.py` (post-merge of the
> Cash-A audit PR #2544) shows lines 141 and 177 are plain
> `GluttonStrategy()` — i.e., the override was a local working-copy
> change that the operator either reverted or never committed. The
> Wave 1b PR therefore **does not need a "revert temporary override"
> step**; it is a clean addition of the `cash_winners_on_lead=True`
> kwarg.

### 5.3 Sequencing

**Hard dependency:** Wave 1b MUST NOT merge before Wave 1a.

If Wave 1b merges first, hosted matches start exercising the buggy
`_draw_trump_lead` immediately on the next deploy — exactly the
failure the Claim 1 fix is meant to prevent. The orchestrator must
gate dispatch of Wave 1b on Wave 1a's merge confirmation.

A safe sequencing pattern:

1. Dispatch Wave 1a (§2.7).
2. Wait for Wave 1a merge + autonomous review pass.
3. Operator confirms Wave 1a is on `main` (`git log` check).
4. Dispatch Wave 1b (§5.4).
5. Wave 1b ships, deploys.
6. Operator runs proving smoke (Wave 5).

### 5.4 Dispatch packet

```bash
uv run python scripts/internal/ops.py task create \
  --title "Flip cash_winners_on_lead=True on OLSa + Bud Bot" \
  --owner brws-author-a \
  --priority normal \
  --domain browser-game \
  --scope "web/ai_manager.py" \
  --validation "uv run python -m pytest tests/unit/hosted_play/test_ai_manager.py -v" \
  --validation "make check-gated" \
  --description "$(cat <<'DESC'
Enable Cash-A in production by adding cash_winners_on_lead=True to
both GluttonStrategy instantiations in web/ai_manager.py.

## Diff

- Line 141 (OLSa): GluttonStrategy() → GluttonStrategy(cash_winners_on_lead=True)
- Line 177 (Bud Bot): same

## HARD PRECONDITION

This packet must NOT be dispatched until the Cash-A.1 PR (analyst-a's
plan §2, packet 8406142dcdfc spawn) has merged to main and CI is
green. If you receive this packet before that merge, **block** and
notify the orchestrator.

## Validation

- `uv run python -m pytest tests/unit/hosted_play/test_ai_manager.py -v`
- `make check-gated`
- Operator local smoke: spin up `make web`, play a hand vs. OLSa,
  observe trump-draw behavior. (This is post-merge, not part of CI.)

## Acceptance criteria

1. `web/ai_manager.py` lines 141 and 177 instantiate GluttonStrategy
   with cash_winners_on_lead=True.
2. Hosted-play unit tests pass.
3. `make check-gated` passes.
4. The next match created on a fresh DB stamps
   matches.play_strategy_version='0.8.1' AND its first hand exhibits
   Cash-A draw-trump-first behavior on a hand with non-trump aces +
   trump.

## Auto-merge policy

NO. Production behavior flip. Operator must run the smoke proving
before merge. After autonomous review returns `passed`, leave open
and notify operator.
DESC
)"
```

### 5.5 Validation summary

Same Tier 1 / Tier 2 as Wave 1a, plus operator smoke proving (see
§7).

### 5.6 Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Wave 1b merges before Wave 1a | Low (procedural) | Dispatch gating in §5.3. Hard precondition stated in the packet description. |
| Cash-A behavior surprises operator on first match | Medium | Operator smoke proving in Wave 5 catches this before pinning to public traffic. |
| Hosted DB cohort boundary ambiguous | Low | The cohort transition is `(version=0.8.1, cash_flag=False) → (version=0.8.1, cash_flag=True)` at the 1b deploy timestamp. Document this transition in MEMORY.md so future analysis can split the cohort by `created_at < 1b_deploy_ts`. The flag itself is not stored on `matches`; it is implicit in the deploy. |

### 5.7 Rollback

**Single-line revert.** Change both `cash_winners_on_lead=True` back
to plain `GluttonStrategy()`. Re-deploy. Total time-to-rollback:
under 5 minutes.

This is the **fastest-acting** rollback for any Cash-A issue and is
the recommended first response if the operator observes any Cash-A
regression after Wave 6.

## 6. Wave Ordering and Dependency Graph

```
Wave 1a (Cash-A.1 fix) ──────────────┬──> Wave 2 (quick-sim) ──> Wave 3 (operator review)
                                     │                                   │
                                     └──> Wave 1b (flag flip) ──────┐    ▼
                                              │                     │   Wave 4a (Enh A)
                                              │                     │       │
                                              ▼                     │       ▼
                                    Wave 5 (operator proving) ◄─────┴──> Wave 4b (Enh B)
                                              │
                                              ▼
                                    Wave 6 (Render deploy)
```

Each wave-to-wave gate is an **operator-controlled signal**:

| Gate | From | To | Operator signal |
|---|---|---|---|
| G1a→2 | Wave 1a merged | Wave 2 dispatched | Operator confirms Cash-A.1 is on main and CI is green; operator gives "run experiment" to the orchestrator. |
| G1a→1b | Wave 1a merged | Wave 1b dispatched | Operator confirms "flip the flag now" to the orchestrator. May be deferred indefinitely if operator wants to let 1a soak first. |
| G2→3 | Quick-sim run finishes | Operator reviews | analyst-d's experiment writes a comparator artifact + report; operator reads. |
| G3→4 | Operator review complete | Enhancement packets dispatched | Operator says "Enhancements A+B clear the gate, dispatch them" OR "no gain, drop them." If "drop", waves 4-6 collapse to "deploy 1a + 1b only". |
| G4→5 | Both Enh A and Enh B PRs merged (or one if the other was dropped) | Operator proves locally | Operator runs the browser smoke against the post-4 main. |
| G5→6 | Operator proving passes | Render deploy | Operator triggers the deploy from `main`. |

### Wave order rationale

- **Wave 1a first** because it is the only blocking bug. Everything
  else stacks on top of it.
- **Wave 1b can be deferred** as long as the operator wants. The
  default is "ship 1a, soak in main for a session, then flip the
  flag", but the operator may flip the flag immediately if they trust
  the test coverage. The plan is agnostic; the dependency is purely
  "1b after 1a".
- **Wave 2 (experiment) blocks Wave 4** because the experiment
  determines whether the GBT enhancements are worth shipping at all.
  If the quick-sim shows no positive delta, the enhancements are
  dropped and Wave 4-5 collapse.
- **Wave 4a and 4b are parallel-or-serial** depending on whether they
  share the bidding_filters module (see §4.2 decision matrix).
- **Wave 5 (proving) before Wave 6 (deploy)** is a hard rule on every
  AI behavior change. The operator must see the new behavior in the
  browser before pinning to the public traffic.

## 7. Test Coverage Matrix

| Packet | Existing tests touched | New tests added | Owner action |
|---|---|---|---|
| Wave 1a (Cash-A.1) | `tests/unit/test_greedy.py::test_lead_highest_trump_when_drawing` (rewrite), `test_version_bumped_to_0_8_0` (rename + retarget) | `test_draw_trump_lowest_fallback_when_masters_unseen`, `test_draw_trump_prefers_sure_winner_when_masters_accounted`, `test_draw_trump_trump_dominant_hand_cashes_top` (×2 for both Glutton classes = 6 total tests) | author-a/b implements |
| Wave 1b (flag flip) | `tests/unit/hosted_play/test_ai_manager.py` (existing model-construction tests) | None required (the kwarg passes through cleanly; existing test asserts roster loads). Optionally add `test_olsa_uses_cash_winners_on_lead` and `test_bud_bot_uses_cash_winners_on_lead` to assert the flag is True on each instance. | brws-author-a implements |
| Wave 2 (experiment) | n/a (analyst-d's experiment is a script run, not a code change) | n/a | analyst-d / experiment runner |
| Wave 4a (GBT Enh A) | TODO(analyst-d): list per-scenario test names from the experiment doc | New test_bidding_filters module (if module split) covering the §3.6 scenarios. At minimum: 5 scenarios × 1-2 test functions = 5-10 new tests. | author-b/c implements |
| Wave 4b (GBT Enh B) | Same module as 4a | New tests in the test_bidding_filters module covering the §4.6 scenarios. At minimum 6 scenarios × 1-2 = 6-12 new tests. | author-b/c implements |

**Coverage gate for the operator:** every new behavior must have at
least one positive test (filter fires when expected) AND at least one
negative test (filter does NOT fire in the specified non-trigger
scenarios). The §3.6 and §4.6 tables are structured so the negative
rows ("filter does NOT fire") are explicit.

## 8. Risk Register and Rollback Plan (whole-stack view)

### 8.1 Per-packet risk summaries

Already documented in §2.9, §3 (skeleton — fill in once analyst-d
lands), §4 (skeleton), and §5.6.

### 8.2 Cross-packet risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Wave 1b ships before Wave 1a | Low (procedural) | Hard dependency gate in §5.3 + the dispatch packet's HARD PRECONDITION block. |
| Cohort boundary in hosted DB confused by 1a + 1b shipping under the same `play_strategy_version="0.8.1"` | Medium | Document the transition `(0.8.1, flag=False) → (0.8.1, flag=True)` in MEMORY.md and the strategy versioning plan §1.1 backfill section. Future analysis splits the cohort by `created_at < 1b_deploy_ts`. The cleaner long-term fix is to also store the flag value on `matches` (deferred — out of scope for this plan). |
| Enhancement A or B introduces a regression that the quick-sim missed | Medium | Operator local proving (Wave 5) is the catch. The single-line rollback is to revert the Wave 4a or 4b PR. |
| GBT model artifact + filter combination produces unexpected interactions on edge auctions | Medium | The filter is **post-model** — the GBT artifact is not retrained, so the worst case is the bidder reverts to its current behavior on every auction (no behavioral lift, but no regression). Pure subtraction. |
| BIDDING_POLICY_VERSION rollout invalidates an in-flight pilot cohort | Low | The MVP versioning plan §1.1 backfill explicitly leaves pre-versioning rows as `NULL`. Same pattern applies to bidder-side versioning. Pre-rollout `Match` rows carry NULL `bidding_policy_version` and that is the honest "unknown cohort" marker. |
| Operator proving (Wave 5) catches a Cash-A.1 issue, not a GBT issue | Low | The flag-flip revert (§5.7) reverses Cash-A independently of the GBT enhancements. The two tracks are independently rollback-able. |

### 8.3 Rollback ladder (fastest to slowest)

For **any** observed regression after Wave 6 deploy:

1. **Flag-flip revert** (~5 min): change `cash_winners_on_lead=True`
   back to default in `web/ai_manager.py`. Reverses Cash-A entirely
   without touching the strategy module. **First response if the
   regression looks Cash-A-shaped.**
2. **Enhancement revert** (~10 min): revert the Enhancement A or B PR
   on `main`, deploy. Reverses the GBT bidder filters without
   touching the rest of the stack.
3. **Full Cash-A revert** (~15 min): revert the Cash-A.1 PR (Wave 1a)
   on `main`, deploy. Restores the pre-Cash-A.1 strategy module. Use
   this only if option 1 doesn't reverse the issue (i.e., the bug is
   in the new `_draw_trump_lead` itself, not in the cashing
   priorities).
4. **Full Cash-A teardown** (~30 min): revert PR #2534 (the original
   Cash-A feature) and Cash-A.1 (Wave 1a), then re-deploy. Restores
   the entire pre-Cash-A baseline. This is the nuclear option; only
   use it if both options 1 and 3 fail.

The rollback ladder is intentionally **stage-additive**: each option
undoes strictly more than the previous one. The operator can climb the
ladder until the regression goes away.

## 9. Out of Scope

This plan does **not** cover, and the implementation packets must
**not** expand to include:

- **Cash-B (sure-winner follow phase).** Tracked separately as per
  analyst-b's 2026-04-06 investigation. When Cash-B is queued, it
  bumps the strategy version to 0.8.2 (this plan re-targets Cash-B
  from the originally projected 0.8.1 because Wave 1a takes the
  0.8.1 slot).
- **Bid-aware GluttonV2.** Tracked in analyst-a's 2026-03-27 plan;
  not in this scope.
- **Retraining OLSa or Bud Bot artifacts.** The GBT enhancements are
  post-model filters — the model artifacts (the hybrid_r3 file,
  the gbt_action_value file, etc.) are unchanged.
- **Non-trump ace tie-break direction (Claim 2 in analyst-c audit).**
  Optional separate issue. The audit already documented why this is
  a long-standing design call rather than a bug.
- **Alembic adoption for hosted DB migrations.** The strategy
  versioning plan §1.5 already noted Alembic as a deferred
  nice-to-have. If §3.5 picks Option A (BIDDING_POLICY_VERSION
  schema column), the migration uses the same in-process ALTER
  TABLE pattern from `web/app.py` lines 118-139.
- **StratBot V3 proving run.** Independent track — flex-a is
  responsible. No dependency on this plan.
- **Per-decision version stamping** on the `decisions` table. Strategy
  versioning plan §1.3 explicitly defers this. Out of scope.
- **CI lint that fails PRs touching `src/bid_euchre/strategy/greedy.py`
  decision functions without a version bump.** Strategy versioning
  plan §2.6 future enhancement. Out of scope.

## 10. Success Criteria for This Plan

After reading this plan, the operator should be able to:

- [ ] Paste the §2.7 dispatch block into `task create` and ship
      Cash-A.1 immediately to author-a or author-b.
- [ ] Decide whether to dispatch Wave 1b (flag flip) immediately or
      after Wave 1a soaks for one session.
- [ ] Run the quick-sim experiment (Wave 2) tomorrow, contingent on
      analyst-d's design landing.
- [ ] Read the experiment results and decide whether to fill in the
      §3 and §4 stubs and dispatch Enhancement A and B, OR drop them
      and skip to Wave 6 with just Cash-A.
- [ ] Identify the rollback action (§8.3 ladder) for any regression
      observed after Wave 6 deploy.

If any of these is unclear, the plan has failed its success criteria
and analyst-a should refresh it before dispatch.

## 11. Outcome

_To be filled after the implementation packets ship and the operator
executes the wave plan._

| Wave | Status | PR(s) | Notes |
|---|---|---|---|
| 1a Cash-A.1 | PENDING | — | Awaiting dispatch from §2.7 |
| 1b Flag flip | PENDING | — | Awaiting Wave 1a merge |
| 2 Quick-sim | PENDING | — | Awaiting analyst-d's experiment doc |
| 3 Operator review | PENDING | n/a | Awaiting Wave 2 |
| 4a GBT Enh A | PENDING (stub) | — | Awaiting fill-in protocol §3.8 |
| 4b GBT Enh B | PENDING (stub) | — | Awaiting fill-in protocol §4.8 |
| 5 Operator proving | PENDING | n/a | Awaiting Wave 4 |
| 6 Render deploy | PENDING | n/a | Awaiting Wave 5 |
