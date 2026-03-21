<!-- review-tier: medium -->
# Platform-1 — Lane Registry Foundation

**ID:** SP-1-01
**Date:** 2026-03-21
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 1 (`1_coordination_core`), `Platform-1`
**Status:** completed
**Owner:** Codex (implemented by author-b)

---

## Summary

Open `Platform-1` with a narrow registry-first slice. The first PR should make
lane identity durable enough for resume-by-name follow-through and make worker
visibility explicit in repo-native operator tooling, without pulling in
`Platform-2`, `Platform-3`, or any PR5 doc overlap.

## Inputs

- `plans/agent_ops/governing_plan.md`
- `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`
- `plans/agent_ops/0_bootstrap/checkpoints.md`
- `plans/agent_ops/sub_plan_registry.md`
- `plans/agent_ops/0_bootstrap/sub/2026-03-20_platform1-prep-pr-handoff.md`
- `plans/sessions/2026-03-21_platform1-kickoff-session-handoff.md`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/status.py`
- `scripts/internal/ops.py`
- `.claude/tmux/steward-session.sh`
- `.claude/scripts/start-role-worktree.sh`
- `.claude/runtime/worktree_registry/README.md`
- `.claude/runtime/session_metadata/README.md`
- `tests/unit/test_ops_worktrees.py`
- `tests/unit/test_ops_status.py`
- `tests/unit/test_ops_cli.py`
- `tests/unit/test_steward_session.py`

## Verified State At Open

- `gh pr list --state open --limit 20 --json number,title,headRefName,author,url`
  returned `[]` on 2026-03-21.
- `author-a` still has local PR5 doc edits in
  `.claude/rules/deferred/60_review_gate.md`,
  `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`, and
  `docs/02_agent/CODEX_GITHUB_REVIEW.md`; this slice must not overlap them.
- `uv run python scripts/internal/ops.py --json status` shows `ops` and
  `review` as `likely_active`; no active task metadata is currently recorded.
- `uv run python scripts/internal/ops.py --json queue` still shows historical
  queue entries, but no open PR currently depends on them.
- `uv run python scripts/internal/ops.py --json reviews` returned `[]`.

## Scope

Define and dispatch the first `Platform-1` implementation PR:

1. add additive registry/session metadata needed for durable lane identity and
   resume targeting
2. surface worker visibility summaries from repo-local state in `ops.py status`
   and `ops.py worktrees`
3. keep volatile task/review state derived on read instead of creating a new
   event bus or continuous registry writer

## Design Decisions

1. Treat the governing plan's `role_class` requirement as satisfied by the
   existing runtime key `lane_class`; do not rename the storage key in this
   slice.
2. Keep schema changes additive and backward compatible. Stay on additive v2
   metadata unless implementation reveals a concrete need for a version bump.
3. Persist only durable identity and visibility fields in registry/session
   metadata. Keep `state`, `current_task_id`, `linked_pr`, and freshness
   derived in `status.py`.
4. Introduce a single `session_handle` field for resume targeting, derived from
   existing launcher transport data.
5. Make `visibility` explicit registry data (`foreground`, `background`,
   `hidden`) written by launchers rather than inferred ad hoc from tmux pane
   layout.
6. If `last_user_attention_at` is introduced in this slice, keep it nullable
   and do not fabricate operator-attention timestamps.

## Recommended PR Shape

- Prefer one PR: `ops: add lane registry visibility and resume foundation`
- Split only if the diff stops being single-concept:
  - `PR-A`: metadata contract, launcher writers, reader normalization
  - `PR-B`: operator surface polish only if output churn materially obscures
    the contract change

## Likely Write Surface

| File | Planned change |
|------|----------------|
| `.claude/tmux/steward-session.sh` | Write additive steward-lane metadata such as `session_handle`, `visibility`, and any default display labels that become part of the contract. |
| `.claude/scripts/start-role-worktree.sh` | Keep the legacy compatibility writer aligned if the registry contract grows. |
| `.claude/runtime/worktree_registry/README.md` | Document additive registry fields and backward-compat behavior. |
| `.claude/runtime/session_metadata/README.md` | Document any additive session resume field if session metadata participates in the contract. |
| `src/bid_euchre/ops/worktrees.py` | Normalize additive registry fields and preserve v1/v2 compatibility. |
| `src/bid_euchre/ops/status.py` | Join registry/session/task data into worker visibility summaries and expose resume-target metadata. |
| `scripts/internal/ops.py` | Surface new fields in `status` and `worktrees` text/JSON output. |
| `tests/unit/test_ops_worktrees.py` | Add normalization and compatibility coverage for additive fields. |
| `tests/unit/test_ops_status.py` | Add worker visibility and derived-summary coverage. |
| `tests/unit/test_ops_cli.py` | Add CLI coverage for new output fields. |
| `tests/unit/test_steward_session.py` | Cover steward launcher metadata writes if the launcher changes. |

## Step Plan

### Step 1: Lock the additive field contract

- Requires:
  - all inputs above
- Produces:
  - final field list for the first slice
  - compatibility rules for older registry entries
  - explicit visibility mapping for dashboard vs background lanes

### Step 2: Update writers and readers

- Requires:
  - Step 1 contract lock
- Produces:
  - launcher writers that emit the additive identity/visibility fields
  - reader normalization in `worktrees.py`
  - compatibility behavior that still accepts existing entries without the new
    fields

### Step 3: Surface worker visibility in operator tooling

- Requires:
  - Step 2 reader support
- Produces:
  - `ops.py status` text/JSON visibility fields
  - `ops.py worktrees` text/JSON visibility fields
  - stable operator output that does not require tmux pane archaeology

### Step 4: Validate and hand off

- Requires:
  - Steps 1-3 implemented
- Produces:
  - targeted automated tests
  - smoke evidence
  - one unhappy-path compatibility check
  - PR/body evidence for the next agent

## Validation

- [ ] `uv run pytest -q tests/unit/test_ops_worktrees.py tests/unit/test_ops_status.py tests/unit/test_ops_cli.py tests/unit/test_steward_session.py`
- [ ] `uv run python scripts/internal/ops.py --json status`
- [ ] `uv run python scripts/internal/ops.py --json worktrees`
- [ ] `bash -n .claude/tmux/steward-session.sh`
- [ ] `bash -n .claude/scripts/start-role-worktree.sh`
- [ ] unhappy-path check: older registry/session fixtures missing the new
      fields still load and render without crashes

## Done When

- a lane's durable metadata includes enough resume-target information for a
  follow-on resume-by-name smoke check
- `ops` can show worker visibility from registry-backed data instead of pane
  guesswork
- older registry/session metadata remains readable
- no `Platform-2` or `Platform-3` behavior lands in this slice

## Out Of Scope

- `orchestrator` lane or task-packet contract (`Platform-2`)
- communication bus, inboxes, review substrate, or merge-policy changes
  (`Platform-3`)
- `SendMessage`, remote operator channels, or worker autoscaling
- PR5 docs cleanup or any overlap with the files still dirty in `author-a`
- queue/review runtime behavior changes

## Safe Parallelism

- Default to one implementation lane for this slice because the contract spans
  launcher shell scripts, Python normalizers, and CLI output.
- A separate reviewer may review the implementation plan or patch read-only
  after Step 1, but do not split the writer and reader changes across multiple
  author lanes.

## Outcome

- Status: completed
- PR: #1218 ("ops: add lane registry visibility and resume foundation")
- Merged: 2026-03-21T20:48:29Z
- Deviations from plan: none — PR shipped exactly the planned write surface
- Issues discovered: none — all "Done When" criteria satisfied
- Validation evidence: 346 tests passed (11 new), `make check-quiet` clean, shell syntax checks clean

## Handoff

- Current state: **completed.** PR #1218 merged. Platform-1 implementation done.
- Next action: Batch A pass gate smoke verification (tracked in Phase 1
  checkpoints, not as a new sub-plan). Verify:
  1. Lane/session identity survives restart without lane collisions.
  2. Resume-by-name works in a live steward smoke check.
  3. `ops` can summarize worker visibility from registry state without pane
     guesswork.
