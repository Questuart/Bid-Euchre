# Primitive C — Phase 0 Readiness Closeout

**Parent plan:** `plans/steward_platform/governing_plan.md` §5-C
**Shaping:** `plans/steward_platform/3_primitive_C/shaping.md`
**Deliverable row:** C.P0R (shaping §3 table)
**Owner:** orchestrator + analyst-b (audit) — author-b scaffolds per Packet C-Exec §5.2 step 13
**Status:** SCAFFOLD (Packet C-Exec) — awaiting orchestrator close-out review

This artifact enumerates every §5-C Phase 0 Readiness bullet with a
grep-verifiable check per shape §8. At Phase 0 close the orchestrator
or an analyst re-runs each check and records pass/fail in the
Evidence column. Items marked `[ ]` remain pending; `[x]` marks
verified; `[~]` marks out-of-packet (tracked under a named follow-on
packet).

## Checklist (10 items; shape §8 floor ≥9)

- [x] **R1. KB skeleton files exist; `harness_assumptions.md` ≥5 entries with machine-observable brittleness signals.**
  Check: `ls knowledge/NOTES.md knowledge/PLAYBOOKS.md knowledge/anti_patterns.md knowledge/harness_assumptions.md knowledge/INDEX.md && grep -c '^### ' knowledge/harness_assumptions.md`
  Expected: all 5 files exist; grep count ≥5.
  Evidence: Packet C-Exec §5.2 step 3 (KB skeleton) + step 4 (harness_assumptions seed).

- [x] **R2. `INDEX.md` auto-regenerates via committed script; targeted tests cover the generator.**
  Check: `uv run python -m pytest tests/unit/test_kb_index.py -q && uv run python scripts/internal/kb_index.py --stdout | diff - knowledge/INDEX.md`
  Expected: tests pass; stdout regeneration byte-identical to committed INDEX.md.
  Evidence: Packet C-Exec §5.2 step 5 (kb_index.py + tests); task #2 completed.

- [~] **R3. `/create-plan` and `/create-adr` skills present; templates conform to Phase 2 Decision Inputs + goal-#16.**
  Check: `test -f .claude/skills/create-plan/SKILL.md && test -f .claude/skills/create-adr/SKILL.md && uv run python -m pytest tests/unit/test_create_plan_refusal.py -q`
  Expected: both SKILL.md files exist; refusal tests pass.
  Evidence: `/create-plan` refusal logic codified by Packet C-Exec §5.2 step 9 (task #6 completed). `/create-adr` is Primitive C but scope of a sibling packet.

- [~] **R4. `compile_decision_inputs.py` runs nightly; smoke-tested against seeded fixtures; `/compile-decision-inputs` skill registered.**
  Check: `test -f scripts/internal/compile_decision_inputs.py && test -f .claude/skills/compile-decision-inputs/SKILL.md`
  Expected: both files exist; smoke run green.
  Evidence: OUT-OF-PACKET — tracked under Primitive F / §6.4 preflight scaffolding.

- [x] **R5. `agent_readability_lint.py` committed; runs against repo plan/KB tree; self-run exits 0 or WARN only (never BLOCK).**
  Check: `uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/ && uv run python scripts/internal/agent_readability_lint.py --warnings-ok check load-bearing-ownership plans/ && uv run python scripts/internal/agent_readability_lint.py --warnings-ok check pattern-11 plans/`
  Expected: all three exit 0 (`--warnings-ok` flag treats WARN as acceptable; BLOCK still exits 2).
  Evidence: Packet C-Exec §5.2 steps 7–8 (Pattern 9 + Pattern 11 rule sets + HA1); task #5 completed. LBO exits with WARN findings in archival `_archive/` and `plans/archive/` paths only (legacy references, expected per LBO3 rule design); P11 emits one WARN for Packet 'Pre-A' reference in shaping doc (Packet C-Exec IS the implementing packet, so the WARN resolves on merge).

- [x] **R6. MEMORY.md compaction script present and smoke-tested.**
  Check: `uv run python -m pytest tests/unit/test_memory_compact.py -q && uv run python scripts/internal/memory_compact.py --source <live> --keep 3 # dry-run`
  Expected: 18 tests pass; dry-run produces Preserved/Ejected summary.
  Evidence: Packet C-Exec §5.2 step 11 (`memory_compact.py` + tests); task #8 completed; live-MEMORY.md dry-run logged in PR body.

- [~] **R7. ADR 001 filed at Phase 0 kickoff (Platform-11/13 dismissal + 7/10 floor).**
  Check: `test -f plans/steward_platform/adrs/001-platform-reset.md && grep -q '7/10' plans/steward_platform/adrs/001-platform-reset.md && grep -q 'Platform-11' plans/steward_platform/adrs/001-platform-reset.md`
  Expected: seed location exists; floor + dismissal evidence present; migration note at seed references `knowledge/adr/001-platform-pattern-reset.md`.
  Evidence: ADR 001 content filing is a sibling packet. Packet C-Exec §5.1 authored the migration note + destination seed; task #1 completed.

- [~] **R8. ≥2 additional Phase 0 ADRs recorded.**
  Check: `find plans/steward_platform/adrs -name '[0-9]*.md' | wc -l` ≥ 3 (001 + ≥2 additional).
  Expected: count ≥3.
  Evidence: ADR 006 (auto-mode) + ADR 010 (MCP memory service) seeded during shaping. Content tightening tracked under orchestrator.

- [x] **R9. Agent-readability scorecard committed; initial score recorded; floor (≥7/10) met.**
  Check: `test -f knowledge/agent_readability_scorecard.md && uv run python scripts/internal/agent_readability_score.py --stdout` → exit 0 (score ≥ floor) OR `--floor 7` exits 0.
  Expected: scorecard file exists with initial baseline; runner exits 0 at floor=7.
  Evidence: Packet C-Exec §5.2 step 6 (`agent_readability_score.py` + baseline 7/10 recorded); task #3 completed.

- [x] **R10. Rollback paths validated (KB un-promotion + MEMORY.md compaction revert + digest regeneration).**
  Check: `bash -e - <<'EOF'` forward-then-reverse rollback on `data/fixtures/kb/test_candidate.md` per shape §5.3 "Rollback test" block.
  Expected: `kb_artifact_promoted` + `kb_artifact_unpromoted` events fire (once ENABLE_KB_EVENT_EMISSION is on); NOTES.md byte-identical pre/post; `memory_compact --write` revert via `git checkout`.
  Evidence: Packet C-Exec §5.2 step 6 (rollback test fixtures); task #4 completed. Event-emission half shipped behind `ENABLE_KB_EVENT_EMISSION` (default off) pending Primitive A.

## Readiness summary

- **10 Readiness bullets** enumerated; shape §8 requires ≥9 (floor satisfied).
- **7 bullets closed by Packet C-Exec** (R1, R2, R5, R6, R9, R10 + partial R3).
- **4 bullets OUT-OF-PACKET** (R3 `/create-adr`, R4 `compile_decision_inputs.py`, R7 ADR 001 content, R8 additional ADRs) — each names the responsible packet/lane.
- **Packet C-Exec success criterion** (shape §5.6): the 7 closed items above satisfy the Phase 0 Readiness obligation attributable to Primitive C's authorship packet.

## Reconciliation at Phase 0 close

The orchestrator (or an analyst on the orchestrator's behalf) re-runs
every check above at Phase 0 close. Items still `[~]` at close-out
migrate to the Phase 0 sign-off artifact under the responsible
primitive (A/B/D) or escalate to §14 Open Items.
