# Shaping: Primitive E Phase 0 Execution Spec — Messaging + Active Triage Closeout

**Date:** 2026-04-24
**Lane:** analyst-d
**Packet:** `af575a2143ad` (Primitive E Phase 0 pre-shape — execution belongs to a later packet; this is SHAPING only per Pattern 11)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-E (Primitive E — Messaging and Active Triage Closeout)
**Scope correction applied:** The task-packet title read "observability / metrics / alerts" and the orchestrator course-corrected via recovery message `892c16001583441c` before draft began — observability / metrics / alerts is Primitive A's territory (`plans/steward_platform/1_primitive_A/shaping.md`). This document shapes the **actual** §5-E scope: messaging-bus debt closeout, bus latency telemetry, active-triage event-driven wiring, conditional-hook migration, `triaging-issues` skill integration, and HTTP-hooks ADR 004.
**Sibling artifacts:**
- `plans/steward_platform/1_primitive_A/shaping.md` — Primitive A event schema + dispatcher (E consumes what A emits; see §3)
- `plans/steward_platform/2_primitive_B/shaping.md` — Primitive B adaptive dispatch + prompt-policy (E coordinates on active-triage prompt-policy clause)
- `plans/steward_platform/6_primitive_F/shaping.md` — Primitive F token economy (E consumes F's `/usage` outliers as one active-triage signal)
- `plans/steward_platform/verification_contract/shaping.md` — Pattern 10 format exemplar and enforcement catalog
- `plans/steward_platform/adrs/` — ADR 004 home (HTTP hooks cost/benefit) is authored during execution, not here
**Status:** DESIGN-SPEC — no code, hook edits, or settings.json mutations authored in this artifact. Produces an execution-ready brief for a downstream author-lane packet (hereafter "Packet E1").
**Purpose:** Pre-shape Primitive E's Phase 0 execution so the orchestrator can dispatch Packet E1 (or decompose into E1a / E1b) to an author lane when the Phase 0 kickoff gate passes, with zero additional shaping work. Mirrors the Packet 2a → 2b and Packet 1 → 3 patterns that worked for the verification contract and Primitive A.

---

## §1. Scope of this document

This is a **shaping document**, not a sub-plan, ADR, or governing-plan edit.
Its single output is an execution-ready specification for the §5-E Phase 0
deliverables enumerated in `governing_plan.md` lines 492–521 (Work + Phase 0
Readiness + Phase 1 Validation), tightened by Pattern 10 (every deliverable
carries a verification surface) and by the native-substrate-first preference
(TeammateIdle / StopFailure / PermissionDenied / WorktreeRemove native hooks
replace bespoke polling synthesis).

**What this document specifies:**

1. Messaging-bus proving-debt closeout (issues #2689, #2690, #2691) — scope,
   validation, and packet-boundary (§2).
2. Bus p50/p95 delivery-latency telemetry pipeline (event source → rollup →
   dashboard panel) (§3).
3. Active-issue-triage event-driven wiring — the five event classes
   (CI-red, review-blocked, stalled-lane, orphan-worktree, token-burn) and
   how each resolves to a `gh issue create` call with correct labels (§4).
4. `triaging-issues` skill integration: event-stream consumption contract,
   dedupe via `incident_fingerprint`, label/priority routing (§5).
5. Conditional-hook migration: the 37 files in `.claude/hooks/` surveyed for
   which can migrate from unconditional → conditional without regression;
   matcher specs; ordering contract in `.claude/hooks/README.md` (§6).
6. HTTP-hooks evaluation → ADR 004 scope (shell-glue → HTTP-hook migration
   boundary; cost/benefit table) (§7).
7. Phase 0 Readiness ↔ Pattern 10 verification-surface map (§8).
8. Phase 1 Validation criteria with grep-verifiable assertions (§9).
9. Packet E1 execution spec — files created, modified, order of operations,
   validation commands, success criterion (§10).
10. Self-review against completeness criteria (§11).
11. Phase 2 Decision Inputs subsection (§15.2 schema) (§12).
12. Verification Plan (Pattern 10 mandate) (§13).

**What this document does NOT do:**

- Author any code under `src/bid_euchre/ops/` or any hook script edits.
  Packet E1 implements; this shapes.
- Modify `governing_plan.md` text. §5-E is the governing reference; this
  document consumes it.
- Author ADR 004. ADR 004 is a §7 deliverable of Packet E1; this shaping
  doc specifies the decision shape and evaluation rubric, not the decision
  itself.
- Author Primitive A's event schema or dispatcher. A owns emission; E owns
  consumption. Cross-reference contract lives in §3.
- Define the `incident_fingerprint` field format. That is A's schema work
  (`plans/steward_platform/1_primitive_A/shaping.md` §2.3); E consumes the
  field as opaque string.
- Re-litigate messaging-bus architecture. The bus is a merged, proven
  substrate (session 2026-04-21c); Primitive E closes remaining debt and
  wires observability + active triage on top of it.

### §1.1 Motivation (one paragraph)

Primitive E closes the messaging-and-active-triage gap between "the bus
works" (proven 2026-04-21c; zero lost messages in recent sessions) and "the
bus is observably healthy AND drives proactive triage of substrate failures
without operator-lag." Today: operator discovers CI failures, stalled lanes,
and token anomalies by reading the dashboard; triage-to-issue latency is
measured in minutes-to-tens-of-minutes. Goal #8 (active triage) requires
event-driven discovery with ≥50% of Phase 1 proving-run issues created via
event-triggered flow; Goal #9 (durable near-instantaneous messaging)
requires bus p95 latency targets observably met on the dashboard. E ships
both, with the native-substrate-first preference (TeammateIdle replaces
heartbeat polling; StopFailure becomes direct active-triage input;
conditional hooks replace per-tool-call overhead) doing much of the heavy
lifting. The A-dependency is strict one-way: E consumes events A emits;
E's active-triage subscribers are wired after A's v1.0 dispatcher ships
(A's Packet 3 → E's Packet E1 in time).

### §1.2 Relationship to Primitive A (consumer / producer)

Primitive A produces events into `data/events/events-<YYYY-MM-DD>-NNN.jsonl`
files via the single `events.emit()` dispatcher (see
`plans/steward_platform/1_primitive_A/shaping.md` §3.1). Primitive E
consumes those events — as a reader, not a subscriber, in v1.0 — and
translates them into two downstream actions:

1. **Dashboard metric rollup** (bus latency p50/p95, event-to-issue
   latency p50/p95, lost-message counter) — reads `.meta.json` sidecars +
   the JSONL files.
2. **Active-triage GitHub-issue creation** — event types
   `permission_denied`, `stop_failure`, `teammate_idle`, `worktree_remove`
   (when anomalous), and steward-emitted `ci_failure` / `dispatch_recommendation`
   outliers drive `gh issue create` calls tagged with the correct labels
   (`follow-up`, `fix:bug`, `fix:process`, priority).

The dependency is **strict one-way, time-ordered**:

- A's Packet 3 **must ship before** E's Packet E1 lands its active-triage
  event consumers. If Packet E1 dispatches before Packet 3 merges, E
  blocks on the v1.0 schema and escalates.
- A's event types relevant to E — `permission_denied`, `stop_failure`,
  `teammate_idle`, `worktree_create`, `worktree_remove`, `post_tool_use_failure`
  — are **registered in v1.0** (per A's §2.2). Emitter wiring for
  TeammateIdle and WorktreeCreate/Remove ships in G's worktree-migration
  packet; E's active-triage consumer reads the emitted events regardless
  of whether G has landed, because native hooks emit into the same JSONL
  stream once A's dispatcher is live.
- Bus-delivery latency event types (`message_sent`, `message_delivered`,
  `message_acked`, `message_resolved`, `message_expired`,
  `message_dead_lettered`) already exist in the **current** `events.py`
  (see `src/bid_euchre/ops/events.py` lines 23–68); they route through
  A's v1.0 dispatcher after Packet 3 migrates call-sites.

**Blocking-surface flags (per shaping.md §4.3 — TBD flagging convention):**
Sections that depend on Primitive A's event schema §3.2 first-class IDs
(`trace_id`, `incident_fingerprint`, etc.) and A's JSONL layout are marked
`Verification: TBD — blocking on Primitive A §3.2` in §13 below. Packet E1
must not start until Primitive A Packet 3 merges.

---

## §2. Messaging-bus proving-debt closeout

### §2.1 Scope

Three open follow-ups from the messaging-revamp proving run (session
2026-04-21c) are Primitive E Phase 0 closeout items. They are the last
residual debt before the bus is declared proven and ready for active-triage
consumers to be wired on top.

| Issue | Title | Status (as of 2026-04-24) | Packet candidate |
|---|---|---|---|
| #2689 | `perf(ops): lane-heartbeat PostToolUse hook spawns uv run on every tool call (PR #2686)` | OPEN; already dispatched to author-b packet `77ee82e6e209` per MEMORY.md session 2026-04-21c | Continue dispatched packet |
| #2690 | `fix(convention): lane-id resolution case statement duplicated across hook scripts (PRs #2676, #2686)` | OPEN; already dispatched to author-d packet `3cba4ccdace3` | Continue dispatched packet |
| #2691 | `fix(bug): permission_denied_alert.sh hand-rolled JSON fallback does not escape control chars (PR #2676)` | OPEN; already dispatched to author-c packet `a4162e2431d5` | Continue dispatched packet |

### §2.2 Packet boundary note

These three follow-ups are **already in flight** via previously dispatched
author-lane packets (MEMORY.md session 2026-04-21c). Packet E1 does not
re-dispatch them; it waits for the three PRs to land. If any of the three
stalls, Packet E1 absorbs the remaining scope into its own branch rather
than blocking indefinitely.

**Orchestrator decision required before Packet E1 dispatch:** confirm
whether the three in-flight packets are still active or should be
re-dispatched under Packet E1 scope. Default assumption: re-absorb only if
staleness exceeds 14 days.

### §2.3 Closeout validation

Bus-debt closeout is validated by:

- All three issues closed via `Fixes #N` (Tier 1 per `.claude/rules/deferred/55_issue_closure.md`).
- `scripts/internal/ops.py inbox stats` shows zero dead-lettered messages
  across the last 72 hours.
- `tests/unit/test_ops_message_bus.py` + `tests/integration/test_bilateral_messaging.py`
  remain green after the three PRs merge.
- No new messaging-bus issues filed in the 7 days following the third
  closeout (operator quiet-period observation).

---

## §3. Bus p50/p95 delivery-latency telemetry

### §3.1 Goal

Publish bus delivery latency to the `ops.py dashboard` as a first-class
metric, with p50 and p95 both shown, updated live as messages flow. Driving
requirement: §5-E Phase 0 Readiness item 2 ("Bus p50/p95 metrics published")
and §5-E Phase 1 Validation item 2 ("Bus p95 meets or beats target set in
Primitive A"). The target itself is set by Primitive A per A's §7
Phase 1 Validation table (currently ≤30s p95).

### §3.2 Event source

Bus latency telemetry derives from the existing message-bus events
registered in `src/bid_euchre/ops/events.py::VALID_EVENT_TYPES`:

- `message_sent` (emitted in `message_bus.py::send_message`)
- `message_delivered` (emitted in `message_bus.py::mark_delivered`)
- `message_acked` (emitted in `message_bus.py::ack_message`)
- `message_resolved` (emitted in `message_bus.py::resolve_message`)
- `message_expired` (emitted in `message_bus.py::_expire_stale_*`)
- `message_dead_lettered` (emitted in `message_bus.py::check_dead_letters`)

Each of these events carries `message_id`, `from_lane`, `to_lane`,
`message_type`, `priority`, and `timestamp` already. Packet E1 adds no new
event types; the existing set is sufficient for p50/p95 computation.

**A-dependency flag (Pattern 10 shaping.md §4.3):** the event records
currently live in `.claude/runtime/events/events.jsonl` (pre-v1.0
layout). Packet E1 reads from whichever layout is canonical when it
ships: if A's Packet 3 has landed and migrated to
`data/events/events-<YYYY-MM-DD>-NNN.jsonl`, E reads from there; otherwise
E reads from the legacy `.claude/runtime/events/events.jsonl`. A reader
helper — `src/bid_euchre/ops/event_reader.py` (new in Packet E1) —
absorbs the layout switch in one place.

**Verification: TBD — blocking on Primitive A §3.2** for the §9.7
first-class IDs (`trace_id`, `task_id`, `lane_id`, `session_id`) which
the latency aggregator is expected to use for grouping. If A has not
shipped them, the aggregator groups by existing payload fields
(`message_id`, `from_lane`, `to_lane`) and a v1.N follow-on adds first-class
ID grouping.

### §3.3 Latency computation

Two derived metrics:

1. **`bus_delivery_latency`** — per-message wall-clock delta from
   `message_sent.timestamp` to `message_delivered.timestamp`. Histogram
   computed over the most recent 1000 messages or last 24 hours (whichever
   is smaller).
2. **`bus_ack_latency`** — per-message wall-clock delta from
   `message_delivered.timestamp` to `message_acked.timestamp`. Shown
   alongside delivery latency to distinguish transport latency (bus → inbox)
   from consumer latency (inbox → ack).

Aggregation: p50, p95, p99 (p99 captured for tail-risk visibility; not
required by governing plan).

Computation home: `src/bid_euchre/ops/bus_latency.py` (new in Packet E1).
Pure function: `compute_latency_stats(events: Iterable[dict]) -> LatencyStats`.
Caller: dashboard `build_dashboard_view()`.

### §3.4 Dashboard surface

Extend `src/bid_euchre/ops/dashboard.py::build_dashboard_view` to include a
`Bus` panel:

```
Bus  delivered: 1847  p50: 0.3s  p95: 2.1s  p99: 8.7s  lost: 0
     acked:    1811  p50: 41s   p95: 184s  dead-letter: 3
     expired:  7  (7d)
```

Text format and JSON format both extended. `DashboardView` dataclass grows
a `bus_stats: BusStats | None` field (None when event stream is unreadable).

### §3.5 Sparkline extension (optional, per §5.6 verification-contract pattern)

Mirror the canary-sparkline pattern (verification-contract shaping.md
§5.6): dashboard sub-row shows a mini-sparkline for `bus_delivery_latency_p95`
across the last 8 sampling windows. Sparkline implementation lives in
`src/bid_euchre/ops/bus_latency.py` alongside the aggregator.

**Deferral note:** Sparklines are a nice-to-have, not gating. If
Packet E1 LOC pressure surfaces, defer sparklines to a v1.N follow-on and
ship only the numeric panel in Phase 0.

### §3.6 Rollback path

- Bus panel rendering is gated on `STEWARD_BUS_PANEL_ENABLED` env var
  (default `"true"`).
- Set `STEWARD_BUS_PANEL_ENABLED=false` → panel disappears from dashboard;
  no other state changes.
- If the aggregator crashes (malformed events, disk pressure), the panel
  renders `Bus  <aggregator error>  fallback: existing inbox stats`
  rather than taking down the whole dashboard. Matches the never-raise
  contract A's dispatcher uses (§3.1 of A's shaping doc).

---

## §4. Active-issue-triage event-driven wiring

### §4.1 Goal

Replace operator-discovery-after-the-fact with event-driven issue
creation. Per §5-E Work bullet 3: event-driven signals auto-create GitHub
issues with correct labels, sourced from native lifecycle hooks rather
than custom polling synthesis.

Five event classes ship in Phase 0, meeting §5-E Phase 0 Readiness item
3 ("Active-triage wiring live for at least 4 event classes"). Fifth
class (orphan-worktree) brings coverage to 5 for headroom.

### §4.2 The five active-triage event classes

| # | Signal class | Event source | Issue label(s) | Priority | Example title |
|---|---|---|---|---|---|
| 1 | CI red | A's `post_tool_use_failure` when `tool_name=gh` + signature matches CI fail; OR steward-emitted `ci_failure` event (existing) | `follow-up`, `fix:bug` | high | `fix(ci): <test_name> failing on PR #<N>` |
| 2 | Review blocked | A's `permission_denied` event for merge / push tool calls | `follow-up`, `fix:process` | normal | `review: permission denied on <action> in PR #<N>` |
| 3 | Stalled lane | A's `teammate_idle` event with idle_duration > threshold | `follow-up`, `fix:process` | high | `ops: lane <lane_id> idle >N minutes; stalled on <last_action>` |
| 4 | Orphan worktree | A's `worktree_remove` event without matching `worktree_create`, OR audit surfacing worktrees absent from settings | `follow-up`, `fix:process` | normal | `ops: orphan worktree <path> detected` |
| 5 | Token-burn anomaly | Primitive F's `/usage` outlier detection (F publishes `token_usage_outlier` event) | `follow-up`, `fix:process` | normal | `token-economy: <lane> burned <N> tokens over <threshold>` |

**Dedupe via `incident_fingerprint`:** each event class computes an
`incident_fingerprint` (per A's §2.3) deterministically from its source
event (test name for CI fails; action + PR for review-blocked; lane_id for
stalled-lane; worktree-path for orphan-worktree; lane + hour-bucket for
token-burn). Duplicate fingerprints within a 24-hour window are coalesced:
`triaging-issues` skill sees the existing issue and appends a comment
instead of opening a duplicate. See §5.3 below.

**Native-substrate-first note:** All five signal classes route through A's
native lifecycle hooks (TeammateIdle, PermissionDenied, StopFailure,
WorktreeCreate/Remove, post_tool_use_failure) rather than bespoke polling.
This is the core §5-E shift.

### §4.3 Consumer architecture

`src/bid_euchre/ops/active_triage.py` (new in Packet E1) is the single
consumer module. Shape:

```python
def run_triage_cycle(
    *,
    events_since: datetime | None = None,
    dry_run: bool = False,
) -> TriageResult:
    """Read events since cursor; for each actionable event, file or update a GitHub issue.

    Args:
        events_since: Only process events with timestamp >= this value.
            Defaults to last-run cursor (persisted to .claude/runtime/active_triage/last_cursor.txt).
        dry_run: If True, compute fingerprints and intended actions but do not call gh.

    Returns:
        TriageResult with lists of issues created, issues updated, issues skipped (dedupe),
        and errors.
    """
```

Invoked by:

1. **Cron** — ops lane runs `/loop Nm /active-triage` (cadence TBD — see
   §4.5 below; recommended 3-5 minutes).
2. **On-demand** — any lane runs `/active-triage` or
   `uv run python scripts/internal/ops.py triage run`.
3. **Hook-triggered** (Phase 1 enhancement, not Phase 0) — conditional
   hooks on the relevant event types invoke `active_triage.run_triage_cycle`
   synchronously. Phase 0 ships cron-only to keep the substrate simple.

**Never-raise contract:** failures in the triage cycle (malformed events,
`gh` errors, rate limits) log to stderr and continue; do not crash the ops
lane's `/loop`. Matches Primitive A's dispatcher contract.

### §4.4 Feature-flag rollback

Per §5-E Phase 0 Readiness item 4 ("Rollback path validated: active-triage
can be disabled via a feature flag without losing inbox state"):

- Feature flag: `STEWARD_ACTIVE_TRIAGE_ENABLED` (default `"true"` once
  Phase 0 Readiness is met; `"false"` during initial Packet E1 soak).
- Off state: `active_triage.run_triage_cycle` reads events + computes
  intended actions but does not call `gh`. Events remain in the JSONL
  stream (no state loss); the triage cursor does not advance when flag is
  off (re-enabling replays missed events).
- On/off transitions are logged via `events.emit("config_change", ...)`
  when A's dispatcher is live; stderr log otherwise.
- **Inbox-state independence:** the active-triage consumer never writes
  to the message bus. Bus state (inbox, pending, dead-lettered) is
  orthogonal to triage state. Rollback validation shows this explicitly.

### §4.5 Cadence tuning

Cron cadence for the triage cycle is a Phase 0 tuning knob:

- **Default:** 5 minutes (`/loop 5m /active-triage`).
- **Phase 1 Validation target:** event-to-issue p95 latency ≤ 10 minutes
  (per §5-E Phase 1 Validation "Zero stale-catch incidents"; stale-catch
  threshold = 10 minutes).
- **If the 5-minute default produces > 10min p95:** step down to 3 minutes.
- **If 3 minutes still produces > 10min p95:** escalate — likely `gh`
  rate-limit or GitHub API latency; switch to a subscriber-style hook
  trigger (Phase 1 work).

Cadence is operator-configurable via the `/loop` invocation; not hardcoded.

---

## §5. `triaging-issues` skill integration

### §5.1 Goal

Integrate the existing `triaging-issues` skill
(`.claude/skills/triaging-issues/SKILL.md`) with event-driven inputs rather
than relying solely on manual invocation from a review follow-up. The skill
remains the canonical place for issue-creation convention; `active_triage`
calls into it.

### §5.2 Contract

Packet E1 extends the skill's surface without breaking its existing
operator-invocable interface:

- **Existing surface:** operator runs `/triaging-issues` from a lane;
  skill reads a description + finding and files an issue with appropriate
  labels + priority.
- **New surface (for `active_triage` consumption):** skill exposes a
  programmatic entry point (CLI or Python) that accepts a structured
  `TriageInput` object:
  ```python
  @dataclass
  class TriageInput:
      signal_class: Literal["ci_red", "review_blocked", "stalled_lane", "orphan_worktree", "token_burn"]
      title_hint: str                  # pre-formatted issue title template
      body_sections: dict[str, str]    # section name → content (Context, Evidence, Reproduction)
      labels: list[str]                # required labels (`follow-up` always auto-added)
      priority: Literal["low", "normal", "high", "urgent"]
      incident_fingerprint: str        # dedupe key (see §5.3)
      source_event_id: str             # A's event record ID for traceability
  ```
- **Implementation:** the skill's `SKILL.md` gains a "Programmatic
  Invocation" section; the actual logic moves to
  `scripts/internal/triage_cli.py` (new in Packet E1) so both operator and
  `active_triage` consume the same code path.

### §5.3 Dedupe and coalescing

Deduplication is the skill's responsibility (not `active_triage`'s):

- Before filing, skill runs:
  ```bash
  gh issue list --label follow-up --state open --search "<fingerprint>" --json number,title,body
  ```
  where `<fingerprint>` is the `incident_fingerprint` value, searched
  against issue bodies.
- Match → append an evidence comment to the existing issue instead of
  opening a new one. Comment format:
  ```
  ## Recurrence observed
  <timestamp> — fingerprint <fp> — event_id <eid>
  <condensed context from source event>
  ```
- No match → open new issue; embed fingerprint in the issue body under
  a hidden `<!-- fingerprint: <fp> -->` marker for future dedupe queries.

**Coalescing window:** 24 hours from first observation. After 24h, a
recurrence re-opens a new issue (prevents a single stale fingerprint from
absorbing entirely new recurrence patterns).

### §5.4 Label and priority defaults

Labels default to the §4.2 table mappings. Operator can override via
programmatic call's `labels` field. Priority defaults per table; override
via `priority` field.

**`fix:*` label families** already defined in
`.claude/rules/deferred/60_review_gate.md`; E's active-triage reuses them,
does not invent new families. ADR 004 (§7) may propose new label families
if HTTP-hooks adoption creates new triage categories; Phase 0 stays within
existing families.

### §5.5 Verification touchpoints

- Unit test: `tests/unit/test_triage_cli.py` (new) — covers programmatic
  invocation with each of the 5 signal classes; dedupe via mocked
  `gh issue list`.
- Integration test: `tests/integration/test_active_triage_e2e.py` (new,
  skipped-by-default; gated on `STEWARD_TEST_GH_INTEGRATION`) — drives one
  complete signal → event → issue-or-comment cycle against a disposable
  test repo.
- Smoke: operator-readable: `uv run python scripts/internal/ops.py triage run --dry-run`
  prints intended actions; zero GH side effects.

---

## §6. Conditional-hook migration

### §6.1 Goal

Per §5-E Work bullet 4: "Migrate existing hook set from unconditional to
conditional hooks where safe; document ordering and scope per hook in
`.claude/hooks/README.md`." This reduces per-tool-call overhead across the
37 hook files in `.claude/hooks/` and prevents the §5-E cascade risk
(unconditional hooks spawning `uv run` per tool call — exactly the
#2689 regression) from recurring.

### §6.2 Current-state survey

`.claude/hooks/` contains 37 files (shell scripts + Python helpers) plus
`README.md`. `.claude/settings.json` registers them with a mix of matchers:

- **Matcher-scoped:** `PreToolUse` + `matcher: "Edit|Write"` (and similar)
  already scope by tool name → already "conditional."
- **Universal:** `PostToolUse` + `matcher: "*"` — fires on every tool call.
  These are the migration candidates.
- **Event-scoped:** `PermissionDenied`, `Stop`, `UserPromptSubmit`,
  `SessionStart`, etc. — fire on native lifecycle events. Already
  event-conditional; no migration needed.

Packet E1 produces a per-hook disposition table in
`.claude/hooks/README.md` §Disposition columns: Current Matcher | Proposed
Matcher | Rationale | Risk if Narrowed. Format:

```
| Hook | Current | Proposed | Rationale | Risk |
|---|---|---|---|---|
| post-bash-dispatch.sh | PostToolUse matcher="*" | PostToolUse matcher="Bash" | Only handles bash dispatch side-effects | Low — existing non-bash tool-calls no-op the hook body |
| lane-heartbeat-post-tool.sh | PostToolUse matcher="*" | PostToolUse matcher="Bash\|Edit\|Write" | Heartbeat only needed after substantive tool-calls, not reads | Medium — defer to pure-shell rewrite (#2689) |
... (37 rows)
```

**Survey method:** Packet E1 author reads each hook, identifies the tool
classes it actually acts on (vs. those where it short-circuits with
"not my concern"), and proposes the narrowest matcher that preserves
current behavior.

### §6.3 README.md documentation contract

`.claude/hooks/README.md` gains three sections in Packet E1:

1. **Hook execution order.** Claude Code runs hooks in registration order
   within a matcher group; the README explicitly lists the contract per
   lifecycle event. Prevents future regressions from hook-ordering
   assumptions (e.g., `permission-denied-log.sh` must run before
   `alert-inject.sh` so the alert has a log entry to reference).
2. **Hook scope per file.** For each of the 37 files: what triggers it,
   what it reads, what it writes, what it short-circuits. One-line-per-hook
   summary.
3. **Per-hook disposition table** (§6.2 above). Lives under a
   `## Conditional-Hook Migration` heading.

### §6.4 Migration approach — bounded, reversible

Conditional-hook migration is applied **per-hook**, not in one big PR:

- Packet E1 ships with ≥8 hook migrations + the README.md documentation.
- Remaining ~15–20 hooks ship as v1.N follow-ons; each migration is a
  single-file diff (`.claude/settings.json` matcher change) + its
  disposition-row update.
- Each migration is independently reversible: revert the settings.json
  diff, hook returns to universal matcher.

### §6.5 Regression-protection tests

- `tests/unit/test_hooks_inventory.py` (new) — asserts every file in
  `.claude/hooks/` has a disposition row in `.claude/hooks/README.md`.
  Prevents silent additions of hook files that bypass the discipline.
- `tests/unit/test_settings_hooks_contract.py` (new) — parses
  `.claude/settings.json` and asserts no hook is registered with
  `matcher: "*"` unless the disposition row explicitly justifies
  universal scope (identified by a sentinel string in the row).

---

## §7. HTTP-hooks evaluation → ADR 004

### §7.1 Goal

Per §5-E Work bullet 6 and governing plan §14 (Open Item 14 — "ADR 004 —
hook migration boundary. Files which existing custom hooks migrate to
native lifecycle subscriptions, which migrate to conditional-hook scope,
which migrate to HTTP hooks, and which stay bespoke."):

- Produce ADR 004 at
  `plans/steward_platform/adrs/004-http-hooks-migration-boundary.md`.
- ADR documents the cost/benefit of migrating each of the 37 hook files to
  one of four destinations: (a) native lifecycle subscription (if Claude
  Code grew a native hook for the surface); (b) conditional-hook (matcher
  narrowing, per §6); (c) HTTP hook (out-of-process); (d) bespoke (keep
  as-is).

### §7.2 Evaluation rubric

Per-hook scoring against four axes:

| Axis | Description | Weight |
|---|---|---|
| **Portability** | Does the hook carry Bid-Euchre literals that HTTP-ization would clean up? | high |
| **Latency** | Does per-tool-call shell-spawn dominate? Would HTTP save measurable ms? | medium |
| **Observability** | Does HTTP migration give steward a reusable HTTP-hook substrate for future work? | medium |
| **Risk** | Forward-compat risk if Claude Code changes native hook payload formats | low |

Score each axis 0–3; sum; destinations by band:

- Sum ≥9 → HTTP hook (high-priority migration candidate)
- Sum 6–8 → Conditional hook (matcher narrowing)
- Sum 3–5 → Bespoke (status quo)
- Sum <3 → Delete (hook has decayed to dead weight)

### §7.3 Expected output

ADR 004 §Decision contains:

- A per-hook disposition table with scores per axis + destination +
  rationale.
- A migration sequence: which hooks go in Packet E1, which in v1.N
  follow-ons, which defer to Phase 1.
- A "keep bespoke" subset with explicit rationale for each (e.g.,
  `pre-merge-review-guard.sh` stays bespoke because it enforces the
  merge-guard contract and HTTP-ization would add latency to merge
  commands).

### §7.4 Phase 0 scope vs. Phase 1 scope

**Phase 0 (Packet E1):** ADR 004 authored; disposition table populated;
zero migrations to HTTP executed. The ADR is the deliverable; migrations
execute in v1.N follow-ons.

**Phase 1:** top 3–5 HTTP-hook migration candidates (per ADR 004 scoring)
execute. Used as scope-matching fodder for Phase 1 proving-run evidence on
goal #5 (token-efficient) and goal #8 (active-triage latency).

### §7.5 ADR 004 cross-references

- Draft 8 governing plan §10.9 Pattern 2 (native-substrate-first preference)
  — HTTP hooks are a reusable substrate choice aligned with Pattern 2.
- Draft 8 governing plan §10.9 Pattern 9 (load-bearing-ownership) —
  every hook has a named owner after ADR 004 lands.
- `.claude/hooks/README.md` §Disposition table — stays in sync with
  ADR 004's migration plan.

---

## §8. Phase 0 Readiness criteria (Pattern 10 mapping)

Per `governing_plan.md` §5-E Phase 0 Readiness (lines 511–515), every
criterion ties to a named verification surface per Pattern 10. This section
provides the explicit map.

| §5-E Phase 0 Readiness criterion | Verification surface | Acceptance condition |
|---|---|---|
| 1. All three follow-up PRs merged; bus closeout debt resolved | `gh issue list --state closed --search "2689 2690 2691"` → expect 3 matches | 3 closed issues with `Fixes` link to merged PRs |
| 2. Bus p50/p95 metrics published | `tests/unit/test_bus_latency.py::test_aggregator_computes_p95` + dashboard scrape `grep -E "Bus\\s+delivered" <(uv run python scripts/internal/ops.py dashboard --json)` | test passes; JSON has `bus_stats.delivery_p95_ms` populated |
| 3. Active-triage wiring live for at least 4 event classes | `tests/unit/test_active_triage.py::test_five_signal_classes_route` + manual smoke `uv run python scripts/internal/ops.py triage run --dry-run` with seeded events covering 5 classes | test passes for all 5 classes; dry-run prints 5 intended `gh issue create` actions |
| 4. Rollback path validated: active-triage can be disabled via a feature flag without losing inbox state | `tests/integration/test_active_triage_rollback.py::test_flag_off_preserves_inbox` | pytest passes: flip flag off → triage no-ops → inbox state unchanged → flip on → backlog processed |

### §8.1 Additional Pattern-10-driven readiness items

Beyond §5-E's four Phase 0 Readiness criteria, the following ship in
Packet E1 and carry verification surfaces per Pattern 10 (see §13):

| Deliverable | Class | Verification surface |
|---|---|---|
| `.claude/hooks/README.md` documentation (§6.3) | KB-class artifact (per Pattern 10 deliverable-class table) | `tests/unit/test_hooks_inventory.py::test_all_hooks_documented` — asserts 1-to-1 correspondence between `.claude/hooks/*.sh,*.py` and README disposition-table rows |
| ADR 004 HTTP-hooks migration boundary (§7) | ADR | Commit citation in ADR + Pattern 7 rollback via ADR-supersession route |
| Conditional-hook migrations (≥8 in Packet E1) | config change (.claude/settings.json) | rollback test: revert each matcher diff; hook behavior returns to universal scope without regression (per-migration) |
| `triage_cli.py` (§5.2) | new script under `scripts/internal/` | `tests/unit/test_triage_cli.py` — covers 5 signal classes + dedupe |
| `active_triage.py` (§4.3) | new Python module under `src/bid_euchre/ops/` | `tests/unit/test_active_triage.py` — cycle + never-raise + flag-off |
| `bus_latency.py` (§3.3) | new Python module under `src/bid_euchre/ops/` | `tests/unit/test_bus_latency.py` — aggregator + edge cases |
| `event_reader.py` (§3.2) | new Python module under `src/bid_euchre/ops/` | `tests/unit/test_event_reader.py` — covers A's v1.0 path + legacy path |

### §8.2 Unowned-event-class audit

Phase 0 readiness includes a one-time audit:

- For each of the 5 active-triage signal classes, find the event source
  (native hook, steward event, or F's `/usage` outlier) and verify at
  least one emitter call-site is live. If any signal class's emitter is
  not yet live, Packet E1 ships the consumer subscribing to a
  not-yet-emitted event class — acceptable, but the audit must report
  it as "deferred to <primitive>" rather than "missing."
- Audit command: `uv run python scripts/internal/ops.py triage audit` (new
  subcommand; lists each signal class + its emitter status).

---

## §9. Phase 1 Validation criteria

Per `governing_plan.md` §5-E Phase 1 Validation (lines 517–521), all
criteria are grep-verifiable or test-verifiable:

| §5-E Phase 1 Validation criterion | Grep / verification |
|---|---|
| Zero lost-message incidents across preflight + proving run | dashboard `Bus lost: 0` throughout Phase 1; `grep '"event_type":"message_dead_lettered"' data/events/events-*.jsonl \| wc -l` → 0 OR matches followed by a recovery event within N minutes |
| Bus p95 meets or beats target set in Primitive A | dashboard `Bus p95` ≤ A's §7 target (currently 30s); sampled daily during proving run |
| Active triage produces ≥50% of issues created during the proving run, measured over ≥20 observed issues | `gh issue list --search "is:issue created:>=<proving-run-start>" --label follow-up --json labels,body \| jq` — count issues with `fingerprint: ` marker in body → ratio ≥ 0.5 |
| Zero stale-catch incidents recorded | custom assertion: for each active-triage-eligible event in `data/events/`, measure timestamp delta from event to matching issue/comment; p95 ≤ 10 min; zero >30 min outliers |

### §9.1 Additional Pattern-10-driven assertions

Beyond §5-E's direct criteria:

- Event stream contains ≥1 instance of each of the 5 signal classes during
  the proving run. Verification:
  ```bash
  for cls in ci_red review_blocked stalled_lane orphan_worktree token_burn; do
      grep -c "\"signal_class\":\"$cls\"" data/events/events-*.jsonl || echo "$cls MISSING"
  done
  ```
- `triaging-issues` dedupe rate matches expected (recurrence rate ≥1 per
  signal class over proving run → at least 1 issue has a "Recurrence
  observed" comment).
- Every conditional-hook migration from Packet E1 maintained its original
  behavior: no hook-related regressions in review findings during Phase 1.

---

## §10. Packet E1 execution spec

Concrete enough that an author lane can execute without additional shaping.

### §10.1 Scope declared (Packet E1)

**Files created:**

- `src/bid_euchre/ops/active_triage.py`
- `src/bid_euchre/ops/bus_latency.py`
- `src/bid_euchre/ops/event_reader.py`
- `scripts/internal/triage_cli.py`
- `tests/unit/test_active_triage.py`
- `tests/unit/test_bus_latency.py`
- `tests/unit/test_event_reader.py`
- `tests/unit/test_triage_cli.py`
- `tests/unit/test_hooks_inventory.py`
- `tests/unit/test_settings_hooks_contract.py`
- `tests/integration/test_active_triage_rollback.py`
- `tests/integration/test_active_triage_e2e.py` (skipped-by-default)
- `plans/steward_platform/adrs/004-http-hooks-migration-boundary.md`
- `.claude/skills/active-triage/SKILL.md` (thin wrapper — invokes
  `ops.py triage run`)
- `.claude/skills/triaging-issues/SKILL.md` **(modified; new "Programmatic
  Invocation" section added — counts as created-fragment)**

**Files modified:**

- `.claude/settings.json` — register conditional matchers for ≥8 hooks
  (§6.4)
- `.claude/hooks/README.md` — add ordering + scope + disposition table
  sections (§6.3)
- `src/bid_euchre/ops/dashboard.py` — add `Bus` panel reading
  `bus_latency` output
- `scripts/internal/ops.py` — add `triage` subcommand group (`triage run`,
  `triage audit`, `triage rollback-test`)
- `.claude/rules/feature_flags.md` — new entry `STEWARD_ACTIVE_TRIAGE_ENABLED`,
  plus `STEWARD_BUS_PANEL_ENABLED`
- `plans/steward_platform/governing_plan.md` §14 — mark "ADR 004" open
  item as resolved by Packet E1 (referenced from the ADR)
- `MEMORY.md` — post-merge: add Primitive E Phase 0 closeout entry

**Files NOT modified by Packet E1 (deferred to other packets):**

- Primitive A event schema + dispatcher (A's Packet 3) — Packet E1
  consumes only; does not author.
- Remaining ~15–20 hook conditional-hook migrations — v1.N follow-ons per
  ADR 004 sequence.
- HTTP-hook migrations themselves — Phase 1 work per §7.4.
- `ops/worktrees.py` native-WorktreeCreate/Remove migration — Primitive G.
- Phoenix container / deployment — Primitive A Packet 3 or 3.1.

### §10.2 Order of operations (Packet E1)

1. **Branch + scope lock.** `feat/primitive-e-active-triage-phase0` from
   `origin/main`.
2. **Blocker check.** Verify Primitive A's Packet 3 has merged
   (`ls src/bid_euchre/ops/event_schema.py`). If not, escalate to
   orchestrator; do not proceed.
3. **Event-reader first.** `event_reader.py` with dual-layout support
   (v1.0 `data/events/` + legacy `.claude/runtime/events/`). Unit test
   covers both layouts and graceful degradation on missing files.
4. **Bus-latency aggregator second.** `bus_latency.py` pure function;
   unit test covers aggregation, empty-stream, malformed records.
5. **Dashboard integration third.** Extend `dashboard.py::build_dashboard_view`;
   add `Bus` panel to text + JSON output. Unit test covers rendering +
   feature-flag disable.
6. **Active-triage fingerprinting fourth.** `active_triage.py` skeleton
   with fingerprint helpers per signal class. Unit test covers
   determinism + collision boundaries.
7. **`triage_cli.py` programmatic entry fifth.** Extract dedupe + create
   logic from `triaging-issues` SKILL.md into reusable CLI. Unit test
   covers each signal class + mocked `gh` calls.
8. **Active-triage consumer wiring sixth.** `active_triage.py` full
   `run_triage_cycle` implementation calling `triage_cli.py`. Unit +
   integration test cover 5 signal classes + flag-off rollback.
9. **`ops.py triage` subcommand seventh.** CLI wrapper for
   `run_triage_cycle`. Covers `--dry-run` mode explicitly.
10. **Conditional-hook migration eighth.** Pick ≥8 of the 37 hooks per
    §6.2 survey; edit `.claude/settings.json` matchers; update
    `.claude/hooks/README.md` disposition table. Per-hook rollback test
    recorded inline in commit messages.
11. **README.md documentation ninth.** Write `.claude/hooks/README.md`
    ordering + scope + disposition-table sections. Unit test
    (`test_hooks_inventory.py`) asserts 1-to-1 correspondence.
12. **ADR 004 authored tenth.** Score all 37 hooks per §7.2 rubric;
    author migration-boundary ADR at
    `plans/steward_platform/adrs/004-http-hooks-migration-boundary.md`.
13. **`.claude/skills/active-triage/SKILL.md` eleventh.** Thin wrapper
    invoking `ops.py triage run`. Covers operator-invocable path.
14. **`.claude/skills/triaging-issues/SKILL.md` programmatic section
    twelfth.** Add "Programmatic Invocation" section documenting
    `TriageInput` schema + `triage_cli.py` entry point.
15. **Self-run audit thirteenth.** `uv run python scripts/internal/ops.py triage audit`
    → green on all 5 signal classes (or explicitly-marked "deferred");
    `uv run python -m pytest tests/unit/test_hooks_inventory.py`
    → green; `make check-gated` (foreground) → green.
16. **Open PR.** Title: `feat(ops): land Primitive E Phase 0 closeout —
    active triage + bus latency + conditional hooks + ADR 004 (Packet E1)`.
    Body includes `Verification Performed` section with audit + lint +
    pytest output pasted per §4.2 of analyst prompt-policy.

### §10.3 Validation commands (Packet E1 Tier 2)

```bash
# Tier 1 — unit (during development)
uv run python -m pytest tests/unit/test_event_reader.py
uv run python -m pytest tests/unit/test_bus_latency.py
uv run python -m pytest tests/unit/test_active_triage.py
uv run python -m pytest tests/unit/test_triage_cli.py
uv run python -m pytest tests/unit/test_hooks_inventory.py
uv run python -m pytest tests/unit/test_settings_hooks_contract.py

# Tier 1 — integration
uv run python -m pytest tests/integration/test_active_triage_rollback.py
STEWARD_TEST_GH_INTEGRATION=1 uv run python -m pytest tests/integration/test_active_triage_e2e.py

# Self-run audit
uv run python scripts/internal/ops.py triage audit
uv run python scripts/internal/ops.py triage run --dry-run

# Dashboard smoke (bus panel)
uv run python scripts/internal/ops.py dashboard --json | jq '.bus_stats'
# Expect: populated object with delivery_p50_ms / delivery_p95_ms / lost

# Hook inventory lint
uv run python -m pytest tests/unit/test_hooks_inventory.py -v

# Tier 2 (pre-PR; foreground, never background)
git fetch origin main && git rebase origin/main
make check-gated
```

### §10.4 Coordination notes (Packet E1)

- **Blocking dependency on Primitive A's Packet 3.** If Packet 3 has not
  merged at Packet E1 dispatch time, Packet E1 blocks and escalates. The
  blocker-escalation path is the existing `message send --type blocker
  --priority high` via `ops.py`.
- **Issue-closeout dependency on #2689/2690/2691.** Packet E1 does not
  re-dispatch; it confirms closure before opening PR. If any of the three
  is stalled, escalate to orchestrator for decision: absorb into E1 or
  wait.
- **Primitive F coordination.** Signal class 5 (token-burn anomaly)
  depends on F emitting `token_usage_outlier` events. If F's Packet 11
  has not shipped that emitter by Packet E1 completion, signal class 5
  is marked "deferred to F" in the audit; remaining 4 classes satisfy
  §5-E Phase 0 Readiness item 3.
- **Primitive G coordination.** Signal class 4 (orphan-worktree) depends
  on G's worktree-migration packet emitting `worktree_create`/`_remove`
  via native hooks. If G has not shipped, Packet E1 uses the existing
  `ops.py worktrees` output as the event source (degraded mode);
  re-migrates to native hook events when G ships.
- **Conditional-hook migration scope pressure.** 8 migrations is the
  floor; Packet E1 may ship more if LOC budget allows. If author
  estimates Packet E1 exceeds 2500 net LOC, orchestrator may decompose
  into Packet E1a (active triage + bus latency) and Packet E1b
  (conditional-hook migration + ADR 004 + README.md) to keep PR review
  load reasonable.
- **Native-substrate-first discipline.** If a native Claude Code feature
  surfaces during Packet E1 that subsumes E's bespoke synthesis (e.g.,
  native active-triage primitive; native bus-latency telemetry), file an
  ADR (per §10.9 Pattern 2) and coordinate with orchestrator. Do not
  silently rewrite to native without an ADR.

### §10.5 Packet E1 success criterion

> Packet E1 is complete when:
>
> (a) all files in §10.1 are created or modified per spec,
> (b) §10.3 validation commands pass (foreground; Tier 2 green),
> (c) `ops.py triage audit` reports green: each of the 5 signal classes
>     has at least one emitter live, or is marked "deferred to
>     <primitive>",
> (d) `.claude/hooks/README.md` has a disposition row for every file in
>     `.claude/hooks/` (test_hooks_inventory enforces),
> (e) at least 8 conditional-hook migrations landed in
>     `.claude/settings.json` with accompanying rollback-test notes,
> (f) ADR 004 authored and committed with per-hook scoring table,
> (g) PR merged with `Verification Performed` evidence in the body
>     (audit output + lint output + pytest output + rollback-test output
>     pasted per analyst-policy §4.2).
>
> After Packet E1 merges, §5-E Phase 0 Readiness is declared met and
> Primitive E enters Phase 1 Validation instrumentation readiness.

### §10.6 Packet E1 effort estimate

- LOC estimate: ~1800–2500 net additions. Approximate split:
  - 500–700 LOC: `active_triage.py` + `triage_cli.py` + tests
  - 300–400 LOC: `bus_latency.py` + `event_reader.py` + tests
  - 200–300 LOC: dashboard `Bus` panel + settings.json diffs
  - 200–300 LOC: `tests/unit/test_hooks_inventory.py` + `test_settings_hooks_contract.py`
  - 400–600 LOC: `.claude/hooks/README.md` (ordering + scope + disposition)
  - 200–300 LOC: ADR 004 content
  - 100–200 LOC: skill markdown + feature-flags + MEMORY.md
- Author-lane effort hint: **high**.
- Estimated turnaround: 2–3 author-lane sessions if no major blockers
  surface. 4 if conditional-hook migrations hit unexpected matcher
  regressions; 5 if ADR 004 per-hook scoring discovers significant
  scope we had not budgeted.
- Decomposition option: split to E1a (triage + latency + dashboard;
  ~1200 LOC) and E1b (conditional hooks + README + ADR 004; ~1000 LOC).
  Orchestrator's call based on lane capacity.

---

## §11. Self-review against completeness criteria

The analyst-lane prompt-policy clause (§4.3 of
`verification_contract/shaping.md`) requires shaping docs end with a
`## Verification Plan` section (§13 below). This section is the analyst's
self-audit against shaping completeness.

### §11.1 Completeness criteria stress-test

| Criterion | Check | Outcome |
|---|---|---|
| Metric catalog (event→metric rollup) named | §3 specifies bus_delivery_latency + bus_ack_latency sourced from message_* event types | ✓ |
| Alert taxonomy (severity/routing) named | §4.2 enumerates 5 signal classes with labels + priority + dedupe | ✓ (5 classes, 4 labels, 4 priorities) |
| Dashboard/equivalent surface named | §3.4 specifies `Bus` panel; §3.5 specifies sparkline extension (optional) | ✓ |
| Rollup queries named | §9 grep-verifiable commands; §8 readiness surfaces include dashboard scrapes + pytest paths | ✓ |
| Execution Packet Spec present | §10 with files/order/validation/success criterion/effort | ✓ |
| Verification Plan (Pattern 10 mandate) | §13 with per-deliverable surface | ✓ |
| A-dependency flagged explicitly | §1.2 identifies strict one-way dependency; §3.2 and §8.1 flag specific TBD-blocking surfaces | ✓ |
| Phase 0 Readiness → Pattern 10 surface map | §8 has all 4 §5-E Phase 0 Readiness criteria mapped + extras | ✓ |
| Phase 1 Validation grep-verifiable | §9 has all 4 §5-E criteria mapped with explicit commands | ✓ |
| Cross-ref existing infra | §2 cites issues; §3 cites message_bus.py + events.py; §4.1 cites monitor.py severity taxonomy; §5.1 cites triaging-issues skill; §6.2 cites all 37 hook files | ✓ |
| Exemplar followed (Primitive A shaping.md) | Section structure parallels §1/§2/§3/§4/§5/§6/§7/§8/§9/§10/§11 of A's doc; §15.2 Phase 2 Decision Inputs appears at §12 here | ✓ |
| Scope correction called out | §Preamble "Scope correction applied" + §1 "What this document does NOT do" | ✓ |

### §11.2 Risks I surfaced during self-review (orchestrator decision)

1. **Event-reader layout-switch complexity.** §3.2 specifies dual-layout
   reader supporting both A's v1.0 `data/events/` path and legacy
   `.claude/runtime/events/` path. Risk: if A's Packet 3 merges between
   Packet E1 dispatch and Packet E1 merge, the dual-layout support is
   temporarily dead code. **Recommendation:** keep the dual-layout
   reader as a reliability buffer; v1.N follow-on removes legacy path
   after ≥2 weeks of stable v1.0 emission.

2. **Signal class 5 (token-burn) dependency on Primitive F Packet 11.**
   F's token-usage-outlier emission has not shipped. Risk: §5-E Phase 0
   Readiness item 3 requires "at least 4 event classes" — satisfied by
   classes 1–4 — but shipping only 4 instead of the specified 5 is a
   scope question. **Recommendation:** accept scope class 5 as "deferred
   to F," but orchestrator should confirm before Packet E1 dispatch.
   Alternative: Packet E1 absorbs a minimal `/usage` outlier stub
   (reads `ops.py token-economy` output + thresholds) to ship class 5
   in Phase 0; orchestrator's call.

3. **Conditional-hook migration count.** §6.4 sets floor at 8. Risk: 8
   is an arbitrary floor; actual migration budget depends on per-hook
   complexity. **Recommendation:** author-lane ships as many as pass
   regression-test-driven confidence check; floor of 8 stands; ceiling
   is effort-budget-driven. If author lands < 8, blocker escalation to
   orchestrator rather than silent scope reduction.

4. **ADR 004 authoring load.** §7.2 requires per-hook scoring across 4
   axes × 37 hooks = 148 scored cells. Risk: authoring load within
   Packet E1 is ~1-2 sessions on top of the implementation work.
   **Recommendation:** decompose to Packet E1b per §10.6; ADR 004
   lives in E1b rather than E1. Orchestrator's call.

5. **`triaging-issues` skill refactor risk.** §5.2 moves the skill's
   implementation logic into `triage_cli.py` while preserving the
   operator-invocable interface. Risk: skill-to-CLI extraction may
   surface hidden invariants (e.g., skill currently inlines `gh issue
   create` calls; CLI extraction must preserve `gh` argument escaping).
   **Recommendation:** author lane adds regression-test at
   `tests/unit/test_triaging_issues_compat.py` asserting CLI
   reproduces skill output for a fixed input fixture.

6. **Bus panel rendering cost in dashboard.** §3.3 aggregator scans last
   1000 messages or 24h; §3.4 panel renders on every dashboard build.
   Risk: dashboard latency regresses for heavy bus traffic.
   **Recommendation:** aggregator caches stats in `.claude/runtime/bus_stats.json`
   with 30s TTL; panel reads cached file if fresh. Dashboard build
   remains fast.

### §11.3 Orchestrator option — adversarial review

If the orchestrator wants independent adversarial review of this shaping
before Packet E1 dispatch, dispatch a separate packet to any non-recused
analyst lane (analyst-a/b/c, recusal applied — analyst-d authored) with
the prompt:

> "Review `plans/steward_platform/5_primitive_E/shaping.md` for: (a) §5-E
> Work + Phase 0 Readiness + Phase 1 Validation coverage (every bullet
> lines 503–521 of governing_plan.md has a matching §N deliverable); (b)
> Phase 0 Readiness ↔ Pattern 10 surface coverage integrity (every §5-E
> Phase 0 Readiness criterion has a named surface); (c) Packet E1 spec
> executability (an author lane could open a PR from this without
> ambiguity); (d) A-dependency flagging correctness (§3.2, §8.1 TBD
> markers match Primitive A §3.2 actual deliverables); (e) self-review
> §11.2 risk surfacing adequacy. Recommended but not blocking per task
> framing."

### §11.4 Constraint encountered

The analyst-lane YAML frontmatter structurally disallows the `Agent` tool
(per `.claude/agents/steward-analyst.md` system prompt), so a spawned-
subagent review is not available from this lane regardless. Self-review
per §11.1 + §11.2 substitutes; orchestrator may upgrade to adversarial
review per §11.3.

The packet-description text drift ("observability / metrics / alerts" in
packet summary, corrected to messaging+triage by orchestrator recovery
message `892c16001583441c`) is noted in §Preamble and §1. Orchestrator
should close the packet-summary-text gap if it dispatches follow-on
packets to prevent reshaping cost recurrence.

---

## §12. Phase 2 Decision Inputs

**Portability readiness:** Improved. Active-triage signals route through
Primitive A's v1.0 event schema (§9.7 first-class IDs and correlation
fields), which already carries the portability seams. Conditional-hook
migration reduces per-tool-call overhead and makes the hook set more
amenable to an HTTP-hook substrate adoption (ADR 004 §7). Source: §3, §6,
§7 of this shaping doc.

**Meta-layer need:** No change. Primitive E adds one new module each under
`src/bid_euchre/ops/` (active_triage, bus_latency, event_reader) and one
CLI subcommand; no meta-framework implied.

**Kill signal for primitive(s) named:** No. This shaping sharpens Primitive
E implementation; it does not propose killing any primitive. If Packet E1
lands and the event-to-issue p95 exceeds 10 minutes consistently in Phase
1, §11-E kill criterion triggers per `governing_plan.md` §11 ("Active
triage produces <20% of issues created, measured over ≥20 observed issues
→ revert to operator-discovery model"). Shaping doc itself does not
trigger.

**Re-evaluation needed in Phase 3:** Possibly. If Packet E1 implementation
reveals that the 5-signal-class set is too narrow (e.g., dispatch-latency
anomalies or orchestrator-backlog anomalies emerge as noise-drivers),
re-evaluate active-triage scope at Phase 3. Re-evaluation window: end of
proving run. **RE-EVAL: end-of-Phase-1**

**Surprise finding:** The three bus-debt issues (#2689, #2690, #2691)
were already dispatched to author lanes during session 2026-04-21c
(MEMORY.md). §2.2 treats them as in-flight rather than Packet E1 scope;
but if any stalls beyond 14 days, Packet E1 absorbs. This is the first
concrete case where Phase 0 closeout depends on *prior-session
dispatched packets* completing, rather than on new Phase-0 dispatches
only. If more such prior-session dependencies surface during Phase 0
kickoff (e.g., #2658 portability audit, #2645 export schema, #2415
dashboard cutover), orchestrator may want to add a "prior-session
dependency audit" step to the Phase 0 kickoff checklist.

**Disposition:** open

---

## §13. Verification Plan (Pattern 10 mandate)

Per the analyst prompt-policy clause (§4.3 of
`verification_contract/shaping.md`): every shaping doc deliverable names a
verification surface. This shaping doc itself is the deliverable; its
"verification surface" is whether downstream Packet E1 can be authored
from it without additional shaping. Per Pattern 10 deliverable-class
mapping, this is a **shaping artifact** with operator-review surface form.

| Deliverable (§N.M of this shaping doc) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2 Messaging-bus proving-debt closeout | tracking spec | `gh issue list --state closed --search "2689 2690 2691"` → 3 matches before Packet E1 opens PR | author (E1); orchestrator (dispatch gate) | all 3 issues closed before PR opens |
| §3 Bus p50/p95 delivery-latency telemetry | shaping spec for new module under `src/bid_euchre/ops/**` | Packet E1 author can author `bus_latency.py` + `event_reader.py` + dashboard extension from §3 alone | author (E1) | Packet E1 PR `bus_latency.py` + `event_reader.py` match §3.2–§3.6 design |
| §3.2 Event reader A-dependency | blocking surface | **Verification: TBD — blocking on Primitive A §3.2** — event layout + first-class IDs specified by A's Packet 3; Packet E1 waits | author (E1); orchestrator | A's Packet 3 merged before E1 dispatch |
| §4 Active-triage event-driven wiring | shaping spec for `active_triage.py` + 5 signal classes | Packet E1 author can author `active_triage.py` from §4 alone | author (E1) | Packet E1 PR's 5 signal classes match §4.2 table exactly |
| §5 `triaging-issues` skill integration | shaping spec for skill refactor | Operator-invokable + programmatic path both preserve behavior | author (E1); operator review | skill integration test passes (see §10.3); operator smokes `/triaging-issues` pre- and post-E1 and confirms behavior identical |
| §6 Conditional-hook migration | shaping spec for `.claude/settings.json` + `.claude/hooks/README.md` | Packet E1 author ships ≥8 migrations + README disposition table | author (E1) | ≥8 matcher diffs; `test_hooks_inventory.py` passes |
| §7 HTTP-hooks ADR 004 | ADR specification | Per Pattern 10 ADR-class surface: Pattern 7 rollback (ADR supersession route) + commit citation + per-hook scoring table | author (E1) | ADR committed at `plans/steward_platform/adrs/004-*.md`; per-hook scoring fills all 37 rows |
| §8 Phase 0 Readiness map | reconciliation against `governing_plan.md` §5-E | §5-E lines 511–515 each have a matching §8 row with a named surface | analyst (this packet); orchestrator (review) | grep cross-check §8 ↔ governing plan lines 511–515 |
| §8.1 Additional Pattern-10-driven readiness | extras beyond §5-E minimum | Each listed deliverable has a named surface in col 3 | analyst (this packet) | table in §8.1 complete; every row has non-TBD surface |
| §9 Phase 1 Validation criteria | shaping spec for grep-verifiable assertions | Each Phase 1 criterion is grep-checkable | ops (during proving run) | grep commands in §9 return expected results |
| §10 Packet E1 execution spec | dispatch-readiness | Orchestrator can dispatch Packet E1 from §10 without re-shaping | orchestrator | Packet E1 dispatched with §10 contents copied verbatim into Validation field |
| §11 Self-review | analyst-discipline check | All §11.1 criteria checked | analyst (this packet) | §11.1 table all ✓ |
| §12 Phase 2 Decision Inputs | required §15.2 schema subsection | 5 prompts + disposition all populated | analyst (this packet) | §12 has all 5 prompts + disposition |
| §13 Verification Plan | this section | Lint cross-walks every §N.M to a surface | analyst (this packet); lint (post-Packet-2b `agent_readability_lint.py check verification-contract`) | lint clean against this file |

**Worked example for reading this section (per Pattern 10 lenient-form):**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §4.2 five signal classes | schema-design constraint | grep `^\| [0-9] \|` in §4.2 table → expect exactly 5 rows | author (E1) | grep returns 5 |
| §6.4 ≥8 conditional-hook migrations | incremental deliverable constraint | `git diff origin/main -- .claude/settings.json \| grep -c '"matcher"'` for E1's diff → expect ≥8 matcher additions | author (E1) | grep ≥ 8 |
| §7 ADR 004 existence | ADR-class surface (Pattern 10 table) | `test -f plans/steward_platform/adrs/004-http-hooks-migration-boundary.md && grep -c '|' <file>` → counts scoring-table rows | author (E1); review_driver precheck | file exists; scoring table has ≥37 data rows |

### §13.1 Blocking-surface summary (per shaping.md §4.3 TBD convention)

| § | Blocking surface | Blocking on |
|---|---|---|
| §3.2 Event-reader layout | **Verification: TBD — blocking on Primitive A §3.2** for first-class IDs + JSONL layout | Primitive A Packet 3 merge |
| §4.2 signal class 5 (token-burn) | Deferred — acceptable in shaping; Packet E1 marks "deferred to F" in audit if F's emission absent | Primitive F Packet 11 token-usage-outlier emission |
| §4.2 signal class 4 (orphan-worktree) | Degraded-mode fallback specified; not TBD-blocking | Primitive G worktree-migration native hook emission |
| §2 bus-debt closeout | Dispatched packets from session 2026-04-21c; not TBD-blocking but external | author-b/c/d completing `77ee82e6e209` / `a4162e2431d5` / `3cba4ccdace3` |

Only §3.2 is strictly TBD-blocking per shaping.md §4.3; others are
degraded-mode or external-dependency patterns.

---

## §14. References

- `plans/steward_platform/governing_plan.md` §5-E (lines 492–521) — primary source for Primitive E scope
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 2 (native-substrate-first) / Pattern 7 (rollback) / Pattern 8 (observable-by-default) / Pattern 9 (load-bearing-ownership) / Pattern 10 (verification-surface-per-deliverable) — pattern enforcement
- `plans/steward_platform/governing_plan.md` §11-E — kill criterion (active triage produces <20% of issues → revert)
- `plans/steward_platform/governing_plan.md` §12 Risks — E's implicit risks (cascade from A slip)
- `plans/steward_platform/governing_plan.md` §14 Open Item 14 — ADR 004 (HTTP-hooks migration boundary)
- `plans/steward_platform/governing_plan.md` §15.2 — Phase 2 Decision Inputs subsection schema
- `plans/steward_platform/1_primitive_A/shaping.md` — Primitive A event schema + dispatcher (E consumes A)
- `plans/steward_platform/verification_contract/shaping.md` §2 (Pattern 10 deliverable-class table), §4.3 (analyst TBD convention), §5 (canary as meta-verification)
- `plans/steward_platform/6_primitive_F/shaping.md` §7 — `/usage` native-substrate adoption (E's signal class 5 source)
- `src/bid_euchre/ops/message_bus.py` — current bus substrate (no E changes to core; latency telemetry added alongside)
- `src/bid_euchre/ops/events.py` — current event log (migrates to A's v1.0 dispatcher via A's Packet 3; E reads after migration)
- `src/bid_euchre/ops/monitor.py` — severity taxonomy (SEVERITY_INFO/WARN/HIGH); E's active-triage reuses; does not expand
- `src/bid_euchre/ops/attention.py` — nudge routing by (message_type, priority); unchanged by E
- `src/bid_euchre/ops/alert_push.py` — push-evaluation; unchanged by E (operator Telegram path stays)
- `.claude/skills/triaging-issues/SKILL.md` — current operator-invocable issue-creation skill; E adds programmatic entry
- `.claude/hooks/README.md` — current hook documentation; E extends with ordering + scope + disposition-table sections
- `.claude/rules/deferred/55_issue_closure.md` — Tier-1 vs Tier-2 issue closure policy (E's `active_triage` defaults to Refs until verified)
- `.claude/rules/deferred/60_review_gate.md` — label families (`fix:*`) and V1–V6 precheck taxonomy (ADR 004 may extend V-checks for HTTP-hook surface)
- `.claude/rules/prompt_policy/analyst.md` — analyst-lane shaping-doc obligation (this doc complies)
- Task packet: `af575a2143ad` (Primitive E pre-shape)
- Orchestrator scope-correction message: `892c16001583441c` (2026-04-24T05:41:56Z)

---

## Outcome

_Filled after Packet E1 lands._

- Packet E1 dispatched: (pending orchestrator)
- PRs merged: (pending)
- Deviations from shaping: (pending)
- Surprise findings: (pending)

## Handoff

_Filled at session end if work is incomplete._

- Current state: shaping doc authored; scope correction applied per orchestrator recovery msg `892c16001583441c`; PR pending.
- Next action: orchestrator reviews; dispatches Packet E1 (or decomposes E1a + E1b) when A's Packet 3 has merged.
- Blockers: Primitive A Packet 3 merge is the hard dependency (§3.2 TBD-blocking).
- Files with uncommitted changes: `plans/steward_platform/5_primitive_E/shaping.md` (this file, to be committed by analyst-d).
