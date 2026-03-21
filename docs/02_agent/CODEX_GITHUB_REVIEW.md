# Review Architecture — Coordinator + Advisory Overlays

> The **local review coordinator** (`review_driver.py`) is the single
> reviewer of record.  `reviewing-changes` is the merge-relevant review
> gate (advisory — not required by branch protection; see note below).
> `claude-review` is an advisory GitHub check.  Codex Cloud is an optional
> overlay via `@codex review`.
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
| `reviewing-changes` commit status | Merge-relevant gate; published by `review_driver.py` only |
| Canonical PR summary comment | Single upserted comment with `<!-- review-loop-comment -->` marker |

The coordinator:
1. Runs deterministic prechecks
2. Waits for GitHub CI to pass
3. Invokes Codex CLI for code review
4. Auto-fixes safe patterns (convention fixes)
5. Iterates (max 3 rounds) until clean or stopped
6. Publishes `reviewing-changes` commit status
7. Posts the canonical PR summary comment
8. Enables auto-merge (squash) when review passes

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
| `reviewing-changes` | Commit status | No (advisory) | Review coordinator | **Reviewer of record** |
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
2. PostToolUse hooks dispatch `/reviewing-changes` and launch
   `review_driver.py` in the background
3. The review coordinator runs prechecks and waits for CI
4. The coordinator invokes Codex CLI and scores findings
5. On success, the coordinator publishes `reviewing-changes=success`,
   posts the canonical summary comment, and enables auto-merge
6. GitHub merges automatically once CI and branch protection are satisfied

No human merge step required.  If auto-merge fails (e.g., conflicts, repo
setting disabled), the coordinator publishes success and the PR can be merged
manually.

Codex Cloud, when used, is additive commentary.  It does not publish a
merge-blocking artifact for this repo.

## Changes for Daily Usage

This section describes what changed with the review-architecture reset and
what the operator should do differently.

### What Changed

1. **One reviewer of record:** `review_driver.py` is explicitly declared as
   the single reviewer of record.  Previously, multiple review surfaces
   (local loop, `claude-review`, Codex Cloud) coexisted without a clear
   hierarchy.
2. **One canonical summary comment:** The PR summary comment with the
   `<!-- review-loop-comment -->` marker is the single machine-owned review
   comment.  It is upserted (updated in place), not duplicated.
3. **Advisory surfaces are explicitly demoted:** `claude-review` and Codex
   Cloud are documented as advisory overlays, not review truth.
4. **Fallback is degraded pass:** If Codex CLI is unavailable, the
   coordinator publishes a degraded pass instead of blocking indefinitely.

### What the Operator Should Do

- **Stop treating `claude-review` as canonical.** It is advisory only.
- **Stop treating `@codex review` as part of the normal merge path.** It is
  an optional overlay.
- **Use the canonical review comment + `reviewing-changes` as the source of
  truth.** The comment with `<!-- review-loop-comment -->` is the only
  machine review that matters for merge decisions.
- **Use the documented rerun path when review is stuck:**
  ```bash
  python scripts/internal/review_driver.py --pr <N> --trigger manual
  ```
- **Use the admin override only as a last resort:**
  ```bash
  scripts/internal/set_review_status.sh success "Manual override"
  ```

### What to Look At First on a PR

1. `reviewing-changes` status (green/red/pending)
2. The canonical summary comment (findings, stop reason, recovery)
3. CI checks (`tests`, `governance`)

### What to Ignore Unless Troubleshooting

- `claude-review` check
- Codex Cloud comments (`chatgpt-codex-connector[bot]`)
- Other bot comments without the `<!-- review-loop-comment -->` marker

## Recovery

See `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` for crash recovery procedures
for the review coordinator.
