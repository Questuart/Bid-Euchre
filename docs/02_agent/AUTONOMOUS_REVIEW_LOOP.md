# Autonomous Review Loop

## Overview

The autonomous review loop is a local state machine where Claude (author)
writes/fixes code and Codex CLI (reviewer) reviews it. The loop is persisted
to disk, resumable after restarts, and bounded (max 5 iterations).

During rollout, the loop stops at `ready_to_merge` — it does not auto-merge.

## Architecture

### Components

| Module | Purpose |
|--------|---------|
| `scripts/internal/review_state.py` | State schema, persistence, state enum |
| `scripts/internal/review_driver.py` | Main orchestrator (state transitions, dispatch) |
| `scripts/internal/deterministic_prechecks.py` | Fast local checks (merge markers, RNG, imports) |
| `scripts/internal/github_pr_state.py` | GitHub CLI wrappers (CI status, PR metadata) |
| `scripts/internal/codex_review_adapter.py` | Codex CLI invocation + output parsing |
| `scripts/internal/claude_fix_adapter.py` | Deterministic fix application from Codex findings |

### State Machine

```
initialized → pr_open → waiting_for_ci → waiting_for_codex
                                              ↓
                                         applying_fixes → retesting → waiting_for_ci
                                              ↓
                                         ready_to_merge → merged
```

Terminal (stop) states: `stopped_max_iterations`, `stopped_no_progress`,
`stopped_ci_failure`, `stopped_review_failure`.

### Runtime Artifacts

State files and per-round artifacts are stored under
`.claude/runtime/review_loops/pr_<N>/` (gitignored). Durable validation
evidence is committed under `docs/04_reports/codex_validation/`.

### Backends

- **Codex CLI** (primary): `npx @openai/codex review --base main`, local,
  ~60s latency, uses ChatGPT subscription (no API billing)
- **GitHub Codex** (passive overlay): Auto-fires on PR open, visible on PR
  page for humans, not orchestrated by the state machine

### Deterministic Prechecks

Extracted from `/reviewing-changes` Phases 0-2 into a standalone module.
Both the skill and the state machine call `deterministic_prechecks.py`
independently. Checks include:

- Merge conflict markers (P0)
- `TODO: remove before merge` (P1)
- Large commented-out blocks >10 lines (P1)
- Unseeded `random.Random()` / global random.* (P1, library only)
- Falsy numeric guard `x = x or fallback` (P1, library only)
- Import boundary violations (P1, library only)
- Convention patterns: `== None`, `== True`, `breakpoint()` (P2)

### Codex CLI Adapter

Invokes `npx @openai/codex review --base main` with a mode-specific prompt.
Parses two output formats:

1. Standard: `[P1] file:line — message (C1)`
2. Alternative: `[CRITICAL][C1] file:line — message`

Findings are normalized into `CodexFinding` dataclass with severity, file,
line, category, check_id, and message. Results saved to
round_N/codex_review.json.

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

## Usage

```bash
# Start a review loop for a PR
python scripts/internal/review_driver.py --pr 42 --branch feature-branch

# Resume after CI completes
python scripts/internal/review_driver.py --pr 42 --trigger ci_complete

# Check state
cat .claude/runtime/review_loops/pr_42/state.json
```

## Governing Plan

See `plans/sessions/2026-03-08_autonomous-review-loop.md` for the full
design, state transitions, stop conditions, and implementation sequence.
