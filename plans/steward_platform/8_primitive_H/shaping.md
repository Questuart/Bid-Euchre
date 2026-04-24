# Shaping: Primitive H Execution Spec — Reliability Lab, Replay Harness, and Canary Suite (H.0 + H.1)

**Date:** 2026-04-24
**Lane:** analyst-b
**Packet:** `8f8374a5c79a` (Primitive H pre-shape — H.0 + H.1 execution packets belong to later packets, named Packet H.0-Exec and Packet H.1-Exec herein)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-H (lines 608–687)
**Sibling artifacts:**
- `plans/steward_platform/canary_scenarios/dogfood.md` (SP-0-H0-dogfood-v1 sub-plan; canonical canary spec, already authored via Packet 2b)
- `plans/steward_platform/verification_contract/shaping.md` §5 (canary design rationale, cadence, pass metrics, failure taxonomy — the upstream shape dogfood.md derives from)
- `plans/steward_platform/1_primitive_A/shaping.md` (event-schema v1.N + `ops/events.py` dispatcher; H coordinates tightly with A for replay + canary events)
- `plans/steward_platform/3_primitive_C/shaping.md` §4.1 (INDEX regen + KB integration points the canary exercises)
- `plans/steward_platform/6_primitive_F/shaping.md` (F-forward / F-debt boundary pattern reused herein for H.0 / H.1 split)
- `plans/steward_platform/0_hardening/sub/rework_spec.md` (Primitive G Phase-0 changes that H's rollback-validation coverage in H.1 defers to G, not H)
- `plans/steward_platform/adrs/` (ADR 006 auto-mode + future ADR 010 KB-adoption — replay harness assumptions about classifier activation + KB promotion fingerprints)
- `.claude/skills/run-canary/SKILL.md` + `.claude/skills/canary-review/SKILL.md` (stubs already landed via Packet 2b; Packet H.0-Exec promotes stubs to full impl)

**Status:** DESIGN-SPEC — no code, no event emissions, no cron registration, no replay harness, no failure-injection scenarios are authored in this artifact. Produces two execution-ready briefs (Packet H.0-Exec for Phase 0 closeout gating; Packet H.1-Exec for mid-Phase-1 dispatch).

**Purpose:** Pre-shape Primitive H's execution across both phases so the orchestrator can dispatch **Packet H.0-Exec** to an author/ops lane pair as soon as Primitive A's Packet 3 merges (event schema live), and **Packet H.1-Exec** once the proving run begins. Zero additional shaping work required between dispatch and author pickup. Mirrors the Packet 2a → Packet 2b pattern (verification-contract) and the Packet F-shape → Packet 11 pattern (Primitive F).

---

## §1. Scope of this document

This is a **shaping document**. It produces two execution-ready specifications:

1. **Packet H.0-Exec** — Primitive H.0 Phase 0 mini-canary + idempotency checklist execution (§4, §5, §6, §10).
2. **Packet H.1-Exec** — Primitive H.1 Phase 1 reliability suite execution (§7, §8, §9, §11).

### §1.1 What this document specifies

1. The H.0 / H.1 phase-boundary and native-substrate integration (§2, §3).
2. **H.0 work:**
   - §4 Canary execution — **references** `plans/steward_platform/canary_scenarios/dogfood.md` for the core spec; does not duplicate. Adds execution-packet detail.
   - §5 Idempotency checklist — authored in full here (dogfood.md does not cover; listed as sibling H.0 deliverable in §5-H.0 Work bullet 7).
   - §6 Failure-mode auto-issue-filing integration — execution detail beyond dogfood.md §7 (mapping of failure-mode → GitHub labels → ops alert routing).
3. **H.1 work:**
   - §7 Replay harness spec (`tests/reliability/replay.py`): lifecycle reconstruction algorithm, schema v1.N-to-v1.M compatibility assertion, proving-run task selection protocol.
   - §8 Failure-injection scenarios (≥3 for Phase 1 Validation): lane stall, dead-letter, stuck worktree, orphan cron, review-coordinator crash, Telegram outage. Full per-scenario assertion script spec.
   - §9 Postmortem generator: template + invocation against replay artifact + incident-file structure; expanded canary suite design (3–5 tasks beyond dogfood-v1).
4. **Execution packets:**
   - §10 Packet H.0-Exec: files created/modified, order of operations, validation commands, coordination, success criterion.
   - §11 Packet H.1-Exec: same shape for the reliability lab.
5. Self-review against completeness criteria (§12).
6. Verification Plan per Pattern 10 mandate (§13).
7. Risks + mitigations (§14).
8. Phase 2 Decision Inputs per §15.2 schema (§15).
9. References (§16).

### §1.2 What this document does NOT do

- **Duplicate `plans/steward_platform/canary_scenarios/dogfood.md`.** That sub-plan is the canonical canary spec. This shaping doc references it for §3 Work, §6 Pass metrics, §7 Failure behaviors, §8 Cadence, §9 Dashboard integration, §10 Event schema additions, §13 Rollback. Duplication would create dual-source-of-truth drift; this doc instead enumerates the *execution-packet* scope that exercises dogfood.md into reality.
- **Re-design the canary scenario shape.** `verification_contract/shaping.md` §5 is the design authority (9 pass metrics, 4 failure behaviors, sparkline dashboard integration, expected-event-type-set hash). This doc inherits; does not revise.
- **Author the replay harness algorithm in full code.** §7 specifies the algorithm + data contract + invocation interface; Packet H.1-Exec authors the Python module.
- **Decide the failure-injection scenario set.** Governing plan §5-H.1 Phase 1 Validation requires ≥3 scenarios **including at least one analyst-selected post-hoc during Phase 1 after A, B, E ship** (Q3 clarification, goal-surfaced anti-Goodharting measure). This doc specs the first 2 scenarios fully (scenarios 1–2, deterministic) and specs the ≥1 post-hoc slot as a selection protocol, not a concrete scenario. Analyst-selection happens in Phase 1 mid-run, not at shaping time.
- **Cover H-adjacent idempotency or canary work claimed by other primitives.** Specifically:
  - Primitive G owns Phase 0 rollback-validation coverage (§5-G Work). H.1's rollback-validation coverage is Phase-1-specific, not a retroactive re-scope of G.
  - Primitive A owns event schema v1 through v1.N. H coordinates with A on canary_run_* event type additions (§10.5 cross-ref); this doc asserts the coordination path, not the schema itself.
  - Primitive E owns active-triage issue-filing machinery. Canary failure modes in §6 plug into E's existing filing flow; this doc specifies the plug, not the flow.
  - Primitive B owns prompt-policy versioning. The canary asserts prompt-policy trace citation (shaping §5.3 metric #4 via `task_completed` event); B's policy-version emission is B's concern.

### §1.3 Motivation (one paragraph)

Primitive H is the substrate's *self-exercising verification* layer. H.0 (Phase 0) runs a single bounded scenario weekly and gates Phase 0 closeout on a ≥4 consecutive pass streak (SC #22) — proving that the verification surfaces mandated by Pattern 10 (§10.9) actually fire end-to-end, not just syntactically exist. H.1 (Phase 1) extends this into a full reliability lab: replay harness for lifecycle reconstruction, failure-injection scenarios that hit deliberate-break paths, automated postmortem generation from replay artifacts, and an expanded 3–5 task canary suite. Pre-shaping H means: the moment Primitive A ships `ops/events.py` dispatcher + canary_run_* event-type registrations (Packet 3 merge trigger), Packet H.0-Exec dispatches to an author/ops lane pair and the weekly cron starts ticking. The ≥4-pass streak cannot start counting until the canary is implemented; every week of delay is a week of Phase 0 closeout delay. H is therefore dispatch-critical-path during Phase 0 wrap-up.

---

## §2. Relationship to §5-H and canonical sub-plans

§5-H of the governing plan (lines 608–687) is the binding reference. This shaping doc operationalizes the split-phase structure already committed in the governing plan:

| §5-H / canonical sub-plan | Where it lands in this doc | Authoritativeness |
|---|---|---|
| §5-H.0 Work bullets 1–6 (canary impl, skills, cron, hook, dashboard, event schema) | §4 (by reference to `canary_scenarios/dogfood.md`) | dogfood.md is canonical; this doc is execution-packet scope |
| §5-H.0 Work bullet 7 (idempotency checklist) | §5 (authored in full here) | this doc is canonical |
| §5-H.0 Phase 0 Readiness (11 items) | §10 Packet H.0-Exec success criterion | §5-H.0 is canonical; this doc sequences |
| §5-H.1 Work (replay, failure-injection, postmortem, rollback-validation, expanded canary, portability intent) | §7, §8, §9 (authored in full here) | this doc is canonical for H.1; §5-H.1 is the top-level remit |
| §5-H.1 Phase 1 Readiness + Phase 1 Validation | §11 Packet H.1-Exec success criterion | §5-H.1 is canonical |
| §11-H.0 kill criterion (fails ≥2 weekly passes in any 4-week window) | §14 risk row #1 + §15 Decision Inputs | governing plan is canonical |
| §11-H.1 kill criterion (<2 replay scenarios / <3 failure-injection / canary never runs on material change) | §14 risk row #2 + §15 Decision Inputs | governing plan is canonical |
| SC #22 (≥4 consecutive weekly passes) | §10 Packet H.0-Exec success criterion | governing plan is canonical |
| §10.7 design coupling (H.1 Validation gates Phase 2 portability) | §9.5 + §15 Decision Inputs | governing plan is canonical |

### §2.1 No-duplication rule with `canary_scenarios/dogfood.md`

`plans/steward_platform/canary_scenarios/dogfood.md` is the canonical canary sub-plan (SP-0-H0-dogfood-v1). It specifies:
- §2 task spec
- §3 Work (9 bullets)
- §6 Pass metrics (9 assertions)
- §7 Failure behaviors (4 modes)
- §8 Cadence
- §9 Dashboard integration
- §10 Event schema additions (4 event types)
- §12 Verification Plan (per-work-bullet table)
- §13 Rollback (including canary self-reference exclusion)

This shaping doc's §4, §6, §10 add *execution-packet* scope that dogfood.md explicitly leaves to "H.0 follow-on packets" (dogfood.md §3 lists §3.2–§3.8 as "H.0 follow-on"). The dogfood.md sub-plan was scaffolded by Packet 2b at the verification-contract level; the *impl* lives in Packet H.0-Exec (this doc's §10 output). No edit to dogfood.md is expected from Packet H.0-Exec unless scope surprises emerge (§10.4 coordination clause).

### §2.2 Goals served

- #15 (reliability / replay / failure-injection): primary.
- #1 (self-improvement loop): H's failure-injection + postmortem output feed the improvement-quality metrics.
- #2 (data-sufficiency / proving run): replay harness reconstructs proving-run lifecycles for evidence recovery.
- #11 (rollback paths): H.1 rollback-validation coverage for Phase 1 changes; H.0 canary exercises rollback end-to-end as pass-metric #8.
- #13 (kill criteria observable): H's canary-fail / canary-silent paths produce operator-visible kill signals.

---

## §3. H.0 / H.1 boundary + native-substrate integration

### §3.1 H.0 vs H.1 scope (reprise for packet-spec consumers)

**H.0 (Phase 0) — mini-canary + idempotency checklist:**
- **Dispatch trigger:** Primitive A Packet 3 merged (event-schema dispatcher live).
- **Timeline:** Phase 0 weeks 1–N, where N ≥ 4 for streak-gate closeout.
- **Blocks:** Phase 0 closeout (SC #22 gate).
- **Blocked by:** Primitive A `ops/events.py` + v1.0 schema; Primitive B dispatch machinery (for task-packet lifecycle assertions in metric #2); Primitive C KB integration (for metric #5 archivist candidate + metric #6 INDEX regen); Primitive E failure-issue filing (for canary-fail / canary-slow / canary-silent / canary-schema-drift auto-filing).

**H.1 (Phase 1) — full reliability lab:**
- **Dispatch trigger:** Phase 1 kickoff (proving run underway; ≥1 task lifecycle captured in event corpus).
- **Timeline:** Phase 1 ongoing; Phase 1 Readiness mid-run; Phase 1 Validation at end of Phase 1.
- **Blocks:** §10.7 Phase 2 portability decision.
- **Blocked by:** Primitive A v1.0 schema stable; Primitive D archivist delivering candidate files (for ≥1 replay-reconstructed lifecycle); proving-run task selection complete.

### §3.2 Native-substrate integration (draft 8 Tier S inventory, §5-H)

Per §5-H "Native-substrate integration (draft 7 Tier S)":

| Native feature | H usage | Deliverable |
|---|---|---|
| **Monitor tool** | Drives replay-assertion polling (watch events until target state); also canary-trigger monitoring for prompt-policy / routing / messaging changes | H.1 §7.4 replay-assertion loop; H.0 conditional-hook watches |
| **Read-tool token reductions / large tool result persistence** | Changes the cost of "reconstruct a lifecycle"; H.1 replay thresholds MUST be set against post-reduction baseline | H.1 §7.2 threshold-setting step coordinates with Primitive F baseline re-capture |
| **Conditional hooks** | Canary-suite reruns triggered by material platform changes use native conditional hooks, not bespoke CI wiring | H.0 §4.3 trigger-path list (already in dogfood.md §8) |
| **`/go`-style verification pattern** | Canary suite + idempotency checklist work as platform-level verification surface; author lanes verify their own work before slice-complete | H.0 §5 idempotency checklist is the author-lane surface; canary is the platform-level surface |

**Three-tier native-substrate preference (§10.9 Pattern 2):** native-first is honored. `Monitor` (native) drives replay polling; no bespoke polling loop. Conditional hooks (native) drive canary triggers; no bespoke CI wiring. `Read-tool token reductions` (native, Claude Code changelog Tier S) are consumed as Phase-1-baseline re-capture inputs; no bespoke token accounting.

### §3.3 Cross-primitive coordination summary (H as consumer)

| Upstream primitive | What H consumes | Coordination artifact |
|---|---|---|
| **Primitive A** (event schema + `ops/events.py` dispatcher) | v1.0 schema; canary_run_* event-type registrations; replay-harness schema-compat assertions | Packet 3 merge gates H.0-Exec dispatch; H.1 replay harness imports A's schema validator |
| **Primitive B** (prompt-policy registry + dispatch) | Prompt-policy version emission in task traces (canary metric #4 indirectly via task lifecycle) | B.3 registry scaffolding; H.0-Exec assumes policy-version emission live |
| **Primitive C** (KB + archivist C↔D contract) | `knowledge/INDEX.md` regen (metric #6); `knowledge/_candidates/<date>.md` archivist output (metric #5) | C.11 contract; H.0-Exec assumes C.1 + C.11 live |
| **Primitive D** (archivist nightly inflow) | Candidate file generation within 24h of merge (metric #5) | D's inflow schedule; H.0-Exec assumes D.1 inflow loop live |
| **Primitive E** (active-triage issue-filing) | `canary-fail` / `canary-slow` / `canary-silent` / `canary-schema-drift` label auto-filing | E's filing primitive; H.0-Exec §6 consumes the filing API |
| **Primitive F** (token-economy observability) | Baseline re-capture after Read-tool reductions (replay-threshold calibration input) | F baseline in `plans/steward_platform/0_hardening/baseline.md` §3; H.1 §7.2 reads |
| **Primitive G** (rollback validation Phase 0) | G covers Phase 0 rollback-validation; H.1 covers Phase 1 rollback-validation | Clean phase boundary; H.1 does not re-cover Phase 0 changes |

---

## §4. H.0 canary execution — references dogfood.md, enumerates additive scope

### §4.1 dogfood.md-owned scope (NOT in this packet's shape)

Per §2.1 no-duplication rule. Canonical content lives in `plans/steward_platform/canary_scenarios/dogfood.md`:

- §2 task spec (last_verification_run field edit + unit test + mini-ADR + PR + archivist confirmation + rollback)
- §6 pass metrics (9 assertions)
- §7 failure behaviors (4 modes with dashboard status values)
- §8 cadence (weekly cron `0 9 * * MON` + on-demand + conditional-hook)
- §9 dashboard fields + sparkline panel spec
- §10 event schema additions (4 canary_run_* types)
- §13 rollback (feature flag + self-reference exclusion)

Packet H.0-Exec **reads** dogfood.md as its scope-declared spec; does not re-author.

### §4.2 Additive scope (this doc canonical)

Packet H.0-Exec implements dogfood.md's §3 Work bullets §3.1–§3.9 (all marked "H.0 follow-on" in the sub-plan). Concrete deliverables:

| # | Deliverable | Home (path) | Size estimate |
|---|---|---|---|
| 1 | `/run-canary` skill promotion from stub to full impl | `.claude/skills/run-canary/SKILL.md` (modify; stub landed via Packet 2b) | ~80 LOC additions (Phase 1 invocation; Phase 2 recording; Phase 3 auto-file) |
| 2 | Canary packet generator | `tests/reliability/canaries/dogfood_v1_packet.py` (new) | ~60 LOC (builds the canary task packet shape with canary_id metadata + dispatch trigger) |
| 3 | Pass-metric assertion script | `tests/reliability/canaries/dogfood_v1.py` (new) | ~200 LOC (9 assertion functions + expected-event-type-set hash computation + elapsed-time budget + 4 failure-mode routing) |
| 4 | Canary-assertion unit tests | `tests/reliability/canaries/test_dogfood_v1.py` (new) | ~120 LOC (seeded fixtures covering all 9 metrics + hash-mismatch + 4 failure routing paths) |
| 5 | Dashboard integration | `src/bid_euchre/ops/dashboard.py` (modify) | ~40 LOC additions for `canary_last_pass` / `canary_pass_streak` / `canary_last_status` / `canary_last_elapsed` fields + sparkline renderer for 4 sub-metrics |
| 6 | Canary state file | `.claude/runtime/canary_state/dogfood_v1.json` (new; gitignored path) | persisted state: last run, streak, last status, hash-pin, elapsed history (last 8) |
| 7 | Event schema additions coordination | Edit to `src/bid_euchre/ops/events.py` or `schema.json` (depending on A's Packet 3 landing shape) — add `canary_run_start` / `canary_run_complete` / `canary_run_fail` / `canary_rollback_complete` | ~30 LOC schema entries |
| 8 | Conditional hook for material-platform-change | `.claude/hooks/material-platform-change-canary.sh` (new) + `.claude/settings.json` registration | ~40 LOC shell; 1 hook registration entry |
| 9 | Weekly cron | ops lane `/loop 7d /run-canary` — installed by running `/loop 7d /run-canary` in the ops pane at Phase 0 kickoff (not a file deliverable; a tmux/cron setup action with evidence screenshot) | 0 LOC; ops-action step |
| 10 | Failure-mode label creation | 4 GitHub labels: `canary-slow` / `canary-fail` / `canary-silent` / `canary-schema-drift` — created via `gh label create` | 0 LOC; ops-action step |
| 11 | Auto-issue-filing integration | `scripts/internal/file_canary_issue.py` (new) — wraps `gh issue create` with label + ops-alert-push for `canary-fail` only | ~50 LOC |
| 12 | `/canary-review` skill promotion | `.claude/skills/canary-review/SKILL.md` (modify; stub landed via Packet 2b) — add Phase 2 audit protocol + audit-log template + lookback query impl | ~60 LOC additions |
| 13 | Audit log file | `plans/steward_platform/canary_scenarios/audit_log.md` (new; empty template) | ~20 LOC template |

**Subtotal H.0 canary: ~700 LOC across 10 new files + 3 modified files + 2 ops-action steps.**

### §4.3 Dependency on Primitive A Packet 3 merge

Packet H.0-Exec CANNOT dispatch until Primitive A Packet 3 merges. Strict precondition:

- `src/bid_euchre/ops/events.py` dispatcher present with v1.0 schema registered.
- `canary_run_start` / `canary_run_complete` / `canary_run_fail` / `canary_rollback_complete` event types MUST be addable as v1.N additive (Primitive A §5-A event-schema-versioning policy).
- If A's Packet 3 lands with a schema that does not permit v1.N additions (e.g., closed-enum event types), H.0-Exec escalates a blocker to orchestrator and Primitive A's schema is revised before H.0-Exec proceeds. **Escalation path:** blocker message to orchestrator with subject `Primitive H blocked on A event-schema additive compatibility`.

### §4.4 Canary self-reference exclusion (mechanism decision)

dogfood.md §13 requires the canary's own revert-PR to NOT re-trigger a canary run (else recursion). The mechanism is an H.0 implementation decision; this shaping doc picks **Option A — PR label** as the default:

**Option A (adopted): PR label `canary-rollback-pr` attached to any revert PR opened by the canary runner.** Conditional-hook evaluator in `.claude/hooks/material-platform-change-canary.sh` reads PR labels via `gh pr view --json labels` at trigger time and exits 0 (no trigger) if `canary-rollback-pr` is present.
- Pros: simple; no settings.json / hook internals to touch beyond evaluator; `gh` is already in the hook's runtime scope per existing hooks.
- Cons: label must be attached before hook fires (race window); canary runner controls label application so this is deterministic in practice.

**Option B (rejected): commit-footer `Canary-Rollback: true`.** Pros: commit-local, no GitHub API needed. Cons: hook evaluator would need to parse commit-messages across PR commit range — more brittle than label check.

**Option C (rejected): metadata bit in canary state file.** Pros: canary-owned state. Cons: requires hook to read canary state file, which crosses surface boundaries and is fragile.

Packet H.0-Exec author MAY choose B or C if Option A surfaces an operational block; rationale must be committed to PR body. Default path: Option A.

### §4.5 State-file design

`.claude/runtime/canary_state/dogfood_v1.json`:

```json
{
  "canary_version": "dogfood-v1",
  "last_run_id": "dogfood-v1-2026-05-04-0900",
  "last_run_completed_at": "2026-05-04T09:05:12Z",
  "last_run_status": "success",
  "last_pass_timestamp": "2026-05-04T09:05:12Z",
  "pass_streak": 4,
  "elapsed_history": [312, 298, 305, 331, 316, 297, 321, 312],
  "event_type_hash": "sha256:abc123...",
  "event_type_hash_pinned_at": "2026-04-28T09:00:00Z"
}
```

**Invariants:**
- `pass_streak` increments only on `last_run_status == "success"`; resets to 0 on `fail`; *does not* increment on `slow` or `schema-drift`.
- `elapsed_history` FIFO cap 8; used for sparkline rendering + `2× median` soft-fail threshold.
- `event_type_hash` pinned at the last `success` run; re-pinned on operator-approved schema addition via `/canary-review`.

### §4.6 Daylight-saving-time / timezone caveat (scope hazard)

Weekly cron `0 9 * * MON` fires in the ops-lane host's local timezone. If the ops host is PST, DST transitions shift canary run time ±1h relative to UTC-based event timestamps. Acceptance: the canary is indifferent to local-time drift (assertions are elapsed-time-based, not wall-clock-based), but `canary_last_pass` dashboard display SHOULD show UTC to avoid operator confusion across DST boundaries. **Packet H.0-Exec default:** all dashboard timestamp displays in UTC; all state-file timestamps in ISO-8601 UTC.

---

## §5. H.0 idempotency checklist — authored in full

### §5.1 Motivation

§5-H.0 Work bullet 7 requires a static PR-review checklist at `.claude/rules/idempotency_checklist.md` covering every replay/interrupt-sensitive operation. This is Phase 0 scope because it is a static rule-file (no runtime dependency on Phase 1 events). It is H.0 scope (not H.1) because the checklist gates PR merges during Phase 0 closeout and feeds the Phase 1 proving-run's idempotency-discipline Validation bullet.

### §5.2 Scope

Operations that MUST be idempotent per the checklist (non-exhaustive seed list):

1. **Message send** (`src/bid_euchre/ops/message_bus.py`): sending the same message twice should not double-dispatch the receiver.
2. **Task status update** (`src/bid_euchre/ops/task_queue.py`): transitioning a packet to `completed` twice should be no-op on second call.
3. **Event emission** (`src/bid_euchre/ops/events.py`): emitting the same event twice should not double-count in rollups.
4. **File write** — particularly state files, PR artifacts, generated docs (`INDEX.md`, `MEMORY.md`): atomic-rename pattern, not naive open-for-write.
5. **Hook invocation** (`.claude/hooks/**`): any hook that fires on a PR event should tolerate duplicate firing (e.g., GitHub's at-least-once delivery).
6. **Cron/loop registration** (ops `/loop` mechanism): running `/loop 7d /run-canary` twice should not register two crons.
7. **KB promotion** (archivist C↔D contract): promoting the same candidate file twice should be detect-and-skip, not append.
8. **Branch/worktree creation**: `git worktree add` on an existing name should be idempotent or explicitly fail-fast with a clear message.
9. **GitHub API writes** (`gh pr create`, `gh issue create`, `gh label create`): retry-safe with same inputs.
10. **Claude Code slash-command invocation** from hooks: same command twice should not double-execute.

### §5.3 Checklist format

File: `.claude/rules/idempotency_checklist.md`. Format:

```markdown
# Idempotency Checklist — PR Review

> Required PR-review item per §5-H.0 governing plan. Review lane verifies.

For every operation in the diff that matches a row below, confirm:
- [ ] Idempotent: running twice produces the same observable state as running once.
- [ ] Retry-safe: concurrent retries do not corrupt state.
- [ ] Observable: the second call is traceable (e.g., logged as "no-op, already applied").

## Rows

| # | Operation class | Files / surfaces affected | Idempotency mechanism |
|---|---|---|---|
| 1 | Message send | `src/bid_euchre/ops/message_bus.py` | dedup key = (from, to, type, summary, task-id) within 5 min window |
| 2 | Task status update | `src/bid_euchre/ops/task_queue.py` | state-machine guard: transition only if current state matches expected |
| 3 | Event emission | `src/bid_euchre/ops/events.py` | dedup key = (event_type, trace_id, lane_id, canary_id) within emission window |
| 4 | File write (state files) | `.claude/runtime/**/*.json`, `MEMORY.md`, `knowledge/INDEX.md` | atomic-rename (write to temp, fsync, rename) |
| 5 | Hook invocation | `.claude/hooks/**` | explicit at-least-once tolerance; lock file if critical section |
| 6 | Cron/loop registration | ops `/loop` state | check-then-register; `/loop list` before `/loop N` |
| 7 | KB promotion | `knowledge/_promoted/**` via archivist | ADR 010 contract: skip-if-present |
| 8 | Branch/worktree creation | `git worktree add`, `git checkout -b` | fail-fast with clear message; never silently branch from wrong base |
| 9 | GitHub API writes | `gh pr create` / `gh issue create` / `gh label create` | pre-check existence; use `gh` idempotent variants where available |
| 10 | Claude Code slash-command from hook | hook scripts invoking `claude ... /skill` | dedup via trace-ID; hook logs before-and-after state |

## PR Template Integration

PR template (`.github/pull_request_template.md`) includes:

```
## Idempotency

- [ ] I reviewed `.claude/rules/idempotency_checklist.md` and confirmed my changes are idempotent, retry-safe, and observable.
- [ ] For any row that does NOT apply, I explicitly noted it in PR body or confirmed no changed file matches the row's surface column.
```

## Authors: How to cite this checklist

In PR body `Verification Performed` section, paste the checklist as completed, crossing out rows that do not apply. Example:

- [x] Row 3 (event emission): added `canary_run_start` dedup via (event_type, canary_id) key
- [~] Row 1 (message send): no message-send calls in this diff
- [~] Row 7 (KB promotion): no archivist/KB changes in this diff

## Review lane: How to verify

Grep the PR diff for matches against the surfaces column. For each match, confirm the author either addressed idempotency or noted non-applicability. Reject PR if:
- A matching surface is touched and the checklist row is not mentioned in PR body.
- A checklist mechanism is omitted (e.g., naive `open(...)` for a state file).
```

### §5.4 Phase 0 wiring

- Checklist committed at `.claude/rules/idempotency_checklist.md`.
- PR template `.github/pull_request_template.md` extended with `## Idempotency` section per §5.3.
- Review-lane precheck added to `scripts/internal/review_driver.py` (or equivalent) asserting: if PR diff touches any surface row 1–10, PR body must contain the `## Idempotency` section with at least one checkbox state (checked or marked `[~]` non-applicable). Severity: **WARN** (not BLOCK; Phase 0 gets authors used to the checklist without merge-blocking).

### §5.5 Phase 1 wiring

§5-H.0 Work bullet 7 states "Zero PRs merged without the idempotency checklist filled during the proving run (for PRs touching replay/interrupt-sensitive code)." Phase 1 Validation tightens the WARN to BLOCK for surfaces rows 1–4 (message, task, event, state-file) — the highest-impact idempotency hazards during a proving run. Rows 5–10 stay WARN.

---

## §6. H.0 failure-mode auto-issue-filing integration

### §6.1 Routing matrix

Per dogfood.md §7 + run-canary SKILL.md Phase 3. Failure modes route through `scripts/internal/file_canary_issue.py` (new; §4.2 deliverable #11):

| Failure mode | GitHub label | Issue priority | Body template | Ops alert push | Telegram operator |
|---|---|---|---|---|---|
| `canary-slow` | `canary-slow` | normal | §6.2.1 | no | no |
| `canary-fail` | `canary-fail` | high | §6.2.2 | **yes** | **yes** |
| `canary-silent` | `canary-silent` | high | §6.2.3 | yes | yes |
| `canary-schema-drift` | `canary-schema-drift` | normal | §6.2.4 | no | no (signal, not outage) |

### §6.2 Issue body templates (required content)

**§6.2.1 canary-slow:**
```
**Canary run:** {canary_id}
**Elapsed:** {elapsed_seconds}s (threshold: {threshold_2x_median}s; median of last 4 successful runs: {median}s)
**All 9 metrics:** passed
**Hash:** matched last-green pin
**Last 8 elapsed:** {elapsed_history}
**Suspected:** {auto-triage suggestion — e.g., "Primitive C INDEX regen slow" or "review_driver.py CI wait long"}
```

**§6.2.2 canary-fail:**
```
**Canary run:** {canary_id}
**Failed assertions:** {list of numeric §6 indices} — {human-readable names}
**Elapsed:** {elapsed_seconds}s
**Hash match:** {yes|no}
**First failed assertion body:** {details}
**Dashboard:** status=fail; streak reset to 0
**Next action:** debug the first failed assertion; do NOT re-run canary until root cause identified
```

**§6.2.3 canary-silent:**
```
**Last successful canary run:** {last_pass_timestamp} ({days_since_last_pass} days ago)
**Weekly cron present:** {yes|no — from `ops /loop list`}
**Conditional hook registered:** {yes|no — from `.claude/settings.json` read}
**Suspected:** cron died / hook unregistered / ops lane stopped
**Next action:** operator verifies ops lane alive; restart `/loop 7d /run-canary` if cron absent
```

**§6.2.4 canary-schema-drift:**
```
**Canary run:** {canary_id}
**All 9 metrics:** passed
**Hash mismatch:** observed {observed_hash} vs pinned {pinned_hash}
**New event types observed:** {set_diff_added}
**Missing event types:** {set_diff_missing}
**Next action:** quarterly `/canary-review` required within 14 days to either (a) re-pin hash if change is intentional, or (b) file follow-up H.0/H.1 issue if unintended schema drift
```

### §6.3 Ops alert push integration

`canary-fail` and `canary-silent` route through the ops-alert primitive (Primitive E). The `file_canary_issue.py` script calls `scripts/internal/ops.py alert push --priority high --title "<...>" --body "<issue-url>"` after issuing the GitHub issue. Alert payload includes issue URL so operator can click through.

### §6.4 Deduplication

If an open issue with the same label + same `canary_id` already exists, the filing is suppressed (upsert comment instead):

```bash
gh issue list --label canary-fail --state open --search "canary_id:{canary_id}"
# if hit: gh issue comment <N> --body "<new body>"
# if no hit: gh issue create ...
```

Prevents issue spam during `canary-silent` (which fires every poll until resolved).

---

## §7. H.1 replay harness — spec

### §7.1 Purpose

`tests/reliability/replay.py` reconstructs a task lifecycle from the Primitive A event corpus and asserts expected intermediate + final states. Primary use cases:

1. **Phase 1 Validation** (§5-H.1): "Replay harness reconstructs ≥1 proving-run task lifecycle end-to-end with no drift from live events."
2. **Post-incident debugging:** operator picks a failed task's trace ID, runs replay, gets deterministic lifecycle reconstruction.
3. **Schema-compatibility assertion:** replay across a v1.N → v1.M event corpus asserts backward-compat claim.
4. **Phase 2 portability dry-run** (intent, per §10.7): reconstruct a lifecycle against adapter-stubbed cells; flag hidden coupling.

### §7.2 Algorithm

```
Inputs:
  - trace_id (or task_packet_id)
  - event-corpus source: `data/events/**/*.jsonl` or `ops.py events query`
  - expected-final-state (optional; if absent, report-only mode)

Steps:
  1. Query corpus for all events matching trace_id (or task_packet_id).
  2. Sort by `emitted_at` timestamp (ascending); tie-break by `emit_seq` (monotonic per-lane counter; Primitive A v1.0 schema requirement).
  3. Walk events sequentially, maintaining a reconstructed state object:
     - task_packet_state (created / dispatched / in_progress / completed / failed)
     - dispatched_to lane
     - message-bus messages sent/received/acked
     - PR state (opened / CI-status / merged / reverted)
     - KB artifacts created / promoted
     - rollback events
  4. For each event, assert consistency:
     - Status transitions follow the task-queue state machine
     - Every `message_sent` has a matching `message_received` or `message_dead_lettered` downstream
     - Every `pr_opened` has matching `pr_merged` OR `pr_closed_without_merge`
     - Rollback events only follow successful `pr_merged`
  5. Compute final-state digest; compare to expected-final-state if supplied.
  6. Emit `replay_run_complete` event with {trace_id, reconstructed_final_state, drift_detected, inconsistencies}.

Output:
  - stdout: human-readable reconstruction log
  - exit code: 0 if reconstruction clean; 1 if drift detected; 2 if corpus incomplete (missing events); 3 on invocation error.
```

### §7.3 Schema-compat assertion mode

`replay.py --assert-schema-compat --from v1.0 --to v1.1 <trace_id>`:

1. Load trace events.
2. For each event, validate against both v1.0 and v1.1 schemas.
3. Assert: event valid under v1.M (current) AND event valid under v1.N (older, N < M) after optional field-drop normalization.
4. Failure: any event valid under v1.M but invalid under v1.N (schema added a required field; breaking).

### §7.4 Monitor-tool integration (native-substrate)

`replay.py --watch <trace_id>` uses the native `Monitor` tool to poll the event corpus until a target state is reached (e.g., `task_completed`). Polling interval default 5s; timeout default 30min (operator-configurable via `--timeout` flag).

### §7.5 Proving-run task selection

§5-H.1 Phase 1 Validation requires "Replay harness reconstructs ≥1 proving-run task lifecycle end-to-end with no drift from live events." Selection protocol:

1. Analyst lane picks a candidate lifecycle mid-Phase-1 (not end-of-Phase-1) — requirement: the task has already completed (all events emitted) and the lifecycle exercises ≥3 substrate primitives (e.g., shaping → author → review → merge → archivist).
2. Run `replay.py <trace_id>` expecting exit 0.
3. If exit ≠ 0: either (a) real inconsistency in the lifecycle (file a P0 issue; replay-harness succeeded at its job), or (b) replay-harness bug (file a P1 issue; do not claim Validation pass).
4. Expectation: ≥1 trace reconstructs cleanly by Phase 1 mid-run; ≥3 by Phase 1 end.

### §7.6 Output artifact schema

`replay_artifact.json` (written per run when `--write-artifact` flag supplied):

```json
{
  "trace_id": "...",
  "task_packet_id": "...",
  "event_count": 42,
  "first_event_at": "...",
  "last_event_at": "...",
  "reconstructed_final_state": {...},
  "expected_final_state": {...} | null,
  "drift_detected": false,
  "inconsistencies": [],
  "replay_version": "1.0",
  "schema_versions_observed": ["v1.0", "v1.0"]
}
```

Used as input to the postmortem generator (§9).

---

## §8. H.1 failure-injection scenarios — spec

### §8.1 §5-H.1 requirement recap

Phase 1 Validation: "≥3 failure-injection scenarios exercised during the proving run (or during dedicated reliability sessions within it); all either pass or produce a documented incident. **At least one scenario is selected post-hoc by an analyst lane during Phase 1, after primitives A, B, and E ship** — to avoid Goodharting the self-chosen minimum."

### §8.2 Scenario 1: Lane stall (deterministic; shipped at H.1-Exec)

**Setup:**
- Spawn a test task packet; dispatch to a sandboxed lane (author-sandbox or flex-d under test).
- Inject a 30-minute stall by mocking the agent's Bash tool to sleep on a benign command.

**Expected behavior:**
- Primitive A emits `lane_stalled` event after N minutes of no activity (threshold per A.stall-detection).
- Primitive E's active-triage files an issue labeled `lane-stall` within M minutes of the event.
- Monitor lane (ops) receives alert push.

**Pass criterion:**
- `lane_stalled` event present in corpus.
- Issue auto-filed with correct label.
- Ops alert push delivered.
- After stall cleared, lane resumes (or fails cleanly) per Primitive G rollback path.

**Assertion script:** `tests/reliability/failure_injection/lane_stall.py` — invokes the scenario, polls via `Monitor`, asserts pass criteria, emits `failure_injection_run` event.

### §8.3 Scenario 2: Dead-letter message (deterministic; shipped at H.1-Exec)

**Setup:**
- Send a message to a lane that does not exist (e.g., `author-z`).
- Expected: message bus should detect non-existent recipient and dead-letter.

**Expected behavior:**
- `message_dead_lettered` event emitted with reason `recipient_not_found`.
- DLQ (dead-letter queue) grows by 1.
- Primitive E files an issue labeled `message-dead-lettered` for operator visibility.

**Pass criterion:**
- DLQ entry present in state.
- `message_dead_lettered` event present in corpus.
- Issue auto-filed.

**Assertion script:** `tests/reliability/failure_injection/dead_letter.py`.

### §8.4 Scenario 3+: Analyst post-hoc (Phase 1 mid-run)

Per §5-H.1 Q3 clarification. Candidate scenarios (analyst picks ≥1):

| # | Scenario | Injects | Exercises |
|---|---|---|---|
| 3a | Stuck worktree | Dirty worktree with un-pushed commits left behind | Worktree cleanup + operator-notification path |
| 3b | Orphan cron | Cron survives /park; fires after lane is parked | Cron reconciliation + `/park` idempotency |
| 3c | Review-coordinator crash | `review_driver.py` killed mid-review | Review queue recovery + fallback status |
| 3d | Telegram outage | Telegram API 503 response for N min | Push-queue buffering + backoff + operator-surface-of-outage |
| 3e | Archivist candidate flood | 100 candidate files generated in one inflow window | Operator promotion throttling + KB-index cadence |
| 3f | Event-corpus disk-full | `data/events/` directory fills to 90% | Log-rotation / compression / operator alert |
| 3g | Merge race | Two PRs target same file; both merge within 30s | Branch protection / rebase-before-merge pattern |

Analyst files selection rationale as a Phase 1 ADR (Primitive B prompt-policy history entry). Scenario spec + assertion script authored as part of Phase 1 reliability session — not at shaping time.

### §8.5 Common scenario assertion shape

Every failure-injection scenario (shipped or post-hoc) follows:

```
1. Setup — inject the failure (via test fixture, mock, or controlled degradation)
2. Wait — `Monitor` polls for expected telemetry (event, issue, alert) up to `timeout`
3. Assert — pass criteria met within timeout
4. Teardown — undo the injection; assert substrate returns to baseline
5. Emit `failure_injection_run` event with scenario_id, pass/fail, elapsed, and observed events
```

### §8.6 Scenario isolation

Scenarios MUST NOT leak state across runs. Rules:

- Each scenario runs in a dedicated test-lane or test-namespace (e.g., `flex-d` reserved for reliability sessions; not used concurrently).
- Teardown step restores state (`rm` dirty worktree, `/park` the test lane, clear DLQ of test entries).
- Failure-injection events are tagged `test_run=true` metadata bit; Primitive A's event-corpus queries can filter out test runs from production rollups.

---

## §9. H.1 postmortem generator + expanded canary suite

### §9.1 Postmortem generator — spec

**File:** `scripts/internal/postmortem_generator.py`.

**Inputs:**
- `--replay-artifact <path>` — a `replay_artifact.json` from §7.6.
- `--template <path>` — default `plans/_templates/incident_postmortem.md` (new; §9.3).

**Output:**
- Markdown file at `knowledge/incidents/<YYYY-MM-DD>-<trace_id_short>.md` (committed after operator review).

**Algorithm:**
1. Load replay artifact.
2. Identify incident-triggering event (first `task_failed` / `canary_run_fail` / `failure_injection_run` with success=false, or operator-supplied `--trigger-event-id`).
3. Render template with fields:
   - `trace_id` / `task_packet_id`
   - Event timeline (condensed to unique event types + timestamps)
   - Inconsistencies (from replay artifact)
   - Automated root-cause hypothesis (simple rule: first inconsistency in replay + lane/tool + error text if present)
   - Template sections: Summary, Timeline, Root Cause (to be filled by operator), Impact, Resolution, Follow-ups, Prevention
4. Commit as draft to `knowledge/incidents/<draft>/` for operator review.
5. Emit `postmortem_generated` event with incident file path + trace_id.

### §9.2 Template

`plans/_templates/incident_postmortem.md`:

```markdown
# Incident: {title}

**Date:** {date_UTC}
**Trace:** {trace_id}
**Detected via:** {canary / replay / operator-report / failure-injection}
**Severity:** {low | medium | high | critical}

## Summary

(Operator fills: one paragraph — what broke, what fired, what it looked like.)

## Timeline (auto-generated from replay)

{event_timeline}

## Inconsistencies observed (auto-generated)

{replay_inconsistencies}

## Root cause (operator fills)

## Impact (operator fills)

- Tasks affected:
- Lanes affected:
- Data integrity:
- Recovery action taken:

## Resolution (operator fills)

## Follow-ups

- [ ] (filed as issue #N, label `incident-followup`)
- [ ] ...

## Prevention

Per Primitive B.3 prompt-policy / Primitive H canary / Primitive E triage:
- [ ] ...
```

### §9.3 Automated smoke-test

Phase 1 Readiness (mid-Phase-1): "Automated postmortem generator template committed and smoke-tested." Smoke test: run `postmortem_generator.py` against a synthetic replay artifact fixture (`tests/fixtures/replay_artifact_synthetic.json`); assert output file exists + contains expected template fields; assert `postmortem_generated` event emitted.

### §9.4 Expanded canary suite

**§5-H.1 Work:** "Expanded canary task suite: grow from the single dogfood-v1 (already running from H.0) to 3-5 canonical steward tasks defined as YAML/markdown specs at `tests/reliability/canaries/`."

**Per-scenario spec requirement** (from §5-H.1):
- Task description
- Expected lane routing
- Approximate token budget
- Expected prompt-policy citations in traces
- Pass/fail verdict protocol

**Candidate expansion scenarios (operator selects 2–4 in Phase 1):**

| # | Name | Task description | Lane | Token budget | Prompt-policy checks |
|---|---|---|---|---|---|
| 2 | `docs-minor-v1` | Update MEMORY.md with one canonical entry; PR; merge; archivist promotes | analyst-? | ~30k | analyst.md verification-surface-at-shaping cited |
| 3 | `script-fix-v1` | Add a unit test to an existing `scripts/internal/*.py` script; PR; merge | author-? | ~50k | author.md verification-surface-at-slice-close cited |
| 4 | `skill-addition-v1` | Add a new `.claude/skills/<name>/SKILL.md` stub; PR; merge; skill appears in `/help` | any | ~40k | — |
| 5 | `hook-modification-v1` | Add a no-op log line to an existing hook under `.claude/hooks/`; PR; merge; post-merge review verifies | ops | ~40k | — |

**Trigger:** expanded-suite reruns auto-trigger on material change to prompt-policy / dispatch / messaging bus / replay harness (per §5-H.1); sharing §8 trigger-path list extension.

### §9.5 Canary-regression metric

§5-H.1 Phase 1 Validation: "at least one canary run catches a regression (or, if none caught, the operator records in Primitive B's prompt-policy history an ADR stating 'no regressions caught' as either evidence of stability or as a kill-candidate signal for canary scope)."

Implementation:
- Canary suite tracks per-run whether any previously-green assertion now fails.
- End of Phase 1: aggregate metric `canary_regressions_caught` reported.
- If 0: operator files ADR `canary_zero_regressions_phase_1.md` with evidence + kill-candidate disposition.

### §9.6 §10.7 portability-dry-run intent

§5-H.1 "Intended to be" hedge: H.1 is **design intent** usable as Phase 2 portability dry-run tool, not Phase 1 Validation requirement. Packet H.1-Exec authors the replay-harness shape such that pointing at adapter stubs would be a small additional layer, but Packet H.1-Exec does not *implement* that layer. Portability-dry-run implementation is a Phase 2 sub-plan under the portability decision, if the decision goes portable.

---

## §10. Packet H.0-Exec — execution spec

### §10.1 Scope declared

**Files created:**
- `tests/reliability/canaries/dogfood_v1.py` (canary impl, ~200 LOC)
- `tests/reliability/canaries/dogfood_v1_packet.py` (canary packet generator, ~60 LOC)
- `tests/reliability/canaries/test_dogfood_v1.py` (unit tests, ~120 LOC)
- `tests/reliability/__init__.py` + `tests/reliability/canaries/__init__.py`
- `.claude/hooks/material-platform-change-canary.sh` (conditional hook, ~40 LOC)
- `scripts/internal/file_canary_issue.py` (issue-filing wrapper, ~50 LOC)
- `tests/unit/test_file_canary_issue.py` (~50 LOC)
- `.claude/rules/idempotency_checklist.md` (~80 LOC template + rows)
- `plans/steward_platform/canary_scenarios/audit_log.md` (empty template, ~20 LOC)

**Files modified:**
- `.claude/skills/run-canary/SKILL.md` — promote stub to full impl (~80 LOC additions)
- `.claude/skills/canary-review/SKILL.md` — add Phase 2 audit protocol (~60 LOC additions)
- `src/bid_euchre/ops/dashboard.py` — canary fields + sparklines (~40 LOC additions)
- `src/bid_euchre/ops/events.py` (OR `schema.json` per A's landing shape) — register canary_run_* event types (~30 LOC)
- `.claude/settings.json` — register `.claude/hooks/material-platform-change-canary.sh` hook
- `.github/pull_request_template.md` — add `## Idempotency` section (~10 LOC)
- `scripts/internal/review_driver.py` — add idempotency-checklist precheck (WARN severity; ~20 LOC)

**Gitignore (if not already):**
- `.claude/runtime/canary_state/` (state file path; per §4.5 `dogfood_v1.json` written by runner, not committed)

**Ops-action steps (no LOC; require tmux / gh access):**
- Install weekly cron: invoke `/loop 7d /run-canary` in ops lane pane
- Create GitHub labels: `gh label create canary-slow` / `canary-fail` / `canary-silent` / `canary-schema-drift`

**Subtotal:** ~680 LOC across 9 new files + 7 modified files + 2 ops-action steps.

### §10.2 Order of operations

Packet H.0-Exec sequence (dependency-ordered):

1. **Branch + scope lock.** `ops/primitive-h0-canary-exec` from `origin/main`.
2. **Coordinate with A merge.** Confirm Primitive A Packet 3 merged; verify `src/bid_euchre/ops/events.py` (or equivalent) present + v1.0 schema registered. If absent, escalate blocker and halt.
3. **Event schema additions first.** Register canary_run_* event types as v1.N additive; commit + push (smallest-blast-radius dependency; unblocks assertion script).
4. **Canary impl + unit tests second.** Author `dogfood_v1.py` + `dogfood_v1_packet.py` + `test_dogfood_v1.py`; run tests; commit.
5. **`/run-canary` skill promotion third.** Upgrade stub to full impl; tie to `dogfood_v1.py` invocation; commit.
6. **Dashboard integration fourth.** Extend `ops/dashboard.py` with canary fields + sparklines; state-file-read path; commit.
7. **Failure-mode auto-issue-filing fifth.** Author `file_canary_issue.py` + `test_file_canary_issue.py`; wire from `dogfood_v1.py` failure paths; commit.
8. **Conditional hook sixth.** Author `material-platform-change-canary.sh`; register in `settings.json`; commit.
9. **Idempotency checklist + PR template seventh.** Author checklist; extend PR template; commit.
10. **Idempotency-checklist precheck eighth.** Extend `review_driver.py` with WARN-severity precheck; commit.
11. **`/canary-review` skill promotion ninth.** Upgrade stub; commit.
12. **Audit log template tenth.** Add empty template; commit.
13. **Ops-action steps eleventh.** Create labels; install cron; validate cron in `/loop list`.
14. **Tier 2 validation twelfth.** Run `make check-gated`; attach output to PR body.
15. **Self-run canary once.** Invoke `/run-canary --trigger=on-demand`; expect `canary_run_complete` event + dashboard update. This is the first pass toward the ≥4 streak.
16. **Open PR.** Title: `feat(steward-platform): Primitive H.0 canary + idempotency checklist (Packet H.0-Exec)`. Body includes `Verification Performed` with Tier 2 output + first canary-run evidence.

### §10.3 Validation commands (Tier 2)

```bash
# Unit
uv run python -m pytest tests/reliability/canaries/test_dogfood_v1.py -v
uv run python -m pytest tests/unit/test_file_canary_issue.py -v

# Integration / dry-run
uv run python tests/reliability/canaries/dogfood_v1.py --dry-run
# Expect: 9 assertions exercised against fixture; exit 0

uv run python scripts/internal/file_canary_issue.py --dry-run --mode canary-fail \
  --canary-id dogfood-v1-test --failed-assertions 3,7
# Expect: issue body rendered to stdout; no actual gh call

# Dashboard
uv run python scripts/internal/ops.py dashboard
# Expect: Canary row renders; sparkline placeholders if no runs yet

# Skill registration
claude --print "/run-canary --help"
# Expect: skill recognized; no "Unknown command" error

# Cron (ops action)
# In ops lane: /loop list
# Expect: "/run-canary 7d" entry present after step 13

# Labels
gh label list | grep canary-
# Expect: 4 canary-* labels present

# Tier 2
make check-gated
```

### §10.4 Coordination notes

- **Dependency on Primitive A Packet 3.** Hard precondition. See §4.3 escalation path.
- **Dependency on Primitive E issue-filing API.** If E's filing API is not yet live, `file_canary_issue.py` wraps `gh issue create` directly as a fallback (lose priority-routing granularity but retain auto-filing).
- **Dependency on Primitive C INDEX regen.** Pass-metric #6 requires `knowledge/INDEX.md` regeneration via `scripts/internal/kb_index.py`. If C.1 not live, metric #6 WARNs rather than fails (graceful-degradation mode for Phase 0 week 1–2; full-fail after C Readiness).
- **Dependency on Primitive D archivist inflow.** Pass-metric #5 requires archivist candidate file within 24h. If D's nightly loop is not live yet (Phase 0 week 1), metric #5 WARNs rather than fails; full-fail after D.1 Readiness.
- **Graceful-degradation schedule:** at Phase 0 kickoff (week 1), metrics #5 and #6 are WARN-severity (do not fail the run); they become FAIL-severity by week 4, giving the ≥4 streak a 3-week grace period while C + D primitives land. State in `dogfood_v1.py` constants and make explicit in PR body.
- **Non-overlap with other Phase 0 packets.** Packet H.0-Exec does not touch `plans/steward_platform/governing_plan.md`, `plans/_templates/**`, or `.claude/rules/prompt_policy/**`. Collision risk with other in-flight packets is low.

### §10.5 Success criterion

> Packet H.0-Exec is complete when:
> (a) All files in §10.1 are created / modified per spec.
> (b) §10.3 validation commands pass (Tier 2 included).
> (c) Event schema additions registered; `canary_run_start` emits cleanly on test invocation.
> (d) First canary run completes with `canary_run_complete` event; dashboard shows the entry (even if status is "degraded" due to §10.4 graceful-degradation).
> (e) PR merged with `Verification Performed` evidence.
>
> After Packet H.0-Exec merges, the weekly cron `/loop 7d /run-canary` begins ticking. The ≥4 consecutive weekly passes streak (SC #22) begins accumulating on the first `canary_last_status=success` run. Phase 0 closeout is gated on this streak reaching 4.

### §10.6 Rollback path

Per §5-H.0 Readiness: "Rollback path validated: canary itself can be disabled." Operator invocation:

```bash
# Disable cron
# In ops lane: /loop cancel /run-canary
# Expect: cron entry removed; no more weekly triggers

# Disable on-demand + conditional-hook
mv .claude/skills/run-canary/SKILL.md .claude/skills/run-canary/SKILL.md.disabled
mv .claude/hooks/material-platform-change-canary.sh .claude/hooks/_disabled_material-platform-change-canary.sh
# Edit .claude/settings.json to remove hook registration

# Feature flag (alternative — retains skill but disables execution)
# In state file: .claude/runtime/canary_state/ENABLE_CANARY_CRON=false
```

Full disable is reversible: revert the file moves + re-register in settings.json + re-install cron. Validation in Packet H.0-Exec: rollback smoke test as part of §10.3 validation — disable, confirm no trigger; re-enable, confirm trigger resumes.

---

## §11. Packet H.1-Exec — execution spec

### §11.1 Scope declared

**Files created:**
- `tests/reliability/replay.py` (replay harness, ~300 LOC)
- `tests/reliability/test_replay.py` (unit tests, ~200 LOC)
- `tests/reliability/failure_injection/__init__.py`
- `tests/reliability/failure_injection/lane_stall.py` (scenario 1, ~150 LOC)
- `tests/reliability/failure_injection/dead_letter.py` (scenario 2, ~100 LOC)
- `tests/reliability/failure_injection/test_lane_stall.py` + `test_dead_letter.py` (~200 LOC combined)
- `scripts/internal/postmortem_generator.py` (~200 LOC)
- `tests/unit/test_postmortem_generator.py` (~100 LOC)
- `plans/_templates/incident_postmortem.md` (template, ~50 LOC)
- `tests/fixtures/replay_artifact_synthetic.json` (fixture, ~50 LOC)
- Expanded canary suite (analyst selects 2–4 from §9.4 candidate set):
  - `tests/reliability/canaries/<name>.py` per chosen scenario (~150 LOC each)
  - `tests/reliability/canaries/test_<name>.py` per chosen scenario (~80 LOC each)

**Files modified:**
- `src/bid_euchre/ops/events.py` — register `replay_run_complete` + `failure_injection_run` + `postmortem_generated` event types (~20 LOC, v1.N additive)
- `.claude/hooks/material-platform-change-canary.sh` — extend path-trigger list for expanded canary suite (~10 LOC additions)
- `plans/steward_platform/canary_scenarios/` — add per-scenario sub-plan stubs for chosen expansion scenarios

**Subtotal:** ~1800 LOC across 12+ new files + 3 modified files (varies by expanded-suite selection).

### §11.2 Order of operations

1. **Branch + scope lock.** `ops/primitive-h1-reliability-exec` from `origin/main`.
2. **Coordinate with proving run.** Confirm Phase 1 kickoff complete; ≥1 task lifecycle present in event corpus (for §7.5 selection).
3. **Event schema additions first.** Register `replay_run_complete` / `failure_injection_run` / `postmortem_generated` as v1.N additive.
4. **Replay harness second.** Author `replay.py` + `test_replay.py`; run against synthetic fixture; commit.
5. **Failure-injection scenario 1 (lane_stall) third.** Author + test; commit.
6. **Failure-injection scenario 2 (dead_letter) fourth.** Author + test; commit.
7. **Postmortem generator + template fifth.** Author + test; commit.
8. **Expanded canary suite sixth.** Analyst-selected 2–4 scenarios; per-scenario author + test; commit per-scenario (one PR per scenario acceptable, or batched).
9. **Conditional-hook trigger-path extension seventh.** Update `material-platform-change-canary.sh` to include new suite scenarios.
10. **Phase 1 Readiness mid-run validation eighth.** Verify:
    - Replay harness reconstructs ≥1 lifecycle (non-proving-run seed task OK for Readiness).
    - ≥2 failure-injection scenarios implemented and passing.
    - Postmortem generator smoke-tested.
    - Canary suite expanded to 3–5 tasks.
    - Idempotency checklist actively cited in recent PR reviews (grep PR bodies for `## Idempotency`).
11. **Phase 1 Validation end-of-phase.** Verify full §5-H.1 Phase 1 Validation bullets.
12. **Open PR.** Title: `feat(steward-platform): Primitive H.1 reliability lab (Packet H.1-Exec)`. Body includes Validation evidence.

**Phase-distribution note:** Packet H.1-Exec may be split into sub-packets by the orchestrator (e.g., Packet H.1-replay, Packet H.1-failure-injection, Packet H.1-postmortem) if single-PR scope exceeds a reviewable size. Each sub-packet retains its own success criterion.

### §11.3 Validation commands (Tier 2)

```bash
# Unit
uv run python -m pytest tests/reliability/test_replay.py -v
uv run python -m pytest tests/reliability/failure_injection/ -v
uv run python -m pytest tests/unit/test_postmortem_generator.py -v

# Integration — replay against synthetic fixture
uv run python tests/reliability/replay.py --replay-artifact tests/fixtures/replay_artifact_synthetic.json
# Expect: clean reconstruction; exit 0

# Integration — replay against proving-run trace
uv run python tests/reliability/replay.py <trace_id_from_proving_run> --write-artifact
# Expect: exit 0; artifact written to data/events/replay_artifacts/<trace_id>.json

# Integration — failure injection (sandboxed)
uv run python tests/reliability/failure_injection/lane_stall.py --sandbox
uv run python tests/reliability/failure_injection/dead_letter.py --sandbox
# Expect: both exit 0; `failure_injection_run` events emitted

# Integration — postmortem against replay artifact
uv run python scripts/internal/postmortem_generator.py \
  --replay-artifact <artifact-path> \
  --template plans/_templates/incident_postmortem.md
# Expect: incident file written to knowledge/incidents/<date>-<trace>.md (draft)

# Tier 2
make check-gated
```

### §11.4 Coordination notes

- **Dependency on proving run.** Replay harness needs real trace data. Do not dispatch H.1-Exec before Phase 1 kickoff.
- **Dependency on Primitive A v1.0 schema stable.** Schema evolution during H.1 author window disrupts replay assertions. If A changes schema mid-H.1, replay-harness tests are rebaselined and an ADR filed.
- **Dependency on Primitive E triage.** Failure-injection scenarios rely on E's active-triage to file issues. E Readiness must hold.
- **Coordination with Primitive G.** G covers Phase 0 rollback-validation; H.1's rollback-validation bullet (§5-H.1 Work) is strictly Phase 1 scope. No overlap.
- **Coordination with Primitive F baseline.** Post-Read-tool-token-reductions baseline re-capture feeds replay threshold calibration (§7.2).
- **Analyst post-hoc scenario selection.** H.1-Exec reserves a slot for analyst-selected scenario; selection happens mid-Phase-1 and is authored as a H.1-followup packet, not within Packet H.1-Exec itself.

### §11.5 Success criterion

> Packet H.1-Exec is complete when:
> (a) All §11.1 files created / modified.
> (b) §11.3 validation commands pass.
> (c) §5-H.1 Phase 1 Readiness bullets all hold (replay ≥1 lifecycle, ≥2 failure-injection passing, postmortem smoke-tested, canary suite 3–5 tasks, idempotency checklist cited).
> (d) PR(s) merged with `Verification Performed` evidence.
>
> Phase 1 Validation closeout (§5-H.1 Phase 1 Validation bullets) is evaluated separately at end-of-Phase-1; not a Packet H.1-Exec gate. §10.7 Phase 2 portability decision is blocked on Phase 1 Validation, not Packet H.1-Exec merge.

### §11.6 Rollback path

- Replay harness: remove `tests/reliability/replay.py`; no runtime state; no rollback needed beyond revert.
- Failure-injection scenarios: each scenario's teardown step (§8.6) restores substrate state. Scenario scripts themselves are removable via revert.
- Postmortem generator: remove script; templates committed to `plans/_templates/` stay; incident drafts in `knowledge/incidents/<draft>/` remain for operator review.
- Expanded canary suite: per-scenario revert; dogfood-v1 remains operational (H.0 scope).
- Event schema additions: v1.N additions can be reverted if replay/failure-injection/postmortem never reach production use; follow Primitive A schema-versioning policy.

---

## §12. Self-review against completeness criteria

### §12.1 Constraint encountered (Agent-tool disallowance)

Per `.claude/rules/70_agent_reliability.md` + analyst-lane YAML frontmatter. The task packet does not explicitly request a reviewer-agent spawn (unlike verification_contract/shaping.md which did); nevertheless I stress-tested the outline against explicit completeness criteria before writing and document the self-review here for orchestrator audit. The orchestrator may dispatch a separate packet to any non-analyst-b flex lane for independent adversarial review (not blocking per packet framing).

### §12.2 Completeness criteria stress-test

| Criterion | Check | Outcome |
|---|---|---|
| H.0 vs H.1 boundary explicit with dispatch triggers | §2 + §3.1 | ✓ (Primitive A Packet 3 for H.0; Phase 1 kickoff for H.1) |
| H.0 scope references dogfood.md; does not duplicate | §2.1 + §4.1 | ✓ (§2.1 no-duplication rule; §4.2 additive-scope table) |
| Idempotency checklist authored in full (new content) | §5 | ✓ (§5.3 full 10-row template) |
| Failure-mode auto-issue-filing detailed beyond dogfood.md | §6 | ✓ (routing matrix + 4 body templates + dedup + ops alert integration) |
| Replay harness algorithm + schema-compat mode + proving-run selection | §7 | ✓ (6 sub-sections) |
| Failure-injection ≥2 deterministic + analyst post-hoc slot | §8 | ✓ (lane_stall + dead_letter + 7 candidates for post-hoc) |
| Postmortem generator + template + smoke-test | §9 | ✓ |
| Expanded canary suite with per-scenario spec requirement | §9.4 | ✓ (5 candidates, operator selects 2–4) |
| Packet H.0-Exec: scope + order + validation + coordination + success | §10 | ✓ (6 sub-sections) |
| Packet H.1-Exec: same shape | §11 | ✓ (6 sub-sections) |
| Verification Plan (Pattern 10 self-compliance) | §13 | ✓ (per §4, §5, §6, §7, §8, §9 deliverables) |
| Risks + mitigations | §14 | ✓ (5 rows) |
| Phase 2 Decision Inputs per §15.2 | §15 | ✓ |
| Cross-primitive coordination summary table | §3.3 | ✓ (7 primitives) |
| Native-substrate integration inventory | §3.2 | ✓ (4 features) |
| §5-H phase-membership + SC #22 + kill criterion coverage | §2 table | ✓ |
| Canary self-reference exclusion mechanism decided | §4.4 | ✓ (Option A: PR label; rationale) |
| State-file schema | §4.5 | ✓ |
| DST / timezone caveat | §4.6 | ✓ |
| Graceful-degradation schedule for Phase 0 week 1–3 | §10.4 | ✓ |

### §12.3 Risks surfaced during self-review (orchestrator decision)

1. **H.0-Exec dispatch-critical-path timing.** If Primitive A Packet 3 merges week 1 and H.0-Exec merges week 2, the ≥4 streak completes week 5 (earliest). Any schedule slip on A compounds on H.0. If A delivers week 3, Phase 0 closeout cannot be declared before week 7. Orchestrator may want to track A→H.0 as a critical path in the Phase 0 burn-down.
2. **Graceful-degradation WARN→FAIL transition boundary (§10.4).** Packet H.0-Exec sets metric #5 / #6 as WARN for weeks 1–3 and FAIL from week 4. The transition is coded as a timestamp comparison in `dogfood_v1.py` (constants + `time.time()` against Phase 0 kickoff date). This timestamp-switch is itself a reliability hazard — if Phase 0 kickoff timestamp is wrong, the graceful-degradation window misbehaves. **Mitigation:** make the kickoff timestamp read from a single source of truth (`plans/steward_platform/phase_0_kickoff.json` or equivalent) committed at Phase 0 start. Orchestrator owns the timestamp commit.
3. **Replay harness brittleness vs v1.N schema evolution.** If Primitive A evolves v1.0 → v1.1 during H.1 dev, replay-test fixtures go stale. **Mitigation:** fixtures carry `schema_version` metadata; test runner validates fixture-vs-runtime-schema mismatch and refuses with clear message.
4. **Expanded canary suite "catches a regression" Phase 1 Validation bullet is a lagging metric.** If no regressions surface during proving run, validation passes vacuously. **Mitigation:** §9.5 operator-ADR fallback; but suggest §5-H.1 be revised to add "canary suite exercises ≥N distinct pass-metric assertions across all tasks combined" as a coverage floor — not in scope for this packet; flag for Packet 15 (governing-plan sharpening).
5. **Failure-injection scenario isolation imperfect.** `flex-d` as dedicated reliability-test lane conflicts with flex-d's existing tactical use. **Mitigation:** reserve `flex-c` or a new `reliability-test` lane for scenarios; coordinate with lane-registry update (`.claude/rules/75_worktree_protection.md`).

### §12.4 Orchestrator option

If the orchestrator wants independent adversarial review of this shaping before Packet H.0-Exec dispatch, dispatch a separate packet to any non-analyst-b flex lane (for recusal) with the prompt: "Review `plans/steward_platform/8_primitive_H/shaping.md` for H.0 + H.1 execution-packet completeness, no-duplication boundary with `canary_scenarios/dogfood.md`, replay-harness algorithm soundness, and failure-injection scenario coverage." Recommended but not blocking.

---

## §13. Verification Plan (Pattern 10 self-compliance)

_Required per Pattern 10 (§10.9 governing plan). Every §N deliverable row has a named verification surface._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §4.2 #1 `/run-canary` skill promotion | `.claude/skills/**` upgrade | `SKILL.md` acceptance command (`claude --print "/run-canary --help"`) | ops | skill recognized; invocation produces `canary_run_start` event |
| §4.2 #2 Canary packet generator | new Python module under `tests/reliability/**` | unit test `tests/reliability/canaries/test_dogfood_v1.py::test_packet_generator` | author | pytest passes; packet shape matches schema |
| §4.2 #3 Pass-metric assertion script | new Python module under `tests/reliability/**` | unit test + integration dry-run (§10.3) | author | all 9 metric paths exercised; dry-run exits 0 |
| §4.2 #4 Canary-assertion unit tests | tests | pytest run | author | all tests pass (seeded fixtures) |
| §4.2 #5 Dashboard integration | `src/bid_euchre/ops/**` modification | `ops.py dashboard` TUI scrape | ops | `canary_last_*` fields render; sparkline shows 8-run history |
| §4.2 #6 Canary state file | gitignored runtime path | presence check + schema validation on runner invocation | author | file created on first run; schema valid |
| §4.2 #7 Event schema additions | Primitive A v1.N additive | replay-harness schema-compat assertion | author | new event types validate against v1.1 schema |
| §4.2 #8 Conditional hook | new `.claude/hooks/**` file | rollback smoke test (disable hook; verify no trigger; re-enable; verify trigger) | ops | both paths exercised; state returns to baseline |
| §4.2 #9 Weekly cron (ops-action) | ops `/loop` state | `/loop list` output | ops | `/run-canary 7d` entry present |
| §4.2 #10 Failure-mode labels (ops-action) | GitHub labels | `gh label list` grep | ops | 4 `canary-*` labels present |
| §4.2 #11 Auto-issue-filing wrapper | new Python script | unit test + dry-run mode | author | `file_canary_issue.py --dry-run` renders body; exits 0 |
| §4.2 #12 `/canary-review` skill promotion | `.claude/skills/**` upgrade | `SKILL.md` audit protocol + operator-review prompt | ops | quarterly audit invocation recognized; audit-log template populated |
| §4.2 #13 Audit log file | template | presence check | ops | file at `plans/steward_platform/canary_scenarios/audit_log.md` |
| §5 Idempotency checklist | new `.claude/rules/**` file | operator-readable review prompt + review-driver precheck | ops | `review_driver.py` emits WARN on matching surfaces + missing checklist section |
| §5 PR template idempotency section | `.github/**` modification | PR template renders section | ops | newly-opened PR shows `## Idempotency` block |
| §6 Auto-issue-filing routing matrix | integration workflow | test-fired fake canary-fail; assert issue created + alert pushed | author | issue present; ops-alert event fired; no spam (dedup works) |
| §7 Replay harness | new Python module under `tests/reliability/**` | unit test + integration against synthetic fixture | author | `test_replay.py` all pass; synthetic-fixture replay exits 0 |
| §7.3 Schema-compat assertion mode | integration surface | run against v1.0 + v1.1 fixtures | author | v1.0 → v1.1 assertion passes; v1.0 → v2 fails with clear message |
| §7.5 Proving-run task selection | shaping-doc artifact | operator-review prompt: first H.1-selected trace replays clean | analyst | exit 0 on operator-selected trace_id |
| §8.2 Scenario 1 (lane_stall) | new Python module + failure-injection | sandboxed scenario run | author | scenario exit 0; `lane_stalled` event + issue + alert all fire |
| §8.3 Scenario 2 (dead_letter) | new Python module + failure-injection | sandboxed scenario run | author | scenario exit 0; DLQ + event + issue fire |
| §8.4 Scenarios 3+ (post-hoc) | per-scenario authoring | per-scenario assertion script + rationale ADR | analyst | scenario exit 0 + ADR committed |
| §9.1 Postmortem generator | new Python script | smoke-test against synthetic replay artifact | author | incident file written; template fields filled; `postmortem_generated` event emitted |
| §9.2 Postmortem template | new `plans/_templates/**` | presence check | author | template at `plans/_templates/incident_postmortem.md` |
| §9.4 Expanded canary suite | new canary modules | per-scenario pass-metric tests | author | per-scenario pytest exit 0 |
| §9.5 Canary-regression metric (Phase 1 end) | operator-review + aggregate metric | Phase 1 Validation sign-off | analyst | metric reported; ADR filed if zero |
| §10 Packet H.0-Exec as a whole | execution-packet artifact | §10.5 success criterion checklist | orchestrator | all (a)–(e) hold; PR merged |
| §11 Packet H.1-Exec as a whole | execution-packet artifact | §11.5 success criterion checklist | orchestrator | all (a)–(d) hold; PR(s) merged |

**Surface-class defaults:** see Pattern 10 table at `plans/steward_platform/governing_plan.md` §10.9 and `plans/steward_platform/verification_contract/shaping.md` §2.

---

## §14. Risks + mitigations

| Risk | Likelihood | Impact | Mitigations |
|---|---|---|---|
| **H.0 dispatch blocked on Primitive A Packet 3** | Medium (A is Primitive-A-top-priority; schedule risk real) | High (every week of A delay shifts Phase 0 closeout by a week) | (1) Orchestrator tracks A→H.0 dependency as critical path; (2) Graceful-degradation window (§10.4) absorbs 3 weeks of C/D readiness slippage post-A; (3) If A slips past Phase 0 week 4, escalate re-scope: drop H.0 idempotency checklist from blocking scope, keep canary; re-evaluate SC #22 streak-window (current 4 weeks) against actual available time. |
| **Canary becomes silent green check** (carryover from §12 governing plan risk table) | Medium | High | (1) Expected-event-type-set hash (dogfood.md §6); (2) Sparkline sub-metrics (dogfood.md §9); (3) Quarterly `/canary-review` (§4.2 #12 + canary-review SKILL.md Phase 2 protocol). Triple-redundant defense. |
| **Replay-harness brittleness vs v1.N schema evolution** | Medium (Phase 1 is long; schema evolution expected) | Medium (false-negative replay failures create noise, not outages) | (1) Fixtures carry `schema_version`; (2) Runner validates fixture-vs-runtime and refuses cleanly; (3) §7.3 schema-compat mode catches regressions at schema-bump time, not replay time. |
| **Failure-injection scenario isolation imperfect** (state leaks across runs) | Low | Medium (polluted fixtures → unreliable test results) | (1) Dedicated test lane (`flex-c` or `reliability-test`); (2) §8.6 teardown step asserts baseline; (3) `test_run=true` metadata bit filters from production rollups. |
| **Expanded canary suite "catches regression" Validation bullet is lagging** | Medium | Low (vacuous-pass failure mode) | §9.5 operator-ADR fallback; additionally flag to Packet 15 (governing-plan sharpening) that §5-H.1 Phase 1 Validation bullet 4 should add a coverage-floor metric (not scope for this packet). |

---

## §15. Phase 2 Decision Inputs

**Portability readiness:**
- H.0 canary: portable-by-design — dogfood.md task is generic (dashboard field edit); substrate surfaces are substrate-generic (plan / dispatch / author / review / merge / archivist / KB / rollback). Same scenario shape works for a second cell. Source: `plans/steward_platform/canary_scenarios/dogfood.md` §Phase 2 Decision Inputs.
- H.1 replay harness: partially portable. Event-corpus ingestion is generic; state-machine assertions encode substrate-specific invariants. Portability requires adapter pattern: substrate-generic ingestor + cell-specific assertion registry.
- H.1 failure-injection: scenarios are cell-specific by definition (each injects a failure at a cell-specific surface). Portability means: shape of a scenario (setup / wait / assert / teardown / emit) is portable; per-scenario content is not.
- H.1 postmortem generator: portable-by-design — template + algorithm are generic.

**Meta-layer need:**
- No change for H.0 (per-cell canary).
- H.1 replay harness portability would introduce a small meta-layer: adapter-pattern for state-machine assertions. Deferrable to Phase 2 unless replay-harness reuse is in Phase 2 portability scope.

**Kill signal for primitive(s) named:**
- §11-H.0 kill: fails ≥2 weekly passes in any 4-week window during Phase 0 → re-scope canary or demote to event-diff assertion.
- §11-H.1 kill: <2 replay scenarios pass OR <3 failure-injection OR canary never runs on material change → demote postmortem + canary expansion; blocks §10.7 portability decision.

**Re-evaluation needed in Phase 3:** yes if:
- H.0 canary's dogfood-v1 task spec becomes inadequate coverage of Phase 0 substrate (e.g., new lane types, new primitives not exercised by dashboard-field-edit task) → redesign task scope.
- H.1 replay-harness throughput too slow for proving-run lifecycles (each reconstruction >5min) → algorithm revision required.
- Expanded canary suite yields persistent zero-regression-catch outcomes → either substrate is extraordinarily stable (good) or canary sensitivity is inadequate (bad); operator-ADR fork per §9.5.

**Surprise finding:**
The dogfood.md sub-plan (Packet 2b scaffold) already specifies H.0 at a granularity that left only *execution-packet* scope for this shaping doc. This is a healthier shaping-doc / sub-plan boundary than typical — the Pattern 11 shape-then-execute sequence worked cleanly here because the intermediate Packet 2a → Packet 2b step landed the sub-plan ahead of this shaping doc. Pattern 11 works well when the dispatchable sub-plan is scaffolded one packet-layer before the execution-packet shape. Recommend preserving this sequence for future primitives with similar "scaffold-then-execute" structure.

**Disposition:** open

---

## §16. References

- `plans/steward_platform/governing_plan.md` §5-H (lines 608–687) — primary remit
- `plans/steward_platform/canary_scenarios/dogfood.md` — canonical SP-0-H0-dogfood-v1 sub-plan (referenced, not duplicated)
- `plans/steward_platform/verification_contract/shaping.md` §5 — canary design rationale upstream of dogfood.md
- `plans/steward_platform/1_primitive_A/shaping.md` — event-schema + dispatcher coordination
- `plans/steward_platform/3_primitive_C/shaping.md` §4.1 — INDEX regen + archivist contract
- `plans/steward_platform/6_primitive_F/shaping.md` — F-forward / F-debt split pattern reused as H.0 / H.1 analog
- `plans/steward_platform/0_hardening/sub/rework_spec.md` — Primitive G Phase 0 rollback-validation scope (complementary to H.1)
- `.claude/skills/run-canary/SKILL.md` — stub (Packet 2b); promoted by Packet H.0-Exec
- `.claude/skills/canary-review/SKILL.md` — stub (Packet 2b); promoted by Packet H.0-Exec
- `.claude/rules/deferred/60_review_gate.md` — BLOCK / WARN / INFO severity definitions (referenced in §5.4)
- `.claude/rules/70_agent_reliability.md` — agent-spawning constraints (§12.1)
- `.claude/rules/25_task_lists.md` — task-list conventions for session
- Task packet: `8f8374a5c79a` (Primitive H pre-shape)
- Recovery message: `e5a26c3f4c4a40e6` (scope correction from orchestrator, 2026-04-24)
