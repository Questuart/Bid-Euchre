# Token Economy Baseline Report

**Date:** 2026-03-23
**Sub-plan:** SP-4-03 (Step 5)
**Data range:** 2026-02-03 to 2026-03-14
**Sessions analyzed:** 308 (8 malformed source files skipped)

---

## Executive Summary

Across 308 sessions consuming 2.67M tokens over ~40 calendar days, the
project achieves a committed-output rate of **52.4%** — meaning 47.6% of all
token spend occurs in sessions that produce zero git commits. The primary
waste driver is **abandoned-work churn**: 129 zero-commit sessions generated
39,579 lines of code that were never committed, consuming 1.15M tokens.
Secondary drivers are wrong-approach friction (60 occurrences) and tool
error accumulation in long sessions.

The data represents the **pre-steward era**: all sessions ran on the main
checkout or ad hoc worktrees before the multi-lane steward platform was
deployed. Lane-level attribution is therefore limited to a single
`main-checkout` pool. Post-steward sessions (after 2026-03-14) are not yet
in the telemetry pipeline and will form the basis for a follow-up
comparison report.

---

## 1. Aggregate Token Economy

| Metric | Value |
|--------|-------|
| Sessions | 308 |
| Calendar span | 40 days (2026-02-03 to 2026-03-14) |
| Total duration | 31,342 min (522.4 hours) |
| Total tokens | 2,671,254 |
| Input tokens | 556,795 |
| Output tokens | 2,114,459 |
| Output/Input ratio | 3.8x |
| Tokens/hour | 5,114 |

### Throughput

| Metric | Value |
|--------|-------|
| Lines added | 72,672 |
| Lines removed | 5,557 |
| Net lines | 67,115 |
| Git commits | 244 |
| Git pushes | 171 |
| Files modified | 664 |
| Tokens/commit | 10,948 |
| Tokens/net line | 40 |

### Interaction

| Metric | Value |
|--------|-------|
| User messages | 1,539 |
| Assistant messages | 18,320 |
| Assistant/User ratio | 11.9x |
| Tool errors | 975 |
| Errors/1K tokens | 0.36 |

---

## 2. Token Allocation: Shipped vs Non-Shipped

| Category | Sessions | Tokens | % of Total |
|----------|----------|--------|------------|
| **Committed sessions** (≥1 commit) | 89 (29%) | 1,400,485 | **52.4%** |
| **Zero-commit sessions** | 219 (71%) | 1,270,769 | **47.6%** |
| — with lines generated | 129 | 1,145,336 | 42.9% |
| — with no output | 90 | 125,433 | 4.7% |

**Key insight:** Nearly half of all token spend (47.6%) produced no
committed output. However, much of this is not pure waste — planning,
exploration, review, and debugging sessions are expected to have zero
commits. The 4.7% with zero lines and zero commits (125K tokens) is the
most clearly wasteful segment.

### Committed Session Efficiency

| Metric | Value |
|--------|-------|
| Sessions | 89 |
| Tokens | 1,400,485 |
| Commits | 244 |
| Tokens/commit | 5,739 |
| Tokens/line added | 42.3 |
| Tokens/net line | 46.9 |

---

## 3. Session Size Distribution

| Size Bucket | Sessions | Tokens | % of Total |
|-------------|----------|--------|------------|
| Small (<2K tokens) | 136 (44%) | 46,125 | 1.7% |
| Medium (2K–20K) | 131 (43%) | 1,137,763 | 42.6% |
| Large (>20K) | 41 (13%) | 1,487,366 | **55.7%** |

**Key insight:** 13% of sessions consume 56% of tokens. The top 10 most
expensive sessions alone account for 642K tokens (24% of total). Large
sessions should be the primary target for efficiency improvements.

### Top 10 Most Expensive Sessions

| Tokens | Commits | Lines | Duration | Files |
|--------|---------|-------|----------|-------|
| 160,457 | 0 | 447 | 34 min | 1 |
| 86,941 | 3 | 321 | 449 min | — |
| 69,883 | 4 | 561 | 368 min | — |
| 62,568 | 0 | 1,313 | 171 min | 1 |
| 60,467 | 4 | 813 | 27 min | — |
| 56,365 | 6 | 510 | 199 min | — |
| 44,999 | 0 | 214 | 10 min | 1 |
| 43,937 | 3 | 614 | 62 min | — |
| 42,214 | 4 | 34 | 9 min | — |
| 41,507 | 5 | 1,141 | 36 min | — |

The most expensive session (160K tokens, zero commits) consumed 6% of all
tokens by itself.

---

## 4. Session Type and Outcome Distribution

### By Session Type

| Type | Sessions | Tokens | Tokens/Session |
|------|----------|--------|----------------|
| (unclassified) | 161 | 909,939 | 5,652 |
| multi_task | 52 | 708,917 | 13,633 |
| iterative_refinement | 44 | 650,100 | 14,775 |
| single_task | 42 | 354,743 | 8,446 |
| exploration | 8 | 47,501 | 5,938 |
| quick_question | 1 | 54 | 54 |

**Key insight:** `iterative_refinement` sessions are the most expensive per
session (14.8K tokens avg), consistent with repeated edit–test cycles. The
161 unclassified sessions (from older telemetry format) represent 34% of
total spend.

### By Outcome

| Outcome | Sessions | Tokens | Tokens/Session |
|---------|----------|--------|----------------|
| (unclassified) | 161 | 909,939 | 5,652 |
| fully_achieved | 75 | 929,415 | 12,392 |
| mostly_achieved | 49 | 658,521 | 13,439 |
| partially_achieved | 18 | 168,189 | 9,344 |
| not_achieved | 3 | 5,190 | 1,730 |
| unclear | 2 | 0 | 0 |

**Key insight:** `mostly_achieved` sessions cost 13.4K tokens/session — nearly
as much as `fully_achieved` — suggesting that "almost done" sessions represent
a significant efficiency opportunity (better scoping could convert partial
completions to full completions).

---

## 5. Friction Analysis

### Top Friction Sources

| Friction Type | Occurrences |
|---------------|-------------|
| wrong_approach | 60 |
| buggy_code | 38 |
| user_rejected_action | 19 |
| misunderstood_request | 17 |
| excessive_changes | 5 |
| tool_failure | 4 |
| tool_errors | 4 |
| external_tool_failure | 3 |
| api_errors | 3 |
| excessive_exploration | 2 |

**Key insight:** `wrong_approach` is the dominant friction at 60 occurrences,
nearly 2x the next friction source. This maps directly to the retry/churn
anti-pattern — sessions where the agent starts down an incorrect path and
must backtrack.

### Tool Error Concentration

| Metric | Value |
|--------|-------|
| Total tool errors | 975 |
| Sessions with >10 errors | 20 |
| Tokens in high-error sessions | 448,540 (16.8% of total) |

High-error sessions consume a disproportionate share of tokens. The worst
offender had 34 errors in a single session.

---

## 6. Tool Usage Profile

| Tool | Invocations | Share |
|------|-------------|-------|
| Bash | 3,933 | 36.3% |
| Read | 2,536 | 23.4% |
| Edit | 1,375 | 12.7% |
| Grep | 558 | 5.2% |
| TaskUpdate | 383 | 3.5% |
| Task | 327 | 3.0% |
| Write | 295 | 2.7% |
| TaskCreate | 217 | 2.0% |
| Glob | 205 | 1.9% |
| TaskOutput | 161 | 1.5% |
| ExitPlanMode | 152 | 1.4% |
| AskUserQuestion | 140 | 1.3% |
| Agent | 48 | 0.4% |

**Key insight:** Bash (36%) + Read (23%) account for 60% of all tool
invocations, indicating a read-heavy workflow. The Read:Edit ratio of 1.8:1
suggests some read amplification — reading files multiple times before
editing. The relatively low Agent usage (48 invocations) is consistent with
the pre-steward single-lane era.

---

## 7. Temporal Distribution

### Busiest Days

| Date | Sessions | Tokens | Commits | Tok/Commit |
|------|----------|--------|---------|------------|
| 2026-02-07 | 37 | 668,804 | 66 | 10,133 |
| 2026-02-21 | 14 | 204,681 | 12 | 17,057 |
| 2026-03-02 | 17 | 174,230 | 9 | 19,359 |
| 2026-02-05 | 57 | 129,865 | 25 | 5,195 |
| 2026-02-18 | 18 | 107,202 | 20 | 5,360 |
| 2026-02-23 | 11 | 105,298 | 9 | 11,700 |
| 2026-02-17 | 20 | 98,156 | 22 | 4,462 |
| 2026-02-26 | 13 | 91,067 | 9 | 10,119 |

**Key insight:** Token efficiency varies 4x across days (4.5K to 19.4K
tokens/commit). The most token-efficient day (2026-02-17, 4.5K tok/commit)
had 22 commits from 20 sessions, suggesting many small focused sessions.
The least efficient (2026-03-02, 19.4K tok/commit) had only 9 commits from
17 sessions, suggesting larger exploratory or planning-heavy work.

### Session Duration

| Metric | Value |
|--------|-------|
| Minimum | 0.0 min |
| Median | 12.0 min |
| Mean | 101.8 min |
| Maximum | 10,024 min |

The large gap between median (12 min) and mean (102 min) indicates a
heavy right tail — a few very long sessions pull the average up
significantly.

---

## 8. Attribution Status

| Category | Sessions | Tokens |
|----------|----------|--------|
| main-checkout | 287 | 2,574,317 |
| unattributed | 21 | 96,937 |

### Attribution Limitations

Lane-level attribution is limited because:

1. **Pre-steward data:** All 308 sessions predate the multi-lane deployment
   (2026-03-14+). There are no steward worktree sessions in this dataset.
2. **Single project path:** 282 sessions map to the main Bid-Euchre checkout.
   Only 5 sessions map to ad hoc worktrees.
3. **Non-project sessions:** 21 sessions (97K tokens) map to non-project
   paths (`~/Desktop`, `~/`, etc.) and cannot be attributed.

**Implication:** Per-lane efficiency rankings are not possible with this
dataset. A follow-up report after 1-2 weeks of steward operation will
enable lane-vs-lane comparison.

### Project Path Distribution

| Path | Sessions | Tokens | Commits |
|------|----------|--------|---------|
| Bid-Euchre (main checkout) | 282 | 2,491,255 | 232 |
| ~/  (home directory) | 13 | 40,940 | 8 |
| ~/Desktop/Fund | 5 | 34,832 | 0 |
| Ad hoc worktrees | 5 | 93,055 | 4 |
| ~/Desktop | 3 | 21,165 | 0 |

---

## 9. Top 3 Token-Waste Patterns

### Pattern 1: Abandoned-Work Churn (HIGH)

**Evidence:** 129 zero-commit sessions generated 39,579 lines of code
that were never committed, consuming **1,145,336 tokens (42.9%** of total).

**Mechanism:** Sessions start implementation, generate substantial code,
but never reach a commit — either due to wrong approach, scope change,
session timeout, or context exhaustion. The generated code is abandoned.

**Scale:** This is the single largest waste category, larger than all
committed-session tokens combined. Even if half of these sessions provided
legitimate planning/exploration value, the remaining ~570K tokens
represents the largest optimization target.

**Recommended fix:** The steward platform's bounded task packets and
scope-lock discipline should directly address this. Each lane gets a
specific deliverable, reducing the probability of unbounded exploration
that generates code without committing. **Monitor this metric
post-steward to validate the hypothesis.**

### Pattern 2: Wrong-Approach Retry Churn (HIGH)

**Evidence:** 60 `wrong_approach` friction events (the #1 friction source),
plus the CLI anti-pattern detector flagged that **71% of sessions (219/308)
produced zero commits**, consuming 1.27M tokens total.

**Mechanism:** The agent starts down an incorrect implementation path,
generates code, hits a wall, and backtracks. The friction data shows
`wrong_approach` (60) is nearly 2x `buggy_code` (38), meaning the
dominant failure mode is strategic (wrong plan) rather than tactical
(wrong code).

**Recommended fix:**
- **Plan review before implementation.** The existing plan-review skill
  should be enforced more consistently — wrong-approach events suggest
  plans were either absent or insufficiently reviewed.
- **Smaller work units.** The iterative_refinement session type (14.8K
  tokens/session avg) should be broken into smaller single_task sessions
  when possible.
- **Early-exit heuristics.** If a session generates >5K tokens without a
  commit, surface a warning to the operator.

### Pattern 3: High-Error Session Tax (MEDIUM)

**Evidence:** 20 sessions with >10 tool errors consumed **448,540 tokens
(16.8%** of total). The errors/1K-tokens rate is 0.36 overall, but
concentrates in specific sessions.

**Mechanism:** Tool errors (Bash failures, file not found, permission
errors, etc.) trigger retry loops. Each retry consumes additional
context tokens as the agent re-reads state and re-attempts. Sessions
with 20+ errors often enter a failure spiral.

**Recommended fix:**
- **Fail-fast on repeated errors.** After 5 consecutive errors of the
  same type, halt the session and surface a diagnostic.
- **Tool error categorization.** The `tool_error_categories` field
  exists in the telemetry but is not yet analyzed. Categorize errors
  to identify which tool types produce the worst cascading failures.
- **Session length caps.** The max session duration (10,024 min ≈ 7
  days) suggests some sessions are left running indefinitely. Cap
  active session time.

---

## 10. Efficiency Benchmarks

These baseline numbers serve as the comparison target for future
optimization work.

| Metric | Baseline Value | Target Direction |
|--------|---------------|-----------------|
| Shipped token rate | 52.4% | ↑ Higher |
| Tokens/commit (all sessions) | 10,948 | ↓ Lower |
| Tokens/commit (committed only) | 5,739 | ↓ Lower |
| Tokens/net line | 40 | ↓ Lower |
| Output/Input ratio | 3.8x | — Monitor |
| Assistant/User ratio | 11.9x | ↓ Lower |
| Tool errors/1K tokens | 0.36 | ↓ Lower |
| Zero-commit session rate | 71% | ↓ Lower |
| Wrong-approach friction | 60 events | ↓ Lower |

---

## 11. Recommendations for Future Optimization Work

### Immediate (address in current platform iteration)

1. **Post-steward comparison report.** After 1-2 weeks of multi-lane
   operation, re-run this analysis with steward-era data. The
   bounded-task-packet model should reduce abandoned-work churn
   measurably. If it doesn't, the task scoping discipline needs
   revision.

2. **Lane-level attribution.** The current attribution maps all
   sessions to `main-checkout`. Post-steward data will enable per-lane
   efficiency rankings. Priority: ensure the attribution logic correctly
   resolves steward worktree paths to lane IDs.

### Near-term (next 2-4 weeks)

3. **Session length monitoring.** Add a dashboard indicator for
   sessions exceeding 20K tokens without a commit. This is a
   leading indicator of the abandoned-work pattern.

4. **Tool error analysis.** Parse `tool_error_categories` and build a
   top-10 error-type report. Prioritize fixes for the categories that
   produce the longest retry chains.

5. **Plan review enforcement.** Track whether sessions that follow
   the plan-review-before-implementation pattern have better
   token efficiency than sessions that skip it.

### Deferred (requires baseline comparison data)

6. **Prompt compression.** Optimize system prompts and context loading
   to reduce input tokens. Current output/input ratio (3.8x) suggests
   output verbosity may be more impactful than input reduction.

7. **Work-type budgets.** Once per-lane data exists, set soft token
   budgets per work type (planning, review, implementation, monitoring).

8. **Context clearing policy.** Measure whether fresh sessions with
   explicit context recovery outperform long-running stale sessions.

---

## 12. Methodology Notes

### Data Source

- Native Claude usage telemetry from `~/.claude/usage-data/session-meta/`
  and `~/.claude/usage-data/facets/`
- Imported via `scripts/internal/ops.py usage import`
- 308 sessions imported; 8 source files skipped due to malformed JSON

### Limitations

1. **Pre-steward only.** Data ends at 2026-03-14, before multi-lane
   deployment. Lane-level comparison is not possible.
2. **Facet data incomplete.** 161 sessions (52%) lack session_type and
   outcome classifications (older telemetry format).
3. **Attribution is coarse.** Only project_path is available for lane
   inference; no direct session-to-task-packet join exists in this
   dataset.
4. **Duration outliers.** Some sessions show extreme durations (>7
   days), likely representing backgrounded or idle sessions rather
   than active work.
5. **No cost data.** Token counts are available but not dollar costs.
   Cost analysis requires model pricing information not captured in
   the telemetry.

### Reproduction

```bash
# Import and attribute
uv run python scripts/internal/ops.py usage import
uv run python scripts/internal/ops.py usage attribute

# Generate summaries
uv run python scripts/internal/ops.py usage summary
uv run python scripts/internal/ops.py usage lanes
uv run python scripts/internal/ops.py usage throughput
uv run python scripts/internal/ops.py usage anti-patterns
```

## Outcome

This report establishes the pre-steward token economy baseline. The key
metrics (52.4% shipped-token rate, 10.9K tokens/commit, 71% zero-commit
session rate) provide the comparison targets for measuring the impact of
the multi-lane steward platform on token efficiency.
