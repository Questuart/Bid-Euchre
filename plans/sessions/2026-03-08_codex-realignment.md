# Codex Realignment: Narrow Expectations, Sharper Guidance

## Goal

Realign the Codex review integration around what GitHub Codex actually does well
(P0/P1 correctness issues) rather than what we wished it did (structured-output
engine + style linter). Based on V1-V5 validation results.

## Design Principles

1. **Product-aligned expectations** — GitHub Codex flags P0/P1 by default; style
   and convention are outside its surface area
2. **Nested AGENTS.md for specificity** — closest file to changed code wins
   (per OpenAI docs)
3. **Deterministic tooling for deterministic checks** — style/convention stays
   in repo-lint and ruff, not Codex
4. **Promotion criteria match product contract** — response rate, P0/P1
   detection, false positive rate; not custom format compliance

## Evidence (V1-V5 Validation Results)

| Test | Finding | Implication |
|------|---------|-------------|
| V1 (#574) | 3/7 CRITICAL detected, 0 FP, inline_review channel | Good at real correctness issues |
| V2 (#579) | 0/4 style issues detected | Style is outside default P0/P1 surface |
| V3 (#578) | 0 hallucinated findings | Clean PRs get clean verdicts |
| V5 (#580) | Generic "no issues" on docs | Docs review is shallow without specific guidance |

## Changes

### 1. Nested AGENTS.md files

Create subtree-specific review guidance using P1 language Codex understands.

**`docs/04_reports/AGENTS.md`** — Report audit guidance:
```markdown
## Review guidelines

- Treat provenance SHA mismatches as P1.
- Treat published metrics without a committed generating script/notebook as P1.
- Treat formal gate-result mismatches or hidden overrides as P1.
- Treat unsupported reproduction claims as P1.
```

**`plans/AGENTS.md`** — Plan audit guidance:
```markdown
## Review guidelines

- Treat nonexistent file references as P1.
- Treat contradictory execution steps as P1.
- Treat unenforceable merge gates as P1.
- Treat workflows that can deadlock branch protection as P1.
```

### 2. Rewrite review-mode prompts in SKILL.md

Replace generic schema-demanding prompts with focused P0/P1 requests.

**Standard:**
```
@codex review for P0/P1 correctness regressions, syntax breakage, merge markers,
determinism violations, and import-boundary violations. Ignore stylistic nits.
```

**Report-audit:**
```
@codex review for provenance errors, irreproducible published metrics, missing
generator scripts, and gate-result/adjudication mismatches. Treat each as P1.
```

**Plan-audit:**
```
@codex review for nonexistent file references, contradictory rollout steps, and
unenforceable or deadlocking gates. Treat each as P1.
```

### 3. Revise promotion criteria

Replace format-compliance-heavy criteria with product-aligned metrics:

| Criterion | Old | New |
|-----------|-----|-----|
| Response rate | ≥ 90% over 10 PRs | ≥ 90% over 10 PRs (unchanged) |
| Format compliance | ≥ 90% | **Removed** — Codex uses native format |
| Parse success | ≥ 90% | **GitHub artifact parseability ≥ 90%** (inline comments extractable via API) |
| Known-severity detection | 100% on seeded | **Seeded P0/P1 detection ≥ target** |
| No missed CRITICAL | 0 misses on seeded | Unchanged (P0/P1 only) |
| False positive rate | ≤ 10% | ≤ 10% (unchanged) |
| Style/convention detection | (implicit) | **Removed from Codex bar** — repo-lint handles this |

### 4. Split validation into two lanes

- **Codex lane**: seeded P0/P1 bugs only (V1, V4-style retests)
- **Repo-governance lane**: style/convention/lint (ruff, repo-lint, make check)

V2-style tests are no longer part of the Codex promotion bar.

### 5. Update validation results with revised assessment

Update `docs/04_reports/codex_validation/results_2026-03-08.md` to reflect the
product-aligned interpretation of V2/V5 results.

## Files Changed

- `docs/04_reports/AGENTS.md` — New: report-audit review guidance
- `plans/AGENTS.md` — New: plan-audit review guidance
- `.claude/skills/reviewing-changes/SKILL.md` — Rewrite review-mode prompts
- `plans/sessions/2026-03-08_codex-review-quality.md` — Revise promotion criteria
- `docs/04_reports/codex_validation/results_2026-03-08.md` — Add V2/V3/V5 results + revised assessment

## Outcome

(To be filled after implementation)
