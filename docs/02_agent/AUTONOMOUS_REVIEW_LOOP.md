# Autonomous Review Loop

## Overview

The **review coordinator** (`scripts/internal/review_driver.py`) is the
single reviewer of record for all PRs in this repository.  It is a local
state machine where Claude (author) writes/fixes code and Codex CLI
(reviewer backend) reviews it.  The loop is persisted to disk, resumable
after restarts, and bounded (max 3 iterations).

The coordinator runs asynchronously after PR creation, triggered by the
`post-pr-review-loop.sh` PostToolUse hook.  When the loop reaches
`ready_to_merge`, it writes a SHA-bound verdict to the shared review queue
and transitions to `merged`.  The local merge guard
(`pre-merge-review-guard.sh`) checks this verdict before allowing
`gh pr merge`.

## Review Coordinator Contract

The review coordinator owns these public artifacts per PR:

| Artifact | Owner | Details |
|----------|-------|---------|
| SHA-bound verdict file | `review_driver.py` via `write_verdict` | Durable pass/fail record in the shared review queue |
| `reviewing-changes` commit status | `review_driver.py` | Advisory review signal (not required by branch protection) |
| Machine-owned PR summary comment | `review_driver.py` via `upsert_review_comment` | Single upserted comment with `<!-- review-loop-comment -->` marker |

The **verdict file** is the merge-relevant artifact: the local merge guard
(`pre-merge-review-guard.sh`) checks it before allowing `gh pr merge`.
The `reviewing-changes` status is an advisory signal — it is useful for
ops monitoring and GitHub UI, but it is not enforced by branch protection
and is not consulted by the merge guard.

Hosted surfaces (`claude-review`, Codex Cloud) are advisory overlays —
they may post their own comments or checks, but those are not part of the
merge gate.

### Fallback Behavior

When the preferred review backend (Codex CLI) is unavailable or returns
unparseable output:

1. The coordinator publishes a **degraded pass** — GitHub `success` with a
   description containing "degraded" (e.g., `"Review passed — degraded
   (unparseable)"`) and writes a `passed` verdict with a degraded reason.
2. The PR summary comment notes the degraded state.
3. The merge guard will allow `gh pr merge` (the verdict is `passed`).

This ensures a broken reviewer never silently blocks the merge queue.

## Architecture

### Components

| Module | Purpose |
|--------|---------|
| `scripts/internal/review_state.py` | State schema, persistence, state enum, SHA tracking |
| `scripts/internal/review_driver.py` | Review coordinator (state transitions, dispatch, status publishing, crash recovery) |
| `scripts/internal/deterministic_prechecks.py` | Fast local checks (merge markers, RNG, imports, N1/N2/N3/X2 heuristics) |
| `scripts/internal/confidence_scorer.py` | Confidence-based filtering of P2 findings (diff-aware, heuristic) |
| `scripts/internal/github_pr_state.py` | GitHub CLI wrappers (CI status, PR metadata, status publishing) |
| `scripts/internal/codex_review_adapter.py` | Codex CLI invocation + output parsing |
| `scripts/internal/claude_fix_adapter.py` | Deterministic fix application from Codex findings |

### Hook Integration

Two PostToolUse hooks fire on `gh pr create`:

1. **`post-pr-review.sh`** — enqueues a durable `ReviewRequest` to the
   shared review queue (`bid_euchre.ops.review_queue`).  This replaces
   the former `/reviewing-changes` dispatcher.  The hook is fast (~2s)
   and does not read files, run checks, or invoke Codex.
2. **`post-pr-review-loop.sh`** — launches `review_driver.py`
   asynchronously in the background.  The driver runs the review loop
   (prechecks, CI wait, Codex CLI, auto-fix) and writes a SHA-bound
   verdict on completion.

A third hook governs merge:

3. **`pre-merge-review-guard.sh`** (PreToolUse) — blocks `gh pr merge`
   unless a verdict exists, matches the current HEAD SHA, is `passed`,
   and CI is green.  This is the hard local merge gate.

Operators do **not** need to invoke `/reviewing-changes` manually — the
queue-backed system handles review startup automatically.

### State Machine

```
initialized → pr_open → waiting_for_ci → waiting_for_codex → scoring_findings
                                 ↑                                  ↓
                                 └── retesting ← applying_fixes
                                                      ↓
                                 ready_to_merge → merged (verdict written)
```

**Note:** `pr_open` runs deterministic prechecks (diff-based, no build needed)
then transitions to `waiting_for_ci`. Local `make check` was removed because
the review loop runs in the main checkout, not the PR worktree — GitHub CI
validates on a clean checkout and is the authoritative build gate. Similarly,
`retesting` (after fixes pushed) transitions directly to `waiting_for_ci`.

The `scoring_findings` state runs confidence-based filtering on P2 findings
before deciding whether to apply fixes or proceed to merge. Low-confidence
P2 findings (e.g., findings on unmodified lines, convention checks in test
code) are filtered out. P0/P1 findings always pass through unfiltered.
Scoring results are saved to the round directory as confidence_scoring.json for audit.

Terminal (stop) states: `merged`, `stopped_max_iterations`, `stopped_no_progress`,
`stopped_ci_failure`, `stopped_review_failure`.

### Runtime Artifacts

State files and per-round artifacts are stored under
`.claude/runtime/review_loops/pr_<N>/` (gitignored). Durable validation
evidence is committed under `docs/04_reports/codex_validation/`.

### Shared Review Queue

The review queue (`bid_euchre.ops.review_queue`) provides durable
request/verdict storage shared across all git worktrees:

```
<main_repo>/.claude/runtime/review_queue/
    pr_<N>/
        request.json    -- current review request (written by hook)
        verdict.json    -- latest verdict (written by driver)
```

The queue root is derived from `git rev-parse --git-common-dir`, so a
verdict written in one worktree (e.g., the review lane) is visible to
the merge guard running in any other worktree (e.g., the author lane).

**Verdict fields:**
- `pr_number` — PR number
- `reviewed_sha` — the HEAD SHA the review covered
- `status` — `passed` or `failed`
- `reason` — human-readable explanation

**Stale verdict detection:** The merge guard compares `verdict.reviewed_sha`
against the PR's current HEAD.  If they differ, the verdict is stale and
the merge is blocked until a new review runs.

### Review Backend

- **Codex CLI** (preferred backend): `codex review --base main`, local,
  ~60s latency, uses ChatGPT subscription (no API billing)

### Deterministic Prechecks

Implemented in `deterministic_prechecks.py`. The loop runs these
as its first step before invoking Codex CLI. String literals inside
triple-quoted blocks are masked before scanning to avoid false
positives on test fixtures. Checks include:

**Per-file checks (run on each changed `.py` file):**

- Merge conflict markers (P0)
- `TODO: remove before merge` (P1)
- Large commented-out blocks >10 lines (P1)
- Unseeded `random.Random()` / global random.* (P1, library only)
- Falsy numeric guard `x = x or fallback` (P1, library only)
- Import boundary violations (P1, library only)
- C5: Redundant except — `except (Specific, ..., Exception)` tuple where
  `Exception` makes specific catches redundant (P2)
- Convention patterns: `== None`, `== True`, `breakpoint()` (P2)
- N1: Missing contract-type facet in notebook groupby/plot (P2, notebooks only)
- N2: Collapsed matchup table without team breakout (P2, notebooks only)
- N3: Inference claim without statistical test (P2, notebooks only)

**Diff-level checks (run once across the full changed-file list):**

- X2: Core/scoring/logging changes without doc update (P2)
- T1: Library code changed (`src/**/*.py`, excluding `__init__.py`) without
  corresponding test changes (`tests/**/*.py`) (P2)

### Plan Validation

Plan validation checks run in `_step_pr_open()` before deterministic
prechecks. They verify that PRs reference a governing or session plan and
that the declared plan file exists with content. Checks:

- **PV1:** Plan reference present in PR description (P2 — non-blocking)
- **PV2:** Referenced plan file exists on disk (P2 — non-blocking)
- **PV3:** Plan file has non-trivial content (P2 — non-blocking)
- **SD1:** Scope drift — files changed but not declared in plan (P2 — non-blocking)

Plan validation is advisory for doc/plan-only PRs and enforced for code PRs.

### Codex CLI Adapter

Invokes `codex review --base main` with a configurable binary resolution
chain. Parses two output formats:

1. Standard: `[P1] file:line — message (C1)`
2. Alternative: `[CRITICAL][C1] file:line — message`

Findings are normalized into `CodexFinding` dataclass with severity, file,
line, category, check_id, and message. Results saved to
round_N/codex_review.json.

**Binary preference order:**

1. `CODEX_REVIEW_CMD` env var (custom launcher, split by whitespace)
2. `codex` in PATH (fastest — no npx overhead)
3. macOS app bundle at /Applications/Codex.app/Contents/Resources/codex
4. `npx @openai/codex` fallback (downloads if needed)

The `CODEX_REVIEW_CMD` env var allows running Codex in alternative
environments (e.g., Docker containers, remote hosts). Example:

```bash
CODEX_REVIEW_CMD="docker exec codex codex" python scripts/internal/review_driver.py --pr 42 --trigger manual
```

If set but empty or whitespace-only, the env var is ignored and the
existing preference chain applies.

Retry logic: up to 3 attempts before `stopped_review_failure`.
Stagnation detection: same findings hash on consecutive rounds →
`stopped_no_progress`.

### Confidence Scorer

After Codex review, the `scoring_findings` state runs heuristic-based
confidence scoring on all P2 findings to filter false positives.

**Design decisions:**
- Deterministic heuristics only (no LLM calls) — fast and reproducible
- P0/P1 findings are never filtered — only P2 goes through scoring
- Default confidence threshold: 75 (out of 100)

**Scoring heuristics (penalty from default score of 80):**

| Heuristic | Penalty | Rationale |
|-----------|---------|-----------|
| Finding on unmodified line | -40 | Pre-existing issue, not introduced by this PR |
| Convention check in test code (C4, X3) | -20 | Lower priority in test files |
| C4 in known-complex file | -25 | Expected complexity in orchestration files |
| N3 inference-without-test | -15 | High false positive rate from regex matching |
| X2 with docs/01_core/ also modified | -30 | Docs update present, likely a false positive |

Penalties stack. Confidence is clamped to [0, 100]. Findings below threshold
are excluded from blocking/follow-up processing but recorded in the audit
report (confidence_scoring.json in the round directory).

### Claude Fix Adapter

Applies deterministic, pattern-based fixes only:

| Pattern | Auto-fix | Reason |
|---------|----------|--------|
| `== None` | Yes → `is None` | Safe mechanical replacement |
| `!= None` | Yes → `is not None` | Safe mechanical replacement |
| `== True` | Yes → `if x:` | Safe for simple cases |
| `== False` | Yes → `if not x:` | Safe for simple cases |
| `breakpoint()` | Yes → remove line | Always safe to remove |
| C1 (unseeded RNG) | No — skip | Requires domain context |
| C2 (falsy guard) | No — skip | Requires semantic understanding |

Skipped findings are recorded with reason in round_N/fix_summary.json
and round_N/claude_fix_summary.md.

### Status Publishing

The coordinator publishes GitHub commit status at key transitions:

| Transition | Status | Description |
|------------|--------|-------------|
| Loop starts | `pending` | "Review coordinator started" |
| Codex invoked | `pending` | "Codex CLI review in progress (round N)" |
| Clean pass | `success` | "Review passed — clean" |
| Warnings only | `success` | "Review passed — N warnings (follow-up issues created)" |
| Degraded pass | `success` | "Review passed — degraded (unparseable)" |
| Blockers found | `failure` | "Review blocked — N blockers" |
| Verdict written | `success` | (status already published at ready_to_merge) |
| Loop crash | `failure` | "Review loop crashed: {error}. Rerun: ..." |

### Follow-up Issues

At `ready_to_merge`, the loop creates GitHub issues for non-blocking (P2)
findings, grouped by category. Issues are labeled with `follow-up` plus
the appropriate category label (`fix:bug`, `fix:convention`, etc.).

### Canonical PR Summary Comment

On terminal states, the review coordinator posts a single structured PR
comment summarizing the outcome.  This is the **canonical machine-owned
review comment** for the PR.  Comments use a `<!-- review-loop-comment -->`
HTML marker for idempotent upsert (existing comment is updated rather
than duplicated on rerun).

Comment contents:
- **Coordinator identity** — identifies this as the canonical review summary
- **Status header** — pass/fail with emoji indicator
- **Stop reason** — why the loop terminated (e.g., blockers found, max iterations)
- **Findings table** — severity, file, check ID, and message for each finding
- **Recovery command** — exact command to rerun the review loop manually
- **Advisory note** — other review comments are overlays, not review truth

## Usage

```bash
# Start a review loop for a PR (normally triggered by hook)
python scripts/internal/review_driver.py --pr 42 --branch feature-branch --trigger pr_created

# Resume after CI completes
python scripts/internal/review_driver.py --pr 42 --trigger ci_complete

# Manual trigger (recovery)
python scripts/internal/review_driver.py --pr 42 --trigger manual

# Check state
cat .claude/runtime/review_loops/pr_42/state.json
```

## Recovery

If the loop crashes or gets stuck:

1. **Check state:**
   ```bash
   cat .claude/runtime/review_loops/pr_<N>/state.json
   ```

2. **Manual rerun:**
   ```bash
   python scripts/internal/review_driver.py --pr <N> --trigger manual
   ```

3. **Admin override** (skip review, unblock merge):
   ```bash
   scripts/internal/set_review_status.sh success "Manual override"
   ```

4. **Fallback workflow:** `review_status_fallback.yml` posts a comment after
   1 hour if status remains `pending`.

The loop's crash recovery publishes a `failure` status with a recovery
command in the description, so the PR is never silently stuck.

## Operator UX

### What to Look At on a PR

1. **Review queue state** — check the verdict file for the PR:
   ```bash
   uv run python scripts/internal/ops.py reviews queue
   ```
   A `passed` verdict with a matching SHA means the merge guard will allow
   `gh pr merge`.
2. **`reviewing-changes` status** — advisory review signal.  Green = review
   passed.  Red = review blocked (check findings in the PR summary comment).
   Pending = loop still running.  Not enforced by branch protection.
3. **The canonical PR summary comment** — the single comment with the
   `<!-- review-loop-comment -->` marker.  Contains findings, stop reason,
   and recovery command.  This comment is upserted (updated in place) on
   each rerun.

### What to Ignore Unless Troubleshooting

- **`claude-review` check** — advisory GitHub Actions check.  Does not
  affect merge.  May carry useful signal but is not the reviewer of record.
- **Codex Cloud comments** — comments from `chatgpt-codex-connector[bot]`.
  These are overlay feedback from an optional `@codex review` invocation.
  Not part of the merge gate.
- **Other bot comments** — unless from the review coordinator marker, other
  machine comments are informational only.

### How to Rerun Review

```bash
# Rerun the review coordinator for a specific PR
python scripts/internal/review_driver.py --pr <N> --trigger manual

# Override the status directly (admin escape hatch)
scripts/internal/set_review_status.sh success "Manual override"
```

### What Happens if the Preferred Reviewer is Unavailable

If Codex CLI fails or returns unparseable output:

1. The coordinator publishes a **degraded pass** (`success` with "degraded"
   in the description) and writes a `passed` verdict with a degraded reason.
2. The PR summary comment notes the degradation.
3. The merge guard will allow `gh pr merge` (the verdict is `passed`).
4. No manual intervention required unless you want to rerun.

The coordinator never silently blocks the merge queue due to reviewer
unavailability.

### GitHub Auto-Merge Caveat

GitHub auto-merge (if enabled on a PR) acts on GitHub-required checks only
(`tests`, `governance`).  Because `reviewing-changes` is advisory with
respect to branch protection, GitHub auto-merge can race the review
coordinator — merging a PR before the coordinator finishes.  The local
merge guard cannot prevent this because it only governs `gh pr merge`
invoked from the CLI.  This was confirmed during Proving Run 2.

## Governing Plan

See `plans/archive/pre_v1/2026-03-08_autonomous-review-loop.md` for the full
design, state transitions, stop conditions, and implementation sequence.

Activation plan: plans/sessions/2026-03-11_autonomous-review-loop-activation.md
