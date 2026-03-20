# PR-5 Slice 5: Skill-Promotion Workflow

**Date:** 2026-03-20
**Status:** COMPLETE
**Parent:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` (PR-5 slice 5)
**Gate:** Slice 3 (#1024) and slice 4 (#1016) are merged.

## Goal

Ship a bounded, reviewed skill-promotion workflow where repeated successful
multi-step workflows can be proposed, reviewed, scanned for safety, and
promoted into the `.claude/skills/` directory with full provenance.

## Design

### What qualifies as a promotable skill candidate

- A repeated multi-step workflow that an operator or lane has used successfully
- Bounded scope — captures one workflow, not a general-purpose agent
- Clear operator value — saves time or reduces error on future invocations
- Provenance-backed — source workflow, proposer, and lineage are recorded

### Stored artifact contract

**Candidates** (pending review) live in `.claude/runtime/skill_candidates/`:
```
.claude/runtime/skill_candidates/<candidate_id>.json
```

**Promoted skills** land in `.claude/skills/<name>/SKILL.md` (committed):
```
.claude/skills/<name>/SKILL.md
```

**Candidate schema** (`SkillCandidate` dataclass):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `candidate_id` | str | yes | UUID |
| `name` | str | yes | Kebab-case skill name |
| `description` | str | yes | One-line description for YAML front matter |
| `content` | str | yes | Full SKILL.md body content |
| `source_workflow` | str | yes | What workflow this captures |
| `proposed_by` | str | yes | Lane ID or "operator" |
| `proposed_at` | str | yes | ISO 8601 |
| `provenance` | dict | yes | `{source_files: [...], prs: [...], sessions: [...]}` |
| `status` | enum | yes | `pending` / `approved` / `rejected` / `promoted` |
| `review_notes` | str | no | Reviewer comments |
| `reviewed_by` | str | no | Who reviewed |
| `reviewed_at` | str | no | When reviewed (ISO 8601) |
| `safety_scan_hash` | str | no | Content hash from context-safety scan |
| `safety_scan_outcome` | str | no | `allow` / `warn` / `reject` |

### Promotion path

1. **Propose:** Create a candidate with name, description, content, provenance.
   Context-safety scan runs immediately. If `reject`, candidate is stored
   but marked with the rejection reason (operator can see why and fix content).
2. **Review:** Operator inspects the candidate and approves or rejects it.
3. **Promote:** Write the skill to `.claude/skills/<name>/SKILL.md`.
   Only if status is `approved` AND safety scan outcome is not `reject`.
   Re-scans at promotion time to catch content that changed between proposal
   and promotion.
4. **Disable/rollback:** Remove or rename a promoted skill. Record the action.

### Context-safety integration

- `scan_content(candidate.content, metadata={source_file: ..., added_by: ...})`
- On `reject`: candidate stored with `safety_scan_outcome: reject`, promotion
  blocked until content is revised and re-scanned.
- On `warn`: promotion allowed, warnings recorded in candidate metadata.
- On `allow`: clean promotion.
- Re-scan at promotion time (not just at proposal time) as a defense-in-depth
  measure.

### Rollback

- `disable_skill(name)` removes the skill directory or renames SKILL.md
  to SKILL.md.disabled.
- Does NOT delete the candidate record — provenance is retained.
- Emits a `skill_disabled` event to the ops event log.

## Files

### New files
- `src/bid_euchre/ops/skill_promotion.py` — core promotion logic
- `tests/unit/test_ops_skill_promotion.py` — comprehensive tests
- `plans/sessions/2026-03-20_pr5-slice5-skill-promotion.md` — this plan

### Modified files
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — add skill-promotion section
- `scripts/internal/ops.py` — add `skills` subcommand (if CLI surface exists)

### Not touched
- Existing `.claude/skills/` contents — no modification of existing skills
- `src/bid_euchre/ops/context_safety.py` — used as-is, no changes needed
- `src/bid_euchre/ops/snapshots.py` — used as-is, no changes needed

## Acceptance criteria

- [ ] `SkillCandidate` dataclass with full schema documented above
- [ ] `propose_skill()` creates candidate, runs context-safety scan, stores JSON
- [ ] `review_skill()` approves or rejects a candidate with notes
- [ ] `promote_skill()` writes SKILL.md to `.claude/skills/<name>/`, re-scans,
      blocks on safety rejection
- [ ] `disable_skill()` disables a promoted skill, retains provenance
- [ ] `list_candidates()` returns all candidates with status filtering
- [ ] Context-safety scan is mandatory — no bypass path
- [ ] Tests cover: happy path, reject on safety, reject on review, malformed
      candidate, promote without approval, disable, re-proposal after rejection
- [ ] Docs explain the operator workflow
- [ ] `make check-quiet` passes

## Out of scope

- Autonomous skill learning loop
- Background self-refinement
- Multi-repo skill sharing
- Dynamic orchestrator prompt synthesis
- Remote-triggered promotion
- CLI subcommand wiring in ops.py (can be a follow-up if ops.py structure needs it)
- Governed-platform Platform-11 behavior

## Outcome

PR #1054 — `ops: add reviewed skill-promotion workflow`
