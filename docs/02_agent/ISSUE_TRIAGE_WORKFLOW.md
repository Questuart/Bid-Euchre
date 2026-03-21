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
- **Role boundary:** The `issues` agent profile (`.claude/agents/issues.md`)
  is strictly triage-only. It never implements fixes. When an issue becomes
  `agent-ready`, it must be handed off to an author lane for implementation.

### Escalation

If an agent believes an issue is `agent-ready` but it lacks the label:
1. Add a comment explaining why it appears ready
2. Do not add the label unilaterally
3. Continue with other work

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
`.claude/agents/issues.md` profile, not by code. If a programmatic
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

## Repair Eligibility Contract

### Purpose

Post-merge review and the review loop create follow-up issues for shipped
mistakes. This section defines when those issues (and any other triage issues)
are eligible for **autonomous repair** — bounded follow-up PRs that fix the
identified problem.

Repair eligibility builds on the [Execution Gate](#execution-gate) above. It
does not create a separate authority path. An issue must pass the execution
gate **and** the additional repair-specific criteria below.

### Eligibility Criteria

An issue is eligible for autonomous repair when **all** of the following are
true:

| # | Criterion | Rationale |
|---|-----------|-----------|
| R1 | Issue is **open** | Closed issues are not actionable |
| R2 | Issue has the **`agent-ready`** label | Human or reviewer has confirmed the fix is bounded and safe |
| R3 | Issue is **assigned** to a specific lane (GitHub assignee or `claimed: <lane>` comment) | Prevents multiple lanes from racing on the same fix |
| R4 | Issue does **not** have the **`needs-human`** label | Human decision is required before work can begin |
| R5 | **No open repair PR** already exists for this issue | One active repair PR per issue at a time |
| R6 | Issue has **sufficient repro context** (error message, failing test, or reproduction command) | Bounded execution requires bounded input |
| R7 | Issue scope fits within a **single follow-up PR** (≤5 files, no architectural changes) | Repairs must be small and focused |

### What Is NOT Repair-Eligible

| Situation | Action Instead |
|-----------|---------------|
| Issue lacks `agent-ready` | Leave in backlog; add a comment if you believe it's ready |
| Issue has `needs-human` | Wait for human decision |
| Repair PR is already open | Wait for it to resolve or be closed |
| Fix requires >5 files or architectural change | Escalate to a governed plan step or session plan |
| Fix touches protected review/bridge files | Escalate to ops or the human operator |
| Repro context is unclear or missing | Add a comment requesting more context; do not attempt |

### Claiming an Issue

To claim an issue for repair:

1. Verify all eligibility criteria (R1–R7) are met
2. Assign yourself (or your lane) via GitHub assignee or a comment:
   `claimed: author-a`
3. Begin the [Repair Execution Path](#repair-execution-path) below

If the issue is already claimed by another lane, do not override the claim.
Wait for the existing claim to resolve.

---

## Repair Execution Path

### The Flow

An agent executing a repair follows this sequence:

| Step | Action | Validation |
|------|--------|------------|
| 1 | **Claim** the issue (see above) | R1–R7 all pass |
| 2 | **Branch** from fresh `origin/main` | `git fetch origin main && git checkout -b fix/<issue>-<slug> origin/main` |
| 3 | **Reproduce** the problem locally | Run the repro command from the issue; confirm the failure |
| 4 | **Patch** the identified code | Minimal fix targeting the root cause |
| 5 | **Validate** with targeted tests + full suite | `uv run pytest tests/unit/test_<module>.py` then `make check-quiet` |
| 6 | **Open follow-up PR** linked to the issue and source PR | Use the PR template; include `Fixes #<issue>` in the body |
| 7 | **Update issue** with a comment noting the repair PR | Link the PR and summarize the fix |

### Branch Naming

Repair branches follow the pattern:

```
fix/<issue_number>-<short_slug>
```

Examples:
- `fix/1045-unseeded-random`
- `fix/1052-missing-assertion`

### PR Requirements

Repair PRs must:

- Use the standard PR template (`.github/pull_request_template.md`)
- Include `Fixes #<issue_number>` in the body (auto-closes the issue on merge)
- Reference the source PR that introduced the problem (if known)
- Include the exact reproduction command and validation output
- Pass `make check-quiet` before opening

### What Happens After

- The repair PR enters the normal review loop (`reviewing-changes`)
- If the review loop finds additional issues, those become separate follow-up
  issues — not scope expansions of the current repair
- On merge, the linked issue is auto-closed via `Fixes #<N>`

---

## Stop Rules and Escalation

### Hard Stop Rules

These rules are non-negotiable. Violation means the repair attempt must stop
immediately.

| Rule | Rationale |
|------|-----------|
| **No direct `main` mutation** | All repairs land via follow-up PRs |
| **One active repair PR per issue** | Prevents racing and conflicting fixes |
| **Maximum 2 repair attempts per issue** | Prevents infinite retry loops |
| **No scope expansion** | Repair fixes the identified issue only; new findings become new issues |

### Escalation Triggers

A repair agent must **stop and escalate** (not retry) when any of the
following occur:

| Trigger | Action |
|---------|--------|
| **Reproduction fails** — the issue cannot be confirmed locally | Add a comment: "Could not reproduce — needs investigation". Remove the lane claim. |
| **Scope drift** — the fix requires changes beyond the issue's identified subsystem | Stop. File a new issue or session plan for the broader fix. |
| **Protected files** — the fix would modify review infrastructure, bridge files, or CI workflows | Stop. Escalate to the operator or ops lane. |
| **Validation failure on second attempt** — `make check-quiet` fails after the second patch attempt | Stop. Add a comment: "Repair blocked after 2 attempts — needs human review". Add `needs-human` label. |
| **Conflict with existing work** — the repair would conflict with an open PR on the same files | Stop. Wait for the conflicting PR to merge, then retry from fresh `main`. |

### Retry Policy

| Attempt | What happens |
|---------|-------------|
| 1st | Normal repair flow. If validation fails, diagnose and try a different approach. |
| 2nd | Second attempt with a different fix strategy. If this also fails, escalate. |
| 3rd+ | **Not permitted.** Add `needs-human` and stop. |

### Escalation Destinations

| Situation | Escalate to |
|-----------|-------------|
| Reproduction unclear | Issue comment + remove claim |
| Scope too broad | New session plan or governed plan step |
| Protected files involved | Operator (ops lane or human) |
| Repeated failure | `needs-human` label on the issue |
| Conflict with open work | Wait and retry after conflicting PR merges |

---

## Relationship to Existing Systems

| System | Creates Issues? | This Workflow Applies? |
|--------|----------------|----------------------|
| Review loop (`review_driver.py`) | Yes (P2 findings) | No — uses its own `fix(<label>)` prefix |
| Infra-incident workflow | Yes (infra failures) | No — uses its own `[infra]` prefix |
| Post-merge review | No (creates PRs) | No |
| Steward periodic review | Yes (manual) | No — manual, free-form |
| **Agent triage (this doc)** | Yes | **Yes** |
| **Agent repair (this doc)** | No (creates PRs from issues) | **Yes** (eligibility + execution) |

The agent triage workflow is additive. It does not replace, modify, or
interfere with any existing issue-creation system. The repair lane consumes
issues created by any of the systems above — it does not create new issues.

---

## Disable / Rollback Path

This workflow is purely prescriptive (documentation + agent profile). It has
no code enforcement and no hooks. To disable or roll back:

| Action | How | Impact |
|--------|-----|--------|
| Disable triage guidance | Delete `.claude/agents/issues.md` | Agents lose triage guidance; no other workflow affected |
| Tighten qualification rules | Edit this doc's thresholds | Single-file change, no downstream breakage |
| Remove workflow entirely | Delete this doc + `.claude/agents/issues.md` | Returns to pre-slice-2 state |
| Remove new labels | Delete `triage`, `agent-ready`, `needs-human` from GitHub | No effect on existing issues using other labels |

---

## References

- `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` — PR-5 governing plan
- `plans/sessions/2026-03-20_post-merge-repair-lane.md` — repair lane session plan
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — canonical operator workflow (includes repair UX)
- `scripts/internal/review_driver.py` — existing review-loop issue creation
- `scripts/internal/ops.py` — operator CLI (`repairs` subcommand for queue visibility)
- `.github/workflows/infra_incident_dedupe.yml` — existing infra-incident dedupe
- `.claude/rules/deferred/60_review_gate.md` — follow-up issue labels and severity
- `.claude/agents/issues.md` — agent profile for triage work
