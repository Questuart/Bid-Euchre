# PR-5 Slice 2: Issue-Triage Workflow

**Date:** 2026-03-19
**Parent plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` (PR-5)
**Slice 1:** #961 (CI event producers, scope management, retry emission)
**Cleanup:** #966 (PR-5 scope labeling, escalation test coverage)

## Goal

Document the issue-triage workflow so that qualified operational findings can
be captured as deduplicated GitHub issues without flooding the backlog or
implying autonomous coding authority.

## Scope

### In scope

1. **`docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`** — new canonical doc defining:
   - Qualification thresholds (when a finding deserves an issue)
   - Dedupe key contract (title prefix + label matching)
   - Label taxonomy for triage issues (extends existing `follow-up`, `fix:*`,
     `infra-incident`, `steward-review` labels)
   - `agent-ready` gating — issue existence does not imply autonomous coding
   - Anti-spam rules (issue budget, cooldown, update-existing-first)
   - Project routing conventions (if GitHub Projects are adopted)
   - Disable/rollback path

2. **`docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`** — update Future Work
   section to:
   - Add "Issue Triage" subsection under Rollout and Safety
   - Reference the new workflow doc
   - Remove issue-triage from the implicit "not yet implemented" bucket

3. **`.claude/agents/issues.md`** — optional agent profile providing bounded
   triage guidance for any agent performing issue-triage work. This is a
   lightweight prompt, not a persistent autonomous fixer.

### Out of scope

- Implementing a programmatic issue-creation helper in `src/bid_euchre/ops/`
  (follow-on, not this slice)
- Persistent `issues` lane or always-on issue fixer
- GitHub Projects board setup (documented as optional convention)
- Context-safety workflow (separate PR-5 slice)
- Skill-promotion workflow (separate PR-5 slice)
- Shadow snapshot/rollback workflow (separate PR-5 slice)

## Existing Infrastructure

The repo already has several issue-creation patterns to align with:

| System | Pattern | Dedupe | Labels |
|--------|---------|--------|--------|
| Review loop (`review_driver.py`) | Creates follow-up issues for P2 findings | Title prefix `fix(<label>): follow-up for PR #N` | `follow-up`, `fix:bug`, `fix:convention`, `fix:test`, `fix:docs`, `fix:process` |
| Infra-incident dedupe workflow (`.github/workflows/infra_incident_dedupe.yml`) | Creates or appends to infra-incident issues | Title prefix `[infra] <subsystem> <failure_key>` | `infra-incident`, `repeat-failure` |
| Steward review | Manual issue creation from periodic reviews | Manual | `steward-review` |
| Post-merge review | Background review agent creates fix PRs for critical findings | N/A (creates PRs, not issues) | N/A |

The issue-triage workflow doc must be consistent with these existing patterns
and must not create a competing dedupe scheme.

## Design Decisions

### Qualification Threshold

A finding qualifies for an issue when:
- It has been observed ≥2 times in separate sessions or PRs, OR
- It is a correctness/contract violation regardless of occurrence count, OR
- It is explicitly flagged by a reviewer as `agent-ready`

A finding does NOT qualify when:
- It is a one-time transient failure (retry succeeded)
- It is already tracked in an open issue (update-existing instead)
- It is a style preference without a documented convention

### Dedupe Key Contract

All agent-created issues use a structured title prefix for dedupe:

```
[<category>] <subsystem>: <failure_key>
```

Where `<category>` is one of: `triage`, `infra`, `fix`, `convention`.

Before creating an issue, the agent must search open issues with the same
category and subsystem. If found, append a comment instead of creating a
duplicate.

**Scope of this prefix scheme:** The `[<category>]` bracket prefix applies
only to new agent-created triage issues. Existing issue-creation systems
keep their own schemes and are not modified:

| Creator | Title Format | Unchanged? |
|---------|-------------|------------|
| `review_driver.py` | `fix(<label>): follow-up for PR #N` | Yes |
| `infra_incident_dedupe.yml` | `[infra] <subsystem> <failure_key>` | Yes |
| Manual (steward review) | Free-form | Yes |
| **New: agent triage** | `[<category>] <subsystem>: <failure_key>` | N/A (new) |

### Label Taxonomy

New labels for triage (extend existing set):

| Label | Color | Purpose |
|-------|-------|---------|
| `triage` | `#D4C5F9` | Agent-created triage issues |
| `agent-ready` | `#0E8A16` | Issue is pre-analyzed and ready for autonomous work |
| `needs-human` | `#B60205` | Issue requires human decision before work begins |

Existing labels reused as-is:
- `follow-up` — review-loop follow-up issues
- `fix:bug`, `fix:convention`, `fix:test`, `fix:docs`, `fix:process` — finding categories
- `infra-incident` — infrastructure failures
- `steward-review` — periodic steward review findings

### Execution Gate

**Issue existence does NOT imply autonomous coding authority.**

An agent may only begin implementation work on a triage issue when:
1. The issue has the `agent-ready` label, AND
2. The issue is assigned to a specific lane (via assignee or comment), AND
3. The agent's current task contract includes the issue's scope

Issues without `agent-ready` are backlog only — they capture knowledge but
do not authorize work.

### Anti-Spam Rules

| Rule | Threshold |
|------|-----------|
| Max new issues per session | 5 |
| Cooldown between issue creates | 60 seconds |
| Must search before create | Always (dedupe check) |
| Must update-existing-first | Always (append comment to matching open issue) |
| Transient failures | Never create issue (retry first) |

## Deliverables

| # | File | Action |
|---|------|--------|
| 1 | `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md` | Create |
| 2 | `.claude/agents/issues.md` | Create |
| 3 | `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | Update (Future Work → add issue triage reference) |

## Validation Plan

### Automated
- `make check-quiet` (full pre-PR gate)

### Manual Pre-PR Checks (not in `make check`)
- Grep consistency check: all labels mentioned in the workflow doc exist in
  the label taxonomy table
- Grep consistency check: dedupe key format matches existing patterns
- These are manual pre-PR steps, not automated gates. They verify doc
  internal consistency only.

### Manual Smoke
- **Happy path:** A qualified repeated finding (e.g., "untested behavior change
  in ops/events.py observed in PRs #961 and #966") maps to a single
  deduplicated issue with `triage` + `fix:test` labels
- **Unhappy path:** A one-time transient lint failure does NOT qualify for
  issue creation (qualification threshold rejects it)
- **Disable path:** Removing the `issues.md` agent profile disables the
  triage guidance without breaking any other workflow

### Failure Injection
- Verify that if the dedupe search returns an existing open issue, the
  workflow prescribes "append comment" not "create new"

### Rollback / Disable Path
- **Agent profile:** Remove `.claude/agents/issues.md` to disable triage
  guidance without affecting any other workflow
- **Workflow doc:** Amend or delete `ISSUE_TRIAGE_WORKFLOW.md` if
  qualification thresholds or anti-spam rules prove too permissive. Since
  the doc is purely prescriptive (no code enforcement), tightening rules
  is a single-file edit with no downstream breakage
- **Labels:** New labels (`triage`, `agent-ready`, `needs-human`) can be
  removed from GitHub without affecting existing issue infrastructure

## Parallelism Assessment

All three deliverables can be written sequentially in a single author lane.
No parallelism needed — the files are small docs, not code. Total estimated
scope: ~200 lines of markdown across 3 files.

## Outcome
<!-- Filled after implementation -->
