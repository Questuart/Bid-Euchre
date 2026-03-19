# Plan Review Rubric

Weighted rubric for evaluating governing plans (multi-rung research designs,
lineage rebuilds, canonical plan revisions). Complements the tactical
`/review-plan` skill, which handles convention compliance for session-scoped
plans via Codex CLI + Claude failsafe.

**When to use this rubric:**
- Governing plans that span multiple rungs or PRs
- Lineage rebuild plans
- Any plan that defines a multi-step research program with promotion gates

**When `/review-plan` is sufficient:**
- Session-scoped plans (single PR)
- Bugfix or small feature plans
- Plans with no experimental evaluation component

**Tiered rubric system:** For automated plan review with tier detection
(small/medium/governing), see `docs/02_agent/PLAN_REVIEW_TIERS.md`.
The governing tier applies the full rubric from this document.

## Scoring Model

Score each dimension `0–5`. Multiply by the dimension weight. Normalize to 0–100:

```
Total = Σ(weight_i × score_i) / (5 × 100) × 100
```

Since weights sum to 100, this simplifies to:

```
Total = Σ(weight_i × score_i) / 5
```

Suggested scale:
- `5`: fully specified, low ambiguity, directly usable
- `4`: strong, small gaps, low execution risk
- `3`: adequate but materially underspecified
- `2`: weak, high agent guesswork required
- `1`: major gaps, not reliable
- `0`: absent or contradictory

Suggested thresholds:
- `90–100`: governing-plan ready
- `75–89`: strong, needs targeted fixes
- `60–74`: directionally right, still underspecified
- `<60`: not safe for agent execution

## Weighted Dimensions

| Dimension | Weight |
|---|---:|
| Research validity | 14 |
| Agent executability | 13 |
| Reporting traceability | 10 |
| Reporting communication quality | 10 |
| Ablation integrity | 9 |
| Tooling alignment | 8 |
| Metric contract quality | 7 |
| Data-generation consistency | 7 |
| Roster and lineage governance | 4 |
| Decision usefulness | 3 |
| Human review ergonomics | 3 |
| Evaluation economics | 3 |
| Knowledge transfer | 3 |
| Operational sustainability | 2 |
| Historical continuity | 2 |
| Failure containment | 2 |
| **Total** | **100** |

## Rubric Questions

### 1. Research validity — 14%
- Does the plan produce evidence that answers the actual research questions?
- Are the core hypotheses measurable and tied to the decisions the lineage is supposed to support?
- Does the plan avoid confounding model class, objective, context, label-generation policy, and evaluation setup?
- Would a reviewer trust the conclusions the plan is designed to produce?
- Does the plan pre-specify what evidence would trigger ADVANCE vs HALT vs INVESTIGATE at each rung boundary?

### 2. Agent executability — 13%
- Can a future agent execute a rung end to end from the plan alone?
- Are commands, inputs, outputs, schemas, directories, and artifact contracts concrete?
- Are sample sizes, seeds, validation checks, and rerun rules explicit?
- Is there a clear fallback or blocking rule when required infrastructure is not yet implemented?
- For plans with multiple artifact-producing steps: are dependencies between steps annotated (what each step requires and produces), so an agent can identify independent work and avoid unnecessary serialization?

### 3. Reporting traceability — 10%
- Can every major claim trace to a table/chart ID?
- Can every table/chart trace to a CSV/JSON artifact?
- Can every artifact trace to a run ID, config, and generating script?
- Does the plan prohibit hand-maintained metrics in canonical reports?

### 4. Reporting communication quality — 10%

*Scope: narrative content, findings clarity, story structure.*

- Do the reports make the story of the rung understandable quickly?
- Are main findings, surprises, decisions, and risks surfaced clearly?
- Are charts and tables complementary rather than redundant?
- Can HITL or a future agent understand what mattered from the report narrative alone, without cross-referencing artifacts?

### 5. Ablation integrity — 9%
- Does each rung isolate a small enough change to support interpretation?
- Are rung-to-rung comparisons clean and consistent?
- Are independent experimental factors (architecture, objective, data, evaluation) varied one at a time across rungs?
- Can the plan support a defensible "what changed and why?" narrative?

### 6. Tooling alignment — 8%
- Does the plan match the repo's current scripts, CLIs, artifact formats, and model interfaces?
- Are unsupported workflows explicitly marked as required implementation work?
- Are file paths, config patterns, and command shapes consistent with the codebase?
- Would a future agent avoid inventing missing flags or unsupported execution paths?

### 7. Metric contract quality — 7%
- Are the canonical metrics fixed and consistently defined?
- Are offline, gameplay, behavioral, and decision metrics separated clearly?
- Are required contract-type facets fixed across all reports?
- Are table schemas precise enough that different agents would generate the same outputs?

### 8. Data-generation consistency — 7%
- Is the training/eval data contract stable across rungs?
- Are continuation policy, feature extraction, context bundles, and label generation clearly defined?
- Are seed and sample-size policies fixed by mode?
- Would rerunning the same rung under the same config reproduce the same evidence package?

### 9. Roster and lineage governance — 4%
- Is the active roster clearly defined?
- Are frozen references, active models, legacy baselines, and exploratory entrants distinguished cleanly?
- Are amendment rules for adding/removing models explicit?
- Are exclusions and status labels defined well enough to prevent silent drift?

### 10. Decision usefulness — 3%
- Does each rung end with a clear decision artifact?
- Does the plan require explicit hypotheses, expected bounds, and observed outcomes?
- Is it easy to tell whether the next action is proceed, investigate, pause, or redirect?
- Does the plan help guide the next rung rather than only record the last one?

### 11. Human review ergonomics — 3%

*Scope: file layout, directory structure, artifact naming, navigation.*

- Can a human reviewer audit a rung quickly without opening raw logs or notebooks?
- Are the most important tables, charts, and summaries surfaced at the top level of the evidence package?
- Is the directory/artifact structure easy to navigate without a guide?
- Does the plan minimize the number of files a reviewer must open to form a judgment?

### 12. Evaluation economics — 3%
- Is the cost of QUICK and FULL evaluations proportionate to the decision value they provide?
- Does the plan clearly distinguish what evidence is required at SMOKE, QUICK, and FULL?
- Are expensive artifacts justified by the research questions?
- Is there a clear way to screen cheaply before paying for full evidence?

### 13. Knowledge transfer — 3%
- Could a new agent understand the lineage's operating model from this plan?
- Are naming conventions, artifact semantics, and execution expectations explained clearly?
- Does the plan reduce dependence on legacy tribal knowledge?
- Could the next agent avoid rereading the entire repo to operate correctly?

### 14. Operational sustainability — 2%
- Is the reporting and artifact burden realistic to maintain?
- Are runtime, storage, and regeneration costs manageable across multiple rungs?
- Can the process survive repeated use without collapsing into overhead?
- Does the plan avoid unnecessary report/file sprawl?

### 15. Historical continuity — 2%
- Does the new lineage remain interpretable relative to legacy `R0` work?
- Are frozen legacy references used thoughtfully for continuity?
- Can reviewers answer "better than old R0?" from the canonical reports?
- Does the rebuild preserve useful comparability without inheriting old confusion?

### 16. Failure containment — 2%
- Does the plan define how to quarantine bad runs or broken artifacts?
- Are rerun, supersession, and invalidation rules explicit?
- Can a bad rung be isolated without contaminating later ones?
- Is canonical vs exploratory failure handling clear?

## Hard Gates

Override checks — if any gate FAILs, the verdict is **Not Ready** regardless of
the weighted score.

| Gate | What It Checks |
|---|---|
| R0* definition | Concrete frozen baseline exists and is referenced |
| Canonical rung definition | Each rung/context bundle has a singular canonical specification |
| Executable runbook | At least one rung has step-by-step executable instructions |
| Fixed metric/table schema | Canonical metrics and report table schemas are pinned |
| Evidence/provenance contract | Artifact → run ID → config traceability chain is defined |
| Stable data-generation policy | Continuation policy, labels, and seeds are fixed across rungs |
| Tooling existence | Any required tooling that doesn't exist is marked as implementation work with block/fallback behavior |
| Contract consistency | Canonical report contract does not contradict the evidence contract |

## Output Template

```markdown
# Plan Rubric Review

## Summary
- Plan: <path>
- Reviewer: <agent/human>
- Date: <YYYY-MM-DD>
- Total Score: <0–100>
- Verdict: <Ready / Needs Targeted Fixes / Underspecified / Not Ready>

## Hard Gate Check

| Gate | Status | Notes |
|---|---|---|
| R0* definition | PASS/FAIL | ... |
| Canonical rung definition | PASS/FAIL | ... |
| Executable runbook | PASS/FAIL | ... |
| Fixed metric/table schema | PASS/FAIL | ... |
| Evidence/provenance contract | PASS/FAIL | ... |
| Stable data-generation policy | PASS/FAIL | ... |
| Tooling existence | PASS/FAIL | ... |
| Contract consistency | PASS/FAIL | ... |

> Hard gate FAIL → verdict is "Not Ready" regardless of total score.

## Findings

| Severity | Dimension | Finding |
|---|---|---|
| CRITICAL | <dimension name> | <finding> |
| WARNING | <dimension name> | <finding> |

## Dimension Scores

| Dimension | Weight | Score (0–5) | Weighted | Notes |
|---|---:|---:|---:|---|
| Research validity | 14 |  |  |  |
| Agent executability | 13 |  |  |  |
| Reporting traceability | 10 |  |  |  |
| Reporting communication quality | 10 |  |  |  |
| Ablation integrity | 9 |  |  |  |
| Tooling alignment | 8 |  |  |  |
| Metric contract quality | 7 |  |  |  |
| Data-generation consistency | 7 |  |  |  |
| Roster and lineage governance | 4 |  |  |  |
| Decision usefulness | 3 |  |  |  |
| Human review ergonomics | 3 |  |  |  |
| Evaluation economics | 3 |  |  |  |
| Knowledge transfer | 3 |  |  |  |
| Operational sustainability | 2 |  |  |  |
| Historical continuity | 2 |  |  |  |
| Failure containment | 2 |  |  |  |
| **Total** | **100** |  | **<sum>** |  |

> Total Score = sum of weighted column / 5

## Strengths
- <bullet>

## Gaps
- <bullet>

## Priority Fixes
1. <highest-value fix>
2. <next fix>
3. <next fix>
```
