# AGENTS.md — Codex Review Guidance

> This file provides context to Codex (and other AI reviewers) when reviewing
> PRs in this repository. For full developer workflow, see `docs/02_agent/AGENTS.md`.

## Project

Bid Euchre AI Research Framework — deterministic simulation and strategy
evaluation for the card game Bid Euchre (double-deck, 10-A variant with bowers).

## Review Focus Areas

When reviewing PRs, prioritize these checks in order:

### Critical (should block merge)

1. **Unseeded randomness** — Any use of `random.Random()` without a seed,
   or global `random.*` calls in `src/` library code. All strategies must use
   local `random.Random(seed)`.

2. **Falsy numeric guards** — `x = x or fallback` on numeric metrics.
   `0.0` is falsy in Python, so this silently replaces valid zeros.

3. **Merge artifacts** — Conflict markers (`<<<<<<<`), `TODO: remove before merge`,
   large commented-out blocks (>10 lines).

4. **Import boundary violations** — `src/` must NOT import from `experiments/`
   or `tests/`.

### Important (should warn)

5. **Missing test coverage** — Behavior changes in `src/` without corresponding
   test updates in `tests/`.

6. **Missing contract-type faceting** — Notebooks that aggregate or visualize
   data without faceting by `contract_type` (suit/high/low).

7. **Statistical claims without tests** — Inference claims in notebooks without
   accompanying p-values, confidence intervals, or effect sizes.

8. **Function complexity** — Functions exceeding 50 lines or nesting depth >4.

### Context

9. **Determinism** — Experiments require `--seed <int>`. Same seed + config
   must produce identical results.

10. **Data policy** — `data/runs/`, `data/reports/`, `data/models/` must never
    be committed. Only `data/fixtures/` is allowed.

## Review Modes

PRs are classified by review mode based on changed file types. Each mode
applies different checks. Codex should use the mode that matches the PR.

### Standard (default)

Applies to: code PRs (`src/`, `tests/`, `scripts/`, `experiments/`)

Use the checks listed in "Review Focus Areas" above. Focus on code
correctness, test coverage, conventions, and determinism.

### Report Audit

Applies to: PRs touching `docs/04_reports/**`, gate/promotion reports,
measurement integrity reviews, or any docs that publish technical results.

These are **reviewable artifacts**, not "docs-only" PRs. Apply these checks:

| ID | Check | Severity |
|----|-------|----------|
| R1 | **Provenance SHA verification** — any commit SHA or run ID cited in the report must exist in the repo history. Flag unverifiable provenance. | CRITICAL |
| R2 | **Reproducibility** — published metrics must trace to a committed script, notebook, or artifact with a repro command. Flag metrics with no committed generating source. | CRITICAL |
| R3 | **Gate result accuracy** — distinguish formal gate pass/fail from override or adjudication. Do not allow "N/A" to hide a fail. | WARNING |
| R4 | **Plan consistency** — cross-check report claims against the governing plan referenced in the PR body. Flag contradictions. | WARNING |
| R5 | **Artifact completeness** — if the report references data files, configs, or model artifacts, verify the paths exist or are explicitly noted as gitignored with repro instructions. | WARNING |

### Plan Audit

Applies to: PRs touching `plans/**`

Use the tiered plan review rubric from `docs/02_agent/PLAN_REVIEW_TIERS.md`.
Classify the plan as small, medium, or governing and apply the corresponding
checks. For quick reference, the minimum checks (small tier) are: P1 (real
paths), P2 (real signatures), P3 (seeds), P5 (scope), P6 (testing), P9
(template), R4 (scope creep).

## Review Output Format

When reporting review findings, use this structured format so that findings
can be parsed consistently by both humans and automated tooling.

### Severity Scale

| Severity | Meaning | Maps to | Action |
|----------|---------|---------|--------|
| **CRITICAL** | Correctness issue that would cause bugs or data corruption | BLOCK checks (C1, C2, X3, N1, N2) | Must fix before merge |
| **WARNING** | Non-blocking issue worth fixing or tracking | WARN checks (C3, C4, T1, X1, X2, N3) | Follow-up issue post-merge |
| **NIT** | Style, readability, or minor improvement | — | Note only, no action required |

### Response Template

```markdown
## Codex Review

### Summary
- Files reviewed: N (M library, K test, J notebook, ...)
- Findings: X CRITICAL, Y WARNING, Z NIT

### Findings

| Severity | File | Line | Check | Finding |
|----------|------|------|-------|---------|
| CRITICAL | src/bid_euchre/strategy/foo.py | 42 | C1 | `random.Random()` without seed — use `random.Random(seed)` |
| WARNING | src/bid_euchre/strategy/foo.py | 87 | C4 | Function `compute_ev` is 63 lines — consider extracting helper |
| NIT | src/bid_euchre/strategy/foo.py | 3 | — | Unused import `os` |

(If no issues found, write "No findings." instead of the table.)

### Checks Performed
- [x] C1: Unseeded randomness
- [x] C2: Falsy numeric guards
- [x] C4: Import boundary violations
- [x] X3: Merge artifacts
- [x] T1: Missing test coverage
- [ ] N1: Contract-type faceting — no notebooks changed
- [ ] N3: Statistical claims — no notebooks changed
```

### Important Notes for Reviewers

- **Always include the Checks Performed section**, even when no issues are
  found. This tells us what was checked vs. what was skipped.
- **Use the check IDs** (C1, C2, C3, C4, T1, X1, X2, X3, N1, N2, N3) from
  the Review Focus Areas section above when a finding maps to a known check.
  Use `—` for findings that don't map to a specific check.
- **Include file paths and line numbers** so findings can be located quickly.
- **Be specific in findings** — describe what's wrong and suggest a fix.

## File Layout

- `src/bid_euchre/` — Library code (rules, simulation, strategies, features)
- `experiments/` — Config files and experiment runner
- `scripts/internal/` — Research tooling (not canonical workflow)
- `tests/` — Unit, integration, performance tests
- `notebooks/` — Jupytext-paired analysis notebooks
- `docs/` — Contracts and guidance
