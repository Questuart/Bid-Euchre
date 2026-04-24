# Migration 01 — `ops/token_economy.py` → native `/usage` + `/cost`

**Date:** 2026-04-24
**Lane:** analyst-a (this shape) → author-b or flex-a (execution; see §7)
**Packet:** `4185244e03fb` (this shaping packet) → execution packet TBD (Orchestrator draws per §7)
**Branch:** `shaping/primitive-G2-token-economy-migration` (this doc) → execution branch `feat/g-c1-token-economy-native-usage`
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-G (Primitive G)
**Upstream shape:**
- `plans/steward_platform/7_primitive_G/shaping.md` §5.1 (packet G-C1 definition) — PR #2784
- `plans/steward_platform/7_primitive_G/bespoke_surface_audit.md` §2.2 + §3 — PR #2815 (this analyst's prior audit)

## Purpose

Produce the **tactical execution plan** for the Primitive G.2 pilot migration —
the first substrate-available-now substitution the fleet ships. The
governing frame and proving-run pattern are already authoritative in
`shaping.md` §5.1 and `bespoke_surface_audit.md` §3; this plan makes both
concrete for `ops/token_economy.py` specifically: every call-site enumerated,
every hard-block mapped to its native substitute or its keep-bespoke
rationale, the Cohort A/B dual-write discipline wired end-to-end, and the
execution packet handed off as dispatch-ready.

The work will be judged against the 8 operator-review pass criteria in the
shaping packet's Validation field — every section below maps to one row of
that contract.

**Scope-lock (from shaping packet):** this plan does NOT edit
`bespoke_surface_audit.md` or `shaping.md`; does NOT write code; does NOT
dispatch the execution packet; does NOT generalize to other §2.2 migrations.

## Upstream gates (from `shaping.md` §5.1)

Both gates remain load-bearing:

1. **Primitive F Packet 11 merged first.** F-forward's
   `token_economy_emitter.py` consumes `token_economy.py` via the rollup
   surface; G-C1 refactors under a stable F-consuming contract. **Operator
   confirms Packet 11 merged before the G-C1 execution packet dispatches.**
   (shaping.md §14 surprise-finding #4.)
2. **ADR 003 seeded by F Packet 11; PROMOTED at Phase 0 close.** ADR 003
   documents which surfaces `/usage` + `/cost` cover vs. which remain
   bespoke. G-C1 lands *before* ADR 003 is promoted; the migration **produces
   ADR 003's disposition row as a deliverable**, not consumes it.

---

## §1. Call-site inventory

All files and lines that read from or write into the `token_economy`
pipeline, measured on origin/main at the time of this shape. Grouped by
consumer class.

### §1.1 Hard-blocks inside `src/bid_euchre/ops/token_economy.py` (the migration target)

Measured via `uv run python scripts/internal/audit_portability.py --json`
on origin/main; filtered to `src/bid_euchre/ops/token_economy.py` entries
with `severity == "hard-block"`.

| Line | Pattern | Kind | Surface |
|---|---|---|---|
| 355 | `project-name-literal` | `Bid-Euchre` literal in slug-suffix check | `_infer_lane_from_slug` heuristic |
| 356 | `project-name-literal` | `"Bid-Euchre"` return value | `_infer_lane_from_slug` heuristic |
| 992 | `worktree-name-literal` + `steward-prefix-regex` | `"Bid-Euchre-steward-author"` key | `_WORKTREE_TO_LANE` platform-pool entry |
| 993 | same | `"Bid-Euchre-steward-author-b"` key | same |
| 994 | same | `"Bid-Euchre-steward-author-c"` key | same |
| 995 | same | `"Bid-Euchre-steward-author-d"` key | same |
| 997 | same | `"Bid-Euchre-steward-brws-author-a"` key | `_WORKTREE_TO_LANE` browser-pool entry |
| 998 | same | `"Bid-Euchre-steward-brws-author-b"` key | same |
| 999 | same | `"Bid-Euchre-steward-brws-author-c"` key | same |
| 1000 | same | `"Bid-Euchre-steward-brws-author-d"` key | same |
| 1002 | same | `"Bid-Euchre-steward-analyst"` key | `_WORKTREE_TO_LANE` analyst-pool entry |
| 1003 | same | `"Bid-Euchre-steward-analyst-b"` key | same |
| 1004 | same | `"Bid-Euchre-steward-analyst-c"` key | same |
| 1005 | same | `"Bid-Euchre-steward-analyst-d"` key | same |
| 1007 | same | `"Bid-Euchre-steward-flex-a"` key | `_WORKTREE_TO_LANE` flex-pool entry |
| 1008 | same | `"Bid-Euchre-steward-flex-b"` key | same |
| 1009 | same | `"Bid-Euchre-steward-flex-c"` key | same |
| 1010 | same | `"Bid-Euchre-steward-flex-d"` key | same |
| 1012 | same | `"Bid-Euchre-steward-review"` key | `_WORKTREE_TO_LANE` control-pool entry |
| 1013 | same | `"Bid-Euchre-steward-ops"` key | same |
| 1015 | same | `"Bid-Euchre-steward-author-scratch"` key | `_WORKTREE_TO_LANE` legacy entry |
| 1095 | `worktree-name-literal` + `steward-prefix-regex` | `re.search(r"Bid-Euchre-steward-([a-z0-9-]+)", ...)` | `infer_lane_from_path` fallback regex |
| 1099 | same | `f"Bid-Euchre-steward-{suffix}"` reconstruction | same function |
| 1105 | `project-name-literal` | `basename == "Bid-Euchre"` branch | same function |
| 1106 | `project-name-literal` | `"/Bid-Euchre/"` substring branch | same function |

**Totals on origin/main today:** 25 unique hard-block lines, 46 hit-total
(most lines match 2 patterns). The "22 hard-blocks" figure from the
governing-plan and shaping text is the `worktree-name-literal` class count
at an earlier snapshot (F Packet 11 handoff); the migration eliminates all
25 lines + 46 hits in one pass. The measured pre-migration count is
recorded verbatim in the PR body for the proving-run baseline.

### §1.2 In-repo consumers of `token_economy` (src/)

| File | Line(s) | Read/write | Surface consumed |
|---|---|---|---|
| `src/bid_euchre/ops/learning.py` | 546 | doc-ref | Cross-references `join_outcomes_with_token_economy` in LaneFeatures docstring |
| `src/bid_euchre/ops/learning.py` | 582-584 | import + call | `build_lane_features()` lazy-imports `join_outcomes_with_token_economy`; drives B.1 adaptive dispatch features |
| `src/bid_euchre/ops/learning.py` | 972-974 | import + call | `recommend_lanes()` lazy-imports same; shared substrate across the candidate set |
| `src/bid_euchre/ops/dashboard.py` | 637 | import + call | `build_dashboard_view()` calls `dashboard_token_economy()` for the dashboard's token-economy panel |
| `src/bid_euchre/ops/dashboard.py` | 780 | doc-ref | `format_dashboard_text()` docstring pointer to `dashboard_token_economy` |
| `src/bid_euchre/ops/__init__.py` | grep-only | export | Module exposure only (no logic) |
| `src/bid_euchre/ops/task_queue.py` | grep-only | unrelated | String match is on `task_queue`'s own module doc; not a consumer |

### §1.3 In-repo consumers (scripts/)

`scripts/internal/ops.py` carries 12 lazy-import sites, all inside
`cmd_usage()` (line 3552) — the CLI façade for the entire token-economy
feature.

| Line | Usage subcommand | Function(s) imported |
|---|---|---|
| 3557-3560 | `usage import` | `import_project_jsonl`, `import_usage_data` |
| 3599 | `usage attribute` | `attribute_sessions` |
| 3621-3626 | `usage summary` | `model_summary`, `reconcile_totals`, `store_status`, `usage_summary` |
| 3700 | `usage lanes` | `lane_summary` |
| 3735 | `usage throughput` | `throughput_summary` |
| 3762 | `usage anti-patterns` | `detect_anti_patterns` |
| 3787 | `usage status` | `store_status` |
| 3819 | `usage reconcile` | `reconcile_totals` |
| 3867 | `usage by-model` | `model_summary`, `usage_summary` |
| 3937 | `usage by-effort` | `effort_summary` |
| 3993 | `usage by-model-outcome` | `model_outcome_summary` |

CLI argparse wiring lives at `scripts/internal/ops.py` lines 5397-5539.

### §1.4 Test-suite consumers

| File | Surface |
|---|---|
| `tests/unit/test_token_economy.py` | Core shape tests — validate_session_meta, validate_facet, import, attribution, lane summary, throughput, anti-patterns, reconcile, dashboard surface, model/effort rollups |
| `tests/unit/test_ops_token_economy.py` | Higher-level contract tests including Slice B (lane × model × effort) rollup parity, `_WORKTREE_TO_LANE` coverage, and CLI-mock integration |
| `tests/unit/test_ops_cli.py` | CLI integration (line 6145: `usage summary` + `model_summary`) |
| `tests/unit/test_ops_dashboard.py` | Dashboard panel shape, including token-economy section |
| `tests/unit/test_portability_audit.py` | Portability-audit measurement surface — validates the `--json` output shape and the hard-block counting |
| `tests/unit/test_steward_session.py` | Lane-model tier resolution — indirect consumer via shared worktree-name vocabulary |

### §1.5 Downstream event-stream consumer (gated upstream)

`src/bid_euchre/ops/token_economy_emitter.py` (F-forward Packet 11) —
**not yet merged on origin/main**; listed here because the `shaping.md`
§5.1 upstream gate "F Packet 11 merged first" binds the emitter to
`token_economy.py`'s rollup surface. G-C1 must leave the rollup contract
consumed by the emitter byte-for-byte intact. The behavioral-equivalence
contract (§4) makes this observable.

---

## §2. Native invocation map

This is the G-C1-specific concretization of `bespoke_surface_audit.md`
§2.2's high-level "Native /usage + /cost overlap where coverage exists;
adapter-boundary reads for residual Bid-Euchre-literal surfaces" entry.
For each bespoke surface or sub-feature the inventory in §1 exposes, this
table names the native substitute (if any), the gap (if any), and the
severity of the gap.

Native surfaces referenced below:

- **Native `/usage`** — Claude Code slash command (Boris Cherny thread,
  post-April-2026). Produces parallel-session / subagent / cache-miss /
  long-context breakdown plus optimization tips. `claude_code_changelog_implications.md`
  §3 row "Native `/usage`" — System-rework tier S.
- **Native `/cost`** — older Claude Code slash command. Produces
  per-session token-cost breakdown. `claude_code_changelog_implications.md`
  §3 row "Native `/cost` breakdown" — System-rework tier S.
- **Raw JSONL telemetry** — Claude Code's on-disk substrate at
  `~/.claude/projects/<slug>/*.jsonl`. This is the same raw data both
  `token_economy.py` and native `/usage` + `/cost` derive from; it is not a
  competing surface.

### §2.1 Native-substitute map (per §1.1 hard-block line)

Every §1.1 hard-block eliminates via the **same mechanism** — extract the
Bid-Euchre-cell-specific literal map + regex into an adapter at
`src/bid_euchre/ops/adapters/token_economy_adapter.py`. The adapter is the
per-deployment-cell knowledge boundary (Platform-10 adapter pattern; see
`rework_spec.md` §3 row `core/provider.py` + `adapters/`). Call-sites in
`token_economy.py` call the adapter; the adapter encapsulates the literal
worktree→lane map and the steward-prefix regex.

**Native /usage + /cost do NOT replace this mapping** — they are lane-agnostic
surfaces (they produce raw session-level token counts, not per-lane rollups).
The hard-block elimination is therefore a **portability-adapter move**, not
a native-substitute substitution. `shaping.md` §5.1 scope wording ("replace
22 Bid-Euchre-literal hard-blocks with: Adapter-boundary reads... Config-sourced
constants... Per-deliverable ADR 003 decision") codifies this directly.

### §2.2 Native-substitute map (per §1.3 CLI subcommand)

This is where `/usage` + `/cost` actually substitute. Each subcommand
under `scripts/internal/ops.py cmd_usage()` is evaluated against native
coverage.

| CLI subcommand | Bespoke function(s) | Native substitute | Coverage | Gap severity |
|---|---|---|---|---|
| `usage import` | `import_usage_data`, `import_project_jsonl` | Native `/usage` reads the same `~/.claude/projects/**.jsonl` substrate directly; no "import" step needed | **Replaceable** | none — native reads raw |
| `usage attribute` | `attribute_sessions` + `_WORKTREE_TO_LANE` | **No native substitute** — native is lane-agnostic | **Keep bespoke** (per-deployment-cell concern) | blocker for substitution; stays bespoke via §2.1 adapter |
| `usage summary` | `usage_summary`, `reconcile_totals`, `store_status`, `model_summary` | Native `/usage` outputs session-level summary (raw in/out/cache per session) | **Partially replaceable** (summary) + **keep bespoke** (reconcile, store_status, model breakdown scoped to steward lanes) | degraded — native summary lacks lane × model × effort structure |
| `usage lanes` | `lane_summary` | **No native substitute** — depends on `_WORKTREE_TO_LANE` | **Keep bespoke** | blocker for substitution; stays bespoke |
| `usage throughput` | `throughput_summary` | **No native substitute** — tokens/commit/net-line/hour depends on lane-attributed git counts | **Keep bespoke** | blocker for substitution; stays bespoke |
| `usage anti-patterns` | `detect_anti_patterns` | Native `/usage` includes "optimization tips" (Cherny thread) | **Partial overlap**; native tips are advisory text, not programmatic findings consumable by dashboard | acceptable — two different outputs; keep bespoke for programmatic use |
| `usage status` | `store_status` | **No native substitute** — store is bespoke runtime state | **Keep bespoke** | blocker for substitution; stays bespoke |
| `usage reconcile` | `reconcile_totals` | **No native substitute** | **Keep bespoke** | blocker for substitution; stays bespoke |
| `usage by-model` | `model_summary` (Slice B) | Native `/usage` breaks down by parallel-session / subagent / cache-miss but NOT by Claude model version | **Partial overlap** | degraded — steward's `by-model` answers "opus vs sonnet vs synthetic" which native does not |
| `usage by-effort` | `effort_summary` (Slice B) | **No native substitute** — `effort_hint` is steward packet metadata | **Keep bespoke** | blocker; stays bespoke |
| `usage by-model-outcome` | `model_outcome_summary` (Slice B) | **No native substitute** — joins `task_completed` events × steward model buckets | **Keep bespoke** | blocker; stays bespoke |

### §2.3 Named gaps (blocker / degraded / acceptable)

The §2.2 columns fold into three gap categories, each with its disposition
for ADR 003 at Phase 0 close:

**Blocker gaps (native cannot substitute; stays bespoke):**
- Lane attribution — `attribute_sessions`, `lane_summary`, `throughput_summary`, `store_status`, `reconcile_totals`, `by-effort`, `by-model-outcome`.
- **ADR 003 disposition:** these surfaces remain bespoke; migration preserves them unchanged behind the adapter.

**Degraded gaps (native substitutes partially; bespoke retained for the missing dimensions):**
- `usage summary` — native `/usage` covers raw counts; steward retains lane × model × effort rollups.
- `usage by-model` — native `/usage` distinguishes session-class but not model-version (`claude-opus-4-7` vs `claude-sonnet-4-6` vs `synthetic`); steward retains `ModelBucket` / `_session_model_label()`.
- **ADR 003 disposition:** bespoke retained; native invocation documented as a *comparison feed*, not a replacement, per `claude_code_changelog_implications.md` §2 Tier S row "Native `/usage`".

**Acceptable gaps (native substitutes sufficiently; keeping bespoke is optional):**
- `usage import` — if the migration commits to reading JSONL directly on each query (no "import" step), the `import_usage_data` / `import_project_jsonl` functions and the `.claude/runtime/token_economy/` store can be retired.
- `usage anti-patterns` programmatic-vs-advisory boundary — bespoke findings feed the dashboard; native tips are operator-read. No substitution needed.
- **ADR 003 disposition:** migration is **free to retire** `import_*` functions and the runtime store IF the proving-run (§3–§4) confirms native `/usage` reads are fast enough to be on the hot path of `dashboard_token_economy()` (which is called on every dashboard render). If not, the import+store layer stays as a cache.

**Net migration scope (as an ADR 003 projection):** eliminate the 25 hard-block lines; extract the lane-mapping literal + regex into an adapter module; **retain all bespoke rollup surfaces** (Slice B contract preserved); optionally retire the import/store layer pending proving-run latency. No `token_economy.py` public-API function is deleted; only the `_WORKTREE_TO_LANE` + `_infer_lane_from_slug` + `infer_lane_from_path` internals move.

---

## §3. Cohort A/B wiring

### §3.1 Feature flag

Following `.claude/rules/feature_flags.md` conventions (Name, Default,
Rollback SLO, Validation surface, Owner):

| Property | Value |
|----------|-------|
| **Name** | `STEWARD_TOKEN_ECONOMY_NATIVE_USAGE` |
| **Type** | Environment variable |
| **Default** | `0` (disabled — bespoke path active during proving-run window; "no env var set" = safe forward path per feature-flag convention #2) |
| **Owning primitive** | G (G-C1 migration) |
| **Trigger** | Proving-run Cohort B activation; flipped to `1` on the Cohort B lane subset during the observation window |
| **Expected effect** | Downstream token-economy call-sites (§1.2–§1.3 consumers) route through the native-reader path (adapter-boundary) instead of the bespoke JSONL scanner where native is equivalence-verified (§2.3 acceptable gap) |
| **Rollback SLO** | Operator unsets flag → consumer re-entry to bespoke path within **1 minute** (matches Primitive A's SLO; the flag is process-env read on each call, no cache) |

**Validation surface for the flag itself:**
`tests/integration/test_token_economy_native_usage_fallback.py` (new in the
execution packet). The test flips the flag, invokes
`dashboard_token_economy()` twice (one run per cohort), and asserts:

- **All §2.3 Blocker dimensions match byte-exactly** across cohorts
  (`attribute_sessions`, `lane_summary`, `throughput_summary`, `store_status`,
  `reconcile_totals`, `by_effort`, `by_model_outcome`). These stay bespoke
  on both cohorts; any divergence is a bug.
- **All §2.3 Degraded dimensions match byte-exactly** across cohorts
  (`usage summary` lane × model × effort rollup, `by_model` model-version
  buckets). These are the **load-bearing Slice B contract that PR #2725 +
  the F Packet 11 consumer depend on**; the flag must not be usable as an
  escape hatch to regress Slice B parity.
- **§2.3 Acceptable dimensions may differ** only in the ways §2.3 names:
  `usage import` / store-metadata retirement; `usage anti-patterns`
  programmatic-vs-advisory boundary.

Correctness over convenience: the acceptance is **exact Slice B parity on
Blocker + Degraded**, not "differs only on by_model/by_effort". The flag
exists to prove equivalence on the migration-scope substitutions, not to
permit regressions on the downstream contract.

### §3.2 Dual-write pattern

During the proving-run window, the **raw-read substrate layer** is
dual-written for the narrow subset of surfaces where native `/usage` has
coverage (§2.3 Degraded + Acceptable). Everything §2.3 flags as Blocker
stays bespoke-unconditional on both cohorts — **native is not invoked
for Blocker surfaces at all**, because it cannot produce the required
fields (lane attribution, `_WORKTREE_TO_LANE`-derived rollups, `effort`
buckets, `model-outcome` joins).

This matters: if the flag could route a Blocker-surface call through
native, the native cohort would either (a) return `None` / partial data
and fail equivalence, or (b) silently fall back to bespoke — either of
which defeats the migration. The flag scope is narrower than
"dual-write all of `dashboard_token_economy`".

Concretely (execution detail — author lane implements):

1. Introduce `token_economy_adapter.py::read_session_records()` that
   accepts a `source` parameter: `"bespoke"` (current JSONL scanner) or
   `"native"` (native `/usage` invocation, parsed into the same
   `SessionRecord` shape). The adapter **only exposes
   `source="native"` for surfaces listed as Degraded or Acceptable in
   §2.3**; calls originating from Blocker surfaces (§2.3 list) pin
   `source="bespoke"` regardless of flag state — the adapter refuses
   `source="native"` at the entry point for those surfaces.
2. `dashboard_token_economy()` runs the bespoke path unconditionally to
   compute the full Slice B rollup (this is the return value used by
   downstream callers and matches PR #2725's consumer contract). When
   the flag is on, the adapter ALSO reads the native substrate for the
   §2.3 Degraded + Acceptable surfaces and emits per-surface divergence
   samples (§3.2 bullet 3) — but the dashboard's return value stays
   Slice-B-parity-locked on bespoke. The flag picks authoritativeness
   only for §2.3 Acceptable surfaces (raw import layer, optional store
   retirement candidates).
3. Both paths (where native is invoked per bullet 1) emit a
   `proving_run_cohort_sample` event (`bespoke_surface_audit.md` §3.7
   Pattern-8 observability hook) with fields
   `(surface="token_economy", subsurface=<§2.3 row>, cohort, lane_id,
   task_id, token_cost, behavioral_divergence_bool, window_id)`.
   `subsurface` identifies which §2.3 row the sample covers so operator
   review can separate Degraded-surface evidence from Acceptable-surface
   evidence.

### §3.3 Which calls go through which cohort

| Consumer (§1 reference) | Cohort during proving-run window |
|---|---|
| §1.2 `ops/learning.py` callers (`build_lane_features`, `recommend_lanes`) | Cohort A only — critical-path for B.1 dispatch; never routed through native until the proving-run passes |
| §1.2 `ops/dashboard.py` caller (`build_dashboard_view`) | Dual-write — both cohorts run; flag picks authoritative |
| §1.3 `ops.py cmd_usage` (interactive CLI) | Dual-write — both cohorts run; flag picks authoritative output |
| §1.5 F-forward emitter (`token_economy_emitter.py`) | Cohort A only — upstream gate; emitter contract must not shift mid-proving-run |

Rationale: the critical-path consumers (learning.py feeding B.1 dispatch;
F-forward emitter) stay on the bespoke path for the full window. Only the
operator-read surfaces (dashboard, CLI) accept dual-write. This isolates
any native regression from affecting dispatch decisions.

### §3.4 Parallel-run duration

Per `bespoke_surface_audit.md` §3.4 (per-surface slot allocation):

> Token-economy native `/usage`+`/cost` (G-C1) — Golden-file rollup
> preservation + `audit_portability.py` hard-block count — **1 week**.

**1 calendar week minimum** of operator fleet operation with the flag
flipped on for the Cohort B lane subset. Extend to 2 weeks if the
Cohort-B cohort size has fewer than 3 fleet-active days of representative
data (e.g., operator away-mode suppressed work mid-window).

---

## §4. Behavioral-equivalence contract

The contract specifies the observables each migration cohort must produce,
the fidelity threshold for "acceptable", and the source of truth for the
comparison.

### §4.1 Preserved exactly (no drift tolerated)

These observables MUST match byte-for-byte between Cohort A and Cohort B,
OR the proving-run fails. Measured per `dashboard_token_economy()` call on
the same input set:

| Observable | Path | Fidelity threshold |
|---|---|---|
| `overview.session_count` | `dashboard_token_economy() → overview.session_count` | exact equality |
| `overview.total_tokens` | same | exact equality |
| `overview.total_input_tokens` / `total_output_tokens` | same | exact equality |
| `overview.total_git_commits` | same | exact equality |
| `top_lanes[*].lane_id`, `pool`, `total_tokens`, `session_count`, `git_commits` | `top_lanes[]` array | exact equality (order included) |
| `efficient_lanes[*]` shape | same | exact equality (order included) |
| `throughput.tokens_per_commit`, `tokens_per_net_line`, `tokens_per_hour` | `throughput` sub-dict | exact equality |
| `by_model.buckets[*].{model, session_count, total_tokens, input/output/cache_*, git_commits}` | `by_model` (Slice B v3) | exact equality; `model` labels from `_session_model_label()` must resolve identically |
| `by_effort.buckets[*].{effort, session_count, total_tokens, git_commits}` | `by_effort` (Slice B v3) | exact equality |
| `store_status.*` | `store_status` sub-dict | exact equality |
| `anti_patterns[*].{pattern_id, name, severity}` | `anti_patterns[]` | exact equality (order-sensitive per bespoke implementation) |

**Rationale:** PR #2725 shipped the lane × model × effort rollups as the
F-forward Packet 11 consumer contract. Any shift in these observables
breaks upstream. The contract makes that consumer-contract binding
explicit.

### §4.2 Tolerance-permitted (normalization allowed)

These observables may differ between cohorts within a documented
normalization. A divergence outside the tolerance is a Warn-tier finding;
≥95% of calls must fall inside the tolerance:

| Observable | Tolerance | Normalization |
|---|---|---|
| `overview.time_range_start` / `time_range_end` | ±1 second ISO timestamp skew | parse to UTC; compare rounded to nearest second |
| `store_status.last_import_at` | native path may skip the import-step entirely | accept "never imported" on native when `_ensure_imported()` is a no-op under the flag |
| `anti_patterns[*].description` | text-string drift | compare `pattern_id` + `severity` only; description is human-facing |

### §4.3 Divergence-permitted (native contributes supplementary dimensions)

Native `/usage` exposes parallel-session / subagent / cache-miss /
long-context breakdown that the bespoke path does not. These are
**additive**, not substitutive — they become NEW fields on the adapter
output, never replacing existing fields. The execution packet may add them
as `dashboard_token_economy() → by_native_class: {...}`; doing so is
optional and does not affect the equivalence contract.

### §4.4 Sampling method

For each call, `dashboard_token_economy(output_dir=<same test path>)` runs
under both cohorts on the **same** on-disk snapshot. The adapter loads
from the same `~/.claude/projects/` tree both times; the difference is
whether the rollup walks the JSONL files directly (bespoke) or calls the
native `/usage` + `/cost` surface and reconstructs the rollup from their
output (native).

Paired sampling per `bespoke_surface_audit.md` §3.1: run Cohort A first,
then Cohort B, on the same snapshot; record the paired delta.

### §4.5 Acceptance criterion

**Pass:** §4.1 observables all match byte-for-byte across the proving-run
window, AND §4.2 observables are within-tolerance on ≥95% of calls.

**Fail:** Any §4.1 observable drifts (§4.2 tolerance doesn't apply) —
stop-loss trip #2 fires (§6).

---

## §5. Token-cost measurement method

Per `bespoke_surface_audit.md` §3.2 — token-cost delta is the **primary**
delta (behavioral-equivalence is secondary but gate-critical). This section
concretizes it for G-C1.

### §5.1 Counter

**Source:** `token_economy.py` itself — we are measuring the cost of the
migration path, not of the migration's target module. The measurement
reads from the same substrate both cohorts ingest from
(`~/.claude/projects/<slug>/*.jsonl`) to get per-task token counts for
the LANES that were active during the window.

**Per-task metric:** `input_tokens + output_tokens + cache_creation_tokens
+ cache_read_tokens` from each SessionRecord ingested during the window,
aggregated per `(lane_id, task_id)` — where `task_id` comes from the
`task_queue` packet ID when the session is attributed to a packet, and is
`None` otherwise. Unattributed sessions contribute to a `task_id=None`
bucket for the cohort.

**Why this works:** both cohorts produce the SAME raw token counts because
both read the SAME JSONL files — the delta we are measuring isn't "did
native save tokens on the existing Claude calls the fleet made?", it is
"did the migration itself change the amount of work the fleet did?" We
expect the delta to be **near-zero**; a negative delta (fleet did less
work under Cohort B) is anomalous and must be explained; a positive delta
(fleet did more work under Cohort B) is a regression.

**Secondary measurement** (cheaper, rougher): the number of
`dashboard_token_economy()` + `cmd_usage()` invocations during the window
× the average size of the rollup output. If native `/usage` is being
invoked as a subprocess on each call, its invocation overhead is a
distinct cost line.

### §5.2 Window

1 week (§3.4), sliced into daily aggregations so operator away-days don't
dominate the mean. The daily slice window runs 00:00 UTC to 23:59 UTC.

### §5.3 Aggregation + statistic

Per `bespoke_surface_audit.md` §3.2:

- **Mean delta** per cohort (Cohort A mean − Cohort B mean), expressed as
  a per-task-mean and as a per-day-mean.
- **Bootstrap 95% CI** on the mean delta (resample task-day pairs with
  replacement; 10k bootstrap iterations per §3.2 canonical discipline).
- **Paired t-test** across task-days where both cohorts had samples
  (paired sampling from §4.4 makes the pairing well-defined).

### §5.4 Pass / Warn / Fail per `bespoke_surface_audit.md` §3.2

- **Pass:** Cohort B mean ≤ Cohort A mean AND (bootstrap 95% CI on the
  delta excludes 0 on the non-positive side OR |mean delta| < 5% of
  Cohort A mean [noise-level equivalence]).
- **Warn:** CI spans 0 AND |mean delta| < 5% — recorded, migration
  proceeds, operator reviews.
- **Fail:** Cohort B mean > Cohort A mean at p < 0.05 — stop-loss trip #1
  (§6) fires.

**Null hypothesis framing:** H0 = migration has no token-cost effect. Pass
rejects H0 on the non-positive side or fails to reject H0 inside the
5%-noise band. Fail rejects H0 on the positive (regression) side.

---

## §6. Stop-loss trip wires

Per `bespoke_surface_audit.md` §3.3, 4 concrete trip wires. Each names the
trip condition (citing a measurement from §4 or §5) and the restore-bespoke
action. **All trips are per-surface, not fleet-wide** — flipping
`STEWARD_TOKEN_ECONOMY_NATIVE_USAGE=0` restores Cohort A (bespoke)
behavior without affecting any other migration.

### §6.1 Trip wire #1 — Token-cost regression

**Trip condition (references §5.4):** Cohort B per-task mean > Cohort A
per-task mean at p < 0.05 over a rolling 3-day window inside the
proving-run observation window. Measured via the bootstrap + paired-t
discipline in §5.3.

**Action:**
1. Operator unsets `STEWARD_TOKEN_ECONOMY_NATIVE_USAGE` → all lanes
   return to Cohort A path within SLO (1 min).
2. File follow-up issue documenting: the bootstrap distribution, the
   per-day delta, the task-ID outliers that drove the regression.
3. Migration **is not promoted** until the cost regression is explained
   (is it native invocation overhead? subprocess latency? adapter bug?).
4. ADR 003 disposition row "acceptable gap — import retirement" reverts
   to "degraded gap — bespoke retained" (the migration may still land for
   hard-block elimination, just without the `import_*` retirement).

### §6.2 Trip wire #2 — Behavioral-equivalence regression

**Trip condition (references §4.1 + §4.5):** ANY §4.1 byte-for-byte
observable diverges OR §4.2 tolerance-permitted observables drift outside
tolerance on > 5% of calls (equivalence rate < 95%).

**Action:**
1. Operator unsets `STEWARD_TOKEN_ECONOMY_NATIVE_USAGE` immediately (do
   not wait for end-of-window).
2. Diff the first 10 divergences; classify (native bug / steward
   assumption violation / sampling mismatch / input-set mismatch).
3. File follow-up issue if any class is novel.
4. Migration **pauses**; does not advance to dispatch until the
   divergence class is resolved.
5. If classification reveals the divergence is legitimate (e.g., the
   Slice B `ModelBucket` uses `claude-opus-4-7` labeling that native
   doesn't provide) — the migration re-scopes to exclude that observable
   and proceeds with the narrower adapter boundary.

### §6.3 Trip wire #3 — Availability regression

**Trip condition:** Native `/usage` OR `/cost` invocation (subprocess or
API call) returns a non-zero exit / non-2xx response ≥ **5 errors in a
24-hour window** per lane. This matches `bespoke_surface_audit.md` §3.3
trip wire 3 canonical threshold.

**Action:**
1. Operator unsets flag immediately; substrate-gate closes for this
   migration.
2. The packet defers to Phase 1 per `shaping.md` §14 surprise-finding
   discipline.
3. MEMORY.md note: which native surface failed, how many events, what
   mode of failure (transient / persistent).
4. ADR 003 disposition rows flip: "acceptable gaps" reclassify as
   "substrate-gated — Phase 1 re-evaluation".

### §6.4 Trip wire #4 — PR #2725 rollup-shape drift

**Trip condition (references §4.1 + §1.5 upstream binding):** Cohort B
run of `dashboard_token_economy()` produces a `by_model.buckets` or
`by_effort.buckets` list with any one of:

- Different set of bucket keys (model labels or effort labels) than Cohort A.
- Different count of buckets.
- Different token-total aggregation (`by_model.total_tokens` ≠ Cohort A's
  `by_model.total_tokens` by ≥ 0.1%).

This is stricter than §4.1 because it's the **F-forward Packet 11
emitter's consumer contract** — any drift here breaks the F→G binding
that `shaping.md` §5.1 names as upstream-gate #1.

**Action:**
1. Operator unsets flag immediately.
2. Run `tests/unit/test_token_economy.py::test_slice_b_rollup_shape`
   (the golden-file test from §7); record divergence.
3. File a BLOCK-severity issue: G-C1 cannot land; Slice B rollup contract
   is load-bearing for F Packet 11's emitter. Operator decides whether to
   (a) widen the adapter to reconstruct the Slice B shape under native,
   or (b) abandon the `import_*` retirement subset of the migration.

---

## §7. Execution packet specification

This section is what the orchestrator packages into the author-lane task
packet once this shape is approved. It is NOT a dispatch — only a draft
for the orchestrator to dispatch.

### §7.1 File scope

Writable by the author lane:

- `src/bid_euchre/ops/token_economy.py` — eliminate 25 hard-block lines (§1.1); delegate lane inference to adapter.
- `src/bid_euchre/ops/adapters/token_economy_adapter.py` — **new**. Houses: `_WORKTREE_TO_LANE` dict (moved verbatim), `_infer_lane_from_slug`, `infer_lane_from_path`. Exports `read_session_records(source="bespoke"|"native")` + cohort-aware dispatch per §3.2.
- `src/bid_euchre/ops/adapters/__init__.py` — add export for new adapter module.
- `scripts/internal/ops.py` — `cmd_usage()` dual-write wiring per §3.3 (12 import sites remain; add flag-reading branch).
- `tests/unit/test_token_economy.py` — golden-file preservation per `shaping.md` §5.1 verification surface: pre/post rollup values for a fixture cell; assert Slice B shape (§4.1) preserved.
- `tests/unit/test_ops_token_economy.py` — update `_WORKTREE_TO_LANE` import path (moves to adapter); assert coverage unchanged.
- `tests/integration/test_token_economy_native_usage_fallback.py` — **new**. Flag-flip test per §3.1 validation-surface requirement.
- `tests/integration/test_slice_f_rollups.py` — verify F-forward consumer contract unchanged (upstream gate #1).
- `.claude/rules/feature_flags.md` — add registry entry per §3.1 convention (Name, Default, Rollback SLO, Validation surface, Owner).

Read-only (referenced, not modified):

- `bespoke_surface_audit.md`, `shaping.md`, this migration plan.
- `scripts/internal/audit_portability.py` — called post-merge, not modified.
- `plans/steward_platform/adrs/003-*` (ADR 003 seed; this packet produces
  the disposition row, does not edit ADR 003 itself until Phase 0 close).

Out-of-scope (author lane refuses if surfaced mid-implementation):

- Any other `ops/*.py` module.
- `token_economy_emitter.py` (F-forward Packet 11; author lane must not
  touch; integration-test it only).
- `learning.py` consumer rewiring (Cohort A only per §3.3; no learning.py
  edits).

### §7.2 Tier 1 validation (during implementation)

```bash
uv run python -m pytest tests/unit/test_token_economy.py -x
uv run python -m pytest tests/unit/test_ops_token_economy.py -x
uv run python -m pytest tests/unit/test_portability_audit.py -x
uv run python -m pytest tests/integration/test_token_economy_native_usage_fallback.py -x
uv run python scripts/internal/audit_portability.py --json \
  | python -c "import json, sys; d=json.load(sys.stdin); \
      hits=[h for h in d['hits'] if 'token_economy.py' in h['file'] and h['severity']=='hard-block']; \
      assert len(hits)==0, f'{len(hits)} hard-blocks remain'; print('portability: 0 hard-blocks')"
```

### §7.3 Tier 2 validation (pre-PR)

```bash
make check-gated
uv run python scripts/internal/audit_portability.py --json  # paste output in PR body
```

The `make check-gated` run must show `Slice F` rollup integration tests
passing (upstream gate #1 intact).

### §7.4 Target lane recommendation

| Candidate | Archetype | Model tier | Currently idle? | Effort policy for `(author, implementation)` | Recommended rank |
|---|---|---|---|---|---|
| `author-b` | author | opus | yes (per operator-verified at shape-time) | `xhigh` (per `.claude/rules/effort_policy.md` table) | **Primary** |
| `flex-a` | flex | opus | yes | `xhigh` | Secondary (flex row in effort policy = `xhigh` for implementation) |
| `author-a` / `author-c` / `author-d` | author | opus | operator-verify at dispatch | `xhigh` | Tertiary |

Rationale: `author-b` is the primary candidate because it carries the
canonical `src/**` + `tests/**` scope under its `permissions.allow`; flex-a
is the secondary because it is currently idle per recent fleet state and
its effort-policy cell matches. Do not dispatch to analyst lanes — the
packet is an implementation packet per `shaping.md` §5.1 effort hint
"max" (on the `analyst` row the corresponding cell is `n/a`; dispatching
analyst would fail `effort_policy.py::effort_for()`).

**Effort hint override note:** `shaping.md` §5.1 specifies "Author-lane
effort hint: max" (verbatim). The recommended effort policy table
(`.claude/rules/effort_policy.md` `author × implementation`) is `xhigh`.
The shaping effort hint **overrides** the policy default; the packet
MUST carry `effort_hint=max` with `override_reason="shaping.md §5.1 explicit"`.
B.1 adaptive dispatch records the override; B.12 improvement-mechanism
evaluation ingests the override-rate signal.

### §7.5 Packet metadata (draft — orchestrator finalizes)

```
task_type: implementation
complexity_estimate: 4   # 1–5 scale; high — multi-file + adapter pattern + proving-run wiring
model_hint: opus
effort_hint: max         # per §7.4 override_reason
prompt_policy_version: author-v1.0
verification_surface: tests/unit/test_token_economy.py + audit_portability.py --json
rollback_path: git revert <merge_sha>; STEWARD_TOKEN_ECONOMY_NATIVE_USAGE=0 (redundant; flag-off is default)
```

### §7.6 Rollback path (Pattern 7 discharge)

Two-layer rollback:

1. **Flag-level (seconds):** `unset STEWARD_TOKEN_ECONOMY_NATIVE_USAGE`
   — all lanes resume bespoke path inside SLO (1 min). No code change.
   This is the first response to any §6 trip wire.
2. **Commit-level (minutes):** `git revert <merge_sha>` — restores
   `token_economy.py` to its 25-hard-block shape; adapter module deleted;
   feature-flag registry entry reverted. This is the response if the
   flag-level rollback reveals the problem is a bug in the adapter
   module itself (not just a native `/usage` availability issue).

**Rollback validation test** (executed by the author lane before PR open,
per `shaping.md` §10): forward → revert → observe pre-merge behavior
restored. Commands:

```bash
# forward
make check-gated  # passes on the migration
# revert
git revert HEAD --no-edit
make check-gated  # passes on the reverted state (bespoke path)
# paste both outputs in PR body
git reset --hard HEAD~1  # un-revert the revert so the PR carries only the forward commit
```

### §7.7 Known risks + scope traps

1. **F Packet 11 not yet merged on origin/main at dispatch time.** If so,
   the upstream gate #1 is open; **the packet does not dispatch** until
   F Packet 11 merges. Orchestrator verifies before dispatching.
2. **Slice B `ModelBucket` label drift.** If native `/usage` exposes
   session-class labels (parallel/subagent/cache-miss) that the author
   lane folds into `by_model` without operator review, the `by_model`
   contract §4.1 shifts and §6.4 trip wire #4 fires. **Mitigation:** the
   author lane must NOT rename any existing bucket label; native
   supplementary dimensions land as NEW fields per §4.3, never as
   replacements.
3. **Test fixture drift.** The golden-file test at
   `tests/unit/test_token_economy.py::test_slice_b_rollup_shape` must
   use a fixture checked into `tests/fixtures/token_economy/` (not a
   snapshot of live `~/.claude/projects/`). Author lane creates the
   fixture if missing.
4. **Adapter import cycle.** `ops.adapters.token_economy_adapter` must
   not import from `ops.token_economy`; the dependency direction is
   adapter → core (ADR 003 Platform-10 pattern). Author-lane sees this
   at first Tier-1 test run.
5. **PR #2725 rollup byte-compatibility.** `.json` output of `ops.py usage
   by-model --json` on the Cohort A path must be byte-for-byte identical
   pre- and post-migration. The §7.2 golden-file test locks this; Tier 2
   `make check-gated` runs it.

---

## §8. Verification Plan

Per Pattern 10 (§10.9 `governing_plan.md`) + analyst prompt policy. Every
deliverable row in this execution plan names a verification surface; the
roll-up surface is operator review against the 8 shaping-packet pass
criteria.

| Deliverable (§N) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §1 call-site inventory | shaping-data claim | `uv run python scripts/internal/audit_portability.py --json` returns 25 hard-block lines in `token_economy.py`; `grep -l "ops\.token_economy" src/ scripts/` returns the 3 listed consumer files | analyst-a (shape) | measured counts match §1 within ±1 (single-day drift tolerance) |
| §2 native invocation map | shaping decision table | grep-verify each cited native surface against `claude_code_changelog_implications.md` §2 + §3 rows; grep-verify each §2.1 adapter claim against `bespoke_surface_audit.md` §2.2 | analyst-a (shape) | 11/11 CLI-subcommand rows reference a cited source |
| §2.3 named gaps (blocker/degraded/acceptable) | disposition spec | operator review: "Do the gap categorizations match ADR 003's eventual disposition scope?" | operator | operator records decision (approve / revise / reject) |
| §3.1 feature flag registry entry | registry row | `.claude/rules/feature_flags.md` carries the row draft from §3.1 once the execution packet lands | author (G-C1 execution) | registry row present with Name / Default / Rollback SLO / Validation surface / Owner populated |
| §3.2 dual-write pattern | execution detail | code review of the execution PR confirms `token_economy_adapter.read_session_records(source=...)` present + both paths emit `proving_run_cohort_sample` event | author (G-C1 execution) | reviewer confirms; `grep -n "proving_run_cohort_sample" src/bid_euchre/ops/adapters/` returns ≥ 1 match |
| §3.3 which calls go through which cohort | routing spec | code review of §1.2–§1.3 consumer call-sites shows: learning.py + emitter still Cohort A only; dashboard + cmd_usage dual-write | author (G-C1 execution) | reviewer confirms |
| §3.4 parallel-run duration | observation window | operator runs fleet with flag flipped for 1 week on Cohort-B subset; records in MEMORY.md | operator | window runs ≥ 1 week OR ≥ 3 fleet-active days |
| §4 behavioral-equivalence contract | test-locked observable | `tests/unit/test_token_economy.py::test_slice_b_rollup_shape` golden-file test passes on both cohorts; integration test `test_token_economy_native_usage_fallback.py` passes | author (G-C1 execution) | both tests exit 0 |
| §5 token-cost measurement method | measurement spec | `grep -h '"event_type":"proving_run_cohort_sample"' data/events/events-*.jsonl \| wc -l` returns ≥ 1 sample/day × 7 days × 2 cohorts during the window; bootstrap on the samples produces a 95% CI per §5.3 | operator (consumes proving-run data) | ≥ 14 samples collected; bootstrap output recorded in the G-C1 PR body |
| §6 stop-loss trip wires | mechanism spec | each trip references a §4 or §5 metric; grep-verify | analyst-a (shape) | 4/4 trip-conditions cite a §4 or §5 metric |
| §7.1 file scope | author-lane contract | execution PR diff lists only the 9 listed files (+ adapter `__init__.py`); `git diff --stat` confirms | author (G-C1 execution) | diff shows only listed files |
| §7.2 + §7.3 validation commands | gate | `make check-gated` passes on execution PR; `audit_portability.py --json` hard-block count = 0 post-merge | author (G-C1 execution) | both commands exit 0; output pasted in PR body |
| §7.4 target lane recommendation | dispatch spec | orchestrator dispatches to author-b OR flex-a with `effort_hint=max` + `override_reason="shaping.md §5.1 explicit"` | orchestrator | dispatch_recommendation event shows matching fields |
| §7.5 packet metadata | packet-contract claim | once execution packet is queued, `ops.py task show <packet_id>` output contains the §7.5 fields | orchestrator | packet metadata matches §7.5 draft |
| §7.6 rollback path | Pattern 7 reversibility | rollback-test commands in §7.6 executed by author lane pre-PR; both outputs pasted in PR body | author (G-C1 execution) | forward-then-reverse passes; outputs pasted |
| This Verification Plan | lint | `scripts/internal/agent_readability_lint.py plans/steward_platform/7_primitive_G/migrations/01_token_economy_to_native_usage.md` (once the G.1 lint ownership-rule scripts exist) | analyst-a (shape) | lint exits 0 on ownership / verification-contract rules |

**Pass = operator reads; the 8 shaping-packet pass criteria are all
satisfied by the §N rows above; the execution packet specification in §7 is
approved for dispatch.**

**Fail modes:**

- Any §1 hard-block line count drift > ±1 between measurement time and
  dispatch time (portability-audit re-run mandatory at dispatch).
- Any §2 row whose gap category contradicts the Cohort A/B wiring in §3.3
  (e.g., marking an observable "acceptable gap" but routing its consumer
  to dual-write anyway — inconsistent).
- Any §3 routing decision that dispatches learning.py OR the F-forward
  emitter through Cohort B (§3.3 explicitly forbids; upstream-gate
  violation).
- Any §4 observable in §4.1 that native `/usage` provably cannot
  reproduce (e.g., if `claude-opus-4-7` vs `claude-sonnet-4-6` bucket
  labels are native-absent) — the migration must re-scope to exclude
  that observable, not force a §6.4 trip at dispatch.
- Any §6 trip wire that doesn't cite a §4 or §5 metric — mechanism gap.
- Any §7 scope item outside the 9-file list surfaced during author-lane
  implementation without escalation to orchestrator.
- Any §8 Verification Plan row whose surface doesn't resolve to a real
  path / command / operator prompt.

---

## §9. Reviewer / parallelism assessment

- **Reviewer agent required before execution begins?** **Yes — per
  `docs/02_agent/AGENTS.md` §12.4 and `.claude/CLAUDE.md` §Implementation
  Handoff Protocol.** After the author lane pulls the execution packet,
  the sequence is: (1) refresh this plan's context; (2) draft or refresh
  a concrete execution plan (may simply be "implement this plan as
  written" if no refresh needed); (3) spawn ≥1 reviewer agent to review
  that execution plan before major edits begin; (4) proceed with the
  task list, implementation, validation, and PR per Protocol.
  - The shaping document itself (this plan) is operator-reviewed against
    the packet's 8 pass criteria (Pattern 10 surface) — that is the
    shape-side review gate.
  - The execution-side reviewer gate is orthogonal and additive: it
    reviews the author's interpretation of the plan and catches
    execution-time seams (test coverage, file scope interpretation,
    feature-flag registry row wording) that the shape cannot pre-judge.
  - **Author lane must explicitly record the reviewer-spawn step in
    the PR body's `Validation Performed` section** (reviewer prompt,
    reviewer findings, disposition). Skipping the reviewer gate is a
    Pattern-10 surface-gap and BLOCKs the execution PR per
    `.claude/rules/prompt_policy/author.md` §Verification-surface-at-slice-close.
- **Parallelism with other G packets?** Safe. G-C1 touches
  `ops/token_economy.py` + one new adapter module + 12 lazy-import sites
  in `ops.py`. Other active G packets (G-A2 `--system-prompt-file`
  rollout, G-A3 Setup hook, G-B1 WorktreeCreate, G-B2 TeammateIdle, G-F2
  skills consolidation, G-D1 `/fewer-permission-prompts`) touch disjoint
  surfaces. Concurrent dispatch is safe provided F Packet 11 has merged.
- **Parallelism within G-C1?** No — single author lane end-to-end. The
  adapter module + `token_economy.py` refactor + test updates + feature
  flag registry + dual-write wiring form one bounded implementation
  unit.

---

## §10. References

- `plans/steward_platform/7_primitive_G/shaping.md` §5.1 (PR #2784) — packet G-C1 source.
- `plans/steward_platform/7_primitive_G/bespoke_surface_audit.md` §2.2 + §3 + §4 (PR #2815) — sidecar audit; strategic frame + proving-run pattern.
- `plans/_templates/execution_plan.md` — template this plan follows.
- `plans/steward_platform/claude_code_changelog_implications.md` §2 + §3 — Tier S native features.
- `.claude/rules/feature_flags.md` — flag convention (§3.1).
- `.claude/rules/prompt_policy/analyst.md` — analyst-lane Verification-Plan obligation.
- `.claude/rules/effort_policy.md` — archetype × task_type matrix referenced in §7.4.
- `plans/steward_platform/governing_plan.md` §5-G; §10.9 Pattern 7 (rollback), Pattern 8 (observability), Pattern 10 (verification surface); §14 surprise-finding discipline.
- `src/bid_euchre/ops/token_economy.py` — migration target.
- `src/bid_euchre/ops/learning.py`, `dashboard.py`, `adapters/` — consumers + adapter boundary.
- `scripts/internal/ops.py` lines 3552-3995 + 5397-5539 — CLI surface.
- `tests/unit/test_token_economy.py`, `test_ops_token_economy.py`, `test_portability_audit.py` — test surface.
- `scripts/internal/audit_portability.py` — portability-audit measurement surface.
- PR #2725 — lane × model × effort rollups consumer contract.
- PR #2784 — Primitive G shaping (packet G-C1 source).
- PR #2815 — sidecar audit (shaping predecessor).
- Primitive F Packet 11 (pending merge) — upstream gate for dispatch.
- ADR 003 (`plans/steward_platform/adrs/003-token-economy-native-vs-bespoke.md`) — disposition target.

## Outcome

(Filled after implementation.) Link to resulting PR(s) or note
abandonment. Expected: single G-C1 execution PR closing 25 hard-blocks +
landing the adapter module + feature flag registry entry; proving-run
evidence committed to the PR body per §5 + §8.
