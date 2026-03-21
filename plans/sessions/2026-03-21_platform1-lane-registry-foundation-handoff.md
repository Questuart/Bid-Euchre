# Platform-1 — Lane Registry Foundation Handoff

**Lane Direction:** Use a free `author-*` lane other than `author-a`. Do not
edit the PR5 review-doc files still dirty in `author-a`.

**Date:** 2026-03-21
**Depends on:** `plans/agent_ops/1_coordination_core/sub/2026-03-21_platform1-lane-registry-foundation.md` (`SP-1-01`)
**Goal:** Implement the first `Platform-1` slice: additive lane/session
metadata for durable resume targeting plus worker visibility surfaced in the
repo-native ops CLI.

## Verified Current State

- `gh pr list --state open --limit 20 --json number,title,headRefName,author,url`
  returned `[]` at kickoff verification time.
- `author-a` still has local PR5 edits in:
  - `.claude/rules/deferred/60_review_gate.md`
  - `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`
  - `docs/02_agent/CODEX_GITHUB_REVIEW.md`
- `uv run python scripts/internal/ops.py --json status` still shows `ops` and
  `review` as `likely_active` from repo-local evidence.
- `uv run python scripts/internal/ops.py --json reviews` returned `[]`.
- Issue-cleanup work appears partially live from dirty author worktrees, but it
  is not durably recorded as active task metadata right now.

## Scope Lock

Ship one narrow PR that:

1. adds additive registry/session metadata needed for resume-by-name follow-on
2. surfaces worker visibility summary fields in `ops.py status` and
   `ops.py worktrees`
3. preserves backward compatibility with existing registry/session files

Do not ship `Platform-2`, `Platform-3`, PR5 doc cleanup, or queue/review
behavior changes in this PR.

## Design Lock

- Keep `lane_class` as the runtime/storage key. Do not rename it to
  `role_class`.
- Prefer additive fields on the current metadata schema rather than a forced
  schema-version migration.
- Persist durable identity and visibility fields only.
- Keep `state`, `current_task_id`, `linked_pr`, and freshness derived in
  `status.py`.
- Use one `session_handle` field for resume targeting.
- Make `visibility` explicit launcher-written metadata:
  - `foreground` for dashboard lanes
  - `background` for off-dashboard worker windows
  - `hidden` reserved, only if the implementation has a real writer for it
- If `last_user_attention_at` is introduced, keep it nullable in this slice.

## Write Scope

| File | Required change |
|------|-----------------|
| `.claude/tmux/steward-session.sh` | Write additive steward-lane metadata such as `session_handle` and `visibility`. |
| `.claude/scripts/start-role-worktree.sh` | Keep the legacy writer aligned if the registry contract changes. |
| `.claude/runtime/worktree_registry/README.md` | Document additive registry fields and compatibility rules. |
| `.claude/runtime/session_metadata/README.md` | Document any additive session resume field if session metadata changes. |
| `src/bid_euchre/ops/worktrees.py` | Normalize additive registry fields and preserve older-entry compatibility. |
| `src/bid_euchre/ops/status.py` | Surface registry-backed worker visibility summary fields. |
| `scripts/internal/ops.py` | Expose the new fields in `status` and `worktrees` text/JSON output. |
| `tests/unit/test_ops_worktrees.py` | Add normalization and compatibility tests. |
| `tests/unit/test_ops_status.py` | Add worker visibility summary tests. |
| `tests/unit/test_ops_cli.py` | Add CLI coverage for the new output fields. |
| `tests/unit/test_steward_session.py` | Cover launcher metadata writes if the launcher changes. |

## Suggested Execution Order

1. Refresh `SP-1-01`, this handoff, and `plans/agent_ops/0_bootstrap/checkpoints.md`.
2. Draft the exact additive field list and default visibility mapping before
   editing code.
3. Spawn at least one reviewer to review the implementation plan before major
   edits.
4. Build the file-by-file task list.
5. Assess safe parallelism.
6. Execute end to end:
   - implement
   - test
   - run smoke and unhappy-path validation
   - commit
   - open or update the PR
   - record validation evidence in the PR body and `SP-1-01`

## Safe Parallelism

- Default to one writer lane for this PR.
- A reviewer can review the plan or patch read-only after the contract draft.
- Do not split launcher writers and Python readers across multiple author lanes
  in this first slice.

## Validation

- `uv run pytest -q tests/unit/test_ops_worktrees.py tests/unit/test_ops_status.py tests/unit/test_ops_cli.py tests/unit/test_steward_session.py`
- `uv run python scripts/internal/ops.py --json status`
- `uv run python scripts/internal/ops.py --json worktrees`
- `bash -n .claude/tmux/steward-session.sh`
- `bash -n .claude/scripts/start-role-worktree.sh`
- unhappy-path check: older registry/session fixtures missing the additive
  fields still load and render cleanly

## Out Of Scope

- `orchestrator` lane or task-packet contract
- communication bus, inboxes, review substrate, or merge-policy changes
- `SendMessage`, remote operator channels, or worker autoscaling
- PR5 doc cleanup or any edits to the files still dirty in `author-a`
- queue/review runtime behavior changes

## Exit Criteria

- the first Platform-1 PR is opened or ready to open
- lane metadata is durable enough to support a follow-on resume-by-name smoke
  check
- `ops` shows worker visibility from registry-backed data without tmux
  guesswork
- backward compatibility with existing registry/session files is covered by
  tests
