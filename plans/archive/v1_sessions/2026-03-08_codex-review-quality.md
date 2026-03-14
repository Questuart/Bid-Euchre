# Codex Review Quality: Gated Rollout to Auto-Merge

## Goal

Standardize Codex review output, instrument Claude to capture what Codex
actually returns, validate with controlled test PRs, and define explicit
promotion criteria for auto-merge. Manual merge is preserved throughout
until promotion criteria are met.

## Design Principles

1. **Manual merge until proven** — no `gh pr merge` in `/reviewing-changes`
   until Codex behavior is proven machine-consumable
2. **Observe before automating** — log Codex response metadata on every PR
3. **Known-answer testing** — seeded test PRs with expected outcomes
4. **Explicit promotion gate** — quantitative criteria, not "looks good"

## Workstream 1: Observability (PR A)

**Principle: observe only, do not intervene.** PR A adds structured Codex
prompting and response logging. Claude does NOT auto-fix Codex findings in
this phase. The iterative fix loop is deferred to PR D, after format
compliance and parser reliability are proven via validation tests.

### AGENTS.md — Structured output format

Add a "Review Output Format" section telling Codex to report findings as:

```markdown
## Codex Review

### Summary
- Files reviewed: N (M library, K test, ...)
- Findings: X CRITICAL, Y WARNING, Z NIT

### Findings

| Severity | File | Line | Check | Finding |
|----------|------|------|-------|---------|
| CRITICAL | path/to/file.py | 42 | C1 | Description + fix suggestion |
| WARNING | path/to/file.py | 87 | C4 | Description |
| NIT | path/to/file.py | 3 | — | Description |

### Checks Performed
- [x] C1: Unseeded randomness
- [x] C2: Falsy numeric guards
- [ ] N1: Contract-type faceting — no notebooks changed
```

Severity scale:
- **CRITICAL** — correctness issue, maps to our BLOCK checks (C1, C2, X3, N1, N2)
- **WARNING** — non-blocking, maps to WARN checks (C3, C4, T1, X1, X2, N3)
- **NIT** — style/readability, no action required

"If no issues found" instruction: still report the Checks Performed section
so we know what was covered vs skipped.

### `/reviewing-changes` SKILL.md — Codex response logging (observe-only)

Update Phase 3 Step 3 to:

1. Post `@codex review` with PR-aware context:
   ```
   @codex review

   **PR scope:** M files changed (K library, J test, ...)
   **Risk level:** [from PR body or file classification]

   Report findings using the structured format in AGENTS.md.
   Use severity levels: CRITICAL, WARNING, NIT.
   Include file path, line number, and check ID for each finding.
   If no issues, still list which checks you performed.
   ```

2. Poll for response (up to 5 min, every 30s)

3. Log response metadata to the review report:
   - `codex_responded`: yes/no
   - `codex_latency_seconds`: time from comment to response
   - `codex_format_compliant`: yes/no (has Summary + Findings table + Checks Performed)
   - `codex_findings_parseable`: yes/no (file paths and severity tags extractable)
   - `codex_finding_counts`: {CRITICAL: N, WARNING: N, NIT: N}
   - `codex_checks_reported`: list of check IDs marked performed

4. Include Codex findings in the review report's Codex Review section
   (parsed into table format if parseable, raw dump as fallback)

5. **Do NOT auto-fix Codex findings.** Report them for human review only.
   Codex findings are informational in this phase — they do not affect
   commit status or merge eligibility.

Claude's own review (Phases 0-2) continues to fix BLOCK findings as before.
Only Codex-sourced findings are observe-only.

### Files changed (PR A)

- `AGENTS.md` — Add Review Output Format section
- `.claude/skills/reviewing-changes/SKILL.md` — Codex logging (observe-only)
  + PR-aware trigger comment
- `.claude/skills/reviewing-changes/HANDOFF_TEMPLATE.md` — Add Codex
  metadata fields to handoff
- `.claude/rules/60_review_gate.md` — Note Codex observe-only phase
- `docs/02_agent/CODEX_GITHUB_REVIEW.md` — Update to reflect observe-only
  Codex integration

## Workstream 2: Validation Tests (PR B)

### Validation matrix

6 controlled test scenarios, each run as a temporary PR (opened, reviewed,
then closed without merging):

| Test | PR Content | Expected Codex Behavior | Pass Criteria |
|------|-----------|------------------------|---------------|
| V1: Obvious correctness bug | Unseeded `random.Random()`, `x = x or 0.0` | Flags as CRITICAL with file:line | Response received, parseable, correct severity |
| V2: Style-only issue | `breakpoint()`, redundant `else` | Flags as WARNING/NIT, not CRITICAL | No severity inflation |
| V3: Clean PR | Trivial doc fix, no issues | "No issues" + Checks Performed list | No hallucinated findings |
| V4: Re-review after fix | Push fix for V1 issues, re-trigger | Fixed issues no longer reported | Delta detection works |
| V5: Docs-only PR | Markdown-only change | Determine if Codex reviews at all | Record coverage gap if no review |
| V6: Timeout/no-response | (Natural — if Codex is slow/down) | Workflow records timeout gracefully | No hang, no false merge signal |

### Per-test recording

For each test, record in `docs/04_reports/codex_validation/`:

```markdown
## Validation: V[N] — [name]

- **PR:** #NNN (closed without merge)
- **Date:** YYYY-MM-DD
- **Response received:** yes/no
- **Latency:** Ns
- **Format compliant:** yes/no
- **Findings parseable:** yes/no
- **Severity correct:** yes/no (expected vs actual)
- **False positive inflation:** yes/no
- **Notes:** [any observations]
```

### Data durability

Test PRs are closed without merging, but validation observations must
survive. Process:

1. Run temporary test PR (V1-V6)
2. Capture Codex response metadata during the test (from PR comments)
3. Record observations locally
4. Close test PR without merging
5. Land all validation results in a **separate results PR** that merges
   into main under `docs/04_reports/codex_validation/results_YYYY-MM-DD.md`

This ensures the validation dataset is committed, versioned, and available
for PR C's aggregation script. Each results file links back to the original
test PR number for traceability.

### Files changed (PR B)

- `docs/04_reports/codex_validation/validation_protocol.md` — Test matrix
  and recording template (new file)
- `docs/04_reports/codex_validation/results_YYYY-MM-DD.md` — Validation
  results from test runs (new file, landed via merged results PR)
- Temporary test branches for V1-V5 (opened and closed, not merged)

## Workstream 3: Promotion Gate (PR C + D + E)

### Promotion criteria for auto-merge

Written into `docs/04_reports/codex_validation/promotion_criteria.md`:

**Revised 2026-03-08** after V1-V5 validation results showed GitHub Codex
operates as a P0/P1 high-severity reviewer, not a structured-output engine.
Criteria realigned to match Codex's actual product contract.

| Criterion | Threshold | Measured Over | Notes |
|-----------|-----------|---------------|-------|
| Codex response rate | ≥ 90% | ≥ 10 PRs | Unchanged |
| GitHub artifact parseability | ≥ 90% | PRs where Codex flagged issues | Inline comments extractable via API |
| Seeded P0/P1 detection | ≥ 80% | Seeded correctness test PRs | P0/P1 bugs only; style excluded |
| False positive rate | ≤ 10% | All PRs | Unchanged |
| Human reviewer sign-off | Required | After reviewing aggregate report | Unchanged |

**Removed criteria:**
- ~~Structured format compliance ≥ 90%~~ — Codex uses native GitHub format
- ~~Known-severity detection 100%~~ — Replaced with P0/P1-scoped ≥ 80%
- ~~No missed CRITICAL on seeded PR~~ — Merged into P0/P1 detection metric

**Rationale:** V1-V5 showed Codex ignores custom format when it has no findings.
Style/convention detection is handled by repo-lint and ruff, not Codex.

### Rollout sequence

**PR C: Aggregation script**
- `scripts/internal/codex_validation_report.py` — reads validation records,
  computes promotion metrics, outputs readiness report
- No merge behavior changes

**PR D: Iterative fix loop + dry-run auto-merge eligibility** (only if criteria met)
- Enable the iterative review-fix loop in `/reviewing-changes`:
  Claude parses Codex CRITICAL findings, fixes agreed ones, pushes,
  re-triggers `@codex review`, iterates up to 5 times
- Add "would auto-merge" reporting — logs whether this PR would have been
  auto-merged, but does NOT actually merge
- Adds `auto_merge_eligible: true/false` to review report with rationale

**PR E: Enable auto-merge** (only after successful dry-run period)
- Update `/reviewing-changes` to call `gh pr merge --squash --delete-branch`
  when `auto_merge_eligible: true`
- Update `.claude/rules/60_review_gate.md` to remove manual merge language
- Requires ≥ 5 consecutive dry-run-eligible PRs with human agreement

## Implementation Sequence

```
PR A: Observability    → structured format + observe-only logging
PR B: Validation       → test protocol + run V1-V6 + commit results
                          ↓ (analyze results)
PR C: Aggregation      → readiness metrics script
                          ↓ (accumulate real PR data)
PR D: Fix loop         → iterative Codex fix + dry-run auto-merge reporting
                          ↓ (verify dry-run accuracy)
PR E: Auto-merge       → enable actual auto-merge (if criteria met)
```

PRs A-B are this session. C-E are future work gated on validation results.

**Key sequencing constraint:** PR A is observe-only. The iterative fix loop
(Claude auto-fixing Codex CRITICALs) is deferred to PR D, after validation
proves that Codex format compliance and parser reliability are sufficient
to act on findings programmatically.

## Validation corpus

**Mixed set, biased toward seeded test PRs first.** Seeded PRs (V1-V5)
provide controlled known-answer baselines. Real PRs during normal development
add real-world variance. Both are needed for deployment readiness.

Target: ≥ 10 total validation data points before PR D (dry-run).

## Outcome

(To be filled after implementation)
