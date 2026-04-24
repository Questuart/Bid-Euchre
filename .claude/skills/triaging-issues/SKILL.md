---
name: triaging-issues
description: Triages GitHub issues and review findings into labeled, prioritized follow-up work. Use when creating follow-up issues from review findings or organizing outstanding work.
---

# Issue Triage & Follow-Up Guide

Structure review findings and bugs into labeled, prioritized GitHub issues.

## Label Taxonomy

| Label | Color | Applied to |
|-------|-------|------------|
| `follow-up` | `#fbca04` | All follow-up issues and corrective PRs |
| `fix:bug` | `#d73a4a` | C1 (unseeded randomness), C2 (falsy numeric guard) |
| `fix:convention` | `#0075ca` | Auto-fix patterns, C4 (function complexity) |
| `fix:test` | `#e4e669` | T1 (untested behavior change) |
| `fix:docs` | `#0e8a16` | X2 (undocumented contract change) |
| `fix:process` | `#c5def5` | X1 (scope drift), X3 (merge artifacts), N1/N2/N3 |

## Priority Mapping

| Severity | Action | Timeline |
|----------|--------|----------|
| **BLOCK** (C1, C2, N1, N2, X3) | Immediate fix PR on current branch | Before merge |
| **WARN** (C3, C4, N3, T1, X1, X2) | Follow-up issue created | Next session |
| **INFO** | Noted in review report only | No action needed |

## Workflow

### 1. Check for Duplicates First

```bash
gh issue list --label follow-up --state open
```

Search for existing issues covering the same finding before creating a new one.

### 2. Create Follow-Up Issues

```bash
gh issue create --title "fix: <description>" \
  --label "follow-up,fix:<type>" \
  --body "Originating PR: #NNN
Finding: <check ID and description>
Files: <affected files>"
```

### 3. Batch Related Fixes

Group related findings into batch PRs:
- Convention: `fix: convention follow-up batch N`
- Typical batch: 3-8 related findings per PR
- Don't create one PR per finding — that's pure churn

## Programmatic Invocation (scaffold)

> Primitive E Phase 0 Packet E1 — **scaffold only**, no runtime. The active-triage
> runtime that consumes this surface is blocked on Primitive A Packet 3
> (event schema + dispatcher). Scaffold landed so downstream work can wire
> to a stable contract without re-shaping.

In addition to the operator-invocable `/triaging-issues` surface, the skill
exposes a programmatic entry point for event-driven callers (Primitive E
`active_triage`, per `plans/steward_platform/5_primitive_E/shaping.md` §5).
Both paths share the same underlying logic in
`scripts/internal/triage_cli.py`.

### Input contract — `TriageInput`

```python
@dataclass(frozen=True)
class TriageInput:
    signal_class: Literal[
        "ci_red",
        "review_blocked",
        "stalled_lane",
        "orphan_worktree",
        "token_burn",
    ]
    title_hint: str                  # pre-formatted issue title template
    body_sections: dict[str, str]    # section name → content
    labels: list[str]                # required labels; `follow-up` auto-added
    priority: Literal["low", "normal", "high", "urgent"]
    incident_fingerprint: str        # dedupe key (see Dedupe section)
    source_event_id: str             # event-bus record ID for traceability
```

### Call shape (scaffold)

```python
from scripts.internal.triage_cli import TriageInput, file_or_recur

result = file_or_recur(TriageInput(
    signal_class="ci_red",
    title_hint="fix: CI red on main after PR #NNNN",
    body_sections={
        "Context": "...",
        "Evidence": "...",
        "Reproduction": "uv run python scripts/... --seed 42",
    },
    labels=["fix:test"],
    priority="high",
    incident_fingerprint="<deterministic SHA256 of (signal_class, pr_number, test_id)>",
    source_event_id="<event record ID from Primitive A dispatcher>",
))
```

### Dedupe contract

`file_or_recur` is idempotent on `incident_fingerprint`:

- **No matching open follow-up:** file a new issue; embed fingerprint as a
  hidden HTML comment `<!-- fingerprint: <fp> -->` in the issue body.
- **Matching open follow-up within 24h coalescing window:** append an
  evidence comment to the existing issue (format in shaping doc §5.3). Do
  not open a duplicate.
- **Matching closed or >24h-old follow-up:** treat as "no match"; open a
  new issue (prevents a stale fingerprint absorbing unrelated recurrences).

### Scaffold runtime status

`scripts/internal/triage_cli.py` ships in Packet E1 with:

- The `TriageInput` dataclass and `SIGNAL_CLASSES` / `PRIORITIES` vocabularies.
- `file_or_recur(...)` signature that raises `NotImplementedError` with a
  pointer to Primitive A Packet 3 as the unblocker.
- Unit tests that pin the dataclass shape and the scaffold signature.

The live GitHub-interacting path (dedupe queries, issue-creation, evidence
comments) lands in a follow-up packet after Primitive A merges and the event
bus surface is observable.

## Gotchas

- Always check for existing issues before creating duplicates — `gh issue list --label follow-up`
- Link follow-up issues to the originating PR in the issue body
- Batch related fixes — don't create one PR per finding
- `fix:bug` label items (C1, C2) should be prioritized over `fix:convention`
- The review loop (`review_driver.py`) auto-creates issues for P2 findings — check those first
- Use the `follow-up` label on ALL follow-up issues, plus the specific `fix:*` sub-label

## References

- `.claude/rules/deferred/60_review_gate.md` — Severity definitions and label assignments
- `.claude/rules/deferred/55_issue_closure.md` — Tiered closure policy (`Fixes` vs `Refs`)
- `/proving-issues` — Verified-close workflow for Tier 2 issues
