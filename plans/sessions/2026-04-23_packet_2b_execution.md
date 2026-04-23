# Execution Plan — Packet 2b (verification-contract + H.0 canary scaffolding)

**Date:** 2026-04-23
**Lane:** author-b
**Packet:** `5729fef49ba3`
**Branch:** `docs+feat/verification-contract-execution`
**Parent plan:** `plans/steward_platform/governing_plan.md` §10.9, §5-H, §6.4, §11, §12, §13
**Shaping source:** `plans/steward_platform/verification_contract/shaping.md` (PR #2759)

## Purpose

Execute shaping doc §11.1–§11.3 per analyst-a's spec: scaffold Pattern 10
"verification surface per deliverable" across 7 enforcement surfaces and
split Primitive H into H.0 (Phase 0 mini-canary, SC #22 gate) + H.1 (full
Phase 1 reliability suite). Scope is *scaffolding only* — full canary
implementation (pass metrics, event emission, weekly cron) is downstream
H.0 packets. The work will be judged against:

1. All files in shaping §11.1 exist or are modified per spec.
2. Validation commands in §11.3 pass.
3. `agent_readability_lint.py check verification-contract` runs clean against
   `plans/steward_platform/`.
4. `dogfood-v1` canary stub is registered and invokable via `/run-canary`.
5. Packet 2b PR merges with Verification Performed evidence.

## Ordered work items

Follows shaping §11.2 order: governing-plan edits first (gives downstream
lint/script/skill work a plan to reference), then templates (creation-time
enforcement surface), then sub-plans (use templates), then scripts, then
skills, then prompt-policy, then PR template, then self-run lint, then
PR open.

### Phase 1 — Governing plan edits (shaping §11.1 "Files modified")

**I1 — Insert Pattern 10 into §10.9 after Pattern 9.**
Target: `plans/steward_platform/governing_plan.md` line ~1029 (end of Pattern
9), insert full Pattern 10 text verbatim from shaping §2. Preserve
"Enforcement surface" closing paragraph following all patterns.
Validation: `grep -c 'Pattern 10' plans/steward_platform/governing_plan.md` ≥ 3.

**I2 — Split §5-H into §5-H.0 + §5-H.1.**
Target: `plans/steward_platform/governing_plan.md` lines 608–645.
Add `#### 5-H.0 — Phase 0 mini-canary (dogfood-v1)` containing H.0
Readiness bullets from shaping §9.3 + §9.2 bullet assignment (bullet 5
single-scenario, bullet 6 idempotency checklist). Rewrite existing §5-H
to `#### 5-H.1 — Phase 1 reliability lab` with remaining bullets.
Validation: `grep -cE '§5-H\.0|§5-H\.1' plans/steward_platform/governing_plan.md > 0`.

**I3 — Update §10.7 phase-membership design-coupling note.**
Target: `plans/steward_platform/governing_plan.md` lines 900–904 + §9.6 text.
Insert the H.0/H.1 split-reference paragraph after "Design coupling note."
Validation: `grep -c 'H\.0 is Phase 0' plans/steward_platform/governing_plan.md > 0`.

**I4 — Split §11-H kill row.**
Target: `plans/steward_platform/governing_plan.md` line 1080.
Replace single H row with H.0 + H.1 rows per shaping §9.7.
Validation: `grep -cE '\| H\.0|\| H\.1' plans/steward_platform/governing_plan.md > 0`.

**I5 — Add §12 Risks row (canary silent-green-check).**
Target: `plans/steward_platform/governing_plan.md` line 1103 (after last row).
Add row per shaping §7 (hash + sparkline + quarterly audit mitigation).
Validation: `grep -c 'Canary becomes silent green check' plans/steward_platform/governing_plan.md > 0`.

**I6 — Add SC #21 + #22 to §13.**
Target: `plans/steward_platform/governing_plan.md` line 1128 (after SC #20).
Add numbered items 21 + 22 from shaping §8.
Validation: `grep -cE '^21\.|^22\.' plans/steward_platform/governing_plan.md ≥ 2`.

**I7 — Add §6.4 preflight preamble sentence.**
Target: `plans/steward_platform/governing_plan.md` line 703 (before table).
Insert preamble per shaping §12 "Alternative (lighter touch, preferred)"
option — one sentence linking each pass-criterion to a verification surface
in `verification_contract/map.md`.
Validation: `grep -c 'verification_contract/map\.md' plans/steward_platform/governing_plan.md > 0`.

### Phase 2 — Template edits (shaping §6)

**I8 — Add `## Verification Plan` section to all 3 templates.**
Targets: `plans/_templates/sub_plan.md`, `execution_plan.md`,
`primitive_closeout.md`. Each gets the shaping §6.1 worked-example table +
cross-reference to §10.9 Pattern 10.
Validation: `grep -l 'Verification Plan' plans/_templates/*.md` = 3 files.

### Phase 3 — Sub-plan + map skeletons (shaping §10)

**I9 — Create verification-contract sub-plan + map + review log.**
Targets:
- `plans/steward_platform/verification_contract/sub_plan.md` (headers per §10.1)
- `plans/steward_platform/verification_contract/map.md` (initial ≥90% coverage;
  walk §5 sub-deliverables A-H + §6.4 preflight items + Phase 0 Readiness
  bullets; target ~60 rows)
- `plans/steward_platform/verification_contract/review_log.md` (empty stub)
Validation: `uv run python scripts/internal/verify_map_coverage.py plans/steward_platform/verification_contract/map.md` → coverage ≥ 90%.

**I10 — Create dogfood canary sub-plan with §13 Rollback self-reference
exclusion (§13.2 risk #4).**
Target: `plans/steward_platform/canary_scenarios/dogfood.md`.
§13 Rollback must document: "Canary's own revert-PR is excluded from
material-platform-change trigger via `canary_rollback_pr=true` metadata
bit or equivalent."
Validation: `grep -c 'canary_rollback_pr' plans/steward_platform/canary_scenarios/dogfood.md > 0`.

### Phase 4 — Scripts (shaping §11.1 + §3)

**I11 — Create `scripts/internal/verify_map_coverage.py` + unit test.**
Targets:
- `scripts/internal/verify_map_coverage.py` — parses map.md rows, counts
  rows vs enumerated deliverables, computes ratio; exits non-zero if
  <threshold (default 90%); stdout report.
- `tests/unit/test_verify_map_coverage.py` — seeded fixture (inline
  minimal map + deliverable set) asserting coverage math, edge cases.
Validation: `uv run python -m pytest tests/unit/test_verify_map_coverage.py`
passes.

**I12 — Create `scripts/internal/agent_readability_lint.py` with
`check verification-contract` sub-command.**
Target: `scripts/internal/agent_readability_lint.py` (does not yet exist).
Module-level docstring documents Pattern 9 + Pattern 10 shared dependency
per §13.2 risk #2 ("both Pattern 9 load-bearing-ownership and Pattern 10
verification-contract enforcement live here; if either degrades, both
degrade — decomposition trades duplication for independence, kept as
sub-commands for now").
Sub-command `check verification-contract` scans `plans/**/*.md` for §N.M
Work/Readiness bullets, verifies each has a matching Verification Plan
row OR a row in `verification_contract/map.md`.
`tests/unit/test_agent_readability_lint.py` covers the sub-command.
Validation: `uv run python -m pytest tests/unit/test_agent_readability_lint.py`
passes.

**I13 — Extend `scripts/internal/review_driver.py` with V1-V6 prechecks +
commit-footer lint.**
Target: `scripts/internal/review_driver.py`.
- V1–V6 check IDs per shaping §3.4 (BLOCK/WARN/INFO).
- V3 ("surface does not exist") gates on `current_head + pr_diff` per
  §13.2 risk #1 (the set of paths to consider valid includes files added
  in the PR's own diff, not just files present at HEAD).
- Commit-footer lint per §3.3 trigger paths; accepts `Verification:`
  footer on ANY commit in PR range per §13.2 risk #3 (not only the
  introducing commit).
- `tests/unit/test_review_driver.py` extended with V1–V6 negative-path
  cases.
Validation: `uv run python -m pytest tests/unit/test_review_driver.py`
passes V1–V6 cases.

### Phase 5 — Skill stubs (shaping §11.1 "Files created")

**I14 — Create 3 skill stubs.**
Targets:
- `.claude/skills/create-plan/SKILL.md` — refusal logic per §3.2.ii;
  invocation shape `/create-plan <kind> <path>`; refuses if Verification
  Plan section missing, empty, or contains stub placeholders
  (TBD/TODO/FIXME/XXX) or if it lacks coverage of enumerated Work
  deliverables. Stub calls out that full implementation is ADR-tracked
  follow-on work.
- `.claude/skills/run-canary/SKILL.md` — stub registering the skill.
  Full canary impl is a downstream H.0 packet.
- `.claude/skills/canary-review/SKILL.md` — stub for quarterly
  operator-audit skill.
Validation: `ls .claude/skills/create-plan/SKILL.md .claude/skills/run-canary/SKILL.md .claude/skills/canary-review/SKILL.md` all exist.

### Phase 6 — Prompt-policy clauses (shaping §4)

**I15 — Create prompt-policy registry + 3 lane files.**
Targets (directory does not yet exist — create):
- `.claude/rules/prompt_policy/orchestrator.md` — §4.1 clause
- `.claude/rules/prompt_policy/author.md` — §4.2 clause
- `.claude/rules/prompt_policy/analyst.md` — §4.3 clause
Per shaping §11.4 coordination note: B.3 registry home location is
being established by Packet 1 (author-b, sibling). If Packet 1 lands
before this, use its registry home; if not, create as new and document
the choice. Current verification: Packet 1 status (TBD per orchestrator
coordination).
Validation: `ls .claude/rules/prompt_policy/{orchestrator,author,analyst}.md` all exist.

### Phase 7 — PR template

**I16 — Add `## Verification Performed` section.**
Target: `.github/pull_request_template.md`.
Section structure: bulleted list of "Surface | Run output | Expected match"
per Pattern 10 surface class. Guidance directs author to paste evidence.
Validation: `grep -c 'Verification Performed' .github/pull_request_template.md > 0`.

### Phase 8 — Self-run lint + PR open

**I17 — Self-run `agent_readability_lint.py check verification-contract`
against `plans/steward_platform/`.** Expect clean. Fix issues until clean.
Validation: `uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/steward_platform/` → exit 0.

**I18 — Pre-PR rebase + Tier 2 validation + PR open.**
```
git fetch origin main && git rebase origin/main
make check-gated
gh pr create --title "docs+feat(steward-platform): implement Pattern 10 verification-contract + H.0 dogfood canary scaffolding (Packet 2b)" ...
```
PR body uses the updated template (Verification Performed section);
pastes lint output + unit test output + grep validation outputs.
References shaping: "Executes plans/steward_platform/verification_contract/shaping.md §11.1–§11.3 per analyst-a shaping (PR #2759)."

## Reviewer / parallelism assessment

**Reviewer:** this lane's system prompt (secondary author, steward
dashboard) structurally disallows the `Agent` tool. Step 2 of the task
packet instructs spawning a reviewer agent; this is not possible. Substitute
applied: a self-review pass against shaping §11.2 ordering sanity and
§13.2 risks, recorded in the "Self-review" section below.

**Parallelism:** all items execute serially within this lane. No
disjoint-write-scope sub-delegation is planned. Items I1–I7 (governing
plan edits) must complete before I8 (templates reference Pattern 10).
I8 must complete before I9/I10 (sub-plan skeletons use templates). I11–I13
(scripts) can interleave with I9/I10 (independent write scopes) but easier
to land serially. I14 (skills), I15 (prompt-policy), I16 (PR template),
and I17 (self-run lint) depend on scripts (I12/I13) being callable.

## Self-review against §11.2 ordering

| Check | Outcome |
|---|---|
| §5 precheck (V1–V6) depends on map.md existing | ✓ V1 references Verification Plan rows; V6 references map.md. Order: map.md in I9 lands before review_driver.py extension in I13. |
| §5 precheck depends on agent_readability_lint.py existing | ✓ I13 happens after I12 (lint script). Both can be unit-tested before self-run I17. |
| `agent_readability_lint.py check verification-contract` requires governing plan already has Pattern 10 text | ✓ I1 (insert Pattern 10) happens in Phase 1; I17 self-run is Phase 8. |
| Skills reference templates | ✓ I14 (create-plan stub) references templates from I8; I8 precedes I14. |
| Prompt-policy registry may depend on Packet 1 | ⚠ Coordination: if Packet 1 hasn't landed B.3 registry home, I15 creates the directory as new and documents the choice. Shaping §11.4 explicitly allows this. |

## Self-review against §13.2 risks

| Risk | Mitigation in this plan |
|---|---|
| #1 V3 false-positive on in-PR surface | I13 explicitly gates V3 on `current_head + pr_diff` (the verification-surface path check must treat files added in the PR's own diff as present). Implementation will pass `pr_diff` paths into the resolver. |
| #2 Pattern 9 + Pattern 10 shared-module dependency | I12 module-level docstring documents the shared dependency as a Phase 1 Validation concern; subcommand-style decomposition keeps them independently testable. |
| #3 Commit-footer any-commit acceptance | I13 commit-footer lint iterates over `git log base..head` and accepts a match on ANY commit in the range. Test case `test_commit_footer_accepts_on_followup_commit` covers it. |
| #4 Canary self-reference exclusion | I10 sub-plan §13 Rollback section explicitly documents `canary_rollback_pr=true` metadata bit as the exclusion mechanism. Full implementation is H.0 follow-on; this PR scaffolds the convention. |

## Files Changed (summary)

Created (14 files):
- `plans/steward_platform/verification_contract/sub_plan.md`
- `plans/steward_platform/verification_contract/map.md`
- `plans/steward_platform/verification_contract/review_log.md`
- `plans/steward_platform/canary_scenarios/dogfood.md`
- `scripts/internal/verify_map_coverage.py`
- `scripts/internal/agent_readability_lint.py`
- `tests/unit/test_verify_map_coverage.py`
- `tests/unit/test_agent_readability_lint.py`
- `.claude/skills/create-plan/SKILL.md`
- `.claude/skills/run-canary/SKILL.md`
- `.claude/skills/canary-review/SKILL.md`
- `.claude/rules/prompt_policy/orchestrator.md`
- `.claude/rules/prompt_policy/author.md`
- `.claude/rules/prompt_policy/analyst.md`

Modified (5 files):
- `plans/steward_platform/governing_plan.md`
- `plans/_templates/sub_plan.md`
- `plans/_templates/execution_plan.md`
- `plans/_templates/primitive_closeout.md`
- `scripts/internal/review_driver.py`
- `tests/unit/test_review_driver.py`
- `.github/pull_request_template.md`

## Validation (Tier 2)

Per shaping §11.3:

```bash
# Unit
uv run python -m pytest tests/unit/test_verify_map_coverage.py
uv run python -m pytest tests/unit/test_review_driver.py
uv run python -m pytest tests/unit/test_agent_readability_lint.py

# Integration
uv run python scripts/internal/verify_map_coverage.py plans/steward_platform/verification_contract/map.md
uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/steward_platform/

# Grep validation (per packet validation)
grep -c 'Pattern 10' plans/steward_platform/governing_plan.md       # ≥ 3
grep -cE '§5-H\.0|§5-H\.1' plans/steward_platform/governing_plan.md # > 0
grep -cE '^22\.' plans/steward_platform/governing_plan.md            # > 0

# Negative path (manual; not committed)
# - Remove a Verification Plan row; rerun lint; expect failure; revert
# - Name fake surface path in map.md; rerun verify_map_coverage; expect failure; revert

# Tier 2
make check-gated
```

## Verification Plan

Pattern 10 self-reference: this execution plan names its own verification
surfaces.

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §Phase 1 governing plan edits (I1–I7) | plan text edit | grep patterns in Validation section above | author-b | all grep exit conditions met |
| §Phase 2 template edits (I8) | plan template edit | `grep -l 'Verification Plan' plans/_templates/*.md` | author-b | 3 files match |
| §Phase 3 sub-plan skeletons (I9–I10) | new plan artifact | `verify_map_coverage.py` + §13 Rollback grep | author-b | coverage ≥ 90%; rollback grep > 0 |
| §Phase 4 scripts (I11–I13) | new Python module | unit tests | author-b | pytest passes |
| §Phase 5 skill stubs (I14) | new `.claude/skills/**` entry | path exists + SKILL.md registration | author-b | ls succeeds; skill registers |
| §Phase 6 prompt-policy (I15) | new `.claude/rules/**` file | path exists + content check | author-b | files created with §4.1/§4.2/§4.3 text |
| §Phase 7 PR template (I16) | config change | grep + rollback = revert commit | author-b | grep matches; revert works |
| §Phase 8 self-run + PR open (I17–I18) | integration runbook | `make check-gated` + PR open | author-b | gate green; PR opened |

**Surface-class defaults:** see Pattern 10 table at §10.9 of governing plan.

## Phase 2 Decision Inputs

**Portability readiness:** Pattern 10 is portable-by-design per shaping
§14; deliverable-class → verification-surface map contains no
Bid-Euchre-specific literals. Same discipline works in a second cell.
**Meta-layer need:** no change. Per-cell discipline; no meta-surface
required.
**Kill signal for primitive(s) named:** N/A at execution stage. §11-H.0
kill (canary fails to achieve ≥2 weekly passes in 4-week window during
Phase 0) triggers after H.0 is implemented — not during this
scaffolding PR.
**Re-evaluation needed in Phase 3:** yes if review-driver precheck V3
integration turns out to have higher false-positive rate than expected,
or if Pattern 9 / Pattern 10 shared-module dependency (§13.2 risk #2)
degrades either lint sub-command's independence during Phase 1.
**Surprise finding:** the self-referential nature of Pattern 10 (an
execution plan verifying itself against Pattern 10's own Verification
Plan section) produced clearer self-review than expected — the table
above is strictly more readable than the narrative self-review checks.
Suggests Pattern 10 enforcement templates should encourage tabular
self-verification even when not strictly required.
**Disposition:** open

## Outcome

(Filled after implementation.) Link to resulting PR(s) or note abandonment.
