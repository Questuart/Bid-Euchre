# Independent Plan Review Agent

## Goal

Replace the self-review pattern (authoring Claude reviews its own plan via
`/reviewing-plans` skill) with an independent agent-based review loop:
**Codex CLI primary → Claude agent failsafe**, with tiered rubrics
(small/medium/governing), 5-iteration revision cap, sidecar file output,
and GitHub issue alerting on Codex fallback.

## Context

### Current State
- `post-plan-review.sh` (PostToolUse hook on Write) auto-triggers
  `/reviewing-plans` skill in the same session → self-review, not independent
- Existing Codex adapter (`scripts/internal/codex_review_adapter.py`) has a
  `"plan-audit"` prompt stub (line 71) and `ReviewMode.PLAN_AUDIT` enum
  (`review_state.py:47`), but neither is wired up
- Code review loop (`review_driver.py`) provides the state machine pattern
  for iterative Codex → fix → re-review loops

### Desired State
- Manual invocation only (no auto-trigger on Write)
- Codex CLI reviews the plan against a tiered rubric
- Claude agent revises the plan based on findings
- Loop up to 5 iterations, then proceed regardless
- Claude agent failsafe if Codex is unavailable/unparseable
- GitHub issue created on every Codex → Claude fallback
- Review output: conversation message AND sidecar `.review.md` file
- Plan author can force tier via frontmatter: `<!-- review-tier: small|medium|governing -->`

## Design

### Tier Classification

Auto-detected by reviewer, overridable via frontmatter.

| Tier | Heuristic | Checks | Expected time |
|------|-----------|--------|---------------|
| **Small** | ≤3 files, single-PR scope, <80 lines | 7 convention checks | ~30s/iteration |
| **Medium** | 4–10 files, multi-PR chain, 80–300 lines, or multi-step | 15 convention + 5 risk flags | ~60s/iteration |
| **Governing** | Multi-rung/phase, >300 lines, `## Governing Plan` header, or `plans/<initiative>/` non-session path | Full 16-dimension weighted rubric + 8 hard gates | ~90s/iteration |

**Tier escalation rules (applied in order):**
1. Frontmatter override (`<!-- review-tier: X -->`) always wins
2. `plans/<initiative>/` paths (non-session) default to **governing**
3. Plans with `## Governing Plan` header OR (>300 lines AND **strong**
   research content signals: `## Hypotheses` section header, `rung` used as
   a structural term (e.g., `R0`, `R1`, `rung ladder`), or
   `promotion gate`/`ADVANCE`/`HALT` decision language) escalate to
   **governing**. Weak signals like bare `gate`, `SMOKE`, `QUICK`, `FULL`
   alone are not sufficient — these appear in tooling plans too.
4. Plans with 4+ files, multi-PR chain, or 80+ lines escalate to **medium**
5. Everything else (including short `plans/sessions/` plans) defaults to **small**

**Key:** Line count alone does NOT escalate to governing. A long tooling or
refactor session plan stays at **medium** unless it contains research content
signals. This prevents false `NOT READY` failures from research-oriented hard
gates (evidence contracts, data-generation policy) on non-research plans.

**Override:** `<!-- review-tier: governing -->` anywhere in the plan file.

### Small Rubric (7 checks)

| ID | Check | Source |
|----|-------|--------|
| P1 | Real file paths (Glob-verified) | `planning-code-first` |
| P2 | Real function signatures | `planning-code-first` |
| P3 | Seeds in experiment/test commands | `20_determinism.md` |
| P5 | Single-concept scope | `40_prs.md` |
| P6 | Testing strategy identified | `15_testing_tiers.md` |
| P9 | Template completeness (Goal, Steps, Files, Outcome) | Convention |
| R4 | Scope creep (>5 files without justification) | Risk flag |

### Medium Rubric (15 checks + 5 risk flags)

All Small checks, plus:

| ID | Check | Condition | Source |
|----|-------|-----------|--------|
| P4 | No import boundary violations | Always | CLAUDE.md Architecture |
| P7 | Data contract doc updates noted | Always | `30_data_contract.md` |
| P8 | Sample size & success criteria | **Research/experiment plans only** — SKIP for pure code/refactor | `05_rigor.md` |
| P10 | Jupytext sync noted if touching notebooks | Always | `45_notebook_boundary.md` |
| P11 | Testable hypotheses with bounds | **Research/experiment plans only** — SKIP for pure code/refactor | `PLAN_REVIEW_RUBRIC.md` §1 |
| P15 | Step dependencies annotated | Always (4+ steps) | `PLAN_REVIEW_RUBRIC.md` §2 |
| R1 | Circular import risk | Always | Risk flag |
| R2 | Stale training data risk | Always | Risk flag |
| R3 | Missing exports | Always | Risk flag |
| R5 | Gate semantics (SKIP/FAIL ordering) | Always | Risk flag |

**Note:** P8 and P11 preserve the existing `/reviewing-plans` SKIP behavior
for non-research plans. The medium tier includes multi-PR refactors and
non-experimental work — these should not receive false findings for missing
sample sizes or hypothesis bounds. The reviewer auto-detects research intent
by looking for keywords: `experiment`, `sample`, `hypothesis`, `SMOKE/QUICK/FULL`,
`--seed`, `run_experiment`, or explicit `## Hypotheses` section.

### Governing Rubric (full)

All Medium checks, plus:

| ID | Check | Source |
|----|-------|--------|
| P12 | One variable per step | `PLAN_REVIEW_RUBRIC.md` §5 |
| P13 | Artifact provenance specified | `PLAN_REVIEW_RUBRIC.md` §3 |
| P14 | Per-tier evidence contracts (SMOKE/QUICK/FULL) | `PLAN_REVIEW_RUBRIC.md` §12 |
| Full rubric | 16 weighted dimensions (0–5 each, normalized to 0–100) | `PLAN_REVIEW_RUBRIC.md` |
| Hard gates | 8 override checks (any FAIL → Not Ready) | `PLAN_REVIEW_RUBRIC.md` |

### Review Loop State Machine

```
plan_written → codex_reviewing → findings_received
                                       ↓
                    claude_fixing → codex_re_reviewing → findings_received
                                       ↓ (max 5 iterations)
                              review_complete → output_written
```

Fallback path:
```
codex_reviewing → codex_failed → claude_fallback_reviewing → findings_received
                                       ↓
                  (GitHub issue created with plan-review-fallback label)
```

### Codex CLI Invocation Strategy

The existing adapter uses `codex review --base main` (diff-oriented). For
plan review, two options were considered:

**Option A — Diff-based with path isolation (chosen):** Create a temporary
git index containing only the plan file's diff, then invoke
`codex review --base main` against that isolated index. This ensures Codex
reviews only the target plan, not unrelated branch changes. Implementation:
`GIT_INDEX_FILE=<temp> git add <plan-path>` to create a scoped index.

**Untracked file handling:** `git diff main -- <plan-path>` returns empty
for newly created untracked files. The adapter MUST `git add` the plan file
into the temporary index before invoking Codex.

**Base tree isolation:** The temporary index MUST be seeded from the `main`
tree (not HEAD), so that the only diff Codex sees is the plan file itself.
Implementation: `git read-tree main` into the temp index, then
`GIT_INDEX_FILE=<temp> git add <plan-path>`, then
`codex review --base main` with `GIT_INDEX_FILE` set. This ensures that
even if the working branch has other changes relative to main, Codex only
reviews the target plan.

**Why A over prompt-based:** The diff-based approach reuses the existing
adapter infrastructure, output parsing, and finding schema. The plan file
naturally appears in the diff. An AGENTS.md section can guide Codex to
apply plan-specific checks. The prompt-based approach (`codex --prompt`)
would require a new invocation path and freeform output parsing.

**Path isolation requirement:** The adapter MUST constrain the diff to
only the target plan file. Without this, `codex review --base main` sees
the entire branch diff and may return findings for unrelated files. The
Claude fixer would then edit outside the plan scope. The adapter function
`invoke_codex_plan_review()` handles isolation before invocation.

**Limitation:** Codex may not apply the full rubric systematically via diff
review alone. This is why the Claude failsafe exists — it can apply the
structured rubric checks deterministically.

### Fallback Alerting

| Event | Action |
|-------|--------|
| Codex crash/timeout/unavailable | GitHub issue with `plan-review-fallback` label |
| Codex output unparseable | GitHub issue with raw output attached |
| Codex returns empty/trivial review | Warning in sidecar file (soft signal) |
| Claude failsafe runs | Sidecar header: `Reviewer: claude-failsafe (codex unavailable)` |

GitHub issue template:
```
Title: Plan review fallback: <plan-name> — Codex unavailable
Labels: plan-review-fallback
Body:
  - Plan file: <path>
  - Tier: <small|medium|governing>
  - Codex error: <error message or "unparseable output">
  - Fallback reviewer: claude-agent
  - Session: <timestamp>
  - Raw Codex output (if any): <attached or truncated>
```

Query fallback rate: `gh issue list --label plan-review-fallback`

### Sidecar Output

Written to `.claude/runtime/plan_reviews/<path-hash>/review.md` (not next
to the plan file). This avoids dirtying `plans/` with generated artifacts
that could be accidentally committed. A symlink or log line in the
conversation output points to the sidecar location for easy access.

```markdown
# Plan Review: <plan-name>

- **Reviewer:** codex-cli | claude-failsafe (codex unavailable)
- **Tier:** small | medium | governing
- **Iterations:** N/5
- **Date:** YYYY-MM-DD
- **Verdict:** READY | NEEDS ATTENTION | NOT READY

## Findings

| Iteration | ID | Severity | Finding | Status |
|-----------|-----|----------|---------|--------|
| 1 | P1 | WARN | Missing path: src/foo.py | FIXED (iter 2) |
| 1 | R4 | FLAG | 7 files without justification | OPEN |

## Final State
<summary of what was fixed vs. what remains>
```

## Plan

### PR-1: Tiered Rubric + Agent Definition

**Files created:**
- `docs/02_agent/PLAN_REVIEW_TIERS.md` — Tiered rubric specification
  (small/medium/governing check lists, scoring, tier classification heuristics)
- `.claude/agents/plan-reviewer.md` — Claude agent definition for plan review
  (failsafe mode + tier-aware rubric application)

**Files modified:**
- `docs/02_agent/PLAN_REVIEW_RUBRIC.md` — Add cross-reference to tiers doc
- `plans/AGENTS.md` — **Update Codex plan-audit guidance** to reference the
  tiered rubric. Without this, `codex review --base main` follows the existing
  basic `plans/AGENTS.md` checks and never enforces small/medium/governing
  rubric distinctions. Add tier-aware check lists so Codex can apply the
  appropriate depth based on plan classification signals.
- `AGENTS.md` (repo root) — **Update the root-level Codex review guidance.**
  The root `AGENTS.md` references the old P1-P10 / R1-R5 checks from
  `/reviewing-plans`. Update the Plan Audit section to point to the new
  tiered rubric in `docs/02_agent/PLAN_REVIEW_TIERS.md` so Codex uses the
  new checks regardless of which AGENTS.md it reads first.

**Testing:** No code changes — doc-only PR. Validate with `make docs-check`.

**Outcome:** Rubric, agent definition, and Codex guidance ready for PRs 2–4.

### PR-2: Codex Plan Review Adapter + Claude Failsafe

**Files created:**
- `scripts/internal/codex_plan_review_adapter.py` — Plan-specific Codex CLI
  adapter. Extends the diff-based invocation with plan-audit mode. Includes:
  - Tier detection from frontmatter + heuristics
  - Plan-specific finding schema (PlanReviewFinding)
  - Fallback trigger detection (Codex failure → Claude agent)
  - Output parsing for plan review findings

**Files modified:**
- `scripts/internal/codex_review_adapter.py` — Extract shared utilities
  (binary resolution, error classification) into importable helpers if needed.
  Keep code review adapter unchanged otherwise.
- `scripts/internal/review_state.py` — Add `PlanReviewState` enum and
  `PlanReviewLoopState` dataclass (parallel to ReviewLoopState but with
  plan-specific fields: tier, plan_path, fallback_used)

**Key functions:**
- `detect_plan_tier(plan_path: Path) -> str` — Reads frontmatter override,
  falls back to heuristics (path, line count, header patterns)
- `invoke_codex_plan_review(plan_path: Path, tier: str, ...) -> CodexReviewResult`
  — Stages plan, invokes Codex, parses findings
- `invoke_claude_failsafe(plan_path: Path, tier: str, ...) -> list[PlanReviewFinding]`
  — Spawns Claude agent with rubric prompt, parses structured output

**Testing:**
- `tests/unit/test_codex_plan_review_adapter.py` — Tier detection (frontmatter
  override, path heuristics, line count), output parsing (findings, clean
  review, unparseable), fallback trigger conditions
- Seed: N/A (deterministic unit tests)

### PR-3: Plan Review Loop Driver + Alerting + Hook Exclusion

**Files created:**
- `scripts/internal/plan_review_driver.py` — State machine orchestrator for
  plan review. 5-iteration loop: Codex reviews → Claude fixes → Codex
  re-reviews. Handles:
  - State persistence (`.claude/runtime/plan_reviews/<path-hash>/state.json`)
    keyed by a hash of the plan's repo-relative path (not basename) to avoid
    collisions between files with the same name across initiatives (e.g.,
    `plans/arc_d_v2/amendments.md` vs `plans/browser_game/amendments.md`)
  - Iteration tracking with stagnation detection (findings hash)
  - Codex → Claude failsafe transition with GitHub issue creation
  - Sidecar `.review.md` file generation
  - Conversation message output

**Files modified:**
- `scripts/internal/review_state.py` — Add plan review state machine
  transitions (if not already in PR-2)
- `.claude/hooks/post-plan-review.sh` — **Add `.review.md` exclusion.** The
  existing hook matches `*/plans/*.md`, so sidecar files written by the loop
  driver would re-trigger the old self-review. Add exclusion:
  `[[ "$FILE_PATH" != *.review.md ]]` to the guard clause. This is needed
  *before* PR-4 removes the auto-trigger entirely, to prevent a broken
  intermediate state on main between PR-3 and PR-4 merges.

**Key functions:**
- `run_plan_review_loop(plan_path: Path, tier: str | None, max_iter: int = 5) -> PlanReviewResult`
  — Main entry point. Detects tier (or uses override), runs loop, writes output.
- `_create_fallback_issue(plan_path: Path, tier: str, error: str) -> str`
  — Creates GitHub issue via `gh issue create` with `plan-review-fallback`
  label. Tolerates missing label: if `gh issue create --label` fails, retries
  without labels (same pattern as `review_driver.py:125-145`). This prevents
  a missing GitHub label from silently swallowing the fallback alert.
- `_write_sidecar(plan_path: Path, result: PlanReviewResult) -> Path`
  — Writes review to `.claude/runtime/plan_reviews/<path-hash>/review.md`
- `_apply_claude_fixes(plan_path: Path, findings: list[PlanReviewFinding]) -> bool`
  — Spawns Claude agent to revise plan based on findings. Returns True if changes made.

**State machine:**
```python
class PlanReviewState(str, Enum):
    INITIALIZED = "initialized"
    CODEX_REVIEWING = "codex_reviewing"
    FINDINGS_RECEIVED = "findings_received"
    CLAUDE_FIXING = "claude_fixing"
    CODEX_FALLBACK = "codex_fallback"          # Codex failed
    CLAUDE_FALLBACK_REVIEWING = "claude_fallback_reviewing"
    REVIEW_COMPLETE = "review_complete"         # Terminal: clean or max iter
    REVIEW_COMPLETE_WITH_ISSUES = "review_complete_with_issues"  # Terminal: open findings remain
```

**Testing:**
- `tests/unit/test_plan_review_driver.py` — State transitions, iteration
  counting, stagnation detection, fallback trigger, sidecar generation
- Seed: N/A (deterministic unit tests)

### PR-4: Skill Wiring + Integration Test

**Files created:**
- `.claude/skills/review-plan/SKILL.md` — Manual skill definition. Invoked
  as `/review-plan [path]`. Calls `plan_review_driver.py` and outputs results.
- `tests/integration/test_plan_review_loop.py` — End-to-end integration test:
  1. Creates a sample plan file with known defects (missing seeds, fake paths)
  2. Runs the plan review loop with a mocked Codex CLI (returns canned findings)
  3. Verifies Claude agent fixes are applied
  4. Verifies sidecar file is written with correct structure
  5. Verifies fallback alerting triggers when Codex mock returns failure
  6. Verifies tier detection (small/medium/governing) from heuristics + override

**Files modified:**
- `.claude/hooks/post-plan-review.sh` — Gut the auto-trigger. Replace with
  a no-op or remove entirely. The `/review-plan` skill is now manual-only.
- `.claude/settings.json` — Remove or comment out the `post-plan-review.sh`
  hook registration from the PostToolUse/Write matcher
- `.claude/hooks/README.md` — Update docs to reflect manual invocation
- `.claude/skills/reviewing-plans/SKILL.md` — Add deprecation note pointing
  to `/review-plan` (keep for backward compat but mark deprecated). Also
  add `.review.md` exclusion to the auto-select logic (Phase 0, step 2)
  so the deprecated skill doesn't accidentally review sidecar files when
  invoked without an explicit path.

**Integration test design:**

```python
# tests/integration/test_plan_review_loop.py

class TestPlanReviewLoop:
    """End-to-end plan review loop with mocked Codex CLI."""

    def test_small_plan_clean_review(self, tmp_path):
        """Small plan with no defects → REVIEW_COMPLETE in 1 iteration."""

    def test_small_plan_with_defects_fixed(self, tmp_path):
        """Small plan with fixable defects → fixed by iter 3."""

    def test_medium_plan_full_rubric(self, tmp_path):
        """Medium plan applies all 15+5 checks."""

    def test_governing_plan_weighted_rubric(self, tmp_path):
        """Governing plan applies full 16-dimension rubric + hard gates."""

    def test_max_iterations_then_proceed(self, tmp_path):
        """5 iterations with persistent findings → REVIEW_COMPLETE_WITH_ISSUES."""

    def test_codex_failure_triggers_claude_fallback(self, tmp_path):
        """Codex CLI returns error → Claude failsafe runs → issue created."""

    def test_codex_unparseable_triggers_fallback(self, tmp_path):
        """Codex output can't be parsed → fallback + issue."""

    def test_tier_override_via_frontmatter(self, tmp_path):
        """<!-- review-tier: governing --> overrides auto-detection."""

    def test_tier_auto_detection_short_session(self, tmp_path):
        """Short plans/sessions/*.md (<80 lines, ≤3 files) → small tier."""

    def test_tier_auto_detection_large_tooling_session_stays_medium(self, tmp_path):
        """Large plans/sessions/*.md (>300 lines, no research signals) → medium tier."""

    def test_tier_auto_detection_large_research_session_escalates(self, tmp_path):
        """Large plans/sessions/*.md (>300 lines + research signals) → governing via rule 3."""

    def test_tier_auto_detection_initiative_path(self, tmp_path):
        """plans/<initiative>/*.md (non-session) → governing tier via rule 2."""

    def test_tier_auto_detection_medium_session(self, tmp_path):
        """plans/sessions/*.md with 4+ files, 80-300 lines → medium tier via rule 4."""

    def test_sidecar_file_written(self, tmp_path):
        """Review output written to <plan>.review.md with correct structure."""

    def test_fallback_github_issue_created(self, tmp_path, mocker):
        """gh issue create called with plan-review-fallback label on fallback."""

    def test_stagnation_detection(self, tmp_path):
        """Same findings hash across iterations → early stop."""
```

**Codex mock strategy:** Use `CODEX_REVIEW_CMD` env var (already supported
by `_resolve_codex_binary()` in the adapter, line 279) to point at a test
script that returns canned findings. No monkey-patching needed.

**Claude mock strategy:** `_apply_claude_fixes()` and the Claude fallback
reviewer need a test seam. Use a `CLAUDE_FIX_CMD` env var (parallel to
`CODEX_REVIEW_CMD`) that the adapter checks before spawning a live Claude
agent. In tests, point it at a deterministic script that applies known
fixes (e.g., adds `--seed 42` to commands, removes fake paths). For the
fallback reviewer, use a `CLAUDE_REVIEW_CMD` env var pointing to a script
that returns canned findings in the expected JSON format. This makes all
integration tests fully deterministic and CI-runnable.

**Testing:** `uv run python -m pytest tests/integration/test_plan_review_loop.py -v`

**Validation command:** After all 4 PRs merged:
```bash
# Manual invocation on a real plan
/review-plan plans/sessions/2026-03-15_independent-plan-review-agent.md
```

## Files Summary

| PR | Created | Modified |
|----|---------|----------|
| PR-1 | `docs/02_agent/PLAN_REVIEW_TIERS.md`, `.claude/agents/plan-reviewer.md` | `docs/02_agent/PLAN_REVIEW_RUBRIC.md`, `plans/AGENTS.md`, `AGENTS.md` |
| PR-2 | `scripts/internal/codex_plan_review_adapter.py`, `tests/unit/test_codex_plan_review_adapter.py` | `scripts/internal/codex_review_adapter.py`, `scripts/internal/review_state.py` |
| PR-3 | `scripts/internal/plan_review_driver.py`, `tests/unit/test_plan_review_driver.py` | `scripts/internal/review_state.py`, `.claude/hooks/post-plan-review.sh` |
| PR-4 | `.claude/skills/review-plan/SKILL.md`, `tests/integration/test_plan_review_loop.py` | `.claude/hooks/post-plan-review.sh`, `.claude/settings.json`, `.claude/hooks/README.md`, `.claude/skills/reviewing-plans/SKILL.md` |

## Dependencies

```
PR-1 (rubric + agent def) ──→ PR-2 (adapter) ──→ PR-3 (loop driver) ──→ PR-4 (wiring + integration test)
```

Linear chain — each PR depends on the previous.

## Risks

| ID | Risk | Mitigation |
|----|------|------------|
| R1 | Codex diff-based review may not apply rubric systematically | Claude failsafe provides structured rubric review; monitor fallback rate via GitHub issues |
| R2 | Claude fix agent may introduce new defects during revision | Each fix iteration is re-reviewed by Codex; 5-iter cap prevents infinite loops |
| R3 | Plan review loop may exhaust agent context window | Keep per-iteration scope small; cap findings per iteration; use offset/limit on reads |
| R4 | `CODEX_REVIEW_CMD` mock in integration tests may diverge from real CLI behavior | Document expected output format; add format validation in adapter |
| R5 | Unscoped diff exposes non-plan files to review/fix | Path isolation in adapter: temp index or `git diff -- <path>` constrains Codex to target plan only |
| R6 | Stacked PR ordering: sidecar `.review.md` re-triggers legacy hook | PR-3 adds `.review.md` exclusion to hook guard; PR-4 removes hook entirely |
| R7 | Missing `plan-review-fallback` GitHub label breaks issue creation | Retry without labels on failure (existing pattern from `review_driver.py`) |
| R8 | Codex ignores tiered rubric without AGENTS.md update | PR-1 updates `plans/AGENTS.md` with tier-aware guidance |
| R9 | State key collision for same-basename plans across initiatives | Path-hash key instead of basename |
| R10 | Line-count-only escalation misclassifies long tooling plans | Rule 3 requires research content signals + line count |
| R11 | Untracked plan files produce empty diff for Codex | Adapter stages file into temp index before review |
| R12 | Temp index seeded from HEAD leaks branch changes to Codex | Seed from main tree via `git read-tree main` |
| R13 | Sidecar files in `plans/` get accidentally committed | Sidecar written to `.claude/runtime/` (gitignored) instead |
| R14 | Claude fix/fallback paths untestable in CI without live session | `CLAUDE_FIX_CMD` and `CLAUDE_REVIEW_CMD` env vars provide test seams |

## Outcome

_To be filled after implementation._
