# Shaping: Primitive F Phase 0 Execution Spec — F-debt vs F-forward + telemetry extraction + `/usage` / `/cost` native adoption

**Date:** 2026-04-24
**Lane:** analyst-c
**Packet:** `24888cf4474d` (Primitive F Phase 0 pre-shape — execution belongs to a later packet, named Packet 11 herein)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-F
**Sibling artifacts:**
- `plans/steward_platform/1_primitive_A/shaping.md` (Primitive A shaping; F is strictly downstream of A's Packet 3)
- `plans/steward_platform/0_hardening/sub/rework_spec.md` §3 row `token_economy.py` (the F-debt enumeration; this shape references, does not duplicate)
- `plans/steward_platform/0_hardening/baseline.md` (landed PR #2766; F-forward's baseline-delta consumer reads this)
- `plans/steward_platform/adrs/006-auto-mode.md` (§"Model tier interaction" — F dispatch feedback to B.1 carries a dual-envelope safety implication)
- `plans/steward_platform/verification_contract/shaping.md` §2–§4 (Pattern 10 surface-class defaults + V1–V6 precheck taxonomy)
- `plans/steward_platform/verification_contract/map.md` (Primitive F coverage rows, added by Packet 11)
- `plans/steward_platform/claude_code_changelog_implications.md` §2 Tier S (`/usage`, `/cost`, read-tool token reductions, per-tool MCP result-size override — all feed F-forward)
**Status:** DESIGN-SPEC — no code, no rollups, no events.py emissions are authored in this artifact. Produces a Packet 11 execution-ready brief.
**Purpose:** Pre-shape Primitive F's Phase 0 execution so the orchestrator can dispatch Packet 11 to an author lane immediately after Primitive A's Packet 3 merges — zero additional shaping work. Mirrors the Packet 2a → Packet 2b pattern (verification-contract) and the Primitive A Packet 1 → Packet 3 pattern (event schema).

---

## §1. Scope of this document

This is a **shaping document**. Its single output is an execution-ready specification for the Primitive F Phase 0 deliverables enumerated in `plans/steward_platform/governing_plan.md` §5-F (Work + Phase 0 Readiness + Phase 1 Validation), split into **F-forward** (execution scope) and **F-debt** (deferred scope owned by Primitive G).

**What this document specifies:**

1. The F-debt vs F-forward boundary — an explicit in-scope / out-of-scope list for Primitive F's execution packet (§2).
2. The Deliverable → Pattern 10 verification-surface table for all five F-forward deliverables (§3).
3. Per-deliverable specs:
   - §4 Telemetry extraction mechanism (lane × model × effort rollups routed through `ops/events.py` dispatcher)
   - §5 Baseline-delta measurement consumer (reads `plans/steward_platform/0_hardening/baseline.md`; defines delta, refresh cadence, promotion gate, dashboard, alert rules)
   - §6 Integration with B.1 adaptive dispatch (data contract, timing, fallback, dual-envelope note per ADR 006)
   - §7 `/usage` + `/cost` native-substrate adoption (tier-1 native → tier-4 bespoke migration boundary; ADR 003 content)
4. Execution packet spec (Packet 11: files created, files modified, order of operations, validation commands, coordination, success criterion) — §8.
5. Self-review against completeness criteria (§9).
6. Phase 2 Decision Inputs subsection per §15.2 schema (§10).
7. Verification Plan section per Pattern 10 mandate (§11).

**What this document does NOT do:**

- Execute any of the 22 `src/bid_euchre/ops/token_economy.py` hard-blocks enumerated in `plans/steward_platform/0_hardening/sub/rework_spec.md` §3. That's F-debt, owned by Primitive G.
- Retire `token_economy.py` entirely. Packet 11 lands F-forward glue on top of the existing module; G decides replacement.
- Define `ops/events.py` dispatcher architecture. That's Primitive A Packet 3; F consumes the committed schema.
- Author the `/usage` + `/cost` native commands. Those are Claude Code substrate; F specifies how steward **parses** their output into events.py emissions.
- Decide the Slice F promote/retain/kill outcome. That decision is recorded by the operator + archivist at Phase 0 close after the 1–2 week observation window. Packet 11 only lands the measurement + feedback + adoption surfaces that make the decision possible.
- Re-design the Slice B rollup that already shipped in PR #2725 (lane × model × effort). F wires emission; it does not re-derive attribution.

### §1.1 Motivation (one paragraph)

Primitive F is the **second** primitive whose Phase 0 execution depends strictly on Primitive A landing first (the first is Primitive E active triage). F-forward consumes A's v1.0 event schema + dispatcher to emit token-economy rollups as first-class events; without A, F's measurement path remains the current JSONL-to-dashboard bespoke pipeline, which does not integrate with B.1's routing decisions. F also carries the token-economy dual-envelope decision surfaced in ADR 006: any B.1 dispatch that lowers model tier simultaneously lowers the permission-model safety envelope, so F's telemetry-to-dispatch feedback loop must flag that tradeoff at emission time, not discover it post-hoc. Pre-shaping F means the moment Packet 3 merges (Primitive A event-schema v1.0 dispatcher live), an author lane can pick up Packet 11 from the queue and execute without further analyst shaping.

### §1.2 Relationship to §5-F and operator direction (draft 8)

§5-F of the governing plan is the binding reference. This shaping doc operationalizes three operator-named framings from §5-F Work bullets and from the draft 8 §5-F discussion preserved in the draft-8-lineage review artifacts:

| §5-F / draft 8 framing | Where it lands in this doc |
|---|---|
| F-debt / F-forward split (draft 8 §5-F) | §2 |
| Slice F observation-window evaluation (PR #2716) | §4.3 + §5 + §10 |
| Re-capture baseline after Read-tool token reductions | §5.2 |
| Native `/usage` as comparison feed + ADR 003 | §7 |
| Per-tool MCP result-size override | §7.3 |
| Lane × model × effort rollups (PR #2725 shipped) | §4.1 |
| Tokens-per-successful-merge metric via Primitive A | §4.2 |

The native-substrate three-tier preference (§10.9 Pattern 2: native → official plugin → third-party plugin → bespoke) is honored: `/usage` + `/cost` are tier-1 and drive §7's adoption spec; `token_economy.py` is tier-4 and stays on as glue for rollup shapes `/usage` does not cover.

---

## §2. F-debt vs F-forward boundary

### §2.1 F-forward (this primitive's execution scope — Packet 11)

**F-forward** is the measurement + feedback loop that closes the token-economy observability gap. It is Phase 0 execution scope for Primitive F.

F-forward deliverables (five; all concurrently authored in Packet 11):

| # | Deliverable | Home | Owner |
|---|---|---|---|
| 1 | Telemetry extraction mechanism — lane × model × effort rollups emitted through `ops/events.py` dispatcher under event types `token_rollup_observed` + `token_rollup_drift` (per §4) | `src/bid_euchre/ops/token_economy_emitter.py` (new, ~100 LOC) + `ops/token_economy.py` glue (modify, small) | Primitive F |
| 2 | Baseline-delta measurement consumer — reads `plans/steward_platform/0_hardening/baseline.md`, computes deltas, surfaces in dashboard, fires alert on regression (per §5) | `src/bid_euchre/ops/token_baseline_delta.py` (new, ~80 LOC) + `ops/dashboard.py` TUI panel (modify) | Primitive F |
| 3 | Integration with B.1 adaptive dispatch — data contract, timing, fallback, dual-envelope note emission (per §6) | Consumed by B.1's own shape (analyst-a Packet 3-B); F exposes the contract in `token_economy_emitter.py` public surface | Primitive F (emitter); Primitive B (consumer, separate packet) |
| 4 | `/usage` + `/cost` native-substrate adoption — comparison-feed capture + diff-surface + ADR 003 filing (per §7) | `scripts/internal/capture_native_usage.py` (new, ~60 LOC) + `ops/token_economy_native.py` (new, ~80 LOC) + `plans/steward_platform/adrs/003-token-economy-native-vs-bespoke.md` (new) | Primitive F |
| 5 | Per-tool MCP result-size override for high-frequency operational commands (`ops.py dashboard`, `task list`, `inbox`) — per §7.3 | `.claude/settings.json` (modify: add `mcp.resultSizeOverride` entries) + `ops/dashboard.py` verbosity tier (modify) | Primitive F |

**F-forward Phase 0 Readiness** (maps §5-F Readiness bullets one-to-one; full map in §11 Verification Plan):

- Slice F observation window underway (`token_rollup_observed` emissions visible in `data/events/` from at least two lanes).
- Rollup dashboard live with `token_rollup_drift` panel rendering.
- Baseline tokens-per-merge captured in `plans/steward_platform/0_hardening/baseline.md` §3 (Token economy snapshot) and re-captured after Read-tool reductions land.

### §2.2 F-debt (deferred to Primitive G execution scope)

**F-debt** is the 22 hard-block literals in `src/bid_euchre/ops/token_economy.py` (per `plans/steward_platform/0_hardening/sub/rework_spec.md` §3, row `token_economy.py`). F-debt is **NOT** Primitive F's execution scope; it is carried forward into Primitive G as "Token economy hard-blocks: zero hard-blocks in `ops/token_economy.py` (22 occurrences). Native `/usage` + `/cost` do not cover these; bespoke fix remains required" (per `governing_plan.md` §5-G Work bullet 4).

F-debt items explicitly out of scope for Packet 11:

| Item | Why F-debt (not F-forward) | Owning packet |
|---|---|---|
| Removal of the 22 Bid-Euchre literals in `token_economy.py` | Portability refactor; orthogonal to measurement | Primitive G native-migration packet |
| Retirement of `token_economy.py` module | Tier-4 bespoke; only replaced if `/usage` + `/cost` + future native features eventually cover the full rollup surface. ADR 003 (§7.4) files at Phase 0 close to document which surfaces migrate and which remain | Phase 1+ native-migration packet |
| 19-lane → 8-archetype consolidation | Lane-topology reshape; unrelated to token-economy measurement | Primitive G G13 first-deliverable sub-sub-plan |
| `ops/token_economy.py` SCHEMA_VERSION bump (currently v3) | Existing schema is stable and compatible with F-forward glue; bump only if F-forward needs new normalized fields not in v3 | Deferred; on-demand if surfaces |

**Boundary rule.** If Packet 11 implementation surfaces a need to modify any of the 22 hard-blocks *in order to* emit a rollup, the author lane escalates via blocker message to the orchestrator and F-forward is re-scoped to route around the hard-block (e.g., by reading `.claude/runtime/token_economy/*.json` directly from `token_economy_emitter.py` without touching the hard-block code path). Silently modifying a hard-block as part of Packet 11 widens scope across the F-debt / F-forward boundary and is rejected at review.

### §2.3 F-forward does NOT claim

- Coverage for the full `token_economy.py` rollup surface. `/usage` + `/cost` capture a subset; bespoke rollups capture a different subset (and overlap with `/usage` in the overlap zone). ADR 003 documents the boundary at Phase 0 close.
- A decision on whether Slice F adaptive dispatch ships as active or advisory. That decision is recorded by the operator after the observation window closes. Packet 11 only lands the measurement that makes the decision *evidenced*.
- Authority over native-substrate evolution. If Anthropic ships a future feature that subsumes `token_economy_emitter.py`, that's a Phase 1 or Phase 2 ADR (following §10.9 Pattern 2 native-substrate-first), not a retroactive re-scope of Packet 11.

---

## §3. Deliverable → Pattern 10 verification-surface table

Per `plans/steward_platform/verification_contract/shaping.md` §2 deliverable-class → surface-class defaults. Strict-existence (every deliverable has a named surface); lenient-form (surface matches deliverable class).

| Deliverable (§N.M of this doc) | Class | Default surface per Pattern 10 | Named surface for Packet 11 |
|---|---|---|---|
| §4 Telemetry extractor `ops/token_economy_emitter.py` | New Python module under `src/bid_euchre/ops/**` | unit test path | `tests/unit/test_token_economy_emitter.py` — asserts `token_rollup_observed` emission shape matches A's v1.0 schema + §9.7 first-class IDs populated |
| §4 Existing emitter routing — `ops/token_economy.py` modification | Module modification | integration test path | `tests/integration/test_token_economy_emission_e2e.py` — seed a session, invoke `import_project_jsonl`, assert one `token_rollup_observed` event lands in `data/events/` |
| §5 Baseline-delta consumer `ops/token_baseline_delta.py` | New Python module | unit test path | `tests/unit/test_token_baseline_delta.py` — asserts delta computation against seeded baseline fixture; asserts alert fires when delta exceeds threshold |
| §5 Dashboard panel — `ops/dashboard.py` modification | Module modification | named runnable command with documented expected output | `uv run python scripts/internal/ops.py dashboard --json \| jq '.token_baseline_delta'` — expected: dict with `delta_pct`, `baseline_window`, `status` ∈ {ok, warn, regression, stale} |
| §6 B.1 integration (public contract) | Data-contract deliverable | operator-review prompt with specific pass criterion | analyst-a's Primitive B Packet 3-B shape document cites `plans/steward_platform/6_primitive_F/shaping.md` §6 explicitly; B.1 shape review (by recused analyst lane) confirms the contract matches F's emitter surface; pass criterion: zero unresolved contract ambiguities |
| §6 Dual-envelope note (ADR 006 cross-reference) | Emit-behavior constraint | event-schema query with expected shape | grep `data/events/events-*.jsonl` for records with `event_type=dispatch_recommendation` where `recommended_model_tier != current_model_tier` — expect a `safety_envelope_delta` field populated (not null) |
| §7 `/usage` + `/cost` capture script `scripts/internal/capture_native_usage.py` | New Python script | unit test path | `tests/unit/test_capture_native_usage.py` — asserts parser handles at least 3 real `/usage` output samples fixtured under `tests/fixtures/native_usage/*.txt` |
| §7 Diff surface `ops/token_economy_native.py` | New Python module | unit test path | `tests/unit/test_token_economy_native.py` — asserts diff between bespoke rollup and native `/usage` flags expected drift categories |
| §7.3 Per-tool MCP result-size override | `.claude/settings.json` config change | rollback test (revert-commit smoke) | `scripts/internal/review_driver.py` V2/V3 precheck verifies the override revert is safe; manual smoke: set override, invoke `ops.py dashboard`, confirm output size reduced by ≥30% (per §7.3 target) |
| §7.4 ADR 003 filing | New ADR under `plans/steward_platform/adrs/` | per Pattern 10 ADR note: Pattern 7 rollback path + commit citation | `plans/steward_platform/adrs/003-token-economy-native-vs-bespoke.md` §Source evidence cites Phase 0 observation-window data; supersession route documented |
| §8 Packet 11 execution spec (dispatch readiness) | Shaping-doc deliverable | operator-review prompt with specific pass criterion | orchestrator can dispatch Packet 11 from §8 without re-shaping; pass criterion: Validation field populated verbatim from §8.3 |

**Surface-class gaps.** None at shaping time. Every §N.M deliverable has a named surface. If Packet 11 implementation surfaces a gap (e.g., `/usage` output format is unstable across Claude Code versions, breaking the fixture contract in §7), the author lane escalates rather than silently defaulting to operator review.

---

## §4. Telemetry extraction mechanism

### §4.1 Goal

Route the lane × model × effort rollups (shipped in PR #2725 as `token_economy.lane_summary()` + `throughput_summary()` outputs) through Primitive A's `ops/events.py` dispatcher as first-class `token_rollup_observed` events. This accomplishes three things:

1. **Replay compatibility.** Primitive H.1's replay harness can reconstruct token-economy state from the event stream alone — no out-of-band JSON store lookup required.
2. **B.1 consumption seam.** B.1 (adaptive dispatch) reads the event stream, not the bespoke store; the dispatcher pattern removes B.1's dependency on `token_economy.py` internals.
3. **Drift detection.** The dispatcher's §9.7 first-class IDs + correlation fields make rollup drift queryable via grep — SC #10 grep-verifiable citation applies to F's emissions.

### §4.2 New event types added to Primitive A's v1.N registry

Per `§5-A` event-schema-versioning policy: additive changes are v1.N compatible with the replay harness. F registers two new event types:

| Event type | Fields | Trigger |
|---|---|---|
| `token_rollup_observed` | `lane_id` (already §9.7 top-level); `rollup_window_start` (ISO8601); `rollup_window_end`; `model_bucket` (Opus/Sonnet/Haiku/unknown); `effort_bucket` (high/medium/low/unknown); `session_count` (int); `total_input_tokens`, `total_output_tokens`, `total_tokens` (int); `tokens_per_commit` (float); `tokens_per_merged_pr` (float, null if 0 merges in window); `schema_version` (already §9.7); `source` ("token_economy" \| "native_usage" — for §7 diff queries) | Nightly cron invokes `token_economy_emitter.emit_nightly_rollups()`; on-demand via `ops.py usage --emit` |
| `token_rollup_drift` | `lane_id`; `rollup_window_start`; `rollup_window_end`; `delta_pct` (float, signed); `baseline_source` ("baseline.md" \| "prior_window"); `drift_category` ("baseline_regression" \| "baseline_improvement" \| "window_anomaly"); `threshold_pct` (float, from config) | Fires when `|delta_pct| >= threshold_pct` (default ±20%); alert routing optional via `ops/alert_push.py` |

**Registration location:** Packet 3 (Primitive A) added both event types to `EVENT_FIELD_REGISTRY` under `event_schema.py` when Packet 11 is dispatched — if Packet 3 shipped without them, Packet 11 must add them in its first commit (additive, v1.0 → v1.1 compatible).

### §4.3 Slice F evaluation hook

The `token_rollup_observed` stream is the primary evidence source for the Slice F decision (§5-F Work bullet 1 + §11-F kill criterion). The operator + archivist at Phase 0 close read `data/events/events-*.jsonl` filtered to `event_type=token_rollup_observed` across the 1–2 week observation window; decision input is the *tokens-per-merged-PR* trend across the window, cross-validated against the baseline-delta surface (§5). Decision: promote (active dispatch) / retain (advisory) / kill (revert per §11-F). Recorded in MEMORY.md + ADR 003 §Consequences.

### §4.4 Public API (for B.1 consumption)

`token_economy_emitter.py` exposes:

```python
def emit_nightly_rollups(
    *,
    output_dir: Path | None = None,
    events_dir: Path | None = None,
    schema_registry: Any | None = None,  # Primitive A's EVENT_FIELD_REGISTRY
) -> list[dict[str, Any]]:
    """Walk the token_economy store, emit one `token_rollup_observed` per (lane, model, effort) bucket over the last 24h window. Returns the emitted event records."""

def drift_check(
    *,
    baseline_source: str = "baseline.md",
    threshold_pct: float = 20.0,
    events_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Compare most-recent `token_rollup_observed` events against baseline or prior-window. Emit `token_rollup_drift` events for breaches. Returns emitted drift records."""

def latest_rollup_for_lane(lane_id: str) -> dict[str, Any] | None:
    """Public read surface for B.1: latest observed rollup for a lane. Reads from the event stream (not the bespoke store). Returns None if no rollup observed in the last 7d."""
```

**Guarantees:**

- `latest_rollup_for_lane` is the **only** stable contract B.1 consumes. The event-stream grep is the reference implementation; B.1 does not read `token_economy.py` internals.
- All three functions **never raise** — on error they log to stderr and return an empty list / None (matches Primitive A's never-raise dispatcher contract).
- Staleness guarantee: `latest_rollup_for_lane` returns None if the latest observation is older than 7 days. B.1 treats None as "no signal, use baseline policy" — see §6.3 fallback.

### §4.5 Storage location

- **Primary storage (authoritative):** event stream under `data/events/events-<date>-NNN.jsonl` (Primitive A's rotation). `token_economy_emitter.py` writes via `events.emit(...)`.
- **Secondary storage (existing, retained):** `.claude/runtime/token_economy/*.json` — the bespoke store. Stays on as input to the emitter. Packet 11 does not modify or migrate the secondary store; the emitter reads from it and writes to the primary.
- **Consumer index (new, optional):** `data/events/.token_rollup_index.json` — a small index the emitter writes for fast B.1 lookups without a full scan. Stale-tolerant; rebuildable from the full stream. Explicitly optional — B.1 may grep the stream directly.

---

## §5. Baseline-delta measurement consumer

### §5.1 Goal

Read `plans/steward_platform/0_hardening/baseline.md` (landed in PR #2766, per the committed artifact) as the authoritative baseline; compute per-lane and fleet-wide deltas against the latest `token_rollup_observed` window; surface in the dashboard; fire alerts on regression. This closes the governing plan's Phase 0 Readiness bullet 3 ("Baseline tokens-per-merge captured in §4.3") and the Phase 1 Validation bullet 2 ("Tokens-per-merge trending flat or down relative to baseline across the proving run").

### §5.2 Delta definition

For each (lane × model × effort) bucket present in both baseline.md and the latest rollup window:

```
delta_pct = 100.0 * (current_tokens_per_commit - baseline_tokens_per_commit) / baseline_tokens_per_commit
```

Where `tokens_per_commit` is drawn from baseline.md §8 ("By lane (top 10 by total tokens)") and from the corresponding `token_rollup_observed` event. Tokens-per-merged-PR delta follows the same shape, drawn from baseline.md §4 (PR velocity) + §3 (Token economy snapshot) joined.

**Sign convention:** positive delta_pct means *more* tokens (regression); negative means *fewer* (improvement). This matches operator intuition and the SC #7 "flat or declining relative to baseline" framing.

### §5.3 Refresh cadence

- **Baseline refresh:** on-demand, via `scripts/internal/capture_steward_baseline.py` (Primitive G-owned; already committed per §5-G Readiness bullet 11). F-forward does **not** re-author baseline capture; it consumes the artifact.
- **Trigger for baseline re-capture:** per §5-F Work bullet 2, the operator re-runs the capture script after (a) Read-tool token reductions + large tool result persistence land, (b) any native-substrate adoption that materially changes the baseline cost profile (e.g., `/usage` becoming a meaningful fraction of operational queries), or (c) a Phase-boundary crossing. Re-capture overwrites `baseline.md` (git tracks history).
- **Delta computation cadence:** nightly, via `token_baseline_delta.refresh()` invoked from the same cron that triggers `emit_nightly_rollups()` (§4.4). Dashboard reads the most recent cached delta; stale-threshold is 48h (dashboard renders `status: stale` if exceeded).
- **Staleness handling.** If baseline.md is missing the target section (e.g., §8 never populated because capture ran on an empty store), `token_baseline_delta` records the section name + "insufficient data" in the cached result. No fatal error; dashboard renders `status: insufficient-baseline`.

### §5.4 Promotion gate: "baseline updated"

A baseline.md commit qualifies as a "baseline-updated" event **only if**:

1. The commit diff includes a materially-changed §3 (Token economy snapshot) OR §8 (Lane × model × effort rollup) section — not just §1 timestamp.
2. The commit message cites the trigger (a/b/c above) explicitly. Pattern: `docs(baseline): re-capture after <trigger>`.
3. `baseline_updated` event is emitted to the v1.0 stream (new event type, registered in Packet 3 A.2 catalog or Packet 11 additive v1.1) with fields: `commit_sha`, `trigger_category`, `captured_at`. Committed via a `.claude/hooks/post-baseline-commit.sh` conditional hook (trigger: commits touching `plans/steward_platform/0_hardening/baseline.md`).

When a `baseline_updated` event fires, the delta consumer invalidates its cached baseline and re-reads. Dashboards pick up the refreshed delta on the next nightly cycle (48h worst-case observation lag; operator can force via `ops.py usage --refresh-delta`).

### §5.5 Dashboard surface

`ops.py dashboard` adds a `Token baseline delta` row:

```
Token baseline delta  fleet: +3.2%  regression_lanes: 0/19  status: ok  baseline_age: 2d
```

Fields:

- `fleet_delta_pct` (float, signed): fleet-wide tokens-per-merged-PR delta vs. baseline.
- `regression_lanes` (int/int): count of lanes whose delta exceeds threshold_pct (default 20%).
- `status` (enum: ok | warn | regression | stale | insufficient-baseline): most recent terminal state per §5.3 + §5.6.
- `baseline_age` (string, human-readable): time since baseline.md was last captured.

**Sub-metric sparklines (mitigation against the "silent green check" risk pattern, §12):** dashboard sub-row renders 8-window sparklines for `fleet_delta_pct`, `tokens_per_merged_pr`, `Opus_tier_share`, `unknown_bucket_fraction`. Operators see drift before threshold breach.

### §5.6 Alert rules

| Condition | Severity | Action |
|---|---|---|
| `fleet_delta_pct > 20` for ≥2 consecutive nightly cycles | high | file GitHub issue `fix:process, token-regression`; push to operator Telegram per `alert_push.py` routing |
| `regression_lanes >= 5` in a single cycle | high | same as above; explicit lane list in issue body |
| `unknown_bucket_fraction > 0.8` for ≥7 consecutive cycles | medium | file issue `fix:convention, token-attribution-drift` — attribution logic degrading (baseline.md §8 currently shows 1.00, so threshold is chosen tight *around* the post-Slice-B-attribution-improvement expected state) |
| `baseline_age > 60d` | medium | file issue `fix:process, baseline-stale`; operator prompt to re-run capture |
| `status = insufficient-baseline` for ≥3 consecutive cycles | low | file issue `fix:test, baseline-coverage`; indicates baseline capture needs extension |

Alert push routing uses existing `ops/alert_push.py` + `ops/telegram_push.py` surfaces; no new alert infrastructure.

### §5.7 Known baseline attribution caveat

Baseline.md §8 (captured 2026-04-23) currently shows **100% "unknown" model** and **100% "unknown" effort** (`Unknown-model fraction: 1.00`). This is expected for the pre-Slice-B-improvement state — the attribution logic runs on legacy session-meta rows that predate the model/effort dimensions introduced in PR #2169. F-forward does not backfill historical attribution. The `unknown_bucket_fraction` sparkline tracks this as it improves over Phase 0 (as new sessions accrue with proper attribution). The §5.6 `unknown_bucket_fraction > 0.8` alert is wired but expected to stay red for the first few cycles of Phase 0 — this is documented in ADR 003 §Open questions as "baseline attribution backfill decision (defer vs. rewrite)."

---

## §6. Integration with B.1 adaptive dispatch

### §6.1 Coordination shape

Primitive B sub-deliverable B.1 (adaptive dispatch) is shaped by analyst-a in a separate packet. F and B.1 are jointly-owned at the hand-off surface but otherwise disjoint:

- **F owns:** `token_economy_emitter.py` emission; `token_baseline_delta.py` computation; `latest_rollup_for_lane` public API; `dispatch_recommendation` event emission contract (shape + field catalog).
- **B.1 owns:** consumption of `latest_rollup_for_lane`; dispatch policy that maps rollups to lane/model/effort routing decisions; emission of `dispatch_recommendation` with the final recommendation.

### §6.2 Data contract (F → B.1)

`latest_rollup_for_lane(lane_id: str) -> dict | None` returns, when not None:

```python
{
    "lane_id": "author-a",
    "rollup_window_start": "2026-04-17T00:00:00Z",
    "rollup_window_end": "2026-04-24T00:00:00Z",
    "model_bucket": "opus",                    # dominant bucket in window
    "effort_bucket": "high",                   # dominant bucket in window
    "session_count": 14,
    "total_tokens": 2_391_778,
    "tokens_per_commit": 10_971,
    "tokens_per_merged_pr": 48_322,            # null if 0 merges in window
    "delta_vs_baseline_pct": 3.2,              # float, signed; null if baseline missing
    "drift_flags": ["unknown_bucket_high"],    # list of active drift signals, may be empty
    "source": "token_economy",                 # or "native_usage" when §7 diff path is consulted
    "schema_version": "1.0",                   # or whatever v1.N the emitter targets
}
```

B.1 treats this dict as **immutable input**; it does not mutate or republish. B.1 may cache by `(lane_id, rollup_window_end)`; cache eviction is a B.1 concern, not F's.

### §6.3 Timing (when does B.1 call)

- **At dispatch time.** When B.1 evaluates a task-packet routing decision, it calls `latest_rollup_for_lane(candidate_lane)` for each candidate.
- **Fallback when F is down or stale.** If the return is None (no rollup in last 7d) or `delta_vs_baseline_pct is None` (baseline missing), B.1 falls back to *baseline policy* — the static per-lane dispatch weights documented in its own shape. This fallback is first-class; F being offline does not stop dispatch.
- **F does not call B.1.** Direction is strictly B.1 → F (read-only pull). F does not know B.1 exists at emission time.

### §6.4 Dual-envelope note (ADR 006 cross-reference)

Per `plans/steward_platform/adrs/006-auto-mode.md` §"Model tier interaction": any B.1 dispatch that lowers a lane's model tier below Opus simultaneously lowers the permission-model safety envelope from `auto` (classifier-gated) to `bypassPermissions`. F has two load-bearing responsibilities here:

1. **Emission-time flagging.** When B.1 emits `dispatch_recommendation` (existing event type in `ops/events.py` VALID_EVENT_TYPES), if `recommended_model_tier != current_model_tier` and the recommended tier is below Opus, the event record carries a `safety_envelope_delta: "downgrade-to-bypass"` field. F's emitter does not write this field directly (B.1 does), but F's `token_economy_emitter.latest_rollup_for_lane` return dict carries a `current_model_tier` field that B.1 must compare against; F is responsible for accurate `current_model_tier` inference from the rollup.
2. **Shaping-doc discipline.** Any future shaping document (orchestrator, analyst lane) that proposes dispatching a task to a non-Opus lane for token-economy reasons must carry the dual-envelope downgrade note in the Validation field. This is prompt-policy, not code; Packet 1 (B.3 prompt-policy registry) is the canonical home. F's shaping doc (this doc) names the requirement; Packet 1 enforces it at future shape-time.

**Out of scope for Packet 11:** B.1's dispatch policy itself. Packet 11 lands the `current_model_tier` field on F's return dict + the downgrade-safety hook in the `dispatch_recommendation` event record shape; B.1's own packet wires the policy.

### §6.5 Fallback if F is down

If `token_economy_emitter.emit_nightly_rollups()` errors or the event stream is empty for ≥7 days:

- `latest_rollup_for_lane` returns None (§4.4 guarantee).
- B.1 falls back to baseline policy (§6.3).
- F emits `token_rollup_emission_failure` event (proposed; optional — if not registered, a stderr log suffices); operator sees it on dashboard via the `Latencies` panel Primitive A adds.
- No rollback required on F's side; the bespoke `token_economy.py` store still exists and can be inspected directly via `ops.py usage` for operator diagnosis.

### §6.6 Enumerated hand-off points (explicit list per task packet requirement)

| # | Hand-off point | F's side | B.1's side | Contract home |
|---|---|---|---|---|
| 1 | Rollup read | `latest_rollup_for_lane(lane_id)` returns dict or None | B.1 calls at every dispatch decision | §6.2 |
| 2 | Drift signal | F emits `token_rollup_drift` event; B.1 subscribes optionally | B.1 may downweight lanes with active drift_flags | §4.2 + §4.4 |
| 3 | Baseline-update signal | F emits `baseline_updated` event; B.1 invalidates any cached delta | B.1 clears rollup cache on this event | §5.4 |
| 4 | Dual-envelope flagging | F provides `current_model_tier` in rollup dict | B.1 compares vs. recommended_tier; writes `safety_envelope_delta` into `dispatch_recommendation` event | §6.4 |
| 5 | Fallback contract | F's None return is first-class | B.1 uses baseline policy | §6.3 + §6.5 |

**Escalation path.** If B.1 shape (Packet 3-B) diverges from this contract, F's author lane (Packet 11) escalates via blocker message rather than accommodating in-line; the orchestrator reconciles by re-shaping one or both packets. Silently stretching the contract across packet boundaries violates §10.9 Pattern 9 load-bearing-ownership.

---

## §7. `/usage` + `/cost` native-substrate adoption

### §7.1 Goal

Adopt native `/usage` and `/cost` as a **comparison feed** alongside steward's bespoke `token_economy.py` rollups. Claim three outcomes:

1. **Drift detection on bespoke measurement.** Discrepancies between `/usage` and bespoke rollups flag (a) drift in steward's attribution path, or (b) `/usage`-specific categories steward doesn't yet surface.
2. **Adoption-surface mapping.** ADR 003 (filed at Phase 0 close) documents which categories steward adopts into its own rollups and which remain native-only.
3. **Migration path to tier-4-retirement.** If future Anthropic native features grow to subsume the bespoke rollup surface, ADR 003's `Supersedes` section is the path toward retiring `token_economy.py` entirely (eventually — not a Phase 0 goal).

Per the three-tier preference (§10.9 Pattern 2), native > plugin > third-party > bespoke. `/usage` + `/cost` are tier-1; `token_economy.py` is tier-4 fallback for rollup shapes tier-1 does not cover.

### §7.2 Capture script — `scripts/internal/capture_native_usage.py`

**Scope (~60 LOC):**

- Invokes `/usage` and `/cost` from a headless Claude Code session (parallel to how `review_lane_runner.py::invoke_review` subprocesses `claude`; reuses the `--permission-mode auto` discipline per ADR 006).
- Parses the textual output into a structured dict matching the `token_rollup_observed` event shape (fields named where overlap exists; native-only fields preserved under a `native_extras` subdict).
- Emits one `token_rollup_observed` event per capture with `source=native_usage` (vs. the bespoke emitter's `source=token_economy`).
- Runs nightly via cron (ops lane); on-demand via `/capture-native-usage` skill (optional; defer to Phase 1 unless operator requests).

**Parser robustness.** `/usage` output format is operator-inspected from a recent version and fixtured under `tests/fixtures/native_usage/*.txt`; parser handles ≥3 fixture samples as unit-test gate. If Claude Code upgrades change the format, the parser fails loudly (stderr + `token_rollup_emission_failure` event) rather than silently mis-parsing; fixtures are regenerated + parser tightened as a follow-up PR.

### §7.3 Per-tool MCP result-size override

**Scope (very small — config + docs):**

- Add `mcp.resultSizeOverride` entries to `.claude/settings.json` for:
  - `ops.py dashboard` — cap at 8KB.
  - `ops.py task list` — cap at 4KB (operators paginate for more).
  - `ops.py inbox` — cap at 4KB.
- Target: ≥30% token reduction on dashboard + inbox subcommand invocations over the observation window (measured via bespoke rollup, confirmed via `/usage` diff).
- Rollback: revert the settings.json commit. Pattern 7 forward-then-reverse gate is the `review_driver.py` V2/V3 precheck.

**Caveat.** Result-size override is a Claude Code substrate feature; if it's not yet exposed in the version the fleet runs at Packet 11 dispatch, the author lane either (a) escalates and the override portion defers to a later packet, or (b) implements a bespoke equivalent via a thin `ops/dashboard.py` verbosity-tier addition (aligned with Primitive A's verbosity tiers). Operator preference: escalate first.

### §7.4 ADR 003 — Token economy native vs. bespoke boundary

**Filing:** `plans/steward_platform/adrs/003-token-economy-native-vs-bespoke.md`, seeded in Packet 11 and promoted at Phase 0 close with observation-window evidence.

**Required sections** (matching ADR 001 / 005 / 006 / 007 / 010 / B8 shape):

- Status (SEEDED at Phase 0 kickoff; PROMOTED at Phase 0 close)
- Primitive: F (meta-referenced by B.1 for dispatch input)
- Context: the `/usage` + `/cost` comparison-feed motivation, per §5-F Work bullet 3
- Decision: which categories steward adopts into its own rollups vs. which remain `/usage`-only vs. which native features remain out of scope until Anthropic ships
- Consequences: downstream implications for B.1 (which signal set drives dispatch), H.1 (which event shapes replay must handle), G (how much `token_economy.py` eventually migrates to native vs. stays bespoke)
- Model tier interaction: cross-reference to ADR 006 §"Practical consequences for B.1" — dual-envelope is a joint concern
- Alternatives considered: (1) bespoke-only (rejected: misses native-only categories like cache-miss + long-context cost); (2) native-only (rejected: `/usage` surface does not replicate bespoke attribution dimensions); (3) current — comparison feed (adopted)
- Open questions: attribution backfill for historical sessions (defer to Phase 1); `/usage` format-stability posture (monitor via parser gate)
- Source evidence: Phase 0 observation-window comparison artifacts; link to `data/events/` date range; link to bespoke vs. native diff artifact committed under `plans/steward_platform/6_primitive_F/`

**ADR 003 is not dispatch-critical.** Packet 11 seeds the ADR file with a `Status: SEEDED` header + a `Decision: TBD — pending Phase 0 observation-window evidence` placeholder. Phase 0 close promotes the ADR with operator signoff. This matches how ADRs 005/007/010/B8 were seeded before Phase 0 kickoff.

### §7.5 Cost tradeoff (native-substrate-first scrutiny)

Per §10.9 Pattern 2, native-substrate-first adoption weighs the cost of the substrate dependency. `/usage` + `/cost` are **not currently documented as production-supported** (parallel to ADR 006's note about auto mode's research-preview status). Tradeoffs:

- **Benefit:** free operator visibility into categories the bespoke path misses (cache-miss cost, subagent overhead, long-context cost).
- **Cost:** format-stability risk (substrate upgrade can break the parser) + per-call subprocess latency for the nightly capture.
- **Mitigation:** parser fixture-gate (§7.2) + fallback to bespoke-only rollup if native capture fails + ADR 003 documenting the dependency at Phase 0 close so any future format-stability issue has a decision record to update.

The three-tier-preference does not require **preferring** native over bespoke when the native surface is explicitly under-specified; it requires **evaluating** native first. Phase 0 evaluation lands the comparison feed + the ADR; Phase 1+ decisions about further adoption depend on the observed cost profile and the future Anthropic roadmap.

---

## §8. Packet 11 execution spec

### §8.1 Files created

- `src/bid_euchre/ops/token_economy_emitter.py` (~100 LOC)
- `src/bid_euchre/ops/token_economy_native.py` (~80 LOC)
- `src/bid_euchre/ops/token_baseline_delta.py` (~80 LOC)
- `scripts/internal/capture_native_usage.py` (~60 LOC)
- `plans/steward_platform/adrs/003-token-economy-native-vs-bespoke.md` (seeded; ~80 lines)
- `tests/unit/test_token_economy_emitter.py` (~100 LOC)
- `tests/unit/test_token_economy_native.py` (~80 LOC)
- `tests/unit/test_token_baseline_delta.py` (~80 LOC)
- `tests/unit/test_capture_native_usage.py` (~60 LOC)
- `tests/integration/test_token_economy_emission_e2e.py` (~80 LOC)
- `tests/fixtures/native_usage/usage_sample_001.txt` through `usage_sample_003.txt` (operator-captured fixture output)
- `.claude/hooks/post-baseline-commit.sh` (~15 LOC — conditional hook on baseline.md commits)

### §8.2 Files modified

- `src/bid_euchre/ops/events.py` — add `token_rollup_observed`, `token_rollup_drift`, `baseline_updated`, optional `token_rollup_emission_failure` to `VALID_EVENT_TYPES` (Primitive A registry-driven home, if Packet 3 has already shipped; otherwise in v1.0 registry directly)
- `src/bid_euchre/ops/token_economy.py` — small glue-path addition: route `lane_summary()` and `throughput_summary()` callers through a new module-level `emit_rollup_event` helper (imported from `token_economy_emitter`) for event emission without duplicating attribution logic
- `src/bid_euchre/ops/dashboard.py` — add `Token baseline delta` row (§5.5); apply verbosity tier / result-size override (§7.3); sparkline sub-row
- `.claude/settings.json` — add `mcp.resultSizeOverride` entries per §7.3 (if supported by the Claude Code version at dispatch time; otherwise flagged per §7.3 caveat)
- `scripts/internal/ops.py` — add `usage --emit` + `usage --refresh-delta` subcommand flags
- `plans/steward_platform/verification_contract/map.md` — add Primitive F coverage rows (F.1–F.5 + F.Phase0Readiness) matching §3 of this doc
- `MEMORY.md` — post-merge entry recording Primitive F telemetry + baseline-delta + native adoption landing

### §8.3 Order of operations (Packet 11)

1. **Branch + scope lock.** `feat/primitive-f-telemetry-extraction` from `origin/main`. Scope declared: files in §8.1 + §8.2 only.
2. **Verify Primitive A dependency.** Before any emitter code lands, confirm `EVENT_FIELD_REGISTRY` in `event_schema.py` exists and is the published v1.0 contract. If missing, escalate to orchestrator — Packet 11 is mis-ordered.
3. **Registry additions first.** Add the four new event types to `EVENT_FIELD_REGISTRY` (or `VALID_EVENT_TYPES` if the registry module hasn't been built yet and events.py is the home). Unit test (`test_event_schema.py` additive coverage if registry; ad-hoc if VALID_EVENT_TYPES).
4. **Emitter second.** `token_economy_emitter.py` + `test_token_economy_emitter.py`. Unit tests first-green; then wire to `token_economy.py` glue.
5. **Baseline-delta third.** `token_baseline_delta.py` + `test_token_baseline_delta.py`. Seed-fixture the baseline.md read path; test delta computation + alert-emission shape.
6. **Native capture fourth.** `capture_native_usage.py` + `test_capture_native_usage.py` + `tests/fixtures/native_usage/*.txt`. Requires fixture files pre-committed (operator captures 3 real `/usage` outputs before or during implementation; author lane does not generate fixtures).
7. **Diff surface fifth.** `token_economy_native.py` + `test_token_economy_native.py`. Diff bespoke vs. native; flag divergences.
8. **Dashboard panel sixth.** `dashboard.py` modifications. Manual smoke: `uv run python scripts/internal/ops.py dashboard` renders the new row.
9. **MCP override seventh.** `.claude/settings.json` entries. Manual smoke: measure token-cost delta on dashboard + inbox invocations (bespoke rollup before/after).
10. **Hook + ADR eighth.** `post-baseline-commit.sh` conditional hook + ADR 003 seeded file.
11. **Integration test ninth.** `test_token_economy_emission_e2e.py` — end-to-end seed → emit → read-back → delta → dashboard-query.
12. **Verification contract map rows tenth.** Add Primitive F rows to `verification_contract/map.md` per §3 of this shape.
13. **Validation run eleventh.** Run `make check-gated` (foreground); run `agent_readability_lint.py check verification-contract`; run the 9 grep-verifiable checks from the task packet's Validation field (§8.4).
14. **Open PR.** Title: `feat(ops): land Primitive F telemetry + baseline-delta + /usage native adoption (Packet 11)`. Body includes `Verification Performed` section with all Tier 1 + Tier 2 pytest output + dashboard smoke + the 9 grep checks pasted.

### §8.4 Validation commands (Packet 11 Tier 2 + task-packet grep gates)

```bash
# Tier 1 — unit (during development)
uv run python -m pytest tests/unit/test_token_economy_emitter.py
uv run python -m pytest tests/unit/test_token_economy_native.py
uv run python -m pytest tests/unit/test_token_baseline_delta.py
uv run python -m pytest tests/unit/test_capture_native_usage.py

# Tier 1 — integration
uv run python -m pytest tests/integration/test_token_economy_emission_e2e.py

# Manual smoke — dashboard surface
uv run python scripts/internal/ops.py dashboard --json | jq '.token_baseline_delta'
# Expected: {"delta_pct": <float>, "baseline_window": "...", "status": "ok" | "warn" | ... , ...}

# Manual smoke — emitter
uv run python scripts/internal/ops.py usage --emit
ls -lt data/events/  # expect at least one events-<today>-NNN.jsonl file with token_rollup_observed records
jq -c 'select(.event_type == "token_rollup_observed")' data/events/events-$(date -u +%F)-001.jsonl | head -3

# Manual smoke — native capture
uv run python scripts/internal/capture_native_usage.py
# Expected: one token_rollup_observed event with source=native_usage; stderr-safe if /usage unavailable

# Grep-verifiable task-packet gates (from packet 24888cf4474d Validation field)
grep -c 'Verification Plan' plans/steward_platform/6_primitive_F/shaping.md  # expect: ≥1
grep -E 'F-debt|F-forward' plans/steward_platform/6_primitive_F/shaping.md   # expect: both terms; ≥5 matches each
grep -cE '/usage|/cost' plans/steward_platform/6_primitive_F/shaping.md      # expect: ≥1 each

# Agent-readability lint (post-Packet-2b)
uv run python scripts/internal/agent_readability_lint.py check verification-contract

# Tier 2
make check-gated
```

### §8.5 Coordination notes (Packet 11)

- **Strict dependency on Primitive A Packet 3.** F emits via `events.emit()`; Packet 3 is the dispatcher home. If Packet 3 hasn't merged, Packet 11 escalates and does NOT ship a shim (the shim would become load-bearing and violate §10.9 Pattern 9). Orchestrator re-orders or delays.
- **Coordination with B.1 shape (analyst-a Packet 3-B).** F's §6 data contract is the B.1 integration surface. Any contract divergence between B.1's shape and this doc's §6 is reconciled by the orchestrator before either packet dispatches.
- **Coordination with Primitive G capture script.** §5.3 consumes `scripts/internal/capture_steward_baseline.py` output (Primitive G-owned, per §5-G Readiness bullet 11). If G's script hasn't committed, Packet 11 creates a `baseline.md` read-path with a `status: insufficient-baseline` fallback; ADR 003 records the dependency direction.
- **Coordination with Primitive H.1 replay harness.** The v1.N additive event types F adds must be replay-compatible. Packet 11's integration test includes a smoke re-parse through the replay reader (if present) to confirm.
- **No coordination with E or D at dispatch time.** Primitive E consumes `stop_failure` + `permission_denied` events (A-owned); Primitive D is archivist infrastructure (D-owned). F does not produce events E or D consume directly.
- **Native-substrate-first escalation path.** If during Packet 11 a future Anthropic feature surfaces that subsumes steward's bespoke rollup surface (e.g., a native per-lane attribution API), Packet 11 author escalates via ADR proposal (per §10.9 Pattern 2) — does not silently rewrite to native. ADR 003 is the right home for that future decision.

### §8.6 Packet 11 success criterion

> Packet 11 is complete when:
>
> (a) all files in §8.1 are created + all files in §8.2 are modified per spec,
> (b) §8.4 Tier 1 + Tier 2 validation passes (foreground; `make check-gated` green),
> (c) the 3 grep-verifiable task-packet gates pass (Verification Plan present; F-debt/F-forward both defined; /usage + /cost each cited),
> (d) `agent_readability_lint.py check verification-contract` runs clean against the artifacts (post-Packet-2b),
> (e) dashboard smoke renders `Token baseline delta` row and the sparkline sub-row,
> (f) at least one `token_rollup_observed` event lands in `data/events/` from an author lane's nightly cron within 48h of merge,
> (g) ADR 003 seeded with `Status: SEEDED` + placeholder Decision (promoted at Phase 0 close),
> (h) PR merged with `Verification Performed` evidence pasted into PR body (pytest output + grep output + dashboard snapshot + event-stream tail).
>
> After Packet 11 merges, the Slice F observation window begins. The 1–2 week window runs concurrently with other Phase 0 primitive work; at window close, the operator + archivist record the promote/retain/kill decision per §11-F kill criterion, and ADR 003 is promoted with evidence-backed Decision + Consequences.

### §8.7 Packet 11 effort estimate

- **LOC estimate:** ~800–1000 net additions (300 emitters + 250 tests + 100 dashboard + 80 ADR + 60 capture + 60 config/hooks + 100 fixtures/docs).
- **Author-lane effort hint:** medium (lower than Packet 3 because Packet 3 builds the dispatcher; Packet 11 consumes it).
- **Estimated turnaround:** 1 author-lane session if no blockers; 2 if fixture capture (§7.2) or MCP override availability (§7.3) surfaces issues.

---

## §9. Self-review against completeness criteria

The analyst-lane prompt-policy clause (§4.3 of `plans/steward_platform/verification_contract/shaping.md`) requires shaping docs end with a `## Verification Plan` section. §11 below provides that. This section is the analyst's self-audit against shaping completeness.

### §9.1 Completeness criteria stress-test

| Criterion | Check | Outcome |
|---|---|---|
| F-debt vs F-forward boundary explicit | §2.1 lists F-forward; §2.2 lists F-debt; boundary rule stated | ✓ |
| §5-F Work bullets all accounted for | Bullet 1 (Slice F eval) → §4.3 + §10; Bullet 2 (baseline re-capture) → §5.2; Bullet 3 (/usage comparison feed + ADR 003) → §7.4; Bullet 4 (MCP result-size override) → §7.3; Bullet 5 (Slice F decision gate) → §10; Bullet 6 (rollups dashboard shipped #2725) → §4.1; Bullet 7 (tokens-per-merge via Primitive A) → §4 | ✓ |
| §5-F Phase 0 Readiness bullets all accounted for | Rollups dashboard live (§4.1); Slice F observation underway (§4.3); Baseline captured (§5) | ✓ |
| §5-F Phase 1 Validation bullets all accounted for | Slice F decision in MEMORY.md + committed artifact (§10, ADR 003); tokens-per-merge trending flat/down (§5.6); tokens-per-proving-run-insight metric published (§4 + §10) | ✓ |
| Deliverable → Pattern 10 surface table | §3 maps all 5 F-forward deliverables to named surfaces | ✓ (10 rows, all surfaces cited by path or command) |
| /usage + /cost adoption specified | §7 spec + §7.4 ADR 003 content | ✓ (both mentioned in both spec + ADR) |
| B.1 integration hand-off enumerated | §6.6 explicit 5-point table | ✓ |
| Dual-envelope (ADR 006) cross-reference | §6.4 | ✓ |
| Baseline-delta definition explicit | §5.2 | ✓ |
| Baseline refresh cadence explicit | §5.3 | ✓ |
| "Baseline updated" promotion gate spec | §5.4 | ✓ |
| Alert rules enumerated | §5.6 | ✓ |
| Dependency on Primitive A explicit | §1 + §4.2 + §8.5 | ✓ |
| Kill criterion (§11-F) addressed | §4.3 names the evidence source; §10 names the disposition | ✓ |
| Phase 2 Decision Inputs subsection | §10 has all 5 prompts + disposition | ✓ |
| Verification Plan section | §11 | ✓ |
| Packet spec covers files + order + validation + coordination + success | §8 | ✓ |

### §9.2 Risks I surfaced during self-review (orchestrator decision)

1. **MCP result-size override availability.** §7.3 depends on a Claude Code substrate feature that may not be stable in the version the fleet runs at Packet 11 dispatch. **Recommendation:** orchestrator confirm before dispatch; if unavailable, either (a) escalate and defer that slice to a later packet (preferred per §7.3 caveat), or (b) replace with a bespoke `ops/dashboard.py` verbosity tier.
2. **Baseline attribution backfill.** Baseline.md §8 currently shows 100% "unknown" buckets. §5.7 documents the caveat; ADR 003 will note the decision. **Recommendation:** defer backfill to Phase 1; accept that the initial few delta cycles will have low signal-to-noise ratio. Operator may prefer a one-shot backfill before Phase 0 observation window begins — that's a separate packet against Primitive G or F, not scope creep for Packet 11.
3. **Packet 3 (Primitive A) dispatch order.** §8.5 makes Packet 11 strictly downstream of Packet 3. If the orchestrator dispatches out-of-order, Packet 11 must escalate and wait. **Recommendation:** orchestrator confirm Packet 3 merged before Packet 11 dispatches; alternatively, accept a ~1-day delay at dispatch time if Packet 3 slips.
4. **B.1 shape divergence.** §6 specifies a data contract F commits to. If analyst-a's B.1 shape (Packet 3-B or whichever packet ID it carries) diverges, §6.6 escalation applies. **Recommendation:** require joint review of both shapes before either packet dispatches — i.e., a 15-minute operator-review step where orchestrator reads §6 of this doc and the B.1 shape side-by-side. If they match, dispatch both.
5. **`/usage` parser fragility.** §7.2 depends on `/usage` output format stability. **Recommendation:** accept format-stability risk as documented in ADR 003 §Open questions; fixture-gate the parser so regressions fail loudly; plan for periodic fixture refresh (every Claude Code minor version bump).
6. **Event-type naming collision.** §4.2 names `token_rollup_observed` + `token_rollup_drift` + `baseline_updated`. If Packet 3's registry already reserves those names for a different shape, collision surfaces at registration time. **Recommendation:** Packet 11 author verifies no collision before adding; Packet 3's registry shape is the authoritative reference.
7. **Dashboard render collision.** §5.5 adds a `Token baseline delta` row to `ops.py dashboard`. If Primitive A Packet 3 adds a `Latencies` panel to the same surface, ordering + layout matters. **Recommendation:** Packet 11 author reads Packet 3's dashboard modification as a prerequisite; the two panels coexist above/below per §10.9 Pattern 9 ownership (both owned via separate primitives; both land in `ops/dashboard.py`).

### §9.3 Orchestrator option — adversarial review

If the orchestrator wants independent adversarial review before Packet 11 dispatch, dispatch a separate packet to any recused analyst lane with the prompt:

> "Review `plans/steward_platform/6_primitive_F/shaping.md` for: (a) F-debt/F-forward boundary integrity (any F-debt item accidentally pulled into F-forward?); (b) Pattern 10 surface coverage adequacy (every deliverable has a named surface that's not 'operator review' without pass criterion?); (c) B.1 integration contract completeness (§6 enumerated hand-off points are exhaustive?); (d) §5.6 alert thresholds defensible against baseline §8 unknown-bucket caveat; (e) Packet 11 spec executability (an author lane could open a PR from §8 without ambiguity). Recommended but not blocking per the task framing."

### §9.4 Constraint encountered

The task packet did not require spawning a reviewer agent. Self-review per §9.1 + §9.2 substitutes. The analyst-lane YAML frontmatter structurally disallows the `Agent` tool (per the analyst system prompt), so a spawned-subagent review is not available from this lane; dispatch to a sibling recused analyst lane is the correct escalation path for adversarial review.

---

## §10. Phase 2 Decision Inputs

**Portability readiness:** Improved. F-forward consumes Primitive A's schema (pattern, not dependency) and carries §9.7 first-class IDs through its rollup emissions, so a second-cell deployment inherits the observability seam for free. The tier-1 `/usage` + `/cost` adoption surfaces are already portable — they travel with Claude Code itself. The tier-4 `token_economy.py` bespoke retention is the portability-cost residue, and ADR 003 at Phase 0 close documents the migration path toward reducing it. Source: §4.4 public API + §6.2 return shape + §7.5 cost tradeoff.

**Meta-layer need:** no change. F is a substrate-measurement primitive; no meta-framework implied. The measurement + feedback loop lives in 4 small modules (~400 LOC combined) routed through the existing dispatcher.

**Kill signal for primitive(s) named:** no. This shaping sharpens Primitive F implementation; it does not propose killing any primitive. The §11-F kill criterion ("Slice F cannot produce a defensible promote/retain/kill decision → freeze adaptive dispatch in advisory indefinitely") triggers only at Phase 0 close if the observation window data is insufficient; Packet 11 lands the measurement that makes the criterion evaluable. If Packet 11 merges and the observation window produces no distinguishable promote/retain/kill signal, the kill criterion fires at Phase 0 close; ADR 003 records the "advisory-indefinite" disposition and B.1 stays in shadow mode.

**Re-evaluation needed in Phase 3:** Possibly. Three soft triggers:

- If the `/usage` format changes materially between Phase 0 and Phase 3, the comparison-feed path needs re-validation.
- If Anthropic ships a native per-lane attribution API, §4.1 bespoke rollups may become redundant; ADR 003's Supersedes section opens.
- If the observation-window decision is "retain advisory" (not kill), Phase 3 re-evaluates whether the 1-2-week window was long enough or whether the observation should extend.

Re-evaluation window: end of Phase 1 proving run, informed by the event-stream corpus + `/usage` drift artifacts accumulated over the run. **RE-EVAL: end-of-Phase-1**

**Surprise finding:** The dual-envelope discovery (ADR 006 §"Model tier interaction") ties F and B.1 much more tightly than the §5-F text alone suggests. F's rollup must carry `current_model_tier` as a first-class field, and B.1's dispatch must emit `safety_envelope_delta` on downgrade-recommending events. Without that coupling, token-economy optimization silently lowers the safety envelope — exactly the failure mode ADR 006 §Alternatives-#5 names (settings encode policy; runtime gate silently inactive). This was not surfaced in the §5-F plan text; it emerges from cross-referencing ADR 006 and is codified here at §6.4. If this pattern recurs across other primitives (B.1, E, D consuming rollups in ways that interact with auto-mode envelope), §10.9 Pattern 2 (native-substrate-first) and Pattern 6 (per-surface owner) may need tightening to name the envelope-delta flagging discipline explicitly.

**Disposition:** open

---

## §11. Verification Plan (Pattern 10 mandate)

Per the analyst prompt-policy clause (§4.3 of `plans/steward_platform/verification_contract/shaping.md`): every shaping doc deliverable names a verification surface. This shaping doc itself is the deliverable; its "verification surface" is whether downstream Packet 11 can be authored from it without additional shaping. Per Pattern 10 deliverable-class mapping, this is a **shaping artifact** with operator-review surface form with an explicit pass criterion.

| Deliverable (§N.M of this shaping doc) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2 F-debt vs F-forward boundary | scope-exclusion decision | operator-review prompt: "Is any item in §2.1 listed in `rework_spec.md` §3 as token_economy.py hard-block? If yes, boundary leaked." | analyst (this packet); orchestrator (review) | zero leak rows at review |
| §3 Deliverable → Pattern 10 surface table | reconciliation against verification-contract shaping.md §2 | each surface in §3 resolves to a real path-or-command at Packet 11 dispatch time | Packet 11 author; lint (post-Packet-2b) | every surface name in §3 is grep-findable; `agent_readability_lint.py check verification-contract` exits 0 against this file |
| §4.1 Telemetry extraction goal + dispatcher routing | shaping spec for new module under `src/bid_euchre/ops/**` | Packet 11 author authors `token_economy_emitter.py` from §4.1–§4.5 alone | author (Packet 11) | Packet 11 PR's emitter module matches §4 spec without analyst clarification |
| §4.2 v1.N additive event types | event-schema addition | replay-harness compat assertion — new types re-parse cleanly through Primitive A's reader | author (Packet 11); H.1 author (Phase 1 validation) | `test_token_economy_emission_e2e.py` round-trips events; H.1 replay reader consumes without compat-shim |
| §4.4 Public API for B.1 | shaping spec for data contract | B.1 shape (analyst-a Packet 3-B) cites `§4.4` explicitly and matches return-dict shape | analyst-a (B.1 shape); orchestrator (joint review per §9.2 risk 4) | §6.6 hand-off points all resolved; zero contract ambiguity at Packet 3-B review |
| §5.2 Delta definition | shaping spec for computation | `test_token_baseline_delta.py` seeded fixture asserts delta formula matches §5.2 | author (Packet 11) | pytest passes |
| §5.4 Baseline-updated promotion gate | shaping spec for event emission | `.claude/hooks/post-baseline-commit.sh` conditional hook fires on baseline.md commit | author (Packet 11) | manual smoke: commit a baseline.md modification; confirm `baseline_updated` event lands in `data/events/` |
| §5.5 Dashboard panel | shaping spec for `ops/dashboard.py` modification | named runnable command | ops (during proving run) | `uv run python scripts/internal/ops.py dashboard --json \| jq '.token_baseline_delta'` returns the dict schema in §5.5 |
| §5.6 Alert rules | shaping spec for alert emission | unit test asserts each alert fires given seeded conditions | author (Packet 11) | `test_token_baseline_delta.py::test_alert_thresholds` passes |
| §6.4 Dual-envelope flagging | emit-behavior cross-reference to ADR 006 | event-stream grep for `dispatch_recommendation` records with `safety_envelope_delta` field populated on downgrade | B.1 author (Packet 3-B); ops (during proving run) | grep finds the field on ≥1 matching event during proving run |
| §6.6 Enumerated hand-off points | dispatch-readiness | all 5 rows of §6.6 resolved at Packet 11 dispatch time | orchestrator | §9.2 risk 4 review step completed; dispatch proceeds |
| §7.2 `/usage` capture script | shaping spec for new Python script | `test_capture_native_usage.py` asserts parser handles ≥3 real fixtures | author (Packet 11) | pytest passes against committed fixtures |
| §7.3 MCP result-size override | config change | rollback test (revert commit smoke) + measurement: ≥30% token reduction on dashboard + inbox invocations | author (Packet 11); ops (during observation window) | bespoke rollup pre/post diff confirms reduction |
| §7.4 ADR 003 seeded | new ADR under `plans/steward_platform/adrs/` | Pattern 10 ADR surface form: Pattern 7 rollback (supersession route) + commit citation | analyst (Phase 0 close filing); operator (signoff) | ADR 003 file exists with Status=SEEDED at Packet 11 merge; promoted at Phase 0 close with evidence |
| §8 Packet 11 execution spec | dispatch-readiness | orchestrator dispatches Packet 11 with §8 Validation contents copied verbatim into packet Validation field | orchestrator | Packet 11 dispatched without analyst re-shaping |
| §9 Self-review | analyst-discipline check | §9.1 table all ✓ + §9.2 risks surfaced | analyst (this packet) | §9.1 all ✓ |
| §10 Phase 2 Decision Inputs | required §15.2 schema subsection | 5 prompts + disposition all populated | analyst (this packet) | §10 complete |
| §11 Verification Plan | this section | lint cross-walks every §N.M to a surface | analyst (this packet); lint (post-Packet-2b) | `agent_readability_lint.py check verification-contract` clean against this file |

**Worked examples for reading this section (per Pattern 10 lenient-form):**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §4.2 `token_rollup_observed` shape | schema-design constraint | grep `data/events/events-*.jsonl` for records with `event_type=token_rollup_observed` missing any of the §4.2 fields → expect 0 matches | author (Packet 11) | grep returns 0 in seeded smoke |
| §7.3 dashboard size reduction target | measurement claim | bespoke rollup delta: `total_tokens(dashboard) pre-override / total_tokens(dashboard) post-override >= 1.3` | author (Packet 11) | ratio ≥ 1.3 on 7-day observation window post-merge |
| §6.4 dual-envelope field population | event-shape constraint | grep `data/events/events-*.jsonl` for `dispatch_recommendation` records where `recommended_model_tier != current_model_tier` AND `safety_envelope_delta IS NULL` → expect 0 matches | B.1 author (Packet 3-B) | grep returns 0 after Packet 3-B merges |

---

## §12. References

- `plans/steward_platform/governing_plan.md` §5-F — primary source for Primitive F scope
- `plans/steward_platform/governing_plan.md` §4.3 — baseline capture commands + storage location
- `plans/steward_platform/governing_plan.md` §11-F — Primitive F kill criterion
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 2 / 8 / 9 / 10 — pattern enforcement
- `plans/steward_platform/governing_plan.md` §15.2 — Phase 2 Decision Inputs subsection schema
- `plans/steward_platform/1_primitive_A/shaping.md` — Primitive A shape; §4.4 return dict depends on A's event registry
- `plans/steward_platform/0_hardening/sub/rework_spec.md` §3 — F-debt enumeration (row `token_economy.py`, 22 hard-blocks)
- `plans/steward_platform/0_hardening/baseline.md` — baseline snapshot; §3 + §8 read by F-forward delta consumer
- `plans/steward_platform/adrs/006-auto-mode.md` §"Model tier interaction" — dual-envelope constraint
- `plans/steward_platform/claude_code_changelog_implications.md` §2 Tier S — native features feeding F-forward
- `plans/steward_platform/verification_contract/shaping.md` §2 / §3 / §4 — Pattern 10 surface-class defaults, V1–V6 precheck, per-lane prompt-policy
- `plans/steward_platform/verification_contract/map.md` — Primitive F coverage rows (F.1–F.5; added by Packet 11)
- `.claude/rules/deferred/30_data_contract.md` — `data/events/` retention alignment
- `.claude/rules/deferred/60_review_gate.md` — review-driver V1–V6 precheck (Packet 11 extension domain)
- `.claude/rules/prompt_policy/analyst.md` — analyst-lane shaping obligation (this doc complies)
- `src/bid_euchre/ops/token_economy.py` — bespoke rollup module; source-grounded via §4.4 + §4.5 spec
- `src/bid_euchre/ops/events.py` — dispatcher home; VALID_EVENT_TYPES extended per §4.2 + §8.2
- PR #2725 — lane × model × effort rollups shipped
- PR #2766 — baseline.md artifact committed
- PR #2716 — Slice F evaluation protocol
- Task packet: `24888cf4474d` (Primitive F pre-shape)
