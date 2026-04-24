# Primitive E Phase 0 Readiness — A-independent Subset

**Status:** PARTIAL — A-independent deliverables shipped via Packet E1
(narrowed). Remaining deliverables blocked on Primitive A Packet 3.
**Authored by:** author-d during Packet E1 (`b51accc33643`) execution,
per orchestrator recovery directive `7f0561631c8f4c29`.
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-E
**Shape:** `plans/steward_platform/5_primitive_E/shaping.md`
**Date:** 2026-04-24

---

## §1. Scope narrowing rationale

The original Packet E1 scope (shape §10.1) required consumption of a
`src/bid_euchre/ops/event_schema.py` module authored by Primitive A Packet 3.
Packet-receipt-time verification (shape §10.2 step 2) found that module
missing on `origin/main`, triggering the mandatory blocker-escalation
protocol.

Orchestrator recovery message `7f0561631c8f4c29` narrowed Packet E1 to the
**A-independent subset** — deliverables that do not consume the event
schema, dispatcher, or §9.7 IDs and therefore do not need to wait on
Primitive A.

This document enumerates what shipped vs. what deferred, maps each shipped
deliverable to its verification surface per Pattern 10, and records the
unblock path for deferred items.

## §2. Shipped in Packet E1 (A-independent)

### §2.1 Bus-debt closeout — PRs already merged

All three bus-debt PRs referenced by shape §2 merged before Packet E1
dispatch (PRs #2739, #2741, #2736). Issues #2689, #2690, #2691 remained
open due to `Refs #N` usage in the commit messages rather than `Fixes #N`;
Packet E1 closes them with verified-close evidence per
`.claude/rules/deferred/55_issue_closure.md` § Tier 2.

| Deliverable | Verification surface | Status |
|---|---|---|
| Issues #2689, #2690, #2691 closed with evidence | `gh issue view <N>` shows verification-evidence comment and `state: closed` | Evidence posted via `verify_issue_closure.py prove` during Packet E1 |

### §2.2 Hook documentation + disposition table

| Deliverable | Verification surface |
|---|---|
| `.claude/hooks/README.md` § Hook Execution Order | Grep for the section heading; present in file |
| `.claude/hooks/README.md` § Per-Hook Scope Summary | Grep for the section heading; 34 rows in the summary table |
| `.claude/hooks/README.md` § Conditional-Hook Migration (Disposition Table) | `tests/unit/test_hooks_inventory.py` — 1-to-1 correspondence between on-disk hooks and table rows (5 tests) |

### §2.3 Conditional-hook migration (narrowed)

Shape §6.4 originally specified "≥8 hook migrations" in Packet E1. Actual
survey found only one unambiguously-safe migration — the rest were already
narrow, event-scoped, dispatched, or justified-universal. Ship what is safe;
document the rest in the disposition table. The README.md § "Why only one
migration?" subsection captures the rationale transparently.

| Deliverable | Verification surface |
|---|---|
| `post-write-check.sh` consolidated `Write`+`Edit` → `Edit\|Write` | `tests/unit/test_settings_hooks_contract.py::test_no_split_registrations_under_related_matchers` — regression lock on re-splitting |
| No universal matcher on `PreToolUse`/`PostToolUse` without the `retained-universal-justified` sentinel | `tests/unit/test_settings_hooks_contract.py::test_universal_matchers_on_high_volume_events_are_justified` |
| Hook command paths in settings.json point to real files | `tests/unit/test_settings_hooks_contract.py::test_every_hook_command_path_exists` |
| No duplicate registrations of the same script under the same (event, matcher) pair | `tests/unit/test_settings_hooks_contract.py::test_no_duplicate_registrations` |

### §2.4 `triaging-issues` skill scaffold

Per orchestrator directive clause (3), the skill integration is **scaffold
only** — the live runtime is blocked on Primitive A's event schema.

| Deliverable | Verification surface |
|---|---|
| `.claude/skills/triaging-issues/SKILL.md` § Programmatic Invocation (new) | Grep for "Programmatic Invocation" heading |
| `scripts/internal/triage_cli.py` with `TriageInput`, `TriageResult`, `TriageRuntimeUnavailable`, `file_or_recur` scaffold | `tests/unit/test_triage_cli_scaffold.py` — 8 tests covering dataclass shape, vocabulary, scaffold-raise-behavior, public-API exports |

### §2.5 ADR 004 — hook migration boundary

| Deliverable | Verification surface |
|---|---|
| `plans/steward_platform/adrs/004-http-hooks-migration-boundary.md` | File exists; §2 disposition table scores all 35 hooks; §3 summary shows destination counts by band; §4 migration sequence enumerates Phase 0 / Phase 1 / Phase 2+ steps |
| ADR index entry (`plans/steward_platform/adrs/README.md`) updated | Row 004 shows status **FILED** |

## §3. Deferred — blocked on Primitive A Packet 3

These deliverables from shape §10.1 are deferred to a follow-up packet after
Primitive A's event schema + dispatcher merge. Each row states the concrete
A-dependency that blocks it.

| Deferred deliverable | A-dependency | Unblock path |
|---|---|---|
| `src/bid_euchre/ops/event_reader.py` | Reads event records; depends on `event_schema.py` field names and JSONL layout | Land after A ships `src/bid_euchre/ops/event_schema.py` |
| `src/bid_euchre/ops/bus_latency.py` | Aggregates p50/p95 over bus delivery events; depends on A's event stream | Land after A's dispatcher emits bus-delivery events |
| `src/bid_euchre/ops/active_triage.py` | Consumes 5 signal classes from A's event stream | Land after A's dispatcher emits signal-class events |
| `src/bid_euchre/ops/dashboard.py` Bus panel | Reads `bus_latency` output | Land with bus_latency |
| `scripts/internal/ops.py triage` subcommand group | Operator-surface for active_triage | Land with active_triage |
| `tests/unit/test_event_reader.py` | Tests consume event fixtures with A's schema | Land with event_reader |
| `tests/unit/test_bus_latency.py` | — | Land with bus_latency |
| `tests/unit/test_active_triage.py` | — | Land with active_triage |
| `tests/integration/test_active_triage_rollback.py` | Requires feature flag + inbox state interaction | Land with active_triage |
| `tests/integration/test_active_triage_e2e.py` (skipped-by-default) | Requires GH integration + full event pipeline | Land after active_triage |
| `.claude/skills/active-triage/SKILL.md` | Thin wrapper invoking `ops.py triage run` | Land with triage subcommand |
| `scripts/internal/triage_cli.py` live runtime (replaces scaffold) | Dedupe queries + issue-creation + recurrence comments rely on A's event IDs and fingerprints | Land after A's `incident_fingerprint` field shipped |
| `.claude/rules/feature_flags.md` `STEWARD_ACTIVE_TRIAGE_ENABLED`, `STEWARD_BUS_PANEL_ENABLED` | Flags correspond to A-dependent surfaces | Land with those surfaces |

### §3.1 Deferred from shape §8 Phase 0 Readiness criteria

The four §5-E Phase 0 Readiness criteria the shape specifies (shape §8):

| #  | Criterion | Status | Reason |
|----|---|---|---|
| 1 | All three follow-up PRs merged; bus closeout debt resolved | **READY** | PRs merged pre-packet; issues closed with evidence in Packet E1 (§2.1) |
| 2 | Bus p50/p95 metrics published | **DEFERRED** | Requires `bus_latency.py` + event_reader (§3 row 2) |
| 3 | Active-triage wiring live for ≥4 event classes | **DEFERRED** | Requires `active_triage.py` + A's signal events |
| 4 | Rollback path validated via feature flag | **DEFERRED** | Requires `active_triage.py` + flag wiring |

Packet E1 (narrowed) satisfies criterion 1 and establishes the Pattern 10
scaffolding for criteria 2–4 (disposition table + ADR + scaffold runtime).
The formal Phase 0 Readiness gate for §5-E cannot close until criteria 2–4
ship; those are A-blocked.

## §4. Pattern 10 verification-surface summary

Every deliverable in §2 names a concrete surface per Pattern 10. Rollup:

| Surface class | Count | Examples |
|---|---|---|
| Unit test path | 2 files, 19 tests | `test_hooks_inventory.py` (5), `test_settings_hooks_contract.py` (6), `test_triage_cli_scaffold.py` (8) |
| Named file grep | 4 | README § heading greps, ADR file existence, SKILL.md heading grep |
| ADR disposition tables | 1 (ADR 004) | `§2. Per-hook disposition` (35 rows) |
| Issue-evidence commands | 1 | `verify_issue_closure.py prove` output on issues #2689/#2690/#2691 |

No deliverable in §2 carries a `Verification: TBD` marker.

## §5. Rollback guidance

Each §2 deliverable is independently reversible per Pattern 7:

| Deliverable | Rollback command |
|---|---|
| `post-write-check.sh` consolidation | `git revert <commit SHA of settings.json matcher diff>` restores split `Write` + `Edit` registrations |
| `.claude/hooks/README.md` disposition table | `git revert <commit SHA>` restores prior README |
| `scripts/internal/triage_cli.py` scaffold | `git rm scripts/internal/triage_cli.py tests/unit/test_triage_cli_scaffold.py` + remove SKILL.md section |
| ADR 004 filing | `git revert <commit SHA>` + restore README.md row to status `Pending` |
| Issue closure on #2689/#2690/#2691 | `gh issue reopen <N>` — no code revert needed |

Trace signature confirming rollback: `tests/unit/test_hooks_inventory.py`
and `tests/unit/test_settings_hooks_contract.py` start failing (missing
disposition table or regression on matcher split); `triage_cli` import
raises `ModuleNotFoundError`.

## §6. Completion marker

When Primitive A Packet 3 merges, the follow-up packet that lands §3's
deferred deliverables should supersede this document by creating
`plans/steward_platform/5_primitive_E/phase0_closeout.md` with the full
Phase 0 Readiness signoff. This document remains the contemporaneous
record of the A-independent half.

## References

- `plans/steward_platform/5_primitive_E/shaping.md` §5–8 (design source)
- `plans/steward_platform/governing_plan.md` §5-E (Primitive E work)
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 7 / 10
- `plans/steward_platform/adrs/004-http-hooks-migration-boundary.md`
- `.claude/hooks/README.md` § Conditional-Hook Migration
- `.claude/rules/deferred/55_issue_closure.md` (Tier 2 closure)
- Orchestrator recovery message `7f0561631c8f4c29` (scope-narrowing directive)
