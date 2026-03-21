# Review Architecture — Coordinator + Advisory Overlays

> The **local review coordinator** (`review_driver.py`) is the single
> reviewer of record.  The queue-backed **verdict file** is the
> merge-relevant artifact, checked by the local merge guard before
> `gh pr merge`.  `reviewing-changes` is an advisory commit status
> (not required by branch protection).  `claude-review` is an advisory
> GitHub check.  Codex Cloud is an optional overlay via `@codex review`.
>
> **Terminology note:** "advisory" is used in two senses in this repo:
> (1) *branch-protection sense* -- `reviewing-changes` is not required for
> merge (only `tests` and `governance` are required); (2) *check-category
> sense* -- `advisory` is one of three categories (`ci`, `review_gate`,
> `advisory`) in the CI classification model.  `reviewing-changes` is
> classified as `review_gate` (not `advisory`) in the three-category model,
> but is advisory with respect to branch protection.

## Review Coordinator (Reviewer of Record)

All merge-relevant automated review is handled by the **review
coordinator** (`scripts/internal/review_driver.py`), which invokes Codex
CLI (`codex review --base main`) locally as its preferred review backend.

The coordinator owns:

| Artifact | Details |
|----------|---------|
| SHA-bound verdict file | Durable pass/fail record in the shared review queue (merge-relevant) |
| `reviewing-changes` commit status | Advisory review signal; published by `review_driver.py` only |
| Canonical PR summary comment | Single upserted comment with `<!-- review-loop-comment -->` marker |

The coordinator:
1. Runs deterministic prechecks
2. Waits for GitHub CI to pass
3. Invokes Codex CLI for code review
4. Auto-fixes safe patterns (convention fixes)
5. Iterates (max 3 rounds) until clean or stopped
6. Writes a SHA-bound verdict to the shared review queue
7. Publishes `reviewing-changes` commit status (advisory)
8. Posts the canonical PR summary comment

### Codex CLI Details

| Property | Value |
|----------|-------|
| Command | `codex review --base main` |
| Binary | Installed locally or via `npx @openai/codex` |
| Usage pool | ChatGPT subscription (no API billing) |
| Latency | ~60s per invocation |
| Retry policy | Up to 3 attempts before `stopped_review_failure` |
| Custom launcher | `CODEX_REVIEW_CMD` env var (optional) |

## Advisory Overlays (Not Reviewer of Record)

### Claude Code Review (`claude-review`)

- **Type:** GitHub Actions check (advisory)
- **Required for merge?** No
- **Published by:** Claude Code Review workflow (`.github/workflows/claude-code-review.yml`)
- **Use case:** May carry useful code-quality signal, but is not part of the
  merge decision
- **Operator guidance:** Ignore unless troubleshooting or looking for
  supplementary feedback

### Codex Cloud (`@codex review`)

- **Type:** PR issue comment (overlay)
- **Required for merge?** No
- **Published by:** `chatgpt-codex-connector[bot]`
- **Trigger:** Manual — comment `@codex review` on a PR
- **Use case:** Optional second opinion from Codex Cloud, delivered as a PR
  comment
- **Operator guidance:** Treat as supplementary feedback.  Do not treat as
  the canonical review or as part of the merge gate.

#### Observed Delivery Mechanism (2026-03-20 proving run)

| Artifact | Present? | Details |
|----------|----------|---------|
| PR review object | No | No Pull Request Reviews API objects created |
| Check run | No | No new GitHub checks beyond normal CI |
| Commit status | No | No new status contexts |
| PR issue comment | Yes | Posted by `chatgpt-codex-connector[bot]` |
| Reaction on trigger comment | Yes | `eyes` reaction acknowledging `@codex review` |

Codex Cloud does **not** flow through the repo's existing review
classification hooks (`classify_check()`, `ADVISORY_CONTEXTS`,
`ops.reviews`).  Codex Cloud findings are now surfaceable in ops tooling
via the PR comment ingestion bridge shipped in #1122 — this is a
comment-ingestion capability, not a review-gate change.

Do not add a speculative `codex-review.yml` workflow or speculative advisory
check-name registration for the ChatGPT-subscription path.

## Relationship To Other Gates

| Surface | Type | Required? | Publisher | Role |
|---------|------|-----------|-----------|------|
| `tests` | GitHub Actions check | Yes (branch protection) | CI | Build truth |
| `governance` | GitHub Actions check | Yes (branch protection) | CI | Repo policy |
| Review queue verdict | Verdict file | N/A (local merge guard) | Review coordinator | **Merge-relevant review truth** |
| `reviewing-changes` | Commit status | No (advisory) | Review coordinator | Advisory review signal |
| `claude-review` | GitHub Actions check | No (advisory) | Claude Code Review workflow | Advisory overlay |
| Codex Cloud | PR issue comment | No (overlay) | `chatgpt-codex-connector[bot]` | Advisory overlay |

### Terminology Note: "Advisory" vs "Advisory"

Two distinct senses of "advisory" appear in this repo:

1. **Branch-protection advisory** — `reviewing-changes` is not enforced by
   GitHub branch protection rules. Only `tests` and `governance` are required.
   The coordinator's status is advisory in the branch-protection sense: GitHub
   will allow a merge even if `reviewing-changes` is pending or failed.

2. **Ops classification `advisory`** — In `classify_check()` and ops tooling,
   `advisory` is a category for checks that provide supplementary signal
   (e.g., `claude-review`). The coordinator's `reviewing-changes` status is
   classified as `review_gate`, not `advisory`, in the ops taxonomy.

The coordinator is the **reviewer of record** — its review is the one that
matters for merge quality — but it is not enforced by GitHub branch protection.

## Review Modes

PRs are classified by review mode based on changed file types:

| Review Mode | Trigger | Focus |
|-------------|---------|-------|
| `standard` | Code PRs (default) | Code correctness, tests, conventions, determinism |
| `report-audit` | PRs touching `docs/04_reports/**` | Provenance, reproducibility, gate semantics |
| `plan-audit` | PRs touching `plans/**` | Scope, real paths, execution risk, testing strategy |

## Merge Flow

1. Claude opens a PR via `gh pr create`
2. `post-pr-review.sh` enqueues a durable `ReviewRequest` to the shared
   review queue
3. `post-pr-review-loop.sh` launches `review_driver.py` asynchronously
4. The review coordinator runs prechecks and waits for CI
5. The coordinator invokes Codex CLI and scores findings
6. On success, the coordinator writes a `passed` verdict to the review
   queue and publishes `reviewing-changes=success` (advisory)
7. The coordinator posts the canonical summary comment
8. Claude (or an operator) runs `gh pr merge` — the local merge guard
   (`pre-merge-review-guard.sh`) verifies the verdict + SHA + CI before
   allowing the merge

**Merge guard checks (all must pass):**
- A verdict file exists for the PR
- The verdict's `reviewed_sha` matches the PR's current HEAD
- The verdict status is `passed`
- CI checks are green

Codex Cloud, when used, is additive commentary.  It does not publish a
merge-blocking artifact for this repo.

**GitHub auto-merge caveat:** GitHub auto-merge acts on branch-protection
requirements only (`tests`, `governance`).  Because `reviewing-changes` is
advisory, GitHub auto-merge can race the review coordinator and merge a PR
before the coordinator finishes.  The local merge guard cannot prevent this
because it only governs `gh pr merge` invoked from the CLI.

## Changes for Daily Usage

This section describes what changed with the review-architecture reset and
what the operator should do differently.

### What Changed

1. **Queue-backed merge gate:** PR creation enqueues a durable review
   request.  The review coordinator writes a SHA-bound verdict.  The local
   merge guard checks the verdict before allowing `gh pr merge`.
2. **One reviewer of record:** `review_driver.py` is explicitly declared as
   the single reviewer of record.  Previously, multiple review surfaces
   (local loop, `claude-review`, Codex Cloud) coexisted without a clear
   hierarchy.
3. **Shared queue across worktrees:** The review queue is derived from
   `git rev-parse --git-common-dir`, so a verdict written in any worktree
   is visible to the merge guard in any other worktree.
4. **One canonical summary comment:** The PR summary comment with the
   `<!-- review-loop-comment -->` marker is the single machine-owned review
   comment.  It is upserted (updated in place), not duplicated.
5. **Advisory surfaces are explicitly demoted:** `claude-review` and Codex
   Cloud are documented as advisory overlays, not review truth.
   `reviewing-changes` is advisory with respect to branch protection.
6. **Fallback is degraded pass:** If Codex CLI is unavailable, the
   coordinator writes a `passed` verdict with a degraded reason instead of
   blocking indefinitely.

### What the Operator Should Do

- **Check the review queue verdict first:**
  ```bash
  uv run python scripts/internal/ops.py reviews queue
  ```
  A `passed` verdict with a matching SHA means the merge guard will allow
  `gh pr merge`.
- **Stop treating `claude-review` as canonical.** It is advisory only.
- **Stop treating `@codex review` as part of the normal merge path.** It is
  an optional overlay.
- **Use the canonical review comment + verdict as the source of truth.**
  The comment with `<!-- review-loop-comment -->` summarizes findings.
  The verdict file is the merge-relevant artifact.
- **Use the documented rerun path when review is stuck:**
  ```bash
  python scripts/internal/review_driver.py --pr <N> --trigger manual
  ```
- **Use the admin override only as a last resort:**
  ```bash
  scripts/internal/set_review_status.sh success "Manual override"
  ```

### What to Look At First on a PR

1. Review queue verdict (via `ops.py reviews queue`)
2. `reviewing-changes` status (green/red/pending — advisory)
3. The canonical summary comment (findings, stop reason, recovery)
4. CI checks (`tests`, `governance`)

### What to Ignore Unless Troubleshooting

- `claude-review` check
- Codex Cloud comments (`chatgpt-codex-connector[bot]`)
- Other bot comments without the `<!-- review-loop-comment -->` marker

## Recovery

See `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` for crash recovery procedures
for the review coordinator.
