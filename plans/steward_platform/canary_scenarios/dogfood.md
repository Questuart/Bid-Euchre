# Sub-Plan: Steward Dogfood Canary Implementation (dogfood-v1)

**ID:** SP-0-H0-dogfood-v1
**Date:** 2026-04-23
**Parent:** `plans/steward_platform/governing_plan.md` §5-H.0 + SC #22
**Status:** proposed (scaffold only via Packet 2b; full impl via H.0 follow-on packets)
**Owner:** author (impl), ops (cron + monitoring), orchestrator (audit)

---

## §1. Purpose

`dogfood-v1` is the Phase 0 mini-canary that proves the verification
surfaces actually catch regressions. SC #22 gates Phase 0 closeout on
its passing streak (≥4 consecutive weekly passes). Full shaping in
`plans/steward_platform/verification_contract/shaping.md` §5.

The canary exercises every substrate surface a real task would
exercise: planning → dispatch → author execution → review → merge →
archivist → KB → rollback. Task scope is small enough (1 file edit + 1
test + 1 ADR stub + 1 PR) that failures isolate to substrate behavior,
not task complexity.

---

## §2. Task spec

Verbatim from shaping §5.2:

> Add a `last_verification_run` field to `src/bid_euchre/ops/dashboard.py`
> TUI output showing the timestamp and pass/fail state of the most
> recent canary run. Create a unit test asserting the field renders.
> File a mini-ADR under `knowledge/adr/` recording the field's purpose.
> Open a PR. Merge after CI + review passes. Confirm the archivist
> (Primitive D) creates a candidate entry referencing the canary's
> trace ID within 24h. Execute rollback: revert the merge; confirm
> dashboard reverts; confirm `canary_rollback_complete` event fires.

Scope is chosen to exercise: planning (packet creation) → dispatch (ops
task queue) → author execution (branch, edit, test, commit) → review
(`review_driver.py` full loop) → merge (`post-merge-notify.sh` hook) →
archivist (Primitive D candidate generation) → KB (INDEX regeneration)
→ rollback (Pattern 7 path).

---

## §3. Work

- **§3.1** Implement `/run-canary` skill (`.claude/skills/run-canary/SKILL.md`). Packet 2b scaffolds the stub; full implementation is H.0 follow-on.
- **§3.2** Implement canary packet generator (`tests/reliability/canaries/dogfood_v1_packet.py`) — H.0 follow-on.
- **§3.3** Implement pass-metric assertion script (`tests/reliability/canaries/dogfood_v1.py`) — H.0 follow-on.
- **§3.4** Extend `ops/dashboard.py` with canary fields + sparklines — H.0 follow-on.
- **§3.5** Extend event schema (Primitive A) with `canary_run_*` event types — H.0 follow-on.
- **§3.6** Wire conditional hook for material-platform-change trigger (shaping §5.5 trigger-path list) — H.0 follow-on.
- **§3.7** Install weekly cron in ops lane `/loop` config (`/loop 7d /run-canary`) — H.0 follow-on.
- **§3.8** Wire failure-mode issue-filing (`canary-slow` / `canary-fail` / `canary-silent` / `canary-schema-drift` labels per §7) — H.0 follow-on.
- **§3.9** Quarterly `/canary-review` skill (`.claude/skills/canary-review/SKILL.md`). Packet 2b scaffolds the stub; full audit protocol exercised Phase 3+.

---

## §4. Phase 0 Readiness

See §5-H.0 Phase 0 Readiness bullets in the governing plan.

- `dogfood-v1` canary implemented per this sub-plan.
- `/run-canary` skill registered and invokable from any lane.
- Weekly cron installed in ops lane (`/loop 7d /run-canary`).
- Conditional hook wired for material-platform-change triggers.
- All 9 pass metrics grep-verifiable on a test-driven seeded run.
- Dashboard integration live; sparklines render.
- Event schema v1.N additive registered.
- Failure-mode routing live.
- Rollback path validated (feature flag `ENABLE_CANARY_CRON`).
- Idempotency checklist committed; PR template section landed.
- ≥4 consecutive weekly passes recorded (SC #22).

---

## §5. Phase 1 Validation

Rolls into H.1 full reliability suite (§5-H.1): canary continues passing
weekly through Phase 1; no regression in `canary_pass_streak` over
2-week window; any canary fail during Phase 1 produces a postmortem
artifact per the automated generator.

---

## §6. Pass metrics

Verbatim from shaping §5.3. Canary passes **iff all 9** assertions hold
for a single `canary_id` within the elapsed-time window:

1. `canary_run_start` event emitted with canary_id
2. Task packet transitioned `created → dispatched → completed` within window (default 6h, operator-configurable)
3. PR exists, CI green, `reviewing-changes` status ∈ {success, warn}, was merged
4. `task_completed` event emitted for the canary packet with matching canary_id
5. Archivist candidate file at `knowledge/_candidates/<date>.md` contains canary_id reference
6. `knowledge/INDEX.md` regeneration succeeded post-merge (no stale INDEX relative to KB filesystem)
7. Dashboard renders the new `last_verification_run` field
8. Rollback PR (revert) opened, CI green, merged; `canary_rollback_complete` event emitted
9. `canary_run_complete` event emitted with `success=true` and `elapsed_seconds` field populated

**Expected-event-type hash:** canary runner computes a hash of `{event_type, canary_id}` pairs observed during a run. Deviations from the last green run's hash fail the canary loudly with a `canary_event_schema_drift` signal, even if the 9 pass-metric assertions all hold — mitigation for §12 Risks silent-green-check row.

---

## §7. Failure behaviors

Per shaping §5.4:

| Mode | Trigger | Action | Dashboard status |
|---|---|---|---|
| **canary-slow** (soft fail) | All 9 assertions pass but elapsed-time > 2× median of last N=4 successful runs | File issue `canary-slow`; no ops alert push | `slow` |
| **canary-fail** (hard fail) | ≥1 pass-metric assertion unmet OR expected-event-type hash mismatch | File issue `canary-fail` priority high; escalate via ops alert; Telegram operator | `fail`; streak resets |
| **canary-silent** | No run recorded for ≥14 days | ops monitor raises `canary-silent` alert; Telegram | `silent` |
| **canary-schema-drift** | Pass-metric assertions pass but observed `{event_type}` set differs from last-green hash | File issue `canary-schema-drift`; no push escalation (signal, not outage) | `schema-drift`; streak does not increment |

---

## §8. Cadence

Per shaping §5.5:

- **Weekly cron:** `/loop 7d /run-canary` in ops lane, installed at Phase 0 kickoff. Cron spec: `0 9 * * MON` via ops `/loop` mechanism (`.claude/skills/loop/SKILL.md`).
- **On-demand:** any lane invokes `/run-canary` to trigger a run; useful during Phase 0 as primitives land.
- **Conditional-hook (material-platform-change):** triggered on PR merges to:
  - `.claude/skills/**`
  - `.claude/hooks/**`
  - `src/bid_euchre/ops/core/**`
  - `scripts/internal/review_driver.py`
  - `src/bid_euchre/ops/dashboard.py` (self-aware — dashboard changes trigger dashboard-assertion re-verification)
  - `.claude/rules/prompt_policy/**`
  - Any `§N.M` modification in `plans/steward_platform/governing_plan*.md`

Hook invokes `/run-canary --trigger=material-change --changed-paths=<list>`.

---

## §9. Dashboard integration

Per shaping §5.6. `ops.py dashboard` renders a `Canary` row:

```
Canary  last_pass: 2026-04-20 09:14  streak: 4  status: success  elapsed: 312s
```

Fields: `canary_last_pass`, `canary_pass_streak`, `canary_last_status`
(success | slow | fail | silent | schema-drift), `canary_last_elapsed`.

**Sub-metric sparklines** (shaping §7 mitigation): dashboard panel
sub-row shows mini-sparklines for `elapsed_seconds`, `event_count`,
`archivist_lag_seconds`, `kb_index_regeneration_ms` across the last 8
runs. Drift visible before threshold breaches.

---

## §10. Event schema additions

Per shaping §5.7. Primitive A v1.N additive (compatible with replay harness):

| Event type | Fields |
|---|---|
| `canary_run_start` | canary_id, trigger (cron / on-demand / material-change), canary_version (dogfood-v1), started_at, lane_id |
| `canary_run_complete` | canary_id, success (bool), elapsed_seconds, pass_metrics (dict of 9 booleans), event_type_hash, completed_at |
| `canary_run_fail` | canary_id, failed_assertions (list of numeric indices per §6), elapsed_seconds, failed_at |
| `canary_rollback_complete` | canary_id, rollback_pr, reverted_at |

---

## §11. Audit

Quarterly `/canary-review` protocol (shaping §7 mitigation + skill stub
at `.claude/skills/canary-review/SKILL.md`). Operator audits: did
recent canary passes catch known failure modes? If not, add assertions
or retire the canary. Audit outcome logged in this sub-plan's §Outcome
section and any new assertions filed as H.1 follow-on work.

---

## §12. Verification Plan

_Required per Pattern 10 (§10.9). Every §3 Work bullet gets a row._

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §3.1 `/run-canary` skill | new `.claude/skills/**` entry | `SKILL.md` acceptance command | ops | skill invokable from any lane |
| §3.2 canary packet generator | new Python module under `tests/reliability/**` | `tests/reliability/canaries/test_dogfood_v1_packet.py` | author | pytest passes |
| §3.3 pass-metric assertion script | new Python module under `tests/reliability/**` | seeded run exercising all 9 metrics | author | 9/9 pass on fixture |
| §3.4 dashboard fields + sparklines | integration surface | `ops.py dashboard` TUI scrape | ops | fields render; sparklines show 8 runs |
| §3.5 event schema v1.N additive | event-schema addition (Primitive A) | replay-harness compatibility assertion | author | schema validator accepts |
| §3.6 conditional hook | new `.claude/hooks/**` file | rollback test + canary-scenario smoke | ops | hook disable path exercised |
| §3.7 weekly cron | config change | rollback test (flag `ENABLE_CANARY_CRON` off) | ops | revert leaves no dangling cron |
| §3.8 failure-mode issue labels | integration workflow | 4 GitHub labels exist + auto-file test | ops | ≥1 canary-* issue auto-filed |
| §3.9 `/canary-review` quarterly skill | new `.claude/skills/**` entry | `SKILL.md` operator-review prompt + audit log | ops | quarterly audit entry logged |

**Surface-class defaults:** see Pattern 10 table at §10.9.

---

## §13. Rollback

- **Feature flag `ENABLE_CANARY_CRON`:** setting false disables weekly cron; any in-flight canary completes but no new runs trigger.
- **Skill disable path:** `.claude/skills/run-canary/SKILL.md` can be moved to `_disabled_` suffix; `/run-canary` invocation reports "canary disabled" rather than error.
- **Conditional hook removal:** revert the hook file under `.claude/hooks/**`; material-platform-change triggers no longer fire.
- **Canary self-reference exclusion (shaping §13.2 risk #4).** The dogfood canary task edits `src/bid_euchre/ops/dashboard.py`, which is in the §8 conditional-hook trigger path list. A revert-PR that reverts the canary's own merge would re-trigger the canary recursively. **Exclusion mechanism:** the canary's own revert-PR is excluded from material-platform-change triggers via `canary_rollback_pr=true` metadata bit (or equivalent PR-title / commit-footer / PR-label marker) that the conditional-hook evaluator checks before firing. The specific mechanism is an H.0 implementation decision; this sub-plan scaffolds the requirement. Acceptance: a test-driven rollback run demonstrates the revert-PR does not re-trigger a canary run.

---

## Outcome

_Filled after completion._

- Status: (pending H.0 follow-on packet completion)
- PR: TBD
- Deviations from plan: (TBD)
- Issues discovered: (TBD)

---

## Phase 2 Decision Inputs

**Portability readiness:** the canary scenario is portable-by-design —
task is generic (dashboard field edit), substrate surfaces exercised are
substrate-generic (plan / dispatch / author / review / merge /
archivist / KB / rollback). Same scenario shape works for a second
cell.
**Meta-layer need:** no change. Per-cell canary; no meta-surface
required.
**Kill signal for primitive(s) named:** §11-H.0 kill (fails to achieve
≥2 weekly passes in any 4-week window during Phase 0) → re-scope or
demote to simpler event-diff assertion.
**Re-evaluation needed in Phase 3:** yes if canary expansion (3-5 tasks
in H.1) reveals that dogfood-v1 specifically over- or under-covers
certain substrate surfaces, or if the expected-event-type hash produces
disproportionate schema-drift false positives.
**Surprise finding:** canary self-reference risk (ops/dashboard.py both
targeted by task edit and listed as trigger path) surfaced during
shaping (§13.2 risk #4) and is addressed via the metadata-bit exclusion
in §13 above. Kept as an explicit design constraint rather than hiding
the problem by removing dashboard.py from trigger paths.
**Disposition:** open
