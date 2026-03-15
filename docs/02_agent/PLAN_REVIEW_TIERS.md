# Tiered Plan Review Rubric

Three-tier rubric for automated plan review. Each plan is classified into a
tier that determines which checks are applied. Higher tiers include all checks
from lower tiers.

**Cross-reference:** The governing tier applies the full weighted rubric and
hard gates from `docs/02_agent/PLAN_REVIEW_RUBRIC.md`.

## Tier Classification

Tiers are determined by the first matching rule (evaluated in order):

1. **Frontmatter override** — `<!-- review-tier: small|medium|governing -->`
   in the first 10 lines of the file always wins.
2. **Initiative path** — Files under `plans/<initiative>/` (excluding
   `plans/sessions/` and `plans/_templates/`) default to **governing**.
3. **Content escalation to governing** — Plans with a `## Governing Plan`
   header, OR plans that are both >300 lines AND contain strong research
   signals, escalate to **governing**. Strong research signals are:
   - `## Hypotheses` section header
   - Keywords: `rung`, `R0`, `R1`, `rung ladder`
   - Keywords: `promotion gate`, `ADVANCE`, `HALT`
   - Weak signals (`gate`, `SMOKE`, `QUICK`, `FULL` alone) are NOT sufficient.
4. **Content escalation to medium** — Plans that reference 4+ files, describe
   a multi-PR chain, or exceed 80 lines escalate to **medium**.
5. **Default** — Everything else is **small**.

## Small Tier (7 checks)

Applies to: session plans, single-PR bugfixes, small feature plans.

| ID | Check | Category |
|----|-------|----------|
| P1 | **Real paths** — All referenced file paths exist on disk (new files being created are exempt) | convention |
| P2 | **Real signatures** — Referenced function/class names and parameter signatures match the codebase | convention |
| P3 | **Seeds specified** — Any experiment or data-generation command includes `--seed <int>` | convention |
| P5 | **Single-concept** — Plan addresses one coherent change (no mixed refactor + feature) | convention |
| P6 | **Testing strategy** — Plan specifies which tests to run or create | convention |
| P9 | **Template completeness** — Required template sections are present (Summary, Outcome placeholder) | convention |
| R4 | **Scope creep** — Plan scope matches the stated goal; no undeclared side-work | risk |

## Medium Tier (15 checks)

Applies to: multi-file changes, multi-PR chains, plans 80-300 lines.

Includes all Small checks plus:

| ID | Check | Category |
|----|-------|----------|
| P4 | **Import boundary** — Plan does not introduce `src/` imports from `experiments/` or `tests/` | convention |
| P7 | **Data contract** — Changes to logging, metrics, or schemas reference the appropriate contract docs | convention |
| P8 | **Sample size** — Research plans specify sample sizes that meet repo minimums (>=2000 for bias detection, >=50000 for production). **SKIP** for non-research plans. Auto-detect research intent via keywords: `hypothesis`, `statistical`, `bootstrap`, `p-value`, `confidence interval`, `sample size`, `n_deals`, `SMOKE`, `QUICK`, `FULL`. | convention |
| P10 | **Jupytext** — Notebook changes reference `.py` files (not `.ipynb` directly) and note `make notebook-sync` | convention |
| P11 | **Hypotheses** — Research plans state testable hypotheses with measurable success criteria. **SKIP** for non-research plans. Auto-detect research intent via the same keywords as P8. | convention |
| P15 | **Step dependencies** — Multi-step plans annotate what each step requires and produces; independent steps are not unnecessarily serialized | convention |
| R1 | **Execution risk** — High-risk steps (schema changes, data regeneration, multi-rung experiments) are identified | risk |
| R2 | **Rollback plan** — Plan describes how to recover if a step fails or produces bad results | risk |
| R3 | **Dependency chain** — External dependencies (other PRs, data artifacts, model artifacts) are listed | risk |
| R4 | **Scope creep** — (inherited from Small) | risk |
| R5 | **Timeline risk** — Plan estimates are realistic given the scope; multi-day work is acknowledged | risk |

## Governing Tier (full rubric)

Applies to: multi-rung research plans, lineage rebuilds, governing plans.

Includes all Medium checks plus:

| ID | Check | Category |
|----|-------|----------|
| P12 | **Evaluation economics** — Plan distinguishes SMOKE/QUICK/FULL evidence requirements and justifies expensive runs | research |
| P13 | **Knowledge transfer** — Plan is self-contained enough for a new agent to execute without repo-wide archaeology | research |
| P14 | **Failure containment** — Plan defines quarantine/rerun/invalidation rules for bad runs or broken artifacts | research |

Additionally, the governing tier applies:

- **16-dimension weighted rubric** from `docs/02_agent/PLAN_REVIEW_RUBRIC.md`
  (research validity, agent executability, reporting traceability, etc.)
- **8 hard gates** from `docs/02_agent/PLAN_REVIEW_RUBRIC.md` (R0* definition,
  canonical rung definition, executable runbook, fixed metric/table schema,
  evidence/provenance contract, stable data-generation policy, tooling
  existence, contract consistency)

A hard gate FAIL overrides the weighted score and produces a **Not Ready**
verdict regardless of the total.

## Output Schema

All tiers produce findings in a common JSON schema:

```json
[
  {
    "severity": "CRITICAL|WARNING|INFO",
    "category": "convention|risk|research",
    "file": "plans/sessions/2026-03-15_example.md",
    "line": 42,
    "description": "Referenced path src/bid_euchre/foo/bar.py does not exist",
    "check_id": "P1"
  }
]
```

If no issues are found, return `[]`.

### Severity Mapping

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Blocks execution or produces incorrect results | Must fix before proceeding |
| **WARNING** | Risk factor or gap worth addressing | Should fix; may defer with justification |
| **INFO** | Minor improvement or observation | Note only |

### Check ID to Default Severity

| Check | Default Severity | Override Conditions |
|-------|-----------------|---------------------|
| P1 (real paths) | CRITICAL | — |
| P2 (real signatures) | CRITICAL | — |
| P3 (seeds) | WARNING | CRITICAL if plan includes experiment comparisons |
| P4 (import boundary) | CRITICAL | — |
| P5 (single-concept) | WARNING | — |
| P6 (testing strategy) | WARNING | CRITICAL for code PRs with no tests mentioned |
| P7 (data contract) | WARNING | CRITICAL if touching core/ or logging/ |
| P8 (sample size) | WARNING | SKIP for non-research plans |
| P9 (template) | INFO | — |
| P10 (jupytext) | INFO | WARNING if plan creates new notebooks |
| P11 (hypotheses) | WARNING | SKIP for non-research plans |
| P12 (eval economics) | WARNING | — |
| P13 (knowledge transfer) | INFO | — |
| P14 (failure containment) | WARNING | CRITICAL for multi-rung plans |
| P15 (step dependencies) | WARNING | — |
| R1 (execution risk) | WARNING | — |
| R2 (rollback plan) | INFO | WARNING for irreversible operations |
| R3 (dependency chain) | WARNING | CRITICAL if dependencies are unmerged PRs |
| R4 (scope creep) | WARNING | — |
| R5 (timeline risk) | INFO | — |
