# Autonomous Review Loop — Local State Machine

## Goal

Build a local, autonomous review loop where Claude authors/fixes code and
Codex CLI reviews it, implemented as a persisted state machine. No API billing
(Codex CLI uses ChatGPT subscription). During rollout, stop at `ready_to_merge`;
do not auto-merge.

## Design Principles

1. **Real state machine** — persisted to disk, resumable after restarts
2. **Codex CLI as primary reviewer** — local, fast (~60s), structured output
3. **GitHub Codex as passive overlay** — auto-fires on PR open, visible on PR
   page for humans, not orchestrated by us
4. **Thin hook** — triggers the driver, nothing more
5. **Deterministic prechecks first** — style/lint/boundary checks before Codex
6. **Bounded iteration** — max 5 rounds, stagnation detection
7. **Auditable artifacts** — per-round findings, fix summaries, CI status
8. **Durable validation separate from runtime state** — runtime logs in
   `.claude/runtime/`, merged evidence in `docs/04_reports/codex_validation/`

## Spike Results (2026-03-08)

Codex CLI confirmed working:
- Auth: ChatGPT subscription (`codex login status` → "Logged in using ChatGPT")
- Command: `codex review --base main` (non-interactive)
- Model: gpt-5.4
- Output: `[P1]` tags with file:line, parseable
- Latency: ~60s (vs ~280s for GitHub Codex)
- Sandbox: read-only
- Reads `AGENTS.md` files (nested, closest-to-code wins)
- Findings quality: consistent with GitHub Codex on same diff

## State Machine

### States

```
initialized          — PR branch exists, no PR yet
authoring            — Claude is writing/modifying code
pr_open              — PR created, awaiting review
waiting_for_ci       — CI running
waiting_for_codex    — Codex CLI review in progress
applying_fixes       — Claude fixing Codex findings
retesting            — make check running after fixes
ready_to_merge       — all clear, human merge (rollout)
merged               — PR merged (future: auto-merge)
stopped_max_iterations    — hit 5-round limit
stopped_no_progress       — same findings twice
stopped_ci_failure        — CI failed after fix attempt
stopped_review_failure    — Codex CLI invocation failed repeatedly
```

### Transitions

```
initialized → pr_open              PR created
pr_open → waiting_for_ci           CI triggered
waiting_for_ci → waiting_for_codex CI green
waiting_for_ci → stopped_ci_failure CI red (after fix attempt)
waiting_for_codex → applying_fixes Codex blocking findings
waiting_for_codex → ready_to_merge No blocking findings
applying_fixes → retesting         Claude pushed fixes
retesting → waiting_for_ci         make check running
retesting → stopped_ci_failure     make check failed 3x
* → stopped_max_iterations         iteration >= 5
* → stopped_no_progress            same normalized findings hash twice
ready_to_merge → merged            human merges (future: auto-merge)
```

### Stop Conditions

1. **Max iterations (5)** — hard stop, emit handoff
2. **No progress** — same `findings_hash` on consecutive rounds
3. **CI failure** — make check fails after fix attempt (3 retries within round)
4. **Review failure** — Codex CLI crashes/hangs 3 times

## Architecture

### File Layout

```
scripts/internal/
├── review_driver.py          # Main orchestrator (state machine)
├── review_state.py           # State schema + persistence
├── deterministic_prechecks.py # Merge markers, breakpoint, imports, lint
├── codex_review_adapter.py   # Codex CLI invocation + output parsing
├── claude_fix_adapter.py     # Apply fixes from normalized findings
└── github_pr_state.py        # gh CLI wrappers (CI status, PR metadata)

.claude/runtime/review_loops/  # Gitignored runtime state
├── pr_<number>/
│   ├── state.json             # Current state machine state
│   ├── round_1/
│   │   ├── prechecks.json     # Deterministic precheck results
│   │   ├── codex_review.json  # Normalized Codex findings
│   │   ├── claude_fix_summary.md
│   │   └── ci_status.json
│   ├── round_2/
│   │   └── ...
│   └── round_N/

docs/04_reports/codex_validation/ # Merged durable evidence
├── results_YYYY-MM-DD.md
└── promotion_criteria.md
```

### Module Responsibilities

**`review_driver.py`** — Main orchestrator
- Loads state from disk, advances one step, saves state
- Each invocation makes bounded progress (one transition), then exits
- Idempotent: duplicate triggers are harmless
- Terminal states → no-op on re-invocation
- Entry point: `python scripts/internal/review_driver.py --pr <N> --trigger <event>`

**`review_state.py`** — State schema + persistence
- Dataclass/TypedDict for state fields
- Read/write `.claude/runtime/review_loops/pr_<N>/state.json`
- Fields:
  - `pr_number`, `branch`, `mode` (standard/report-audit/plan-audit)
  - `state` (current state enum)
  - `iteration_count`, `max_iterations` (default 5)
  - `last_findings_hash` (for stagnation detection)
  - `last_head_sha`, `last_ci_status`, `last_codex_status`
  - `opened_at`, `updated_at`, `stop_reason`

**`deterministic_prechecks.py`** — Fast local checks
- Extracted from `/reviewing-changes` Phases 0-2 (not calling the skill)
- Checks:
  - Merge conflict markers (`<<<<<<<`)
  - `breakpoint()` in library code
  - `== None`, `== True`, `== False` patterns
  - Import boundary violations (`src/` importing `experiments/` or `tests/`)
  - `TODO: remove before merge`
  - Large commented-out blocks (>10 lines)
  - Plan file path existence (for plan-audit mode)
  - Report provenance field presence (for report-audit mode)
- Returns structured findings list (same schema as Codex findings)
- Both `/reviewing-changes` skill AND state machine call this module

**`codex_review_adapter.py`** — Codex CLI interface
- Invokes: `npx @openai/codex review --base main [prompt]`
  or `npx @openai/codex review [prompt] --base main` (test arg order)
- Prompt varies by mode:
  - standard: "Review for P0/P1 correctness regressions..."
  - report-audit: "Review for provenance errors..."
  - plan-audit: "Review for nonexistent file references..."
- Parses stdout for `[P1]`/`[P0]` tagged findings
- Normalized finding schema:
  ```python
  {
      "severity": "P0" | "P1" | "P2",
      "file": "path/to/file.py",
      "line": 42,
      "category": "correctness" | "provenance" | "convention",
      "check_id": "C1" | "R1" | null,
      "message": "description",
      "raw_source": "full Codex output line"
  }
  ```
- Saves to `round_N/codex_review.json`
- Timeout: 5 minutes (Codex CLI is ~60s typically)

**`claude_fix_adapter.py`** — Fix application
- Takes normalized findings from Codex
- Filters to blocking (P0/P1) findings only
- Applies fixes using standard file edit tools
- Records: which findings were addressed, what changed, commit SHA
- Saves `round_N/claude_fix_summary.md`
- Returns: `{fixes_applied: N, commit_sha: str | null}`

**`github_pr_state.py`** — GitHub query wrappers
- `get_pr_head_sha(pr: int) -> str`
- `get_ci_status(pr: int) -> str` (pending/success/failure)
- `get_pr_metadata(pr: int) -> dict` (title, branch, state)
- `publish_review_status(pr: int, state: str, description: str)`
- Does NOT merge (rollout constraint)

### Hook Integration

**`.claude/hooks/post-pr-create.sh`** (thin trigger):
```bash
#!/bin/bash
# Trigger review loop on PR creation
PR_NUMBER=$(echo "$1" | jq -r '.pr_number // empty')
if [ -n "$PR_NUMBER" ]; then
    python scripts/internal/review_driver.py --pr "$PR_NUMBER" --trigger pr_created &
fi
```

The hook only triggers; all orchestration is in `review_driver.py`.

## Review Flow (One Invocation)

```
1. Load state from disk (or initialize if new)
2. If terminal state → exit (no-op)
3. Run deterministic prechecks
   - If blocking precheck failures → record, set stopped_ci_failure
4. If state == waiting_for_ci:
   - Check CI status via gh
   - If pending → save state, exit (resume on next trigger)
   - If failed → stopped_ci_failure
   - If passed → transition to waiting_for_codex
5. If state == waiting_for_codex:
   - Invoke Codex CLI
   - Parse findings
   - If no blocking findings → ready_to_merge
   - If blocking findings → applying_fixes
   - If invocation failed → retry count, eventually stopped_review_failure
6. If state == applying_fixes:
   - Check iteration count → stopped_max_iterations if >= 5
   - Check findings hash → stopped_no_progress if same as last round
   - Apply fixes via claude_fix_adapter
   - If no changes made → stopped_no_progress
   - Commit, push → retesting
7. If state == retesting:
   - Run make check
   - If pass → waiting_for_ci (CI will re-run on push)
   - If fail (3 attempts) → stopped_ci_failure
8. Save state, save round artifacts, exit
```

## Relationship to Existing Workflow

| Component | Current | After This PR |
|-----------|---------|---------------|
| `/reviewing-changes` skill | Phases 0-5 monolith | Phases 0-2 call `deterministic_prechecks.py`; Phases 3-5 replaced by state machine |
| Codex polling (SKILL.md) | 3-channel GitHub API polling | Removed — Codex CLI is local |
| GitHub Codex | Actively polled | Passive overlay (auto-fires, not orchestrated) |
| Review status | `set_review_status.sh` | State machine publishes via `github_pr_state.py` |
| Follow-up issues | Phase 4 of skill | State machine creates on `ready_to_merge` |
| Handoff summary | Phase 5 of skill | State machine emits on terminal state |

## Implementation Sequence

### PR 1: State Machine Infrastructure + Deterministic Prechecks

Files:
- `scripts/internal/review_state.py` — state schema, persistence, state enum
- `scripts/internal/review_driver.py` — orchestrator skeleton (state transitions,
  load/save, idempotency, terminal state handling)
- `scripts/internal/deterministic_prechecks.py` — extracted from `/reviewing-changes`
  Phases 0-2 (merge markers, breakpoint, imports, lint patterns)
- `scripts/internal/github_pr_state.py` — gh CLI wrappers
- `.gitignore` update — add `.claude/runtime/`
- `tests/unit/test_review_state.py` — state transition tests
- `tests/unit/test_deterministic_prechecks.py` — precheck detection tests
- `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` — design doc

Validation:
- State serialization round-trip tests
- Transition validity tests (no illegal transitions)
- Idempotency tests (duplicate triggers)
- Precheck detection tests (seeded fixtures)

### PR 2: Codex CLI Adapter + Claude Fix Adapter + Integration

Files:
- `scripts/internal/codex_review_adapter.py` — Codex CLI invocation, output parsing
- `scripts/internal/claude_fix_adapter.py` — fix application, commit, summary
- `.claude/hooks/post-pr-create.sh` — thin trigger hook
- `.claude/rules/60_review_gate.md` — document state machine workflow
- `.claude/skills/reviewing-changes/SKILL.md` — remove GitHub Codex polling,
  reference state machine for iterative review
- `tests/unit/test_codex_review_adapter.py` — output parsing tests
- End-to-end test with a real PR (V4-style: create PR, run loop, verify)

Validation:
- Codex CLI output parsing (mock outputs for P0/P1/P2 findings)
- Stagnation detection (same findings twice → stopped_no_progress)
- Max iteration enforcement
- Real PR test: branch with seeded bug → loop finds it → Claude fixes → loop passes

## Promotion Criteria (Revised)

The state machine's readiness for auto-merge is tracked separately from its
implementation. Promotion criteria (from codex-review-quality plan, revised):

| Criterion | Threshold | Measured Over |
|-----------|-----------|---------------|
| Codex CLI response rate | ≥ 90% | ≥ 10 PRs through the loop |
| Finding parseability | ≥ 90% | PRs where Codex flagged issues |
| Seeded P0/P1 detection | ≥ 80% | Seeded correctness test PRs |
| False positive rate | ≤ 10% | All PRs |
| Fix success rate | ≥ 70% | PRs where Claude attempted fixes |
| Human reviewer sign-off | Required | After reviewing aggregate report |

Durable validation evidence is committed under `docs/04_reports/codex_validation/`,
not derived from runtime state files.

## What This Does NOT Change

- **Game rules, scoring, strategy code** — zero impact
- **Experiment runner** — unchanged
- **`make check` composition** — unchanged (repo-lint + ruff + pytest + notebook + docs)
- **PR template** — unchanged
- **Branch protection** — `reviewing-changes` status context stays required
- **Auto-merge** — NOT enabled in this plan. `ready_to_merge` is a terminal state
  that requires human action.

## Outcome

(To be filled after implementation)
