---
name: reviewing-plans
description: Reviews plan files against repo conventions, identifies implementation risks, and flags issues before coding begins. DEPRECATED -- use /review-plan instead.
---

> **Deprecated:** This skill has been superseded by `/review-plan`, which
> provides independent review via Codex CLI with Claude failsafe. This skill
> is retained for backward compatibility but is no longer auto-triggered.
> Use `/review-plan [path]` instead.

# /reviewing-plans -- Plan Quality Review

You are reviewing a plan file before implementation begins. The plan file path is provided in the trigger context or as `$ARGUMENTS`.

## Phase 0 — Load Plan

1. Read the plan file at the provided path.
2. If no path provided, check the most recently modified file in `plans/sessions/` or `plans/`:
   ```bash
   ls -t plans/sessions/*.md plans/*/*.md 2>/dev/null | grep -v TEMPLATE | grep -v '.review.md' | head -1
   ```
3. If no plan file found, stop: "No plan file found to review."

## Phase 1 — Convention Compliance

Check each item. Use Glob/Grep/Read to verify against actual repo state.

| ID | Check | How to Verify | Source Rule |
|----|-------|---------------|-------------|
| P1 | Plan references real file paths | Glob each referenced path — does it exist? (Paths being *created* are exempt) | `planning-code-first` |
| P2 | Plan includes actual function signatures (not guessed) | If signatures referenced, Read the source file and compare | `planning-code-first` |
| P3 | Experiment/validation commands include `--seed` | Grep plan content for `run_experiment` or `pytest` without `--seed` | `20_determinism.md` |
| P4 | No planned imports from `experiments/` or `tests/` into `src/` | Check plan's described changes for boundary violations | CLAUDE.md Architecture |
| P5 | Single-concept scope (or explicit multi-PR chain) | Count files touched; flag if >5 without justification | `40_prs.md` |
| P6 | Testing strategy identified | Plan mentions which tests to run during implementation | `15_testing_tiers.md` |
| P7 | Data contract: doc updates noted if touching rules/logging/metrics | Check if plan touches `core/`, `scoring.py`, `logging/` | `30_data_contract.md` |
| P8 | Experiment plans specify sample size and success criteria | Check for N=, threshold, CI requirements | `05_rigor.md` |
| P9 | Template completeness: Goal, Plan/Steps, Files, Outcome | Check for required section headers | New convention |
| P10 | Notebook changes note jupytext sync requirement | Check if plan touches `notebooks/` | `45_notebook_boundary.md` |
| P11 | Research plans state testable hypotheses with expected bounds | Check for measurable success/failure criteria (thresholds, CIs, effect sizes) — not just "improve X" | `PLAN_REVIEW_RUBRIC.md` §1 |
| P12 | Multi-step plans isolate one variable per step | Check that each step/rung changes one factor (architecture, objective, data, or evaluation) — flag confounded comparisons | `PLAN_REVIEW_RUBRIC.md` §5 |
| P13 | Report-producing plans specify artifact provenance | Check that claims trace to committed artifacts (JSON/CSV) with run IDs and generating scripts — not just notebook outputs | `PLAN_REVIEW_RUBRIC.md` §3, `45_notebook_boundary.md` |
| P14 | Multi-mode plans define per-tier evidence contracts | Check that SMOKE/QUICK/FULL tiers each specify what evidence is produced and what decisions each tier supports | `PLAN_REVIEW_RUBRIC.md` §12 |
| P15 | Multi-step plans annotate step dependencies | Check that plans with 4+ artifact-producing steps declare what each step requires and produces — flag steps that consume another step's output without noting the dependency | `PLAN_REVIEW_RUBRIC.md` §2 |

**Scoring:**
- **PASS** — check satisfied
- **WARN** — issue found but non-blocking
- **SKIP** — check not applicable to this plan

## Phase 2 — Implementation Risk Flags

| ID | Risk | Detection |
|----|------|-----------|
| R1 | Circular imports | Plan adds `__init__.py` exports or creates cross-module dependencies between packages |
| R2 | Stale training data | Plan changes feature names in `hand_eval.py` or `auction_context.py` — training data regeneration needed |
| R3 | Missing exports | Plan adds new public classes/functions without noting `__init__.py` update |
| R4 | Scope creep | Plan touches >5 files without clear justification linking all changes to the stated goal |
| R5 | Gate semantics | Plan modifies `validation/` or `diagnostics/` gates without noting SKIP/FAIL ordering |

**Scoring:**
- **CLEAR** — no risk detected
- **FLAG** — risk identified, should be addressed before implementation

## Phase 3 — Output Report

Output the review to chat in this format:

```markdown
## Plan Review: <plan-name>

### Plan Outline
- **Goal:** <1-sentence summary of what the plan aims to achieve>
- **Approach:** <2-3 sentences describing the key steps/changes planned>
- **Expected Result:** <1-sentence summary of the concrete deliverable or outcome>

### Convention Compliance
| ID | Status | Finding |
|----|--------|---------|
| P1 | PASS/WARN/SKIP | Detail |
| ... | ... | ... |

### Implementation Risks
| ID | Status | Finding |
|----|--------|---------|
| R1 | CLEAR/FLAG | Detail |
| ... | ... | ... |

### Summary
- Conventions: X/Y evaluated passed, Z warnings
- Risks: N flags
- Verdict: READY / NEEDS ATTENTION

READY = zero FLAGs and zero critical WARNs (P6 missing tests is critical for code PRs).
NEEDS ATTENTION = any FLAG or critical WARN found.
```

## Important Notes

- **Read-only review.** Do not edit the plan file or any other file.
- **Verify against disk.** Always Glob/Read to check claims — don't trust path references without verification.
- **New files are exempt from P1.** If the plan says "Create `foo.py`", don't flag it as missing.
- **SKIP generously.** If a check category doesn't apply (e.g., no experiments → skip P3/P8, single-step plan → skip P12), mark SKIP and move on.
- **P11–P14 are research-plan checks.** SKIP all four for pure code/bugfix/refactor plans. They apply when the plan involves experiments, multi-rung evaluation, or report generation.
- **P15 applies to any plan with 4+ artifact-producing steps.** SKIP for plans with fewer steps or where all steps are legitimately linear (each step's input is the prior step's output). The check targets plans that serialize independent work without noting it — not plans that are inherently sequential.
- **Don't expand scope.** Review only what the plan describes. Don't suggest additional features or improvements.
- **For governing plans**, recommend the full rubric review from `docs/02_agent/PLAN_REVIEW_RUBRIC.md` in addition to this tactical checklist.
