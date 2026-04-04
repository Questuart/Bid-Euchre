# Issue Triage Workflow

This document defines how autonomous agents create, deduplicate, and manage
GitHub issues for qualified operational findings. It is part of the PR-5
rollout of the autonomous operator workflow.

**Governing plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`

---

## Core Principle

**Issue existence does not imply autonomous coding authority.**

Issues created through this workflow capture knowledge and track backlog.
They do not authorize implementation work unless explicitly gated (see
[Execution Gate](#execution-gate) below).

---

## Qualification Thresholds

A finding qualifies for a GitHub issue when **any** of the following are true:

| Condition | Rationale |
|-----------|-----------|
| Observed >=2 times in separate sessions or PRs | Pattern, not noise |
| Correctness or contract violation (any count) | Severity overrides frequency |
| Explicitly flagged `agent-ready` by a reviewer | Human-endorsed priority |

A finding does **not** qualify when:

| Condition | Action Instead |
|-----------|---------------|
| One-time transient failure (retry succeeded) | Log and move on |
| Already tracked in an open issue | Append comment to existing issue |
| Style preference without a documented convention | Ignore or propose convention first |
| Speculative improvement without evidence | Discuss in session, do not file |

---

## Dedupe Key Contract

### Title Prefix Scheme for Agent-Created Triage Issues

All agent-created triage issues use a structured title prefix:

```
[<category>] <subsystem>: <short_description>
```

**Category values:**

| Category | When to use |
|----------|-------------|
| `triage` | General operational findings from agent sessions |
| `infra` | Infrastructure failures (aligns with infra-incident workflow) |
| `fix` | Code-level findings from reviews or validation |
| `convention` | Convention or style findings that have a documented rule |

**Examples:**

```
[triage] ops/events: stale event file not drained after 72h
[fix] strategy/heuristic: unseeded random in play_card fallback
[convention] tests: missing assertion for new behavior in test_watchdogs
```

### Dedupe Procedure

Before creating any issue, an agent **must**:

1. Search open issues with matching `category` and `subsystem` in the title
2. If a matching open issue exists: **append a timestamped comment** with
   the new occurrence details instead of creating a duplicate
3. If no match exists: create a new issue using the title prefix scheme

### Existing Issue-Creation Systems (Unchanged)

This prefix scheme applies **only** to new agent-created triage issues.
Existing systems keep their own title formats:

| Creator | Title Format | Modified? |
|---------|-------------|-----------|
| `review_driver.py` | `fix(<label>): follow-up for PR #N` | No |
| `infra_incident_dedupe.yml` | `[infra] <subsystem> <failure_key>` | No |
| Manual (steward review) | Free-form | No |
| **Agent triage (this workflow)** | `[<category>] <subsystem>: <desc>` | N/A (new) |

When the `[infra]` category is used for agent-created triage issues, the
agent should first check whether the existing `infra_incident_dedupe.yml`
workflow is more appropriate. Prefer the GitHub Actions workflow for
CI/infrastructure failures that have a clear subsystem and failure key.

---

## Label Taxonomy

### New Labels

| Label | Color | Purpose |
|-------|-------|---------|
| `triage` | `#D4C5F9` | Agent-created triage issues from this workflow |
| `agent-ready` | `#0E8A16` | Issue is pre-analyzed and safe for autonomous implementation |
| `needs-human` | `#B60205` | Issue requires human decision before work begins |

### Existing Labels (Reused As-Is)

| Label | Applied When |
|-------|-------------|
| `follow-up` | Review-loop follow-up issues (from `review_driver.py`) |
| `fix:bug` | Correctness findings (C1, C2) |
| `fix:convention` | Convention/auto-fix findings |
| `fix:test` | Untested behavior changes (T1) |
| `fix:docs` | Undocumented contract changes (X2) |
| `fix:process` | Process/workflow findings (X1, X3, N1/N2/N3) |
| `infra-incident` | Infrastructure failures |
| `steward-review` | Periodic steward review findings |

### Label Selection Rules

Every agent-created triage issue must have:
1. The `triage` label (identifies the creation source)
2. Exactly one `fix:*` label matching the finding category
3. Optionally `agent-ready` or `needs-human` for execution gating

Do not add `follow-up` to triage issues — that label is reserved for
`review_driver.py` outputs.

---

## Execution Gate

### The Rule

An agent may only begin autonomous implementation work on a triage issue
when **all** of the following are true:

1. The issue has the `agent-ready` label
2. The issue is assigned to a specific lane (via GitHub assignee or a
   comment like `assigned: author-a`)
3. The agent's current task contract includes the issue's scope
4. The work fits within the agent's lane charter (see
   `AUTONOMOUS_OPERATOR_WORKFLOW.md` Lane Capability Matrix)

### What This Means

- Issues **without** `agent-ready` are backlog only. They document findings
  but do not authorize any code changes.
- The `agent-ready` label is added by:
  - A human reviewer who has verified the issue is well-defined
  - An agent reviewer who has confirmed the fix is bounded and safe
  - The `needs-human` label, if present, explicitly blocks `agent-ready`
- An agent that discovers a qualified finding should **create the issue**
  and **stop**. It should not also start fixing it in the same session
  unless the finding is already `agent-ready` and assigned.
- **Role boundary:** The `steward-analyst` profile
  (`.claude/agents/steward-analyst.md`) may investigate and package issues,
  but it never implements fixes. When an issue becomes `agent-ready`, it must
  be handed off to an author or repair lane for implementation.

### Escalation

If an agent believes an issue is `agent-ready` but it lacks the label:
1. Add a comment explaining why it appears ready
2. Do not add the label unilaterally
3. Continue with other work

---

## Repair Execution

### Overview

When a post-merge review or follow-up issue identifies a shipped mistake,
the **repair lane** provides a bounded, issue-driven path for autonomous
agents to fix it through a follow-up PR. Repair execution builds on the
[Execution Gate](#execution-gate) above — it does not bypass or replace it.

### Repair Eligibility Contract

An issue is eligible for autonomous repair when **all** of the following
are true:

| # | Condition | Rationale |
|---|-----------|-----------|
| 1 | Issue is **open** | Closed issues are not actionable |
| 2 | Issue has the `agent-ready` label | Explicit readiness signal |
| 3 | Issue does **not** have `needs-human` | Human decision pending blocks autonomy |
| 4 | Issue is **assigned** to a lane or person | Prevents racing / duplicate work |
| 5 | No **open repair PR** already targets this issue | One active repair PR per issue |
| 6 | Issue has enough **repro context** (evidence, commands, file paths) | Bounded execution requires bounded scope |

The helper `src/bid_euchre/ops/repairs.py` implements conditions 1–5
programmatically. Condition 6 is a judgment call made by the claiming
agent before starting work.

### Repair Execution Path

Once an issue passes the eligibility contract:

| Step | Action | Detail |
|------|--------|--------|
| 1 | **Claim** | Assign yourself to the issue (or confirm existing assignment) |
| 2 | **Branch** | Create a branch from fresh `origin/main` in your worktree |
| 3 | **Reproduce** | Confirm the problem locally using the issue's repro context |
| 4 | **Patch** | Implement the minimal bounded fix |
| 5 | **Validate** | Run targeted tests (Tier 1), then `make check-quiet` (Tier 2) |
| 6 | **PR** | Open a follow-up PR with `fix(repair):` title prefix, linking the issue and source PR |
| 7 | **Update issue** | Add a comment with the PR link; do not close the issue (the PR merge closes it) |

**PR conventions for repair PRs:**

- Title prefix: `fix(repair): <short description>`
- Label: `follow-up`
- Body must reference: the issue number (`Refs #N` by default; use `Fixes #N`
  only for Tier 1 single-bounded fixes — see [Tiered Issue Closure](#tiered-issue-closure)) and the source PR
- Scope must stay within the issue's identified subsystem

### Lane Ownership

| Priority | Owner | When |
|----------|-------|------|
| 1st | **Same author lane** that shipped the original PR | Traceable, context-rich |
| 2nd | **Any available author lane** | Original lane busy or unavailable |
| — | **Analyst service lane** | Never — analyst shapes/files issues, does not fix them |

### Stop Rules

Repair execution is explicitly bounded. An agent **must stop** and
escalate when any of the following occur:

| Condition | Action |
|-----------|--------|
| Cannot reproduce the issue locally | Add comment, remove assignment, add `needs-human` |
| Scope drifts beyond the issue's subsystem | Stop, split into a new issue, escalate |
| Protected files involved (review driver, bridge controls, hooks) | Escalate — these require human review |
| Repair PR fails CI or review twice | Add comment, add `needs-human`, stop |
| Already 2 failed repair attempts on this issue | Escalate to human with full context |

**Hard rules:**

- **No direct pushes to `main`.** All repairs go through follow-up PRs.
- **One active repair PR per issue.** Do not open a second PR while one
  is still open.
- **Maximum 2 repair attempts** per issue before mandatory human
  escalation.

### Escalation Path

When repair is blocked or fails:

1. Add a comment to the issue explaining what was tried and what failed
2. Add the `needs-human` label
3. Remove assignment (or reassign to human)
4. Do **not** silently abandon the issue — the comment trail is the
   audit record

### Relationship to Triage

| Role | Creates issues? | Fixes issues? | Profile |
|------|----------------|---------------|---------|
| **Analyst service lane** | Yes | No | `.claude/agents/steward-analyst.md` |
| **Repair agent** | No (may file sub-issues) | Yes | `.claude/agents/repair.md` |

Analyst and repair are separate roles even when the same steward
coordinates both. The analyst shapes and files; the repair agent fixes.

### Operator Visibility

View the repair queue:

```bash
uv run python scripts/internal/ops.py repairs [--json]
```

This shows all `agent-ready` issues, their eligibility status, and any
active repair PRs. See `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
for the full operator repair UX.

---

## Tiered Issue Closure

Issue closure must match the complexity of the fix. Premature closure
(auto-close on merge without verification) has caused repeated context loss
where problems resurface after the tracking issue is already closed.

### Tier 1 — Auto-Close (Simple Fixes)

Use `Fixes #N` in the PR body when **all** of the following are true:

| Condition | Rationale |
|-----------|-----------|
| The fix is a single bounded change (typo, config tweak, one-liner) | Low risk of incomplete resolution |
| The issue has no acceptance criteria beyond "PR merged" | Nothing extra to verify |
| The fix is fully testable by CI (unit/integration tests lock the behavior) | Automated verification sufficient |

When `Fixes #N` is used, GitHub auto-closes the issue on merge. No further
verification step is needed.

### Tier 2 — Verified-Close (Complex Fixes)

Use `Refs #N` in the PR body (NOT `Fixes`) when **any** of the following
are true:

| Condition | Rationale |
|-----------|-----------|
| The issue has explicit acceptance criteria beyond code change | Needs proving in production/fleet |
| The fix addresses a symptom but root cause is uncertain | May resurface |
| The issue spans multiple PRs (incremental resolution) | Partial fix should not close the tracker |
| The fix requires fleet/production verification | CI alone is insufficient |
| The issue was previously closed and reopened | Pattern of premature closure |

**Verified-close workflow:**

1. PR uses `Refs #N` — issue stays open after merge
2. Add the `needs-verification` label to the issue (label already exists)
3. After merge, verify the fix in production/fleet conditions
4. Post verification evidence as an issue comment (proving command + output)
5. Close the issue manually with the evidence comment

### Choosing Between Tiers

When in doubt, default to **Tier 2** (`Refs #N`). The cost of leaving an
issue open for verification is minimal. The cost of premature closure
(lost context, re-investigation) is significant.

### Agent Guidance

- Agents should default to `Refs #N` unless the fix is clearly Tier 1
- When an agent uses `Fixes #N`, the PR description must state why
  auto-close is appropriate (e.g., "Single config fix, locked by unit test")
- Agents must never manually close issues without posting verification
  evidence first

---

## Anti-Spam Rules

| Rule | Threshold | Rationale |
|------|-----------|-----------|
| Max new issues per session | 5 | Prevents runaway issue creation |
| Cooldown between creates | 60 seconds | Rate-limits bursts |
| Must search before create | Always | Dedupe is mandatory, not optional |
| Must update-existing-first | Always | Append comment to matching open issue |
| Transient failures | Never create issue | Retry first; only persistent patterns qualify |
| Already-closed issues | Do not reopen | Create new issue referencing the closed one |

### Budget Enforcement

These thresholds are conventions enforced by agent discipline and the
`.claude/agents/steward-analyst.md` profile, not by code. If a programmatic
issue-creation helper is added in the future (e.g., under `src/bid_euchre/ops/`),
it should enforce these limits at the API level.

### What Happens at the Limit

When an agent hits the session budget (5 issues):
1. Stop creating issues for the remainder of the session
2. Log remaining qualified findings in session notes or `checkpoints.md`
3. Note the overflow in the session handoff so the next session can resume

---

## Project Routing (Optional)

If GitHub Projects are adopted for backlog management:

- Agent-created triage issues should be added to a `Triage` project column
- `agent-ready` issues move to a `Ready` column
- Assigned issues move to an `In Progress` column
- Completed issues move to `Done` on PR merge

This routing is optional. The workflow functions without GitHub Projects —
labels and assignees provide sufficient gating on their own.

---

## Issue Body Template

Agent-created triage issues should use a consistent body format:

```markdown
## Finding

<1-2 sentence description of the finding>

## Evidence

| Field | Value |
|-------|-------|
| **Category** | `<fix:bug / fix:convention / fix:test / fix:docs / fix:process>` |
| **Subsystem** | `<module or file path>` |
| **First observed** | <PR number or session date> |
| **Occurrences** | <count> |
| **Severity** | <BLOCK / WARN / INFO> |

## Context

<Additional context: related PRs, error messages, reproduction steps>

## Suggested Fix

<Brief description of expected fix, if known. "Needs investigation" if not.>

## Constraints

- [ ] Bounded to the identified subsystem
- [ ] Does not require architectural changes
- [ ] Has a clear test to lock the fix
```

---

## Relationship to Existing Systems

| System | Creates Issues? | This Workflow Applies? |
|--------|----------------|----------------------|
| Review loop (`review_driver.py`) | Yes (P2 findings) | No — uses its own `fix(<label>)` prefix |
| Infra-incident workflow | Yes (infra failures) | No — uses its own `[infra]` prefix |
| Post-merge review | No (creates PRs) | No |
| Steward periodic review | Yes (manual) | No — manual, free-form |
| **Agent triage (this doc)** | Yes | **Yes** |

The agent triage workflow is additive. It does not replace, modify, or
interfere with any existing issue-creation system.

---

## Disable / Rollback Path

This workflow is purely prescriptive (documentation + agent profile). It has
no code enforcement and no hooks. To disable or roll back:

| Action | How | Impact |
|--------|-----|--------|
| Disable triage guidance | Delete `.claude/agents/steward-analyst.md` | Agents lose analyst guidance; no other workflow affected |
| Tighten qualification rules | Edit this doc's thresholds | Single-file change, no downstream breakage |
| Remove workflow entirely | Delete this doc + `.claude/agents/steward-analyst.md` | Returns to pre-slice-2 state |
| Remove new labels | Delete `triage`, `agent-ready`, `needs-human` from GitHub | No effect on existing issues using other labels |

---

## References

- `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` — PR-5 governing plan
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — canonical operator workflow
- `scripts/internal/review_driver.py` — existing review-loop issue creation
- `.github/workflows/infra_incident_dedupe.yml` — existing infra-incident dedupe
- `.claude/rules/deferred/60_review_gate.md` — follow-up issue labels and severity
- `.claude/agents/steward-analyst.md` — agent profile for planning and issue packaging
- `.claude/agents/repair.md` — agent profile for repair execution
- `src/bid_euchre/ops/repairs.py` — repair eligibility helper and queue visibility
