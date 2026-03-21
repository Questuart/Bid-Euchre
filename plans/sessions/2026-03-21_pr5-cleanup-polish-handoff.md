# PR5 Cleanup / Polish Handoff

**Lane Direction:** Use a free `author-*` lane for a docs-only cleanup PR. Keep runtime behavior unchanged. Do not edit hooks, settings, queue logic, merge-guard logic, or review-driver code in this PR.

**Date:** 2026-03-21
**Dependencies:** Post-PR4 proving window closed; merge gate now proven enough for normal use
**Goal:** Align the review architecture docs and operator guidance with the queue-backed flow that actually shipped and was proven in PRs `#1190`, `#1192`, `#1195`, and `#1201`.

## Why This PR Exists

The proving window is closed, but several docs still describe the pre-cutover or partially stale review model:

- `/reviewing-changes` dispatcher language that no longer matches the hook path
- coordinator behavior that still claims `make check`, direct auto-merge ownership, or worktree-local assumptions
- operator docs that do not clearly separate:
  - queue-backed local merge enforcement
  - advisory `reviewing-changes`
  - advisory overlays (`claude-review`, Codex Cloud)
  - GitHub auto-merge plumbing (`enable-auto-merge`)

PR5 should clean that up without reopening architecture or merge behavior.

## Scope

Ship only doc / guidance cleanup in:

- `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`
- `docs/02_agent/CODEX_GITHUB_REVIEW.md`
- `.claude/rules/deferred/60_review_gate.md`
- `.claude/hooks/README.md`
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`

Optional only if needed for consistency:

- `plans/sessions/2026-03-20_pr5-prep-parallel-handoff.md` (mark stale or superseded)

## Explicitly Out Of Scope

Do not include:

- `.claude/hooks/*.sh`
- `.claude/settings.json`
- `scripts/internal/review_driver.py`
- `scripts/internal/review_lane_runner.py`
- `scripts/internal/github_pr_state.py`
- `src/bid_euchre/ops/review_queue.py`
- `src/bid_euchre/ops/reviews.py`
- `SendMessage` integration
- delegated subreview implementation
- queue-schema or merge-policy changes

## Required Content Corrections

### 1. Describe the shipped PR-create path accurately

Docs should say:

- `post-pr-review.sh` enqueues a durable review request
- `post-pr-review-loop.sh` launches `review_driver.py` asynchronously
- the merge guard checks the verdict + SHA + CI before allowing `gh pr merge`
- operators do **not** need to invoke `/reviewing-changes` manually

Docs should not say:

- `post-pr-review.sh` auto-invokes `/reviewing-changes`
- the dispatcher is still the normal path for PR review startup

### 2. Distinguish merge truth from advisory surfaces

Make the distinction explicit:

- the queue-backed verdict + merge guard govern steward CLI merges
- `reviewing-changes` remains a review signal and ops `review_gate`, but it is **not required by GitHub branch protection**
- `claude-review` is advisory
- Codex Cloud is advisory/comment-based
- `enable-auto-merge` is plumbing, not a validation check

### 3. Be honest about the current auto-merge behavior

Docs should reflect the proving result:

- GitHub auto-merge can still fire once branch-protection requirements pass
- the local review coordinator does **not** own GitHub merge authority anymore
- if the docs mention `review_driver.py` enabling auto-merge directly, remove or correct that claim

### 4. Update recovery and operator guidance

Operator docs should clearly tell the reader:

- where to look first (`ops.py reviews`, queue/verdict state, CI)
- what `reviewing-changes` means now
- what to ignore unless troubleshooting
- when a manual override is exceptional rather than normal

### 5. Sync rule/deferred docs with the shipped model

`.claude/rules/deferred/60_review_gate.md` should no longer claim:

- `make check` as part of the current coordinator path
- dispatcher-first `/reviewing-changes` behavior as the authoritative startup path
- coordinator-enabled auto-merge as the current end state

It should instead point at the queue-backed merge guard + proving-backed operational model.

## Suggested Narrative For The Updated Docs

Use this as the consistent story across files:

1. PR creation enqueues a durable review request.
2. `review_driver.py` processes the request asynchronously and writes a SHA-bound verdict.
3. The review queue is shared across worktrees, so verdict discovery is not local to the author worktree.
4. Local `gh pr merge` is blocked unless:
   - a verdict exists
   - it matches the current PR head SHA
   - it is `passed`
   - CI is green
5. `reviewing-changes`, `claude-review`, and Codex Cloud remain visible review surfaces, but only the queue-backed verdict path is used by the local merge guard.

Also include the caveat proven in Run 2:

- GitHub auto-merge still acts off GitHub-required checks, so it can race the coordinator because `reviewing-changes` is advisory with respect to branch protection.

## Validation

Minimum:

- `rg -n "/reviewing-changes|make check|enable auto-merge|reviewer of record|shared queue|advisory" docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md docs/02_agent/CODEX_GITHUB_REVIEW.md .claude/rules/deferred/60_review_gate.md .claude/hooks/README.md docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- `git diff --stat origin/main...HEAD`
- `git diff -- docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md docs/02_agent/CODEX_GITHUB_REVIEW.md .claude/rules/deferred/60_review_gate.md .claude/hooks/README.md docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`

Optional:

- `make docs-check`

## PR Notes

The PR body should call out:

- proving is complete
- this PR is docs/polish only
- no runtime review behavior changes are included
- any remaining architectural upgrades (dedicated `review` lane, `SendMessage`, delegated subreview) are deferred to platform work

Suggested commit message:

- `docs: align review guidance with queue-backed merge gate`

## Exit Criteria

- one docs-only PR is opened
- the main review docs no longer contradict the shipped queue-backed path
- operators can read one coherent story about:
  - request enqueue
  - verdict writing
  - shared queue visibility
  - merge guard behavior
  - advisory overlays
  - GitHub auto-merge caveat
