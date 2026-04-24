# Verification Contract Map (Pattern 10 coverage)

**Parent:** `plans/steward_platform/governing_plan.md` §10.9 (Pattern 10), SC #21
**Maintainer:** orchestrator (Phase 0 kickoff review) + author-b (initial scaffold, Packet 2b)
**Coverage target:** ≥90% of enumerated deliverables (computed by `scripts/internal/verify_map_coverage.py`)
**Last reviewed:** 2026-04-23 (initial authoring; not yet operator-reviewed)

This file is the canonical Pattern 10 coverage reference. Every plan
deliverable (§5 primitive sub-deliverable rows, §6.4 preflight items,
Phase 0/1 Readiness bullets, §14 Open Items once resolved) appears as a
row with its verification surface. **Strict existence, lenient form** —
every deliverable has a named surface; the surface need not be
pytest-uniform as long as it matches the deliverable class per the §10.9
Pattern 10 table.

## Coverage by primitive + phase

### Primitive A — Unified Trace and Observability Layer (Phase 0)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| A.1 Event schema v1 (JSONL emission) | new module under `src/bid_euchre/ops/**` | `tests/unit/test_event_schema.py` | author | pytest passes; schema lints clean |
| A.2 Trace collector | new module under `src/bid_euchre/ops/**` | integration test + replay-harness compatibility assertion (H.1) | author | traces reconstruct ≥1 lifecycle |
| A.3 Phoenix local deployment | config change + rollback plan | `docs/ops/phoenix.md` runbook + disable path | ops | deployment reversible; 2 named workflows documented |
| A.4 Event-driven monitoring (≤5 min p95) | integration workflow | Primitive E active-triage test + latency metric dashboard | ops | p95 under target on baseline |
| A.5 Unified trace format migration | data-contract change | replay-harness schema-compat assertion + rollback (Pattern 7) | author | replay reconstructs pre-migration events |
| A.Phase0Readiness — ≥3 promoted findings | outcome metric | Phoenix-surface inspection citations in KB entries / ADRs | analyst | ≥3 findings recorded in proving run |

### Primitive B — Adaptive Dispatch, Skill Improvement, and Prompt-Policy (Phase 0)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| B.1 Skill promotion pipeline | new module under `src/bid_euchre/ops/**` | `tests/unit/test_skill_promotion.py` + trace-ID citation in commit | author | pytest passes; commit cites trace |
| B.2 Adaptive dispatch advisor | new module under `src/bid_euchre/ops/**` | `tests/unit/test_dispatch_advisor.py` | author | pytest passes |
| B.3 Prompt-policy registry (`.claude/rules/prompt_policy/**`) | new `.claude/rules/**` files | `tests/unit/test_prompt_policy_registry.py` + `agent_readability_lint.py check prompt-policy` | author | pytest passes; lint exits 0; all 4 policy files carry `Version/Trigger/Expected effect/Rollback` sections |
| B.4 Policy versioning + lifecycle | data-contract change | `tests/unit/test_policy_version.py` + rollback via version pin (Pattern 7) | author | pytest passes |
| B.5 Skill outcome-feedback loop | integration workflow | ≥1 skill edited with trace-ID citation during proving run (SC #10) | analyst | cited commit exists |
| B.6 Tool risk registry | new `.claude/rules/**` file | `tests/unit/test_tool_risk_registry.py` + `agent_readability_lint.py check tool-risk` + `permission-denied-log.sh` emission schema (approval_class_auto / approval_class_bypass / registry_row_id) | author | pytest passes; lint exits 0; permission-denied JSONL carries 3 new fields |
| B.7 Lane prompt-policy enforcement | integration workflow | ≥50% of proving-run traces cite a policy version (§11-B kill criterion) | analyst | ratio logged in Phase 0 close |
| B.10 Effort policy (`.claude/rules/effort_policy.md`) | new `.claude/rules/**` file + enum extension | `tests/unit/test_effort_policy.py` (table parser + `effort_for` purity) + `VALID_EFFORT_HINTS` includes `max` | author | pytest passes; `max` accepted by `validate_routing_metadata` |
| B.11 Orchestration recipe archive | new KB-class artifact | `tests/unit/test_recipes_archive.py` + `agent_readability_lint.py check recipes` + `INDEX.md` inclusion | author | pytest passes; lint exits 0; ≥1 seeded recipe passes all 6-section schema checks |
| B.12 Improvement-mechanism evaluation | analysis workflow | §13 SC #1 improvement-probe metric + rolling-window delta report | analyst | ≥1 delta report filed |
| B.Phase0Readiness — active routing or advisory ships | outcome metric | SC #9 grep evidence | ops | evidence in proving-run report |

### Primitive C — Durable Memory and Knowledge Base (Phase 0)

The C.1.1–C.1.7 rows below replace the previous coarse C.1 row with
per-skeleton-file granularity per shaping §3 deliverable table and §5.1
Packet C-Exec scope (`plans/steward_platform/3_primitive_C/shaping.md`).
C.2–C.7, C.8–C.12, C.Phase0Readiness retain their original scope.

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| C.1.1 `knowledge/NOTES.md` skeleton | new KB-class artifact | `INDEX.md` inclusion + `agent_readability_lint.py check verification-contract` clean on schema | analyst | 1 worked example at file head; lint exits 0 |
| C.1.2 `knowledge/PLAYBOOKS.md` skeleton | new KB-class artifact | `INDEX.md` inclusion + `agent_readability_lint.py check verification-contract` clean | analyst | 1 worked example; lint exits 0 |
| C.1.3 `knowledge/anti_patterns.md` skeleton | new KB-class artifact | `INDEX.md` inclusion + schema field check (`trigger → harm → preferred alternative`) | analyst | ≥1 entry; lint verifies schema form |
| C.1.4 `knowledge/incidents/` directory + worked example | new KB-class directory | per-file fingerprint matches `incident_fingerprint` in event schema v1.0 | analyst | ≥1 worked example; grep matches `ops/event_taxonomy.py` emission |
| C.1.5 `knowledge/harness_assumptions.md` ≥5 initial entries | new KB-class artifact | each entry's brittleness signal is machine-observable (grep pattern / CI check / hook precondition); `check load-bearing-ownership` HA1 rule | analyst | lint verifies `assumption → observation → brittleness signal → refresh trigger` fields; brittleness-signal-is-machine-observable sub-check passes |
| C.1.6 `knowledge/adr/` directory (incl. ADR 001 migration) | new KB-class directory | per-ADR supersession field + Pattern 7 rollback citation; `diff plans/steward_platform/adrs/001-platform-reset.md knowledge/adr/001-platform-pattern-reset.md` post-migration | analyst | ADR 001 migrated (content identical; seed carries migration note); ≥2 additional Phase 0 ADRs per §5-C Readiness |
| C.1.7 `knowledge/INDEX.md` regeneration script | new Python script under `scripts/internal/**` | `tests/unit/test_kb_index.py::test_index_regenerates_deterministically` + diff against `find knowledge/ -type f` | author | pytest passes; diff empty post-regeneration |
| C.2 `harness_assumptions.md` register (SC #14 refresh/retire evidence) | new KB-class artifact + outcome metric | run-log evidence of ≥1 entry refreshed during Phase 0 proving run | analyst | ≥1 entry refreshed |
| C.3 `agent_readability_lint.py` (Pattern 9 + Pattern 10 + Pattern 11) | new/extended module under `scripts/internal/**` | `tests/unit/test_agent_readability_lint.py` (TestPattern9 + TestPattern10 + TestPattern11 + TestPlanWalker) + self-run on `plans/` | author | pytest passes; self-run exits 0 (WARN allowed, never BLOCK) |
| C.4 `agent_readability_scorecard.md` | new KB-class artifact + config | `INDEX.md` inclusion + ADR 001 §D3 floor lockdown + `agent_readability_score.py --floor 7` exits 0 | ops | scorecard present; score ≥7/10 per ADR 001; runner rejects `--floor 6` |
| C.5 `agent_readability_score.py` runner | new Python script under `scripts/internal/**` | `tests/unit/test_agent_readability_score.py::test_ten_items_present` + `::test_floor_below_seven_rejected` | author | both tests pass; runner exits 0 at floor 7 |
| C.6 Pattern 9 `check load-bearing-ownership` (LBO1–LBO3 + HA1) | extension of existing script | `tests/unit/test_agent_readability_lint.py::TestPattern9` + positive + 3 negative fixtures | author | all fixtures pass |
| C.7 Pattern 11 `check pattern-11` (P11_1–P11_3) | extension of existing script | `tests/unit/test_agent_readability_lint.py::TestPattern11` + positive + 3 negative fixtures | author | all fixtures pass |
| C.8 `/create-plan` skill refusal logic | `.claude/skills/**` upgrade | `tests/unit/test_create_plan_refusal.py` (4 tests, one per R1–R4 refusal condition) | author | all 4 tests pass |
| C.9 Commit policy (tracked/gitignored split, ADR 010 binding) | config + rules extension | `git check-ignore knowledge/_candidates/` exits 0 AND `git check-ignore knowledge/_promoted/` exits 1 (non-ignored); rollback test in `data/fixtures/kb/test_candidate.md` emits `kb_artifact_promoted` + `kb_artifact_unpromoted` | ops | both gitignore assertions hold; rollback test forward-reverse byte-identical |
| C.10 `memory_compact.py` compaction script | new Python script under `scripts/internal/**` | `tests/unit/test_memory_compact.py` + seeded fixture smoke | author | pytest passes; compaction preserves high-priority entries per schema |
| C.11 Archivist C↔D interface contract | docs + integration | `grep -c 'Archivist C↔D Interface Contract' scripts/internal/archivist.py knowledge/INDEX.md` ≥ 2 | analyst | both files contain the block (count ≥2) |
| C.12 Scorecard sub-plan (F10 tightening path) | new sub-plan artifact | `agent_readability_lint.py check verification-contract plans/steward_platform/3_primitive_C/scorecard_sub_plan.md` | analyst | lint exits 0 (sub-plan has own Verification Plan) |
| C.V7 review-driver `V7` precheck (commit-policy enforcement) | extension of existing script | `tests/unit/test_review_driver.py::TestV7CommitPolicy` (10 tests) + `ENABLE_V7_COMMIT_POLICY` feature flag default off until Primitive A ships | author | all V7 tests pass; flag defaults off |
| C.P0R Phase 0 Readiness closeout | outcome artifact | `plans/steward_platform/3_primitive_C/phase0_readiness.md` with ≥9 grep-verifiable checks (shape §8 floor) | orchestrator + analyst | `grep -c '^- \[.\]' phase0_readiness.md` ≥ 9 |
| C.Phase0Readiness — ≥3 promoted lessons grep-cited | outcome metric | proving-run PR body / task-packet description greps (§11-C kill criterion) | analyst | ≥3 citations logged |

### Primitive D — Archivist, Session Postmortem, and Changelog Review (Phase 0 inflow; Phase 1 outflow; Phase 0 changelog)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| D.1 Archivist candidate generator | new module under `src/bid_euchre/ops/**` | `tests/unit/test_archivist.py` | author | pytest passes |
| D.2 Session postmortem generator | new module under `src/bid_euchre/ops/**` | `tests/unit/test_session_postmortem.py` | author | pytest passes |
| D.3 GC report proposal pipeline (Phase 1 outflow) | integration workflow | SC #15 — ≥3 proposals accepted across ≥2 categories | ops | logged in proving-run report |
| D.4 Changelog review skill | new `.claude/skills/**` entry | `SKILL.md` acceptance command + SC #19 (≥2×/week; ≥1 `native-substrate-signal` ledger entry) | ops | run log satisfies SC #19 |
| D.Phase0Readiness — candidate-to-promotion rate ≥10% | outcome metric | proving-run KB promotion log (§11-D kill criterion) | analyst | ratio logged |

### Primitive E — Messaging and Active Triage Closeout (Phase 0)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| E.1 Message-bus finalization (zero lost messages) | integration workflow | SC #8 — zero lost; p95 target | ops | metric logged green |
| E.2 Active triage event-driven issues | integration workflow | §6.4 item 6 — ≥1 triage-filed issue during preflight | ops | issue exists; event trace cites trigger |
| E.3 Hook migration (bespoke → native lifecycle) | config change | ADR 004 + rollback test | ops | migration logged; revert path exists |
| E.Phase0Readiness — ≥20% active-triage rate | outcome metric | §11-E kill criterion — proving-run issue source ratio | ops | ratio logged |

### Primitive F — Token Economy Closeout (Phase 0)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| F.1 Token-economy rollups | new module under `src/bid_euchre/ops/**` | `tests/unit/test_token_rollups.py` | author | pytest passes |
| F.2 Promote/retain/kill decision on adaptive dispatch | decision artifact | SC #9 + ADR 003 native vs. bespoke boundary | ops | decision logged |
| F.Phase0Readiness — defensible decision produced | outcome metric | §11-F kill criterion — decision produced or frozen advisory | ops | decision logged or freeze path recorded |

### Primitive G — Existing-Debt Closeout + Native-Substrate Migration (Phase 0)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| G.1 ops module rework spec | sub-plan artifact | `plans/steward_platform/0_hardening/sub/rework_spec.md` §4 coverage | author | per-module rows filled |
| G.2 `§10.9` extensibility patterns 1-10 | plan-text codification | `grep -c 'Pattern \d\+' plans/steward_platform/governing_plan.md` ≥ 10 | analyst | grep ≥ 10 |
| G.3 Native-substrate adoption (≥1 by end Phase 1) | integration workflow | SC #20 — named adoption with retired bespoke surface | ops | adoption logged |
| G.4 Auto mode codification ADR 006 | ADR | Pattern 7 rollback path (supersession) + commit citation | ops | ADR filed at Phase 0 kickoff |
| G.5 19-lane → 8-archetype mapping | sub-sub-plan | first-deliverable mapping artifact | orchestrator | mapping artifact exists |
| G.Phase0Readiness — rework spec coverage complete | outcome metric | `agent_readability_lint.py` clean across ops modules | author | lint exits 0 |

### Primitive H.0 — Phase 0 mini-canary (dogfood-v1)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| H.0.1 dogfood-v1 canary impl | new module under `tests/reliability/**` | `tests/reliability/canaries/test_dogfood_v1.py` + 9 pass-metric assertions | author | 9/9 assertions pass on seeded run |
| H.0.2 `/run-canary` skill | new `.claude/skills/**` entry | `SKILL.md` acceptance command | ops | skill invokable from any lane |
| H.0.3 `/canary-review` quarterly audit skill | new `.claude/skills/**` entry | `SKILL.md` operator-review prompt + audit log | ops | quarterly audit entry logged |
| H.0.4 Weekly cron (/loop 7d /run-canary) | config change | rollback test — disable flag ENABLE_CANARY_CRON | ops | revert leaves no dangling cron |
| H.0.5 Conditional hook (material-platform-change) | new `.claude/hooks/**` file | rollback test + canary-scenario smoke | ops | hook disable path exercised |
| H.0.6 Dashboard integration (canary row + sparklines) | integration surface | scrape `ops.py dashboard` TUI for canary row + sparkline fields | ops | fields render; sparklines show 8 runs |
| H.0.7 Event schema v1.N additive (canary_run_*) | event-schema addition | replay-harness compatibility assertion (Primitive A) | author | schema validator accepts |
| H.0.8 Failure-mode issue labels (4 labels) | integration workflow | GitHub label creation + auto-file test | ops | 4 labels exist; ≥1 canary-* issue auto-filed |
| H.0.9 Idempotency checklist | new `.claude/rules/**` file | PR template inclusion + review-lane citation | ops | ≥1 PR review cites checklist |
| H.0.Phase0Readiness — ≥4 consecutive weekly passes | outcome metric | SC #22 — dashboard canary_pass_streak ≥4 | ops | streak displayed ≥4 at Phase 0 close |

### Primitive H.1 — Phase 1 reliability lab

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| H.1.1 `tests/reliability/replay.py` | new module under `tests/reliability/**` | `tests/reliability/test_replay.py` | author | reconstructs ≥1 lifecycle |
| H.1.2 Failure-injection scenarios (≥3) | new modules under `tests/reliability/**` | scenario-per-file pytest | author | all pass; ≥1 analyst-selected post-hoc |
| H.1.3 Automated postmortem generator | new module under `src/bid_euchre/ops/**` | integration test + ≥1 real incident draft | author | draft produced |
| H.1.4 Rollback-validation coverage for Phase 1 changes | integration workflow | SC #13 — every reversible Phase 1 change has tested rollback | ops | tested rollback list logged |
| H.1.5 Expanded canary suite (3-5 tasks) | integration workflow | canary suite runs on ≥2 material platform changes | ops | run log exists |
| H.1.6 Portability dry-run (design intent) | design intent | §10.7 readiness criterion + adapter-stub shim point | analyst | dry-run decision documented |

### §6.4 Preflight items (Phase 1a)

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| Preflight-1 Trace reconstruction | integration workflow | Primitive A event corpus reconstructs preflight task | ops | reconstruction exit 0 |
| Preflight-2 Event-driven monitoring latency | integration workflow | ≥1 event triggers operator signal within target | ops | latency logged within target |
| Preflight-3 Routing correctness | integration workflow | every sub-task routed correctly (Primitive B) | ops | log confirms |
| Preflight-4 Prompt-policy citation | integration workflow | every lane session cites a policy version (Primitive B) | ops | log confirms |
| Preflight-5 Messaging zero-loss + p95 | integration workflow | SC #8 — zero lost; p95 target | ops | log confirms |
| Preflight-6 Active triage issue filed | integration workflow | ≥1 issue created via event-driven triage | ops | issue exists |
| Preflight-7 Archivist candidate promoted | integration workflow | ≥1 candidate referencing preflight; ≥1 entry promoted | analyst | log confirms |
| Preflight-8 KB + agent-readability ≥7/10 | integration workflow + scorecard | ADR 001 floor + scorecard re-scored | analyst | ≥7/10 recorded |
| Preflight-9 Rollback exercised | integration workflow | 1 reversible change rolled back (goal #13) | ops | log confirms |
| Preflight-10 End-to-end data discipline | integration workflow | mutual-consistency check across Primitives A + E + C + task queue | ops | check exit 0 |
| Preflight-11 Repeat-task improvement probe | integration workflow | second pass cleaner by ≥1 metric (B.12) | analyst | metric delta logged |

### Cross-cutting / pattern enforcement

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| Pattern 10 `verification_contract/map.md` itself | new KB-class artifact | `verify_map_coverage.py` + `check verification-contract` lint | author | coverage ≥90%; lint clean |
| SC #21 map-review commit link | outcome metric | review_log.md entry + commit cited by orchestrator | orchestrator | review entry logged |
| SC #22 dogfood streak ≥4 | outcome metric | dashboard `canary_pass_streak` + `canary_last_pass` | ops | streak ≥4 at Phase 0 close |
| ADR 001 (pattern-reset evidence + scorecard floor) | ADR | Pattern 7 supersession path + Phase 0 observation evidence | orchestrator | ADR filed at Phase 0 kickoff |
| ADR 006 (auto-mode codification) | ADR | `.claude/rules/80_permission_model.md` + Phase 0 observation | orchestrator | ADR filed at Phase 0 kickoff |

## Coverage summary

- Rows: ~70 deliverables listed above (Primitive C rows expanded by Packet
  C-Exec from 8 to 19 with C.1.1–C.1.7 granular split + C.8–C.12 + C.V7 +
  C.P0R + retained C.Phase0Readiness; B.10–B.12 + Preflight-11 added by
  surrounding primitives). Section headers not counted.
- Coverage target: ≥90% of enumerated deliverable set (≥63 rows if the
  enumerated set is ~70; computed precisely by `verify_map_coverage.py`).
- Rows with placeholder/stub surfaces (TBD/TODO/FIXME/XXX): **zero**
  (placeholders fail the `check verification-contract` lint; must be
  resolved before Phase 0 close).

## Notes

- The map is the single file `agent_readability_lint.py check
  verification-contract` walks for coverage ratio; every row's
  Verification surface column must match a deliverable-class default
  from §10.9 Pattern 10 or carry an explicit justification in a Notes
  column (not yet present; add if needed during Phase 0 review).
- At Phase 0 close, the map is regenerated; `review_log.md` records
  drift since Phase 0 kickoff and any rows added or retired.
