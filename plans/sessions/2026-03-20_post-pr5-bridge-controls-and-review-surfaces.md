# Post-PR-5 Bridge: Controls and Review Surfaces

**Date:** 2026-03-20
**Status:** complete
**Goal:** Finish the small bridge work that should land after PR-5 closeout and
before `Platform-1`: repo-bounded filesystem controls, PR comment ingestion for
review overlays, and the operator-facing acceptance/checklist docs that define
the real Platform-1 entry bar.

## Entry Conditions

This bridge should begin only after the PR-5 closeout cleanup lands on
`origin/main`.

Assumed baseline at bridge start:

- PR-5 slices 5-7 are merged and no longer treated as active work
- `reviewing-changes` remains the merge-relevant gate
- `claude-review` remains advisory
- Codex Cloud behavior remains:
  - triggered by `@codex review`
  - delivered as a PR issue comment from `chatgpt-codex-connector[bot]`
  - not delivered as a check run, commit status, or PR review object

## Why This Exists

PR-5 established the rollout/safety substrate, but two bridge capabilities are
still intentionally outside the shipped PR-5 slice set:

1. agents should not freely read or write outside the repo by default
2. Codex Cloud arrives as PR issue comments, so review-surface visibility needs
   comment ingestion rather than check/status classification

These should land before `Platform-1` so the platform does not start on top of
loose filesystem boundaries or incomplete review-surface visibility.

## Decisions Locked By This Plan

These decisions should not be re-litigated inside the implementation PRs:

1. **Codex Cloud integration path**
   - treat Codex Cloud as comment-based until new empirical evidence says
     otherwise
   - do not add `codex-review.yml`
   - do not add speculative `ADVISORY_CONTEXTS` entries for Codex Cloud

2. **Filesystem boundary model**
   - “in boundary” includes the main checkout, registered repo worktrees, and
     repo-owned runtime dirs under `.claude/runtime`
   - outside-boundary access requires an explicit exception path

3. **Comment-bridge behavior**
   - ingestion/surfacing is in scope
   - autonomous public replies are out of scope
   - trusted command execution may be parsed/prepared, but should not be
     broadly enabled in this bridge unless a tiny, explicitly approved follow-up
     is taken

4. **Platform boundary**
   - this bridge is still pre-Platform-1 work
   - do not introduce orchestrator, bus, dashboard-first UI, or remote control
     features here

## Shared Constraints

- This is **not** `Platform-1` implementation.
- Do **not** expand into orchestrator, dashboard-first UI, remote channels, or
  broad autonomous reply logic.
- Keep the existing review contract intact:
  - `reviewing-changes` remains the merge-relevant gate
  - `claude-review` remains advisory
  - Codex Cloud remains comment-based unless later evidence changes that
- Keep the bridge bounded and repo-local.

## Worktree / Ownership Boundaries

To avoid merge conflicts, the bridge should use these write-scope boundaries.

### Lane A owns

- `.claude/tmux/steward-session.sh`
- `scripts/internal/_repo_utils.py`
- `scripts/internal/ops.py` only for filesystem-boundary surfaces
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/events.py` only if needed for filesystem-boundary audit
  events
- `src/bid_euchre/ops/fs_boundary.py` if added
- tests for those surfaces

### Lane B owns

- `scripts/internal/github_pr_state.py`
- `src/bid_euchre/ops/reviews.py`
- `src/bid_euchre/ops/index.py`
- `src/bid_euchre/ops/events.py` only if needed for comment-ingestion events
- `scripts/internal/ops.py` only for comment/review visibility surfaces
- tests for those surfaces

### Lane C owns

- plans/checkpoints/governing docs
- operator docs
- optional checklist doc

### Shared-file rule

If both Lane A and Lane B need:
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/events.py`

they should keep changes surgically separated and rebase on the latest merged
bridge PR before final validation.

## Concrete Deliverables

| Lane | Deliverable | Must ship | May defer |
|------|-------------|-----------|-----------|
| A | Repo-bounded filesystem policy in repo-owned entrypoints | path classification, default deny for external paths, explicit override/audit path | full process/container sandboxing |
| B | PR comment ingestion as operational signal | query/normalize comments, identify trusted bot, emit/index/surface overlays | autonomous replies, broad command execution |
| C | Platform-1 entry checklist and aligned docs | updated plans/checkpoints/docs | future platform design detail |

## Workstreams

### Lane A: Filesystem Boundary Bridge

**Primary goal:** Make repo-bounded file access the default policy for
repo-owned steward/ops surfaces.

#### Required outcome

- default path policy distinguishes:
  - current repo checkout
  - registered worktrees for this repo
  - managed runtime dirs under `.claude/runtime`
  - external paths
- repo-owned launch/ops surfaces reject external paths by default unless an
  explicit override/exception path is used
- any outside-boundary use is visible in ops/audit state

#### Important nuance

“Repo-bounded” cannot mean only the current checkout root. The steward model
uses multiple repo worktrees (for example `Bid-Euchre-steward-author-b`,
`Bid-Euchre-steward-review`). Those worktrees must count as in-boundary.

#### Likely files

- `.claude/tmux/steward-session.sh`
- `scripts/internal/_repo_utils.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/events.py`
- optional new helper module: `src/bid_euchre/ops/fs_boundary.py`
- `tests/unit/test_steward_session.py`
- `tests/unit/test_ops_cli.py`
- new unit tests if a dedicated helper module is added

#### Implementation shape

1. Create a shared path-classification helper.
2. Define allowed path classes and explicit external-path detection.
3. Use that helper in repo-owned launch/ops entrypoints.
4. Emit an event or audit signal when an external-path override is used.
5. If full process-level enforcement is impossible from repo code, enforce what
   the repo owns and document the remaining gap honestly.

#### Minimum policy contract

The implementation should classify paths into one of:

- `repo_root`
- `registered_worktree`
- `managed_runtime`
- `explicit_exception`
- `external`

Expected default behavior:

- allow `repo_root`
- allow `registered_worktree`
- allow `managed_runtime`
- deny `external`
- permit `explicit_exception` only when explicitly requested through the chosen
  override path

#### Preferred entrypoints to cover first

1. steward session bootstrap / launch path
2. operator CLI paths that take filesystem arguments
3. any repo-owned helper that writes to arbitrary paths and can be bounded

#### Explicit non-goals for Lane A

- preventing the desktop app itself from reading outside the repo
- claiming OS-level confinement that repo code cannot guarantee
- retrofitting every historical research script in one PR

#### Out of scope

- OS/container sandboxing outside repo-owned entrypoints
- desktop-app internals
- unrelated liveness/status work

#### Done when

- repo/worktree/runtime paths are allowed
- external paths are rejected by default in repo-owned entrypoints
- external overrides are visible/auditable
- tests cover allowed vs rejected path classes

#### Suggested validation

- targeted tests for the new boundary helper and steward/CLI entrypoints
- `uv run pytest -q tests/unit/test_steward_session.py tests/unit/test_ops_cli.py`
- `make check-quiet`

#### Suggested PR title

- `ops: add repo-bounded filesystem access policy`

### Lane B: PR Comment Ingestion Bridge

**Primary goal:** Make PR comments a first-class ops signal, especially Codex
Cloud comments from `chatgpt-codex-connector[bot]`.

#### Required outcome

- PR issue comments are ingestible as repo-local operational signals
- trusted bot identity is distinguishable from human comments
- comment-derived review overlays are visible without changing CI or the merge
  gate
- Codex Cloud comments can be surfaced operationally without pretending they
  are checks, statuses, or PR review objects

#### Current repo reality

- `scripts/internal/github_pr_state.py` already has machine-comment helpers for
  PR comments
- `src/bid_euchre/ops/events.py` and `src/bid_euchre/ops/index.py` already form
  the durable event/index substrate
- `src/bid_euchre/ops/reviews.py` currently aggregates checks/statuses, not PR
  comment streams

#### Likely files

- `scripts/internal/github_pr_state.py`
- `src/bid_euchre/ops/events.py`
- `src/bid_euchre/ops/index.py`
- `src/bid_euchre/ops/reviews.py`
- `scripts/internal/ops.py`
- `tests/unit/test_github_pr_state.py`
- `tests/unit/test_ops_events.py`
- `tests/unit/test_ops_index.py`
- `tests/unit/test_ops_reviews.py`
- `tests/unit/test_ops_cli.py`

#### Implementation shape

1. Add a PR comment query/normalization path.
2. Classify comment source identity:
   - human
   - trusted bot (`chatgpt-codex-connector[bot]`)
   - other bot / unknown automation
3. Emit/index comment-derived signals into repo-local ops state.
4. Surface comment overlays separately from CI and `reviewing-changes`.
5. Optionally parse explicit trusted commands, but do **not** execute them in
   this slice.

#### Minimum ingestion contract

At minimum, the bridge should be able to represent:

- PR number
- comment id
- author login
- author type/category (`human`, `trusted_bot`, `other_bot`)
- timestamp
- body excerpt or normalized content
- source channel (`issue_comment`; review-thread comment support may be added if
  cheap)

#### Trusted identity rules

This bridge should explicitly recognize:

- `chatgpt-codex-connector[bot]` as the primary trusted-bot case

Everything else should be treated conservatively unless an existing repo rule
already establishes trust.

#### Preferred event/index shape

The exact schema may vary, but the resulting signal should support:

- event-log visibility
- audit index ingestion/query
- operator CLI visibility without confusing comment overlays with CI

#### Explicit non-goals for Lane B

- auto-posting replies to Codex comments
- auto-resolving PR conversations
- changing branch protection / merge gate behavior
- pretending comments are equivalent to checks

#### Out of scope

- autonomous public replies
- free-form agent conversations in PR threads
- merge-gate changes
- speculative `ADVISORY_CONTEXTS` additions for Codex Cloud

#### Done when

- Codex Cloud PR comments are visible in repo-local ops state
- comment signals are queryable/indexed
- comment ingestion cannot poison CI or the merge gate
- tests cover trusted bot vs human comment handling

#### Suggested validation

- targeted tests for comment query helpers, event emission, index ingestion, and
  review/CLI presentation
- `uv run pytest -q tests/unit/test_github_pr_state.py tests/unit/test_ops_events.py tests/unit/test_ops_index.py tests/unit/test_ops_reviews.py tests/unit/test_ops_cli.py`
- `make check-quiet`

#### Suggested PR title

- `ops: ingest PR comment signals for review overlays`

### Lane C: Docs / Acceptance / Platform-1 Entry Checklist

**Primary goal:** Make the bridge contract and the real Platform-1 entry bar
operator-visible and durable.

#### Required outcome

- plan/docs/checkpoints say the same thing about the post-PR-5 bridge
- there is a short operator-facing checklist for Platform-1 entry
- docs describe Codex as comment-based and Claude review as advisory
- docs do not claim any bridge feature is live before the implementation PRs
  merge

#### Likely files

- `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`
- `plans/agent_ops/0_bootstrap/checkpoints.md`
- `plans/agent_ops/governing_plan.md`
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- `docs/02_agent/CODEX_GITHUB_REVIEW.md`
- optional short checklist doc under `docs/02_agent/`

#### Implementation shape

1. Mark PR-5 as closed once the closeout cleanup lands.
2. Set the next queue explicitly:
   - filesystem boundary bridge
   - PR comment ingestion bridge
   - bounded trusted command handling only if still needed
   - then `Platform-1`
3. Publish a concise Platform-1 entry checklist.
4. Keep the docs aligned with actual shipped behavior.

#### Minimum checklist contents

The Platform-1 entry checklist should answer:

1. Is PR-5 actually closed?
2. Is repo-bounded filesystem access active in repo-owned entrypoints?
3. Are Claude and Codex review surfaces operationally visible?
4. Are trusted comment/command behaviors still bounded?
5. What remains intentionally deferred to Platform-1 or later?

#### Out of scope

- code changes
- new platform design scope
- promising autonomous comment replies before the control layer exists

#### Done when

- docs/checkpoints/governing plan align
- no stale “slice 7 pending” / “Platform-1 next immediately” language remains
- a future agent can read one checklist and understand the bridge gate

#### Suggested validation

- `rg -n "Platform-1|filesystem|Codex Cloud|comment ingestion|trusted command|PR-5" plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md plans/agent_ops/0_bootstrap/checkpoints.md plans/agent_ops/governing_plan.md docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md docs/02_agent/CODEX_GITHUB_REVIEW.md`
- targeted diff review for stale sequencing text

#### Suggested PR title

- `docs: add platform entry checklist for review and filesystem bridges`

## Parallelization Plan

The bridge is intentionally split so multiple lanes can work in parallel.

- **Lane A** and **Lane B** can proceed in parallel if they keep write scopes
  separate.
- **Lane C** can start in parallel but should do a final sync pass after A/B
  land so the acceptance checklist matches shipped behavior.

## Merge Order

Preferred order:

1. Lane A or Lane B may merge first; neither is a strict prerequisite for the
   other
2. Lane C should merge last so the checklist reflects the final shipped bridge
   behavior

If Lane C lands early, it must be refreshed before the platform gate is treated
as satisfied.

## Integration Rules

1. Do not let comment ingestion alter CI truth or merge-gate truth.
2. Do not let filesystem-boundary work block registered worktrees for this repo.
3. Keep trusted-command work bounded; ingestion first, execution later.
4. If any claimed enforcement cannot be implemented from repo-owned code alone,
   document the residual gap explicitly instead of implying full sandboxing.

## Blockers / Escalation Rules

- If Lane A discovers the repo cannot enforce the desired path policy from its
  owned entrypoints, stop and document the exact residual gap instead of
  hand-waving “sandboxing”.
- If Lane B discovers Codex Cloud behavior changed from the proven comment-based
  path, record the new evidence before changing the design.
- If either lane needs broader trusted-command execution, split that into a
  follow-up rather than widening this bridge PR silently.

## Validation Expectations

### Lane A

- targeted unit tests for path classification / CLI / steward session wiring
- relevant operator CLI tests

### Lane B

- targeted unit tests for PR comment querying, event emission, indexing, and
  review-surface formatting

### Lane C

- docs consistency checks via `rg` and targeted diff review

### Shared

- `make check-quiet` on implementation PRs

## Exit Criteria

The bridge is complete when:

- repo-owned entrypoints default to repo/worktree/runtime-bounded file access
- PR comments are visible as operational review overlays
- docs/checkpoints/governing plan define a clear Platform-1 entry checklist
- the repo can begin `Platform-1` without unresolved ambiguity about review
  surfaces or filesystem access boundaries

## Outcome

**Bridge gate satisfied** (2026-03-21). All exit criteria met.

### Lane A: Filesystem Boundary Bridge
- Shipped in #1115 (`src/bid_euchre/ops/fs_boundary.py`)
- Repo root, registered worktrees, managed runtime dirs allowed; external
  paths denied by default with explicit exception + audit path

### Lane B: PR Comment Ingestion Bridge
- Shipped in #1122 (`src/bid_euchre/ops/reviews.py`,
  `scripts/internal/github_pr_state.py`)
- Codex Cloud comments queryable as operational signals
- Does not change CI truth or merge-gate behavior
- Local review coordinator reset shipped in #1123

### Lane C: Docs / Acceptance / Platform-1 Entry Checklist
- Entry checklist published in earlier PR by author-d
- Final reconciliation and gate closure in this PR by author-b

### Additional Bridge Work (Beyond Original Plan)
- Bounded post-merge repair lane shipped in #1138
- Deterministic precheck hardening shipped in #1126, #1132
- Post-merge review fixes (batch 6) shipped in #1133

### Trusted Command Handling
- Deferred to Platform-1 (N/A for bridge). Rationale: filesystem boundary
  + comment ingestion together provide sufficient pre-Platform-1 control.

### Superseded PRs
- #1140 (docs: reconcile post-1122 review-surface terminology) — superseded
  by this finalization; conflicting with main after bridge PRs merged
- #1141 (ops: add bounded post-merge repair lane) — duplicate of merged
  #1138; already closed
