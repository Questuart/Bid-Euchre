# PR-1 Autonomous Ops Workflow Contract
**Date:** 2026-03-18
**Goal:** Turn PR-1 of the autonomous agent ops initiative into a bounded implementation slice that establishes the workflow contract, lane/bootstrap metadata, and repo-owned startup conventions without pulling in operator automation, scheduling, or queue processing.

## Plan
- Reconcile the already-committed role-model and steward-model artifacts into one explicit workflow contract instead of planning a greenfield build.
- Define the minimum bootstrap/tooling surface needed to start named lanes consistently from repo scripts, while deferring health checks, event queues, review queues, and scheduler behavior to later PRs.
- Extend the existing runtime metadata contracts so later PRs can depend on stable paths and schemas instead of inventing or duplicating registries.
- Document the transition from legacy role terminology to canonical lane identity without forcing dynamic lane orchestration into PR-1.

## Current State
- Existing workflow doc:
  - `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
  - captures the original three-role model (`author`, `review`, `ops`) and tmux baseline.
- Existing bootstrap scripts:
  - `.claude/scripts/start-role-worktree.sh`
  - `.claude/scripts/start-agent-role.sh`
  - these implement the original three-role bootstrap and already write runtime metadata.
- Existing runtime schema docs:
  - `.claude/runtime/worktree_registry/README.md`
  - `.claude/runtime/session_metadata/README.md`
  - `.claude/runtime/task_state/README.md`
- Existing deployed session launcher:
  - `.claude/tmux/steward-session.sh`
  - this is the currently used `cmux + tmux` steward layout with `author-a`, `author-b`, `author-c`, `author-d`, `author-scratch`, `review`, and `ops`.

PR-1 should therefore be framed as a reconciliation/migration slice:
- update existing docs
- extend existing schemas
- align existing launchers/scripts
- deprecate or wrap outdated terminology
- avoid creating parallel artifacts unless there is a clear non-overlapping reason

## Locked Pre-Implementation Decisions

### 1. Legacy Role Scripts
- `start-role-worktree.sh` and `start-agent-role.sh` remain in the repo as **compatibility-only** entrypoints.
- They are not the canonical bootstrap path for the steward workflow.
- PR-1 may update them only to:
  - keep runtime metadata compatible with the reconciled schema
  - add comments/help text that point users toward the steward model
- PR-1 should **not** extend them into a second first-class bootstrap universe.

### 2. Registry And Session Field Contracts
- In `worktree_registry`:
  - `class` remains the **lifecycle class** field (`persistent`, `ephemeral`)
  - `lane_class` is added as the **functional class** field (`ops`, `review`, `author`, `scratch`, future classes)
- In `session_metadata`:
  - `lane_id` becomes the canonical machine identity for the session
  - `role` remains as an optional compatibility field during transition
- PR-1 should document these as explicit v2 schema decisions, not leave them implicit in implementation.

## Objectives
- Establish the canonical operating model:
  - `ops` and `review` are persistent control lanes.
  - worker lanes are extensible and not conceptually limited to a fixed small set.
  - the main checkout is a control plane and audit root, not a write surface.
- Define canonical machine identity independently of presentation metadata:
  - machine identity comes from lane ID + worktree path + tmux target.
  - human-facing labels may use tmux pane/window titles and Claude session names.
- Reconcile the legacy role-model scripts and the deployed steward session into one documented identity model.
- Lock the file/path contract for runtime state so PR-2 and PR-3 can implement routing, scheduling, and operator workflows without reopening schema decisions.

## Deliverables
- Revised workflow contract documentation that updates the existing operator workflow doc instead of creating a parallel one.
- Explicit naming/identity decision covering:
  - legacy `author/review/ops` role terminology
  - deployed steward lane names
  - future dynamic lane IDs
- Schema updates to existing runtime metadata docs:
  - `worktree_registry` v1 -> v2
  - `session_metadata` v1 -> v2 if required
  - `task_state` kept as-is unless a concrete delta is necessary
- Bootstrap alignment across:
  - `.claude/scripts/start-role-worktree.sh`
  - `.claude/scripts/start-agent-role.sh`
  - `.claude/tmux/steward-session.sh`
- Clear deferral notes so PR-1 does not accidentally absorb:
  - `ops.py`
  - scheduler/daemon behavior
  - event log processing
  - review queue mechanics
  - CI remediation
  - audit index

## Proposed Implementation

### 1. Naming And Identity Decision
- Canonical machine identity is `lane_id`, treated as an opaque string.
- In PR-1, the currently deployed steward lane names become valid canonical lane IDs for the default layout:
  - `ops`
  - `review`
  - `author-a`
  - `author-b`
  - `author-c`
  - `author-d`
  - `author-scratch`
- Future generated worker IDs such as `author-001` are supported by the model but are not required to land in the PR-1 launcher.
- Legacy role names remain compatibility terminology for the older three-role scripts:
  - `review` and `ops` map directly
  - `author` is treated as a legacy compatibility alias for the worker class, not the sole canonical worker lane

### 2. Workflow Contract And Docs
- Update `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` instead of creating a parallel doc.
- Add a reconciliation section that explains:
  - original three-role model
  - current steward deployment
  - canonical lane identity model going forward
- Define:
  - lane classes: `ops`, `review`, `author`, `scratch`, future specialized classes
  - control-plane rules:
    - main checkout is read/audit only
    - writes happen in registered worktrees only
  - bootstrap rules:
    - repo launchers own worktree creation/resume
    - repo launchers record runtime metadata at session start

### 3. Runtime Metadata Contracts
- Do not create a second canonical registry.
- Extend `.claude/runtime/worktree_registry/README.md` from schema v1 to schema v2 so it remains the single source of truth for live lane/worktree identity.
- Proposed v2 additions:
  - `lane_id`
  - `lane_class`
  - optional `display_name`
  - optional `tmux_session`
  - optional `tmux_window`
  - optional `tmux_pane`
  - optional `cmux_workspace_ref`
  - optional `cmux_surface_ref`
  - optional `legacy_role`
- `class` remains the lifecycle field from v1 and is not renamed.
- Update `.claude/runtime/session_metadata/README.md` to add canonical `lane_id` while keeping optional compatibility `role` during transition.
- Treat `.claude/runtime/task_state/README.md` as the baseline contract; only propose changes if a concrete PR-1 need emerges.

### 4. Bootstrap Alignment
- Update existing scripts instead of introducing parallel greenfield scripts unless a wrapper is strictly necessary.
- `start-role-worktree.sh`:
  - keep as a compatibility entrypoint for the legacy three-role model
  - update it to write the reconciled registry schema if touched
  - add header/help text that marks it as compatibility-only and points to the steward launcher for the primary workflow
- `start-agent-role.sh`:
  - keep as a compatibility entrypoint for the legacy three-role model
  - update it to write session metadata aligned with canonical lane identity if touched
  - add header/help text that marks it as compatibility-only and points to the steward launcher for the primary workflow
- `steward-session.sh`:
  - remains the canonical deployed launcher
  - PR-1 should explicitly list any changes, limited to:
    - adding reconciled metadata writes for launched lanes
    - documenting lane IDs vs display labels
    - avoiding duplicate identity logic across scripts
- Keep the bootstrap thin:
  - no scheduling loop
  - no queue draining
  - no health polling
  - no event processing

### 5. Runtime Directory Scaffolding
- Reuse the existing runtime directory structure:
  - `.claude/runtime/worktree_registry/`
  - `.claude/runtime/session_metadata/`
  - `.claude/runtime/task_state/`
- Add `.claude/runtime/README.md` only if it adds value as a top-level index over the existing runtime paths.
- Do not add `.claude/runtime/lane_registry/` unless a distinct non-overlapping purpose is documented.

### 6. VS Code / Audit Alignment
- Keep PR-1 limited to documenting the audit assumptions needed by the bootstrap contract.
- Do not add the full VS Code workspace/tasks surface here; that remains PR-2.
- If helpful, add references from the workflow doc to the existing audit workspace and tmux launcher so the operator model reads as one coherent system.

## Files
- `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` — cross-link PR-1 execution details and adjust wording if the implementation slice clarifies naming or sequencing.
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — revise the existing workflow doc to reconcile legacy role tooling with the steward deployment and canonical lane identity.
- `.claude/runtime/README.md` — optional top-level runtime-state index if needed.
- `.claude/runtime/worktree_registry/README.md` — extend schema v1 -> v2 and declare it the canonical live lane/worktree registry.
- `.claude/runtime/session_metadata/README.md` — add canonical `lane_id` and retain optional compatibility `role`.
- `.claude/runtime/task_state/README.md` — only update if a concrete PR-1 schema delta is necessary.
- `.claude/scripts/start-role-worktree.sh` — keep as compatibility-only bootstrap for legacy three-role mode; update only as needed for schema reconciliation and deprecation/help text.
- `.claude/scripts/start-agent-role.sh` — keep as compatibility-only launcher for legacy three-role mode; update only as needed for schema reconciliation and deprecation/help text.
- `.claude/tmux/steward-session.sh` — explicitly document and, if needed, update the launcher to write canonical lane metadata without adding scheduler behavior.

## Validation
- Repo-doc review:
  - the workflow doc, runtime README(s), and session plan agree on canonical lane IDs, compatibility aliases, and source-of-truth paths.
  - the locked pre-implementation decisions appear consistently in the plan, docs, and schema READMEs.
- Bootstrap validation:
  - legacy three-role scripts still function or are clearly marked compatibility-only.
  - the steward launcher still brings up the current `cmux + tmux` baseline cleanly.
  - runtime metadata written by touched launchers matches the documented v2 registry/session fields.
- Session alignment validation:
  - confirm lane identity written to metadata matches the launched worktree/tmux targets.
  - confirm display names and compatibility aliases do not become the sole routing identity.
- Scope guard:
  - no `ops.py`
  - no scheduler loop
  - no review queue
  - no event-drain implementation

## Risks
- The main risk is overreaching into PR-2 or PR-3 by trying to implement dynamic lane orchestration instead of just the contract and bootstrap.
- Lane naming can drift if we keep human labels, legacy role names, and future generated IDs ambiguous; PR-1 must document that distinction clearly while keeping one canonical machine identity.
- Schema fragmentation is a real risk; PR-1 should prefer extending existing runtime contracts over adding parallel registries.
- Compatibility scripts can become misleading if they look canonical after the steward model is documented; PR-1 should mark them explicitly as compatibility or legacy-mode entrypoints where appropriate.

## Explicit Deferrals
- `ops.py` operator CLI
- queue-driven review execution
- durable event production/consumption
- scheduler/daemon behavior
- `launchd` recovery
- CI remediation
- audit indexing and searchable memory
- full dynamic lane create/retire commands

## Outcome
- PRs:
  - #835 — Reconcile role-model and steward-model into unified workflow contract (merged 2026-03-18)
  - #839 — Add task discipline contract and lane governance (merged 2026-03-18)
  - #841 — Add progress-state contract and strengthen one-task-per-lane rule (merged 2026-03-18)
- Notes:
  - Delivered as three PRs instead of one due to review feedback identifying gaps in the initial slice.
  - PR #835 landed identity reconciliation, registry v2, compatibility scripts, and steward metadata writes.
  - PR #839 added task-discipline fields (owner_lane, in_scope, out_of_scope, escalation_triggers) to task_state v2, lane governance section to workflow doc, and transitional labeling for review_loops/plan_reviews.
  - PR #841 added durable progress-state contract (progress object with last_completed_item, last_artifact, last_validation, current_blocker, last_forward_progress_at) and strengthened one-task-per-lane from advisory to mandatory.
  - No deviations from locked pre-implementation decisions. All schema contracts landed as planned.
  - task_state was upgraded to v2 (originally planned as "unchanged unless needed"); the governing plan's task-discipline requirements created the concrete need.
