# Primitive C Scorecard Sub-Plan — Floor Tightening (C.12)

**ID:** SP-0-C-12
**Date:** 2026-04-23
**Parent:** `plans/steward_platform/3_primitive_C/shaping.md` §4.2 (Agent-readability scorecard) and §3 deliverable row C.12
**Status:** proposed
**Owner:** orchestrator (tightens if/when the 7/10 floor needs to move to 8/10 or 9/10)

This sub-plan exists to hold the **tightening path** for the agent-readability
scorecard floor. Packet C-Exec ships the scorecard with the ADR 001 §D3 floor
(≥7/10) locked in by runtime enforcement (`--floor < 7` rejected with an
explicit ADR 001 citation in `scripts/internal/agent_readability_score.py`).
This sub-plan is the registered home for any future decision to raise that
floor — the decision itself is **not made here**; the sub-plan enumerates the
trigger conditions, the evidence requirements, and the verification surfaces
that a tightening change would have to satisfy.

**This is not a placeholder.** Every section below names concrete inputs,
concrete acceptance commands, and concrete verification surfaces. Placeholder
tokens (TBD / TODO / FIXME / XXX) are absent from the Verification surface
column per `/create-plan` R3 refusal rule (shaping §4.4.1) and `check
verification-contract` rule VC3.

---

## Inputs

What this sub-plan consumes before a tightening decision can be made.

- **ADR 001 §D3:** `plans/steward_platform/adrs/001-platform-reset.md` —
  records the ≥7/10 floor as the Phase 0 Readiness minimum. Post-migration,
  the authoritative copy is `knowledge/adr/001-platform-pattern-reset.md`;
  the seed location retains a migration note.
- **Phase 0 baseline score:** `knowledge/agent_readability_scorecard.md`
  `Phase 0 baseline:` line — recorded at Packet C-Exec merge via
  `agent_readability_score.py --write`. This is the "start" reading against
  which tightening is measured.
- **Phase 1 end score:** same file, `Phase 1 end score:` line — recorded at
  Phase 0→1 close. A tightening decision requires the Phase 1 end score to
  be ≥ the baseline (per §5-C Phase 1 Validation) AND ≥ the proposed new
  floor.
- **10-item scorecard (frozen):** `plans/steward_platform/3_primitive_C/shaping.md`
  §4.2 — the 10 items are frozen by Packet C-Exec; this sub-plan does not
  add or remove items. It may only raise the pass threshold count.
- **Runner:** `scripts/internal/agent_readability_score.py` — already
  enforces `--floor ≥ 7`. Tightening this sub-plan to 8 or 9 requires
  updating the `_MIN_FLOOR` constant in that file; the runner already
  rejects loosening below 7.
- **Run log:** `knowledge/agent_readability_scorecard.md` `## Run log`
  section — provides the rolling-window evidence trail.

## Assumptions

Conditions assumed true. If any are violated, escalate before proceeding.

- **Scorecard items are frozen at 10** (shaping §4.2 committal). Tightening
  changes the pass threshold, never the item set.
- **ADR 001 §D3 remains the floor source of truth.** If the floor is
  superseded (new ADR), this sub-plan is superseded with it (Pattern 7
  supersession path recorded in the replacement ADR).
- **The run log is append-only.** Entries in `## Run log` are never
  retroactively edited; they form the evidence trail a tightening decision
  cites.
- **No autonomous tightening.** The orchestrator (or an operator-sanctioned
  agent) is the sole actor that flips the floor. Author lanes MUST NOT raise
  the floor without an orchestrator-dispatched tightening packet.

## Dependencies

- **Packet C-Exec merged** — this sub-plan's verification surfaces all rely
  on the scorecard runner + scorecard file being live.
- **Primitive C Phase 0 Readiness closed** — the Phase 0 baseline entry in
  `knowledge/agent_readability_scorecard.md` must exist before a tightening
  evaluation is meaningful.
- **Phase 1 proving run at least one review window completed** — a
  tightening decision backed by a single scorecard reading is too thin; the
  Phase 1 end score + ≥1 intermediate run log entry is the minimum evidence
  bar.

## Plan

### Step 1: Evaluate trigger conditions

A tightening decision is considered when **any** of:

- **T1 (sustained over-performance):** The rolling 30-day run-log window
  shows the score has been ≥ (current_floor + 1) in **every** entry (no
  dips). Grep check: every `## Run log` entry on or after
  `(today - 30 days)` parses to a score ≥ `current_floor + 1`.
- **T2 (Phase transition close):** At Phase 0→1 close or Phase 1→2 close,
  the Phase-end score is ≥ (current_floor + 2). This is the "headroom
  lets us lock in tighter" case.
- **T3 (analyst-surfaced recommendation):** A recurring analyst review
  flags that the current floor is failing to catch a genuine degradation
  class (e.g., items 6 + 10 are both passing but KB navigability has
  materially worsened). This is the qualitative override; it requires an
  analyst-reviewed evidence bundle, not just a score reading.

### Step 2: Draft the tightening packet

If any trigger fires and the orchestrator accepts, an implementation packet
updates:

- `scripts/internal/agent_readability_score.py` — change the `_MIN_FLOOR`
  constant (from 7 to 8, or 8 to 9).
- `knowledge/agent_readability_scorecard.md` — update the
  `**Floor (per ADR 001):**` line AND add a run-log entry explaining the
  tightening.
- `knowledge/adr/001-platform-pattern-reset.md` — update §D3 with a
  supersession note (NOT a replacement; per Pattern 7 reversibility the
  old floor is annotated, not erased).
- `plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` (this file)
  — update Status to `completed` once the tightening packet merges.

### Step 3: Cover Pattern 7 (reversibility)

The tightening PR body names the rollback path explicitly:

> Rollback: revert the `_MIN_FLOOR` constant back to its prior value;
> append a run-log entry noting the revert; update ADR 001 §D3 with the
> revert note.

No symmetry-breaking state mutation (the run log stays append-only; the
revert is a forward motion through the log).

### Step 4: Emit the tightening event (Pattern 8, Observable-by-default)

The tightening packet emits a `kb_scorecard_floor_raised` event (Primitive A
event schema; additive) with fields:

- `old_floor: int` (7 or 8)
- `new_floor: int` (8 or 9)
- `trigger: "T1" | "T2" | "T3"`
- `evidence_path: str` (path to the run-log window or analyst review cited)
- `operator_id: str` (non-null; mandatory per ADR 010 pattern)

If Primitive A is not yet live at tightening time, the event emission is
degraded to a PR-body citation (the text "Tightening evidence:"
followed by the run-log snippet) — acceptable per Primitive C's general
pattern of progressive event-emission coverage.

## Files Changed

Per this sub-plan's *execution* (if ever triggered). At proposal time, no
files change beyond this sub-plan's own creation.

- `scripts/internal/agent_readability_score.py` — change `_MIN_FLOOR`
  constant.
- `knowledge/agent_readability_scorecard.md` — update floor line + add run
  log entry.
- `knowledge/adr/001-platform-pattern-reset.md` — update §D3 with
  supersession note (Pattern 7).
- `plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` (this file)
  — Status → `completed`.

## Verification Plan

_Required per Pattern 10 (§10.9 of
`plans/steward_platform/governing_plan.md`). Every deliverable below ties to
a named verification surface. **Strict existence, lenient form** — every
row names a concrete surface; no TBD / TODO / FIXME / XXX placeholders
appear in the Verification surface column (per `/create-plan` R3 and
`check verification-contract` VC3)._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §Step 1 T1 trigger (rolling-30-day evaluation) | analysis workflow | `awk '/^## Run log/{f=1;next} f && NF' knowledge/agent_readability_scorecard.md` piped to a parser that extracts date + score; all scores on/after `(today - 30 days)` must satisfy `score ≥ current_floor + 1` | orchestrator | parser exits 0; window is contiguous |
| §Step 1 T2 trigger (Phase-end score) | outcome metric | `grep -E '^\*\*Phase [01] end score:\*\*' knowledge/agent_readability_scorecard.md` returns a score ≥ `current_floor + 2` | orchestrator | grep match + numeric check |
| §Step 1 T3 trigger (analyst review bundle) | analysis workflow | An analyst-authored review under `plans/steward_platform/3_primitive_C/reviews/<date>_floor_tightening.md` naming the item(s) masking degradation + the observed harm | analyst | review file exists; reviewed by orchestrator |
| §Step 2 `_MIN_FLOOR` change | new Python change | `uv run python -m pytest tests/unit/test_agent_readability_score.py::test_floor_below_seven_rejected` passes AND a new test `test_floor_below_new_value_rejected` is added mirroring the pattern | author | both tests pass |
| §Step 2 scorecard file update | KB-class artifact edit | `diff <(grep '^\*\*Floor' knowledge/agent_readability_scorecard.md) <(echo '**Floor (per ADR 001):** ≥N/10')` is empty for the new N | author | diff empty |
| §Step 2 ADR 001 §D3 update | ADR supersession | `grep -c 'Pattern 7' knowledge/adr/001-platform-pattern-reset.md` ≥ 1 AND §D3 carries a "superseded on YYYY-MM-DD by ≥N/10" annotation (not a replacement) | orchestrator | annotation present; old floor text preserved above the annotation |
| §Step 3 Rollback path (Pattern 7) | PR-body discipline | PR-body contains a `## Rollback` section naming the revert steps; review-driver VC lint (if V6 rollback-section rule is live) exits 0 | author | PR-body section present |
| §Step 4 Event emission (Pattern 8) | new event schema additive | If Primitive A live: `tests/unit/test_event_schema.py::test_kb_scorecard_floor_raised_accepted` passes. If Primitive A not live: PR-body contains the evidence snippet verbatim (grep-verifiable) | author | test passes OR PR-body snippet grep-matches |
| Sub-plan lint cleanness (self) | new sub-plan artifact | `uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` exits 0 | analyst | lint exits 0; no VC1/VC2/VC3 findings against this file |

**Surface-class defaults** — see Pattern 10 table at §10.9 of
`plans/steward_platform/governing_plan.md` for the full deliverable-class →
default-surface mapping.

## Validation

How to verify correctness before marking COMPLETE (applies when a
tightening actually lands; at proposal time the only validation is "the
sub-plan file itself passes the acceptance lint").

### Pass/Fail Criteria

- [ ] **Sub-plan existence + lint:** `uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/steward_platform/3_primitive_C/scorecard_sub_plan.md`
  - Expected: exit 0
- [ ] **Runner floor test:** `uv run python -m pytest tests/unit/test_agent_readability_score.py::test_floor_below_seven_rejected -v`
  - Expected: 1 test passes; runner rejects `--floor 6` citing ADR 001
- [ ] **Scorecard run-log append-only proof:** `git log -p -- knowledge/agent_readability_scorecard.md | grep '^-' | grep -v '^--- '`
  - Expected: no deleted lines in `## Run log` section across the history
- [ ] **ADR 001 supersession preservation (when tightening executes):**
      `git log --all -p -- knowledge/adr/001-platform-pattern-reset.md`
      carries the old §D3 text in the diff-preserved lineage
  - Expected: old floor value still findable in git history; not erased in place

## Planned Outputs

Artifacts this sub-plan's *execution* (if triggered) will produce.

- Updated `scripts/internal/agent_readability_score.py` with raised
  `_MIN_FLOOR`.
- Updated `knowledge/agent_readability_scorecard.md` floor line + run-log
  entry.
- Updated `knowledge/adr/001-platform-pattern-reset.md` §D3 with
  supersession annotation.
- New unit test(s) locking in the new floor boundary.
- New `kb_scorecard_floor_raised` event (if Primitive A live) or PR-body
  evidence snippet (otherwise).

## Observed Outputs

_Filled during/after execution._

- (Not yet triggered; filled when a tightening packet merges.)

## Outcome

_Filled after completion._

- Status: proposed (no tightening triggered as of 2026-04-23)
- PR: N/A
- Deviations from plan: N/A
- Issues discovered: N/A

## Handoff

_Filled at session end if work is incomplete._

- Current state: sub-plan authored + registered; no tightening triggered.
  Packet C-Exec ships the scorecard at the 7/10 floor; this sub-plan is the
  registered home for any future raise.
- Next action: re-evaluate triggers at Phase 0→1 close (orchestrator).
- Blockers: none.
- Files with uncommitted changes: none at handoff; this file is the
  proposal artifact.
