# Autonomous Review Loop

## Overview

The autonomous review loop is a local state machine where Claude (author)
writes/fixes code and Codex CLI (reviewer) reviews it. The loop is persisted
to disk, resumable after restarts, and bounded (max 5 iterations).

The loop is the sole review mechanism for all PRs. It runs asynchronously
after PR creation, triggered by the `post-pr-review-loop.sh` PostToolUse hook.
When the loop reaches `ready_to_merge`, it enables GitHub auto-merge (squash)
and transitions to `merged`. GitHub merges once CI + branch protection pass.

## Architecture

### Components

| Module | Purpose |
|--------|---------|
| `scripts/internal/review_state.py` | State schema, persistence, state enum, SHA tracking |
| `scripts/internal/review_driver.py` | Main orchestrator (state transitions, dispatch, status publishing, crash recovery) |
| `scripts/internal/deterministic_prechecks.py` | Fast local checks (merge markers, RNG, imports, N1/N2/N3/X2 heuristics) |
| `scripts/internal/github_pr_state.py` | GitHub CLI wrappers (CI status, PR metadata, status publishing) |
| `scripts/internal/codex_review_adapter.py` | Codex CLI invocation + output parsing |
| `scripts/internal/claude_fix_adapter.py` | Deterministic fix application from Codex findings |

### Dispatcher Integration

The `/reviewing-changes` skill acts as a fast dispatcher (~5s):
1. Publishes `pending` status immediately
2. Generates a handoff summary for the session
3. Does NOT read files, run checks, or poll for Codex — the loop handles all of that

The dispatcher and the loop hook both fire on `gh pr create`:
- `post-pr-review.sh` triggers `/reviewing-changes` (in-session dispatcher)
- `post-pr-review-loop.sh` launches `review_driver.py` (async background)

### State Machine

```
initialized → pr_open → waiting_for_ci → waiting_for_codex
                                              ↓
                                         applying_fixes → retesting → waiting_for_ci
                                              ↓
                                         ready_to_merge → merged (auto-merge enabled)
```

Terminal (stop) states: `merged`, `stopped_max_iterations`, `stopped_no_progress`,
`stopped_ci_failure`, `stopped_review_failure`.

### Runtime Artifacts

State files and per-round artifacts are stored under
`.claude/runtime/review_loops/pr_<N>/` (gitignored). Durable validation
evidence is committed under `docs/04_reports/codex_validation/`.

### Review Backend

- **Codex CLI** (sole reviewer): `codex review --base main`, local,
  ~60s latency, uses ChatGPT subscription (no API billing)

### Deterministic Prechecks

Implemented in `deterministic_prechecks.py`. The loop runs these
as its first step before invoking Codex CLI. Checks include:

- Merge conflict markers (P0)
- `TODO: remove before merge` (P1)
- Large commented-out blocks >10 lines (P1)
- Unseeded `random.Random()` / global random.* (P1, library only)
- Falsy numeric guard `x = x or fallback` (P1, library only)
- Import boundary violations (P1, library only)
- Convention patterns: `== None`, `== True`, `breakpoint()` (P2)
- N1: Missing contract-type facet in notebook groupby/plot (P1, notebooks only)
- N2: Collapsed matchup table without team breakout (P1, notebooks only)
- N3: Inference claim without statistical test (P2, notebooks only)
- X2: Core/scoring/logging changes without doc update (P2, diff-level)

### Plan Validation

Plan validation checks run in `_step_pr_open()` before deterministic
prechecks. They verify that PRs reference a governing or session plan and
that the declared plan file exists with content. Checks:

- **PV1:** Plan reference present in PR description (P2 — non-blocking)
- **PV2:** Referenced plan file exists on disk (P1 — blocking)
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

The loop publishes GitHub commit status at key transitions:

| Transition | Status | Description |
|------------|--------|-------------|
| Loop starts | `pending` | "Review loop starting" |
| Codex invoked | `pending` | "Codex CLI review in progress (round N)" |
| Clean pass | `success` | "Review passed — clean" |
| Warnings only | `success` | "Review passed — N warnings (follow-up issues created)" |
| Blockers found | `failure` | "Review blocked — N blockers" |
| Auto-merge enabled | `success` | (status already published at ready_to_merge) |
| Loop crash | `failure` | "Review loop crashed: {error}. Rerun: ..." |

### Follow-up Issues

At `ready_to_merge`, the loop creates GitHub issues for non-blocking (P2)
findings, grouped by category. Issues are labeled with `follow-up` plus
the appropriate category label (`fix:bug`, `fix:convention`, etc.).

### Blocker PR Comments

On terminal states, the review loop posts a structured PR comment
summarizing the outcome. Comments use a `<!-- review-loop-comment -->`
HTML marker for idempotent upsert (existing comment is updated rather
than duplicated on rerun).

Comment contents:
- **Status header** — pass/fail with emoji indicator
- **Stop reason** — why the loop terminated (e.g., blockers found, max iterations)
- **Findings table** — severity, file, check ID, and message for each finding
- **Recovery command** — exact command to rerun the review loop manually

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

## Governing Plan

See `plans/archive/pre_v1/2026-03-08_autonomous-review-loop.md` for the full
design, state transitions, stop conditions, and implementation sequence.

Activation plan: plans/sessions/2026-03-11_autonomous-review-loop-activation.md
