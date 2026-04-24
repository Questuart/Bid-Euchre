# Shaping: Primitive G Phase 0 — Existing-Debt Closeout + Native-Substrate Migration

**Date:** 2026-04-24
**Lane:** analyst-c
**Packet:** `c7c6a25ee902` (Primitive G Phase 0 pre-shape; execution decomposes into Packets G-A1…G-F2 herein)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-G (lines 552–606)
**Sibling artifacts:**
- `plans/steward_platform/0_hardening/sub/rework_spec.md` — per-surface tactical catalog (42 ops modules + 34 hooks + 38 skills + `.claude/agents/` + worktree sweep)
- `plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` — first-deliverable sub-sub-plan, merged PR #2768 (20-lane → 8-archetype mapping + scaffolds)
- `plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` — B.9a file-authoring shape (by analyst-d); §8 execution packet spec; §7.3 empirical-verification protocol
- `plans/steward_platform/0_hardening/baseline.md` — PR #2766 Phase 0 baseline capture (consumed by Primitive F-forward + G12 capture script)
- `plans/steward_platform/adrs/G10-system-prompts-vs-agents.md` — ADR G10 orthogonal-relationship ruling, merged PR #2765
- `plans/steward_platform/adrs/006-auto-mode.md` — auto-mode codification (§"Model tier interaction" ties G's permission-mode surfaces to B.1)
- `plans/steward_platform/1_primitive_A/shaping.md` §4 event schema — consumed by G's event-emitting surfaces
- `plans/steward_platform/6_primitive_F/shaping.md` §2.2 F-debt boundary — G owns the 22 token-economy hard-blocks
- `plans/steward_platform/verification_contract/shaping.md` §2 Pattern 10 surface-class defaults + §4 per-lane prompt-policy
- `plans/steward_platform/claude_code_changelog_implications.md` §2 Tier S — WorktreeCreate/Remove, Setup hook, TeammateIdle, PermissionDenied, `/fewer-permission-prompts`, remote sessions, shared project memory

**Status:** DESIGN-SPEC — no code edits, no hook subscriptions, no config changes authored in this artifact. Produces an execution-ready packet decomposition for Primitive G Phase 0.
**Purpose:** Pre-shape Primitive G Phase 0 so the orchestrator can dispatch the 11–13 author-lane execution packets against the enumerated tracks with zero additional analyst shaping work per packet. Matches the pre-shaping pattern of Primitive F Packet 11 (`plans/steward_platform/6_primitive_F/shaping.md` §8).

---

## §1. Scope of this document

This is a **shaping document**. Its output is the execution-ready packet decomposition for all 12 Primitive G Phase 0 work items enumerated in `governing_plan.md` §5-G "Work" (lines 577–590).

**What this document specifies:**

1. Track-level decomposition — 6 tracks (A–F) covering 12 work items + the 2 downstream B.9a/B.9b archetype deliverables Primitive G consumes (§2).
2. Packet-level specs — 11–13 execution packets with scope, surface, dependencies, effort (§3–§8).
3. Deliverable → Pattern 10 verification-surface table (§9).
4. Rollback-validation coverage (Pattern 7 + Goal #13 slice) (§10).
5. Phase 2 Decision Inputs per §15.2 schema (§11).
6. Verification Plan per Pattern 10 mandate (§12).

**What this document does NOT do:**

- Re-shape G13 (already shipped, PR #2768) or B.9a pilot (already shipped, PR #2779). Track A references these as upstream-complete.
- Re-decide G10 (orthogonal; ADR PR #2765). Track A packets inherit the ruling.
- Duplicate the per-surface tactical dispositions in `rework_spec.md`. Packets cite the relevant rows; they do not re-enumerate.
- Execute any hard-block removal, hook migration, or skill retirement. Every edit is an author-lane packet concern.
- Cover Primitive H.0 Phase 0 canary (own primitive; governing plan §5-H.0) or H.1 Phase 1 reliability suite. G supplies rollback-validation evidence for Phase 0 changes; H.0 exercises it.
- Re-scope the F-debt boundary (the 22 hard-blocks in `ops/token_economy.py`). F-shape §2.2 already names that boundary; Track C packet executes against the named boundary.
- Own the token-economy emitter or baseline-delta consumer (Primitive F Packet 11). Those land on Primitive A's event schema; G only touches `token_economy.py` for hard-block removal, not for emission.

### §1.1 Motivation (one paragraph)

Primitive G is the **non-capability primitive that gates all others**: every other primitive's Phase 0 Readiness depends on G-owned surfaces being in a state where native-substrate integration (Primitive A events, Primitive E triage, Primitive F telemetry, B.9a archetype prompts) can actually fire. The major draft 7/8 scope reshape pivoted G from "refactor bespoke Bid-Euchre literals" to "migrate to Claude Code native substrate" — a strictly larger and more varied work surface because native features replace bespoke surfaces (saving LOC) while also requiring adapter shims, rollback paths, and coordination across primitives. Pre-shaping G means the 12 Phase 0 Work bullets are pre-decomposed into dispatch-ready packets with named surfaces, ordering, and effort envelopes; author lanes execute against the packet list as Primitive A Packet 3 (event-schema dispatcher) lands and unblocks the emission-dependent packets (G1 native-worktree, G7 heartbeat retirement, G11 skill-consolidation telemetry).

### §1.2 Relationship to §5-G Work bullets

§5-G of the governing plan (lines 577–590) is the binding reference. This shaping doc operationalizes each Work bullet into one or more execution packets. Strict-existence: every Work bullet has at least one packet row in §3–§8 below. Lenient-form: some Work bullets decompose into multiple packets (e.g., bullet 1 "Native worktree migration" is one packet, bullet 3 "Setup hook adoption" is split between G-A2 files adoption and G-A3 Setup hook itself).

| §5-G Work bullet (line) | Where it lands in this doc |
|---|---|
| Native worktree migration (578) | §4 Track B Packet G-B1 |
| Periodic `/fewer-permission-prompts` cron (579) | §7 Track D Packet G-D1 |
| Setup hook adoption + `--system-prompt-file` launch (580) | §3 Track A Packets G-A2 + G-A3 |
| Token-economy hard-blocks (581) | §5 Track C Packet G-C1 |
| Retire `agent_ops/5_*` subtrees (582) | §8 Track E Packet G-E1 |
| Retire heartbeat classifier → TeammateIdle (583) | §4 Track B Packet G-B2 |
| Messaging-bus proving overlap with Primitive E (584) | §8 Track E Packet G-E2 (reference-only — E owns) |
| Platform-11 adaptive-dispatch closeout (585) | §8 Track E Packet G-E3 |
| Rollback validation for Phase 0 changes (586) | §10 + cross-cut through every §3–§8 packet |
| Non-protected ephemeral worktree sweep (587) | §7 Track D Packet G-D2 |
| Skills consolidation pass (588) | §6 Track F Packet G-F2 |
| `plans/sessions/` archive sweep via `sweep_session_plans.py` (589) | §7 Track D Packet G-D3 |
| Baseline capture via `capture_steward_baseline.py` (590) | §7 Track D Packet G-D4 |
| B.9a fan-out (§5-B B.9a, first-deliverable-gated via G13) | §3 Track A Packet G-A1 |
| B.9b launch adoption (§5-B B.9b, consumes G-A1 + G-A3) | §3 Track A Packet G-A2 |

The native-substrate three-tier preference (§10.9 Pattern 2: native → official plugin → third-party plugin → bespoke) is honored at every packet: Track B adopts WorktreeCreate/Remove + TeammateIdle (tier 1); Track A adopts `--system-prompt-file` + Setup hook (tier 1); Track D adopts `/fewer-permission-prompts` (existing skill, now scheduled); Track C retains bespoke `token_economy.py` only because `/usage` + `/cost` do not cover the 22 hard-block surfaces (ADR 003 documents).

### §1.3 Track topology

Six tracks group the 13+ packets by seam + coordination profile:

| Track | Seam | Coordination profile |
|---|---|---|
| **A** Archetype system-prompts | `.claude/system_prompts/` + `.claude/tmux/steward-session.sh` | Serial (G13 → B.9a pilot → #2767 resolution → A1 fan-out → A2 launch adoption; A3 Setup hook may parallelize A2 now that #2767/#2778 decouples the serialization) |
| **B** Native-substrate code migrations | `src/bid_euchre/ops/worktrees.py`, `dashboard.py`, `lane_heartbeat.py`, `idle_detector.py` | Medium (B1 is single largest LOC surgery; B2 is smaller cascade; both depend on Primitive A v1.0 event schema for conditional-hook wiring) |
| **C** Token-economy F-debt | `src/bid_euchre/ops/token_economy.py` hard-block paths | Gated by Primitive F Packet 11 landing first (F-forward consumes the module via `token_economy_emitter.py`); C1 executes against a stable upstream surface |
| **D** Operational hygiene scripts + scheduling | `scripts/internal/sweep_session_plans.py`, `scripts/internal/capture_steward_baseline.py`, `/fewer-permission-prompts` cron, ephemeral-worktree sweep | Parallel-safe; no shared files |
| **E** Plan + scope cleanup | `plans/agent_ops/5_*/`, `plans/agent_ops/post_pr5_follow_on_roadmap.md`, messaging-bus reference to E, Platform-11 disposition | Docs-only; parallel-safe |
| **F** Cross-cutting | Rollback-validation record-keeping; skills consolidation pass | F1 runs throughout (each packet records rollback); F2 is one coordinated pass |

---

## §2. Upstream artifact crosswalk (what's already landed)

This sub-section is explicit about what is **already in the repo on main** so downstream packets can *cite rather than duplicate*. Every row below is grep-verifiable.

| Artifact | Home | Landed via | Role for Primitive G |
|---|---|---|---|
| ADR G10 (orthogonal) | `plans/steward_platform/adrs/G10-system-prompts-vs-agents.md` | PR #2765 (merged 2026-04-23) | Settles the `.claude/system_prompts/` vs `.claude/agents/` relationship; Track A packets inherit the ruling without relitigation |
| G13 mapping sub-plan | `plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` (478 lines) | PR #2768 (merged 2026-04-23) | Supplies §2.1 20-lane → 8-archetype mapping + §2.2 8 scaffolds; consumed by G-A1 fan-out |
| B.9a authoring shape | `plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` (~1047 lines) | Authored pre-pilot; referenced by pilot PR #2779 | Supplies file-authoring contract (§3 voice + structure invariants, §4.1 5-slot template); G-A1 fan-out executes against it |
| B.9a pilot — `analyst.md` | `.claude/system_prompts/analyst.md` + `knowledge/harness_assumptions.md` | PR #2779 (merged 2026-04-24) | **Empirically verifies** `--system-prompt-file` replacement fires in both print and interactive modes on Claude Code 2.1.114 (ClaudeLog print-only claim falsified); G-A1 fan-out proceeds to 7 remaining archetypes without re-verification |
| Rework spec | `plans/steward_platform/0_hardening/sub/rework_spec.md` (233 lines) | On main | Per-surface tactical catalog; every G packet cites one or more `rework_spec.md` rows rather than duplicating |
| Baseline snapshot | `plans/steward_platform/0_hardening/baseline.md` | PR #2766 | Schema skeleton for G-D4 `capture_steward_baseline.py`; also consumed by Primitive F-forward delta consumer |
| Heartbeat classifier (shipped, to retire) | `src/bid_euchre/ops/dashboard.py` heartbeat | PR #2743 (merged earlier 2026-04) | G-B2 retires this surface in favor of native TeammateIdle — the deprecation-on-arrival is deliberate (`rework_spec.md` §3 row 4) |
| Prompt-policy registry | `.claude/rules/prompt_policy/{orchestrator,author,analyst,common}.md` | PR #2762 (initial) + PR #2780 B-exec.α (Version/Trigger/Expected effect/Rollback sections + PP0-PP4 lint) | Versioned per `<archetype>-v<MAJOR>.<MINOR>` format; cited by B.9a file bodies; Track A packets compose against versioned registry |
| B-exec.α — tool-risk + effort + recipes | `.claude/rules/tool_risk_registry.md`, `.claude/rules/effort_policy.md`, `knowledge/orchestration_recipes/` | PR #2780 (merged 2026-04-23) | Ships B.3/B.6/B.10/B.11 — G packets may cite tool-risk rows (G-C1 destructive-family classification), effort policy (G-D1 `/fewer-permission-prompts` cron cadence), and the `shape_then_execute_pattern11.md` recipe (every Pattern 11 packet composes against it) |
| Model-tier-aware permission-mode | `.claude/lane_models.json` + `scripts/internal/lane_models.py` + `.claude/tmux/steward-session.sh` + `scripts/internal/review_lane_runner.py` | PR #2778 (merged 2026-04-23, Fixes #2767) | **Unblocks G-A2** — launch scripts now emit `--permission-mode auto` for Opus lanes and `--dangerously-skip-permissions` for Sonnet/Haiku; G-A2 layers `--system-prompt-file` on top of this conditioned structure without conflict |
| Lane × model × effort rollups | `ops/dashboard.py` + `ops/token_economy.py` | PR #2725 | Primitive F-forward rollup source; G-C1 (hard-blocks) must not break this shipped rollup |
| Lane-id dedup library | `scripts/internal/lane_id.sh` | PR #2741 | Consumed by hooks touching lane identity; G hook consolidation (§6 rework_spec §5) must not break this |
| Pure-shell heartbeat hook | `.claude/hooks/lane-heartbeat-hook.sh` | PR #2739 | G-B2 retires this alongside the dashboard.py classifier |
| Auto-mode classifier codification | `.claude/rules/80_permission_model.md` | Existing | G-D1 `/fewer-permission-prompts` cron builds proposals that augment `permissions.allow` (fast-path) without weakening classifier gate |
| Model-tier-aware permission-mode issue | Issue #2767 (CLOSED by PR #2778) | Resolved 2026-04-23 | **G-A2 now unblocked** — launch scripts already emit per-tier permission flags; G-A2 layers `--system-prompt-file` on conditioned structure without conflict (see B-exec.α row above) |

**Non-duplication rule.** A packet that restates material from any of these artifacts rather than citing it is re-shape spill; reviewers should bounce such packets back to shaping.

---

## §3. Track A — Archetype system-prompts (G13 + B.9a + B.9b chain)

Track A completes the archetype-prompts chain that G13 + B.9a pilot #2779 unblock. Three packets; serial ordering.

### §3.1 Packet G-A1 — B.9a fan-out (7 remaining archetype files)

**Scope (declared files created; no modifications):**
- `.claude/system_prompts/orchestrator.md` — concrete lane: `orchestrator` (1); model opus; effort xhigh.
- `.claude/system_prompts/ops.md` — concrete lane: `ops` (1); model sonnet; effort lower.
- `.claude/system_prompts/review.md` — concrete lane: `review` (1); model opus; effort xhigh.
- `.claude/system_prompts/author.md` — concrete lanes: `author-a/b/c/d` (4); model opus; effort xhigh.
- `.claude/system_prompts/brws-author.md` — concrete lanes: `brws-author-a/b/c/d` (4); model opus; effort xhigh.
- `.claude/system_prompts/flex.md` — concrete lanes: `flex-a/b/c/d` (4); model opus; effort xhigh.
- `.claude/system_prompts/scratch.md` — concrete lane: `author-scratch` (1); model opus OR sonnet (operator choice at authoring); effort lower.

**Authoring contract:** `plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` §3 voice + structure invariants; §4.1 5-slot template (Role, Operating Rules, Surfacing Uncertainty, Constraints, Named Skills, Tool Posture Reminder); §3.6 length target 40–90 body lines; §3.5 no-frontmatter rule. G13 §2.2 scaffolds supply the per-archetype skeleton.

**Upstream gates (all satisfied):**
- G13 mapping merged (PR #2768) — ✓
- ADR G10 filed (PR #2765) — ✓
- B.9a pilot merged (PR #2779) — ✓
- `--system-prompt-file` empirically verified — ✓ (per PR #2779 Probe 1–4)
- 5-business-day observation window per B.9a shape §8.3 — **operator-gated** (dispatch when window closes; start date = 2026-04-24 PR #2779 merge; window close ≥ 2026-04-29 business-day-inclusive)

**Downstream gate unblocked:** G-A2 launch adoption (B.9b).

**Verification surface (Pattern 10 default for `.claude/system_prompts/**` per b9a shape §8.6):** Launch-smoke per file: `claude -p --permission-mode auto --system-prompt-file .claude/system_prompts/<archetype>.md "describe your role in one sentence"` → response paraphrases archetype one-liner (§8.2 3-outcome Protocol, outcome A pre-verified).

**Rollback path:** `git revert <merge-commit>` removes 7 files; analyst-a lanes retain `analyst.md` (pilot); other lanes revert to default prompt at next restart. Blast radius: 15 of 19 lanes (non-analyst-*) until restarted.

**Effort estimate:** 7 files × ~80 lines each ≈ 560 lines net additions + 7 launch-smoke outputs in PR body. Author-lane effort hint: medium. Turnaround: 1 author-lane session.

### §3.2 Packet G-A2 — B.9b fleet launch adoption (`--system-prompt-file` on every launch)

**Scope (files modified):**
- `.claude/tmux/steward-session.sh` — add `--system-prompt-file .claude/system_prompts/<archetype>.md` to each of 19 `$CLAUDE_BIN` launch lines (archetype resolved per G13 §2.1 row).
- `scripts/internal/review_lane_runner.py::invoke_review` — add `--system-prompt-file .claude/system_prompts/review.md` to the `claude` subprocess argv.
- `tests/unit/test_steward_session.py::TestSystemPromptFile` — new test class; asserts every `$CLAUDE_BIN` launch line contains `--system-prompt-file .claude/system_prompts/<archetype>.md` where `<archetype>` matches G13 §2.1; 0 bare-default launches.
- `tests/unit/test_review_lane_runner.py::TestInvokeReviewSystemPromptFile` — new; mocks `subprocess.run`; asserts argv contains `--system-prompt-file`.

**Upstream gates:**
- G-A1 merged (7 archetype files committed; 8 total with pilot).
- **Issue #2767 / PR #2778 already merged 2026-04-23.** Launch scripts now emit `--permission-mode auto` (Opus) or `--dangerously-skip-permissions` (Sonnet/Haiku) per `.claude/lane_models.json`. G-A2 layers `--system-prompt-file .claude/system_prompts/<archetype>.md` on top of this conditioned structure — no coordination blocker. Archetype resolution for each launch line: read `.claude/lane_models.json` for the lane-id, then map lane-id → archetype per G13 §2.1 (e.g., `orchestrator` → `orchestrator.md`, `author-a` → `author.md`, `analyst-b` → `analyst.md`).

**Verification surface (Pattern 10: new `.claude/tmux/**` + `scripts/internal/**` = unit test path):**
- `uv run python -m pytest tests/unit/test_steward_session.py::TestSystemPromptFile tests/unit/test_review_lane_runner.py::TestInvokeReviewSystemPromptFile` — passes; paste output in PR body.
- Phase 1 Validation: `prompt-policy-cited-in-trace` rate rises post-merge (observable in proving-run telemetry — Primitive F emits via A's dispatcher).

**Rollback path:** Revert commit; `steward-session.sh` drops all `--system-prompt-file` args; review runner drops its arg; fleet reverts to pre-B.9b at next restart. Per-lane disable: comment out the arg on a single launch line (rollback test per b9a shape §8.4).

**Effort estimate:** 19 launch-line edits + 1 review-runner edit + 2 test files ≈ 150 LOC. Low-medium.

### §3.3 Packet G-A3 — Setup hook adoption (replace `steward-session.sh` imperative with declarative + Setup hook)

**Scope (conditional on Claude Code Setup hook availability):**
- `.claude/hooks/setup-steward-lanes.sh` (new) — declarative lane-config file + Setup-hook-driven launcher.
- `.claude/config/lanes.yaml` (new, or similar) — declarative lane config (archetype, model tier, permission-mode, worktree path).
- `.claude/tmux/steward-session.sh` — collapsed to entrypoint or fully replaced by Setup hook; pure-shell glue preserved only for orchestration lifecycle (worktree creation / tmux session attach).
- `tests/unit/test_setup_hook_adoption.py` — new; asserts all 19 lanes present in declarative config; asserts hook invocation produces identical launch argv to pre-migration (golden-file comparison).

**Upstream gates:**
- G-A2 merged (B.9b launches work imperatively; Setup hook is the declarative replacement).
- Claude Code Setup hook substrate stable on the fleet version. **If Setup hook is unavailable at dispatch time, G-A3 is deferred to Phase 1 or a sub-version bump**; G-A2 remains sufficient for the B.9b Phase 0 Readiness criterion (`--system-prompt-file` on every launch).

**Verification surface (Pattern 10: new `.claude/hooks/**` = rollback test path):**
- Disable-hook smoke: rename the hook file `setup-steward-lanes.sh.disabled`; run `steward-session.sh` fallback path; confirm fleet launches (with or without system-prompt-file per fallback shape); restore the hook; confirm normal launch.
- Golden-file test: `tests/unit/test_setup_hook_adoption.py` — argv comparison.

**Rollback path:** Revert commit; `steward-session.sh` resumes full imperative role; hook file removed. Blast radius: fleet-wide but only on next restart.

**Effort estimate:** Medium-high (declarative schema design + 19-lane migration + golden-file test). Turnaround: 1–2 author-lane sessions. **If Setup hook surface is unstable on the fleet version, accept Phase 1 deferral** (operator gate).

---

## §4. Track B — Native-substrate code migrations

### §4.1 Packet G-B1 — `ops/worktrees.py` native migration (~80% LOC reduction)

**Scope (files modified heavily; files removed selectively):**
- `src/bid_euchre/ops/worktrees.py` — trim from current ~1000+ LOC to ~200 LOC shim. Remove: `PROTECTED_WORKTREES` literal, `WORKTREE_LANE_MAP` literal, most worktree-creation / removal / sweep functions. Keep: repo-specific adapter boundary (e.g., calls to `.claude/tmux/steward-session.sh` on worktree creation), error-translation between native hook errors and steward's error taxonomy.
- `.claude/hooks/worktree-create-register.sh` (new, if native WorktreeCreate hook surface available) — declarative registration.
- `.claude/hooks/worktree-remove-protect.sh` (new) — protection-list check against `.claude/rules/75_worktree_protection.md`; blocks native WorktreeRemove on protected rows.
- `.claude/config/worktrees.yaml` (new, or similar) — declarative protected list; replaces `PROTECTED_WORKTREES` Python constant.
- `tests/unit/test_worktrees.py` — extend; golden-file comparison of pre/post-migration lane-list output; assert protection invariants preserved (no protected worktree removable by native WorktreeRemove).

**Upstream gates:**
- Primitive A Packet 3 merged (events v1.0 dispatcher + registry) — G-B1 emits `worktree_created`/`worktree_removed` events via dispatcher.
- `rework_spec.md` §3 row 1 disposition (`worktrees.py` → "Trim hard ~80%") — ✓ (already disposition-catalogued).

**Verification surface (Pattern 10: new Python module / hook / config all require tests; pick the most binding):**
- Unit test path: `tests/unit/test_worktrees.py` extended for protection invariants + golden-file lane list.
- Rollback test (Pattern 7): `git revert <commit>` restores imperative `worktrees.py` full content; native hooks deactivate; lane spawn still works via legacy path. Record in PR body.
- LOC reduction measurement: `git diff --stat src/bid_euchre/ops/worktrees.py` shows ≥ 80% deletion. Paste output.

**Rollback path:** Single-commit revert restores pre-migration `worktrees.py`; hooks deactivate; declarative config orphaned (no runtime reference). Medium blast radius — affects all worktree operations until restart.

**Effort estimate:** High. Largest single LOC surgery in Primitive G. Author-lane effort hint: max. Turnaround: 2 author-lane sessions. **Gate hardening: operator-review of the migrated shim before merge**; reviewer confirms the adapter boundary is clean (no duplicated protection list between Python and YAML; hook error-translation tested end-to-end).

### §4.2 Packet G-B2 — Heartbeat classifier retirement → TeammateIdle

**Scope (files modified / removed):**
- `src/bid_euchre/ops/dashboard.py` — remove heartbeat classifier block (per PR #2743 shipped); replace with TeammateIdle subscription handler.
- `src/bid_euchre/ops/lane_heartbeat.py` — **remove** (`rework_spec.md` §3 row indicates "Retire"; overlaps with dashboard heartbeat).
- `src/bid_euchre/ops/idle_detector.py` — **remove** (per rework_spec §3 row).
- `.claude/hooks/lane-heartbeat-hook.sh` — **remove** (per rework_spec §5 row; pure-shell surface retired).
- `.claude/hooks/teammate-idle-subscribe.sh` (new) — native TeammateIdle subscription; emits `lane_idle` + `lane_resumed` events via Primitive A dispatcher.
- `tests/unit/test_dashboard.py` — extend; assert new TeammateIdle handler populates dashboard idle column; assert no references remain to removed modules.
- `src/bid_euchre/ops/dashboard.py` **CHANGELOG-like note** in module docstring citing this migration.

**Upstream gates:**
- Primitive A Packet 3 merged — event schema `lane_idle` / `lane_resumed` available.
- TeammateIdle native substrate stable on fleet version. **If TeammateIdle is unavailable, defer G-B2 to Phase 1**; heartbeat classifier stays shipped (already in #2743) as interim.
- G-A2 merged (non-blocking, but reduces coordination; G-B2 strictly touches `dashboard.py` without conflicting).

**Verification surface (Pattern 10: new `.claude/hooks/**` = rollback test; existing Python module change = unit test extension):**
- Unit test: `tests/unit/test_dashboard.py::TestTeammateIdleIntegration` — passes; idle column populates from event stream.
- Rollback test: disable `teammate-idle-subscribe.sh`; dashboard idle column emits "unknown"; confirm no crash; restore.
- Observation: `data/events/events-*.jsonl | grep lane_idle` — records appear within 10 min of a lane going idle on the proving run.

**Rollback path:** Revert commit; restore removed modules (via git); heartbeat classifier returns in dashboard; TeammateIdle subscription dormant. Low blast radius.

**Effort estimate:** Medium. Author-lane effort hint: xhigh. Turnaround: 1 author-lane session.

---

## §5. Track C — Token-economy F-debt (22 hard-blocks)

### §5.1 Packet G-C1 — Token-economy hard-block elimination (22 occurrences in `ops/token_economy.py`)

**Scope (one file modified; no new files):**
- `src/bid_euchre/ops/token_economy.py` — replace 22 Bid-Euchre-literal hard-blocks with:
  - Adapter-boundary reads via `src/bid_euchre/ops/core/` adapters (Platform-10 pattern; `rework_spec.md` §3 row `core/provider.py` + `adapters/`).
  - Config-sourced constants via `.claude/config/` or equivalent cell-local config.
  - Per-deliverable ADR 003 decision: which surfaces stay bespoke vs migrate to `/usage` + `/cost` overlap.
- `src/bid_euchre/ops/adapters/token_economy_adapter.py` (new, if needed to encapsulate the cell-specific knowledge that was literal in `token_economy.py`).
- `tests/unit/test_token_economy.py` — extend; golden-file pre/post rollup values for a fixture cell; assert PR #2725 rollup shape preserved verbatim; assert no bit-rot in lane × model × effort attribution.
- `scripts/internal/audit_portability.py` — run post-merge; assert `ops/token_economy.py` hard-block count = 0.

**Upstream gates:**
- **Primitive F Packet 11 merged first** — F-forward's `token_economy_emitter.py` consumes `token_economy.py` via the rollup surface. G-C1 refactors `token_economy.py` under a stable F-consuming contract.
- **ADR 003 at Phase 0 close** — documents which surfaces `/usage` + `/cost` cover vs. which remain bespoke. G-C1 lands before ADR 003 promotion; ADR 003 records the resulting boundary.

**Verification surface (Pattern 10: Python module change = unit test; portability = `audit_portability.py` reframing row in rework_spec.md §4):**
- Unit test: `tests/unit/test_token_economy.py` — passes with golden-file preservation (rollup values unchanged pre/post migration).
- Portability measurement: `uv run python scripts/internal/audit_portability.py --module ops.token_economy` — 0 hard-blocks. Paste output.
- Integration test: `tests/integration/test_slice_f_rollups.py` — passes (F-forward consumer unchanged).

**Rollback path:** Revert commit; adapter shim module removed; `token_economy.py` restored to 22-hard-block shape. Medium blast radius — any F-forward telemetry consuming the post-migration contract reverts to the pre-migration contract; F Packet 11 must be evaluated for re-run.

**Effort estimate:** High. Author-lane effort hint: max. Turnaround: 1–2 author-lane sessions. **Note:** ADR 003 promotion (Phase 0 close) bundles the disposition — which surfaces F-forward kept native (`/usage` + `/cost`) vs. which stayed bespoke (G-C1's adapter surface).

---

## §6. Track F — Cross-cutting (skills consolidation)

### §6.1 Packet G-F2 — Skills consolidation pass (30+ → reduced)

**Scope (files retired / consolidated per `rework_spec.md` §6):**
- **Monitoring family (6 → 2):** retain `/fleet-check` (aggregator) + `/lane-status` (one-off); retire `/monitor`, `/check-in`, `/inbox-poll`, `/capture-pane` as standalone SKILL directories — their content folds into `/fleet-check` and `/lane-status` SKILL.md files (source-code move, not delete; cross-ref update in any callers).
- **Playtest family (4 → 2 + computer-use evaluation):** consolidate `/playtesting`, `/playtest-hybrid`, `/playtest-strategic`, `/playtest-playwright` per rework_spec; evaluate Computer Use in Desktop / CLI as substrate replacement (deferral acceptable).
- **Loop / scheduling family (3 → 1 evaluated):** `/loop`, `/schedule`, `/away-mode` — evaluate against Monitor + remote sessions; defer execution if native substrate not stable.
- `tests/integration/test_skills_surface.py` — extend; assert retired skill directories no longer present; assert kept skills still invoke correctly.
- `.claude/skills/` directory cleanup — retire 8 skill dirs; add 0 (new skills from drafts 6/7 are separate packets under Primitives B/C/D).

**Upstream gates:**
- Primitive A Packet 3 merged (Monitor tool substrate used by `/fleet-check`).
- TeammateIdle merged (per G-B2) — consumed by `/fleet-check` aggregator.
- **Operator approval of retired skill list** before dispatch (skills are high-salience operational surface; losing one without review is an observability regression).

**Verification surface (Pattern 10: new `.claude/skills/**` = named runnable acceptance command in SKILL.md; retirement = smoke-test that consolidated skill covers retired skill's acceptance command):**
- Per-retired-skill smoke: each retired skill's original SKILL.md acceptance command is re-run from the consolidated target skill; paste outputs.
- Integration test: `tests/integration/test_skills_surface.py` passes.

**Rollback path:** Revert commit; retired skill dirs restored; consolidated skill changes rolled back. Low-medium blast radius — operator workflow disruption proportional to retired skill count.

**Effort estimate:** Medium. Author-lane effort hint: xhigh. Turnaround: 1 author-lane session. **Gate: operator sign-off on retired skill list before dispatch.**

---

## §7. Track D — Operational hygiene scripts + scheduling

### §7.1 Packet G-D1 — Periodic `/fewer-permission-prompts` cron (1×/week)

**Scope (files modified / scheduled):**
- `.claude/cron/` or equivalent scheduler surface — schedule `/fewer-permission-prompts` with cadence 1×/week.
- `scripts/internal/ops.py cron add` CLI invocation or equivalent (mechanism depends on fleet cron substrate — currently `ScheduleWakeup` tool or a dedicated cron skill).
- No SKILL changes — `/fewer-permission-prompts` SKILL.md remains the authoring contract; scheduling adds invocation cadence only.
- `docs/02_agent/PERMISSION_MODEL_OPERATOR_RUNBOOK.md` (new or extended) — documents the weekly cadence, the proposal review surface (operator reads proposed allowlist additions before merging), and the rollback mechanism.

**Upstream gates:**
- `/fewer-permission-prompts` SKILL already ships (existing); no authoring needed.
- Fleet cron substrate stable.

**Verification surface (Pattern 10: config change = rollback test; skill scheduling = operator-review prompt):**
- Rollback test: disable the cron entry; run `/fewer-permission-prompts` manually; confirm identical output; restore.
- Operator-review prompt: "After N weekly runs, proposed allowlist additions have been reviewed and merged K times; K/N ratio ≥ 0.5 indicates the cron produces actionable output." Record in ops lane's observation log.

**Rollback path:** Remove cron entry; skill remains manually invokable. Minimal blast radius.

**Effort estimate:** Low. Author-lane effort hint: lower. Turnaround: half session.

### §7.2 Packet G-D2 — Non-protected ephemeral worktree sweep

**Scope (one-shot operational sweep; no permanent code):**
- `scripts/internal/sweep_ephemeral_worktrees.py` (new, ~60 LOC) — enumerates worktrees; classifies against `.claude/rules/75_worktree_protection.md` (protected list) + PR-state check (PR merged → worktree removable); emits a proposal.
- Operator-gated execution: the script emits a dry-run proposal first; operator reviews; operator approves; script executes `git worktree remove` for approved rows only.
- `tests/unit/test_sweep_ephemeral_worktrees.py` — new; asserts no protected worktree is ever proposed for removal; asserts PR-state classification handles all 6 classification outcomes (merged / closed-no-merge / open / not-found / dirty / clean).
- `rework_spec.md` §8 worktree sweep rows are the initial target list; script's output should include or exceed those rows.

**Upstream gates:**
- None. Parallel-safe with all other Track D packets.

**Verification surface (Pattern 10: new Python script = unit test + named runnable command):**
- Unit test: `tests/unit/test_sweep_ephemeral_worktrees.py` passes.
- Named runnable: `uv run python scripts/internal/sweep_ephemeral_worktrees.py --dry-run` — emits proposal table; paste in PR body.

**Rollback path:** Revert commit; script removed. Sweep actions already executed (git worktree remove) are non-trivial to un-apply — **script must be dry-run-first-always**; no sweep executes without operator approval; any removed worktree's recovery path is "recreate the worktree from the branch via git worktree add" (per branch still existing in origin).

**Effort estimate:** Medium. Author-lane effort hint: xhigh. Turnaround: 1 author-lane session.

### §7.3 Packet G-D3 — `sweep_session_plans.py` + archive sweep (~264 files)

**Scope (script + execution):**
- `scripts/internal/sweep_session_plans.py` (new, ~30 LOC per rework_spec §3 G12 note) — enumerates `plans/sessions/*.md`; classifies each by Outcome section (`COMPLETED` / `ABANDONED` / `SUPERSEDED` / `open` / `missing-outcome`); emits archival proposal (`plans/sessions/_archive/<year>/<month>/`).
- `tests/unit/test_sweep_session_plans.py` — new; asserts classification logic handles all 5 outcomes; asserts `open` + `missing-outcome` never archived.
- Operator-gated sweep: dry-run proposal → operator review → batch `git mv` execute.
- `plans/sessions/_archive/2026/` (new directory structure) — archived session plans land here.

**Upstream gates:**
- None. Parallel-safe.

**Verification surface (Pattern 10: new Python script = unit test; sweep action = operator-review prompt):**
- Unit test: `tests/unit/test_sweep_session_plans.py` passes.
- Operator-review prompt: dry-run output shows ~N archival rows; operator reviews for false positives (active session plans wrongly classified); approves; executes.
- Post-sweep measurement: `ls plans/sessions/*.md | wc -l` dropped from ~264 to active-subset (target: ≤ 50). Paste output.

**Rollback path:** Revert commit; script removed. Sweep actions (git mv to archive) are trivially reversible via `git mv` back.

**Effort estimate:** Low-medium. Author-lane effort hint: xhigh. Turnaround: half session (script); operator review separate.

### §7.4 Packet G-D4 — `capture_steward_baseline.py` (I7 tool-backed baseline capture)

**Scope (script; home Primitive G per Pattern 9 ownership audit, consumed by Primitive F):**
- `scripts/internal/capture_steward_baseline.py` (new, ~40 LOC per governing plan §4.3 and I7 note) — wraps named capture commands (agent readability, token economy, skill inventory, hook inventory, worktree inventory) into a single invocation that writes a timestamped snapshot into `plans/steward_platform/0_hardening/baseline.md` sections.
- `tests/unit/test_capture_steward_baseline.py` — new; asserts each section populates from its named command; asserts snapshot is deterministic given fixed inputs.
- `plans/steward_platform/0_hardening/baseline.md` — already exists (PR #2766 skeleton); G-D4 populates via script invocation.

**Upstream gates:**
- None. Parallel-safe.

**Verification surface (Pattern 10: new Python script = unit test + named runnable):**
- Unit test: `tests/unit/test_capture_steward_baseline.py` passes.
- Named runnable: `uv run python scripts/internal/capture_steward_baseline.py` — writes snapshot; paste timestamp + section summary in PR body.

**Rollback path:** Revert commit; script removed; `baseline.md` retains last-captured snapshot (read-only artifact).

**Effort estimate:** Low-medium. Author-lane effort hint: lower. Turnaround: half-session.

---

## §8. Track E — Plan + scope cleanup

### §8.1 Packet G-E1 — `agent_ops/5_*` subtree retirement notes

**Scope (docs-only; files touched in `plans/agent_ops/`):**
- Each of `plans/agent_ops/5_extraction/`, `plans/agent_ops/5_cross_model/`, `plans/agent_ops/5_skill_learning/`, `plans/agent_ops/5_portability_and_learning/` gets a top-level `STATUS.md` (or equivalent) naming the disposition: **superseded** (point to current governing plan), **absorbed** (point to current sub-plan), or **abandoned** (with reason). See rework_spec.md §7 rows.
- `plans/agent_ops/post_pr5_follow_on_roadmap.md` — move to `plans/agent_ops/_archive/` + add explicit "superseded by `plans/steward_platform/governing_plan.md`" note.
- MEMORY.md index entries updated to reflect archived status.

**Upstream gates:**
- None. Docs-only.

**Verification surface (Pattern 10: plan/sub-plan edit = `verification_contract/map.md` row):**
- Grep verification: `grep -l 'STATUS.md' plans/agent_ops/5_*/ | wc -l` = 4.
- Operator-review prompt: confirm each STATUS.md disposition is defensible (the "absorbed" ones point to the real absorbing sub-plan; the "abandoned" ones name the reason).

**Rollback path:** Revert commit; STATUS.md files removed; archived roadmap un-moved. Trivial.

**Effort estimate:** Low. Author-lane effort hint: lower. Turnaround: half-session.

### §8.2 Packet G-E2 — Messaging-bus proving overlap reference (cross-ref to Primitive E)

**Scope (reference-only; Primitive E owns execution):**
- No new files created by this packet.
- One line added to `governing_plan.md` §5-G Work list explicitly deferring messaging-bus proving-remaining-items to Primitive E (ops/message_bus.py ownership is Primitive E per rework_spec §3 row).
- Tracking-only: if residual messaging-bus proving items surface during Phase 0 work that Primitive E hasn't absorbed, file them as follow-up issues against Primitive E's sub-plan.

**Verification surface:** governing plan edit = `verification_contract/map.md` row.
**Rollback:** Revert commit.
**Effort:** Trivial.

### §8.3 Packet G-E3 — Platform-11 adaptive-dispatch closeout

**Scope (docs + sub-plan disposition):**
- `plans/agent_ops/5_portability_and_learning/SP-5-02-partial-reactivation.md` (existing, per MEMORY.md 2026-04-20 note) — add Outcome section: adaptive-dispatch subset status (Slice C/D/E merged per MEMORY.md; Slice A/B/F status) and explicit disposition (**absorbed** into Primitive B.1 adaptive dispatch, or **abandoned** with reason).
- `plans/steward_platform/governing_plan.md` §5-B — confirm B.1 absorbs the adaptive-dispatch subset; cross-reference added.
- Explicit note that PR5 (skill suggestion pipeline) stays POSTPONED until dispatch advisor validated (per MEMORY.md).

**Upstream gates:**
- Primitive B.1 shaping dispatched (analyst-a Packet 3-B per Primitive F shape §6).

**Verification surface (Pattern 10: plan edit = map.md row; disposition = operator-review prompt):**
- Grep verification: `grep 'Platform-11\|SP-5-02' plans/agent_ops/5_portability_and_learning/SP-5-02-partial-reactivation.md` returns outcome section.
- Operator-review prompt: "Does the disposition note identify which slices merged, which remain open, and which are permanently abandoned?" — YES/NO.

**Rollback path:** Revert commit; disposition note removed. Trivial.

**Effort estimate:** Low. Author-lane effort hint: lower. Turnaround: half-session (coordinated with B.1 shape landing).

---

## §9. Deliverable → Pattern 10 verification-surface table (cross-track)

Per `plans/steward_platform/verification_contract/shaping.md` §2 deliverable-class → surface-class defaults. Strict-existence (every deliverable has a named surface); lenient-form (surface matches deliverable class).

| Deliverable (§N) | Class | Default surface per Pattern 10 | Named surface for this packet |
|---|---|---|---|
| §3.1 G-A1: 7 archetype prompt files | New `.claude/system_prompts/**` | Launch-smoke (b9a shape §8.6) | `claude -p --system-prompt-file <file> "describe your role in one sentence"` per file; response paraphrases archetype one-liner (outcome A per B.9a pilot Probe pattern) |
| §3.2 G-A2: `steward-session.sh` launch-flag edits | Python / shell script edit | unit test path | `tests/unit/test_steward_session.py::TestSystemPromptFile` + `tests/unit/test_review_lane_runner.py::TestInvokeReviewSystemPromptFile` |
| §3.3 G-A3: Setup hook + declarative lane config | New `.claude/hooks/**` | rollback test + unit test | Disable-hook rename smoke + `tests/unit/test_setup_hook_adoption.py` golden-file argv comparison |
| §4.1 G-B1: `ops/worktrees.py` native migration | Python module change + new hooks + declarative config | unit test + rollback test | `tests/unit/test_worktrees.py` extended; revert-commit smoke; LOC-reduction measurement ≥ 80% |
| §4.2 G-B2: Heartbeat classifier retirement + TeammateIdle subscription | Python module change + new hook | unit test + event-stream grep | `tests/unit/test_dashboard.py::TestTeammateIdleIntegration`; grep `data/events/events-*.jsonl` for `lane_idle` records |
| §5.1 G-C1: 22 token-economy hard-blocks eliminated | Python module change + adapter + portability measurement | unit test + portability lint | `tests/unit/test_token_economy.py` golden-file; `scripts/internal/audit_portability.py --module ops.token_economy` returns 0 hard-blocks |
| §6.1 G-F2: Skills consolidation | Skill retirement + consolidation | named runnable acceptance command per SKILL.md + integration test | Per-retired-skill acceptance command re-run from consolidated target; `tests/integration/test_skills_surface.py` |
| §7.1 G-D1: `/fewer-permission-prompts` cron | Scheduler config change | rollback test + operator-review prompt | Disable-cron smoke; K/N actionability ratio ≥ 0.5 after N weeks |
| §7.2 G-D2: Ephemeral worktree sweep script | New Python script | unit test + named runnable | `tests/unit/test_sweep_ephemeral_worktrees.py`; `--dry-run` proposal table |
| §7.3 G-D3: `sweep_session_plans.py` + archive sweep | New Python script + sweep action | unit test + operator-review prompt | `tests/unit/test_sweep_session_plans.py`; post-sweep `ls plans/sessions/*.md \| wc -l` ≤ 50 |
| §7.4 G-D4: `capture_steward_baseline.py` | New Python script | unit test + named runnable | `tests/unit/test_capture_steward_baseline.py`; one timestamped snapshot in `baseline.md` |
| §8.1 G-E1: `agent_ops/5_*` retirement notes | Plan/doc edit | `verification_contract/map.md` row + operator-review prompt | Grep `STATUS.md` count = 4; disposition defensibility review |
| §8.2 G-E2: Messaging-bus cross-ref | Plan edit | map.md row | Grep governing plan for cross-ref line |
| §8.3 G-E3: Platform-11 closeout | Plan/sub-plan edit | map.md row + operator-review prompt | SP-5-02 Outcome section populated; disposition reviewable |

**Rollback coverage (§10, Pattern 7).** Every row above has a named rollback path in the per-packet spec (§3–§8 each include a "Rollback path" line). §10 enumerates the Goal #13 Phase 0 slice coverage.

---

## §10. Rollback validation (Pattern 7 + Goal #13 slice)

Per `governing_plan.md` §5-G "Rollback validation recorded for every reversible change introduced in Phase 0" — this is the Phase 0 slice of Goal #13 (rollback paths validated for every reversible change). Primitive H Phase 1 covers the Phase 1 slice.

**Coverage requirement.** Every §3–§8 packet ships with a documented rollback path (`git revert <commit>` + any follow-on restoration steps) *and* a smoke-test that validates the rollback path actually works. The smoke-test pattern is:

1. **Forward path:** merge the packet; observe the intended outcome (e.g., launch-flag fires, event stream populates, hard-block count drops).
2. **Reverse path:** `git revert` the merge commit on a test branch (do NOT push); observe the fleet reverts to pre-merge behavior on restart or on the next relevant trigger.
3. **Paste both outputs** into the packet's PR body Verification Performed section.

**Phase 0 Readiness for this slice:**

- [ ] Every Primitive G packet PR body contains a "Rollback Smoke" subsection.
- [ ] Rollback-smoke template (link to `.claude/skills/` or `docs/02_agent/` location TBD by G-E1-adjacent docs packet) is referenced in each PR.
- [ ] Operator review confirms at least one non-docs packet had its rollback smoke actually **executed** (not just documented) during Phase 0.

**Execution discipline:** rollback smoke runs in a disposable worktree (typically `Bid-Euchre-steward-author-scratch` or an ephemeral `work-*` worktree) so the fleet isn't disturbed. Primitive H.0 canary scenario absorbs some of this coverage at runtime; G's responsibility is the per-commit record-keeping.

---

## §11. Phase 2 Decision Inputs

**Portability readiness:** Strongly improved. The Primitive G scope reshape from "bespoke refactor" to "native-substrate migration" directly increases portability — each native surface adopted (WorktreeCreate/Remove, TeammateIdle, Setup hook, `--system-prompt-file`, shared project memory, plugin executables on PATH, tool-search) is portable by construction because it travels with Claude Code itself. The portability-cost residue lives at the adapter shims (G-B1 trimmed `worktrees.py`; G-C1 `token_economy_adapter.py`; F-forward's `token_economy_emitter.py`) + the tier-4 bespoke retention documented in ADR 003 (token economy) and ADR 004 (hook migration boundary). A second-cell deployment inherits the native surfaces for free and re-authors the adapters against its own cell conventions.

**Meta-layer need:** none. Primitive G's scope is substrate migration + debt closeout — no new meta-framework implied. The cross-cutting discipline (rollback record per change, verification-surface per deliverable) is already owned by Patterns 7 + 10.

**Kill signal for primitive(s) named:** no kill signal for G. G is gating, not capability — its non-completion blocks Phase 0 Readiness for dependent primitives but does not itself fail. Sub-kill-signals at the packet level: G-A3 (Setup hook) can be **deferred to Phase 1** if the native substrate is unstable at dispatch time; G-B2 (TeammateIdle) same deferral applies. Neither deferral fails G; both narrow G's Phase 0 scope. Operator records deferrals in MEMORY.md + the relevant packet disposition.

**Re-evaluation needed in Phase 3:** Possibly, along 3 soft triggers:

- If Claude Code ships a native skill-consolidation substrate (e.g., a SKILL-graph aggregator) post-Phase-0, G-F2 skills consolidation may need re-auditing against the new substrate.
- If auto-mode classifier costs become material (§80_permission_model.md Known limitation), G-D1 `/fewer-permission-prompts` cron cadence may need increasing or the mechanism may migrate to a different substrate.
- If a second cell is deployed during Phase 3, the G-B1 adapter shim gets re-audited against cell differences.

Re-evaluation trigger tags: **RE-EVAL: Phase-3-start**, **RE-EVAL: on-second-cell**, **RE-EVAL: on-classifier-cost-spike**.

**Surprise finding:** The governing plan §5-G scope reshape to "native migration" surfaced a coordination dimension that the pre-reshape version didn't have: **every native-substrate adoption couples G to a Phase 0 dependency on Claude Code version stability on the fleet**. If the fleet runs a version where WorktreeCreate or TeammateIdle or Setup hook is not stable, the corresponding G packet defers to Phase 1 — not as a scope decision but as a substrate availability fact. This makes the `CLAUDE_CODE_CHANGELOG_IMPLICATIONS.md` Tier S inventory (cited in §1 sibling artifacts) a first-class dependency input for G's Phase 0 execution order. Packets in strict dependency order: G-A1 (no native blocker; files-only) → G-A2 (already-stable `--system-prompt-file`) → G-A3 (Setup hook; substrate-gated) → G-B1 (WorktreeCreate/Remove; substrate-gated) → G-B2 (TeammateIdle; substrate-gated) → Track C/D/E/F (non-substrate-gated). Operator confirms substrate availability before dispatching G-A3 / G-B1 / G-B2.

**Disposition:** open (pending packet dispatch).

---

## §12. Verification Plan (Pattern 10 mandate)

Per the analyst prompt-policy clause (§4.3 of `plans/steward_platform/verification_contract/shaping.md`): every shaping-doc deliverable names a verification surface. This shaping doc itself is the deliverable; its "verification surface" is whether downstream packet dispatch can proceed without additional shaping work.

| Deliverable (§N of this shape) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §1 Scope-in / scope-out | scope declaration | operator-review prompt: "Does §1 exclude Primitive H, F-debt execution beyond boundary, and token-economy emitter (Primitive F concerns)?" | analyst (this packet); orchestrator (review) | all three exclusions explicit |
| §2 Upstream artifact crosswalk | reference decision | grep: every row's cited artifact exists on main | analyst (this packet) | `gh pr view <pr>` + `ls <path>` verify each row — 12 rows pass |
| §3 Track A packets (G-A1 / G-A2 / G-A3) | shaping spec for archetype chain | B.9a authoring shape §8 + G13 §2.1 / §2.2 + ADR G10 compliance | author (packet dispatch); orchestrator (review) | G-A1 PR lands 7 files matching b9a shape §3/§4.1; G-A2 PR lands unit tests matching §3.2 spec; G-A3 PR (if dispatched) matches §3.3 spec |
| §4 Track B packets (G-B1 / G-B2) | shaping spec for native migrations | rework_spec.md §3 rows 1, 4, `lane_heartbeat.py`, `idle_detector.py` dispositions match | author (packet dispatch) | G-B1 LOC reduction ≥ 80% on `worktrees.py`; G-B2 removes 2 modules + 1 hook file; both pass extended unit tests |
| §5 Track C packet (G-C1) | shaping spec for token-economy hard-blocks | `rework_spec.md` §3 row `token_economy.py`; `audit_portability.py` pre/post | author (packet dispatch) | post-merge `audit_portability.py --module ops.token_economy` returns 0 hard-blocks; PR #2725 rollup shape preserved |
| §6 Track F packet (G-F2) | shaping spec for skills consolidation | `rework_spec.md` §6; operator approval gate | author (packet dispatch); operator (review) | Retired skill list operator-approved; 6 monitoring + 4 playtest + 3 loop families reduced per rework_spec targets |
| §7 Track D packets (G-D1 / G-D2 / G-D3 / G-D4) | shaping spec for operational hygiene | rework_spec.md §4 / §6 / §7 rows | author (packet dispatch) | Each of D1–D4 lands unit test + named runnable; operator reviews sweep proposals before D2/D3 execute |
| §8 Track E packets (G-E1 / G-E2 / G-E3) | shaping spec for plan cleanup | rework_spec.md §7 rows | author (packet dispatch); orchestrator (review) | E1 lands 4 STATUS.md + archive move; E2 lands 1-line cross-ref; E3 lands Outcome section on SP-5-02 |
| §9 Pattern 10 surface table | reconciliation against verification-contract shaping.md §2 | every surface in §9 resolves to a real path-or-command at packet dispatch time | packet authors; lint (post-Packet-2b merge) | every surface name grep-findable; `agent_readability_lint.py check verification-contract` exits 0 against this file |
| §10 Rollback validation | Phase 0 slice of Goal #13 | Pattern 7 compliance per packet | packet authors; H.0 canary (runtime) | Every packet PR has "Rollback Smoke" subsection; at least 1 non-docs packet had rollback actually executed |
| §11 Phase 2 Decision Inputs | required §15.2 schema subsection | 5 prompts + disposition all populated | analyst (this packet) | §11 complete |
| §12 Verification Plan | this section | lint cross-walks every §N to a surface | analyst (this packet); lint (post-Packet-2b) | `agent_readability_lint.py check verification-contract` clean against this file |
| **Whole-file readability** | agent-readability lint | `scripts/internal/agent_readability_lint.py plans/steward_platform/7_primitive_G/shaping.md` (G1 script, once shipped) | analyst (this packet); G1 author | Lint exits 0 against §10.8 conventions |

**Worked examples for reading §9 (per Pattern 10 lenient-form):**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §4.1 G-B1 LOC reduction target | measurement claim | `git diff --stat src/bid_euchre/ops/worktrees.py` post-merge shows ≥ 80% deletion | author (G-B1 packet) | ratio ≥ 0.8 |
| §4.2 G-B2 TeammateIdle event emission | event-shape constraint | grep `data/events/events-*.jsonl` for `event_type=lane_idle` records within 10 min of proven-idle lane | ops (during proving run) | ≥ 1 match per idle lane |
| §5.1 G-C1 hard-block count | portability measurement | `uv run python scripts/internal/audit_portability.py --module ops.token_economy \| grep -c 'BID_EUCHRE_LITERAL'` | author (G-C1 packet) | count = 0 |
| §7.3 G-D3 session-plan archive count | sweep-outcome measurement | `ls plans/sessions/*.md \| wc -l` post-sweep | author (G-D3 packet); operator (review) | count ≤ 50 |

---

## §13. Self-review against completeness criteria

The analyst-lane prompt-policy clause (§4.3 of `plans/steward_platform/verification_contract/shaping.md`) requires shaping docs end with a `## Verification Plan` section. §12 provides that. This section is the analyst's self-audit against shaping completeness.

### §13.1 Completeness stress-test

| Criterion | Check | Outcome |
|---|---|---|
| All 12 §5-G Work bullets mapped to packets | §1.2 table shows bullet-to-packet mapping | ✓ (13 rows, 12 Work bullets + 2 B.9a/B.9b) |
| Upstream-landed artifacts cited (not duplicated) | §2 table | ✓ (12 rows, each grep-verifiable) |
| Every packet has: scope, upstream gates, verification surface, rollback, effort | §3–§8 per-packet spec shape | ✓ (G-A1, G-A2, G-A3, G-B1, G-B2, G-C1, G-F2, G-D1, G-D2, G-D3, G-D4, G-E1, G-E2, G-E3 all specified) |
| Deliverable → Pattern 10 surface table | §9 | ✓ (14 rows) |
| Rollback validation Phase 0 slice | §10 | ✓ |
| Phase 2 Decision Inputs | §11 | ✓ (5 prompts + disposition) |
| Verification Plan | §12 | ✓ (13 rows + 4 worked examples) |
| Track topology + coordination profiles | §1.3 | ✓ |
| F-debt boundary respected | §1 explicit; §5.1 consumes Primitive F Packet 11 as upstream | ✓ |
| B.9a pilot empirical verification inherited | §2 row for PR #2779; §3.1 does not re-verify | ✓ |
| Issue #2767 coordination resolved | §3.2 G-A2 Upstream gates (updated: #2778 merged 2026-04-23; no longer a serialization risk) | ✓ |

### §13.2 Risks I surfaced during self-review (orchestrator decision)

1. **Setup hook substrate availability (G-A3).** If Claude Code's Setup hook is not stable on the fleet version, G-A3 defers to Phase 1; G-A2 remains sufficient for Phase 0 Readiness. **Recommendation:** orchestrator confirm substrate availability before dispatching G-A3; if deferred, accept Phase 0 Readiness partial-satisfaction and document in MEMORY.md.

2. **TeammateIdle availability (G-B2).** Same pattern as G-A3. **Recommendation:** same — operator-gate the dispatch.

3. **WorktreeCreate/Remove availability (G-B1).** Same pattern. Additional concern: G-B1 is the single largest LOC surgery in G; substrate failure means 1000+ LOC refactor stays pending until substrate lands. **Recommendation:** operator confirm before dispatch; if unavailable, consider smaller pre-cursor packet that migrates the literals to declarative config (step 1) independent of native-hook adoption (step 2), which requires substrate.

4. **F → G dependency (G-C1).** Primitive F Packet 11 must merge before G-C1. **Recommendation:** operator confirm Packet 11 merged before G-C1 dispatches.

5. **~~G-A2 ↔ Issue #2767 serialization~~ (RESOLVED 2026-04-23).** PR #2778 (Fixes #2767) merged before this shape; the serialization hazard is retired. G-A2 now layers `--system-prompt-file` onto the model-tier-conditioned launch lines cleanly. Historical note preserved for lineage.

6. **Skills consolidation operator sign-off (G-F2).** Skills are operational surface; retiring 8 without review is a visibility regression. **Recommendation:** G-F2 dispatch requires operator pre-approval of retired skill list.

7. **Rollback-smoke execution discipline (§10).** "At least 1 non-docs packet had rollback actually executed" can slip if every packet just documents the path without running it. **Recommendation:** operator nominates a single packet early in Phase 0 (e.g., G-A1 or G-D2) whose rollback smoke is deliberately executed; the smoke output lives in the PR body as exemplar for later packets.

### §13.3 Constraint encountered

The task packet did not require spawning a reviewer agent. Self-review per §13.1 + §13.2 substitutes. The analyst-lane YAML frontmatter structurally disallows the `Agent` tool (per the analyst system prompt), so a spawned-subagent review is not available from this lane; dispatch to a sibling recused analyst lane is the correct escalation path for adversarial review.

### §13.4 Orchestrator option — adversarial review

If the orchestrator wants independent adversarial review before packet dispatch, dispatch to any recused analyst lane with the prompt:

> "Review `plans/steward_platform/7_primitive_G/shaping.md` for: (a) coverage of §5-G Work bullets (any bullet unmapped to a packet?); (b) Pattern 10 surface adequacy (every packet has a named surface that's not 'operator review' without pass criterion?); (c) upstream dependencies enumerated correctly (F → G-C1, A → G-B1/G-B2, G-A1 → G-A2); (d) rollback validation Phase 0 slice coverage; (e) Packet spec executability (each §3–§8 packet could be dispatched without re-shape). Recommended but not blocking per the task framing."

---

## §14. References

- `plans/steward_platform/governing_plan.md` §5-G (lines 552–606) — primary source for Primitive G scope
- `plans/steward_platform/governing_plan.md` §5-B B.9a / B.9b — system-prompt archetype chain G13 → B.9a → B.9b
- `plans/steward_platform/governing_plan.md` §10.9 Patterns 2 / 7 / 8 / 9 / 10 — native-substrate preference, rollback, observability, ownership, verification
- `plans/steward_platform/governing_plan.md` §13 SC #22 — Phase 0 canary gate (H.0 consumer of G's rollback coverage)
- `plans/steward_platform/governing_plan.md` §15.2 — Phase 2 Decision Inputs subsection schema
- `plans/steward_platform/0_hardening/sub/rework_spec.md` §2 priority sequence + §3 ops catalog + §4 scripts + §5 hooks + §6 skills + §7 plans/docs + §8 worktrees — per-surface tactical dispositions
- `plans/steward_platform/0_hardening/sub/g13_archetype_mapping.md` §2.1 + §2.2 + §2.3 — lane-archetype mapping (merged PR #2768)
- `plans/steward_platform/0_hardening/sub/b9a_prompt_authoring_shaping.md` §3 / §4.1 / §6 / §7 / §8 — file-authoring shape consumed by G-A1
- `plans/steward_platform/0_hardening/baseline.md` — PR #2766 skeleton; G-D4 populator
- `plans/steward_platform/adrs/G10-system-prompts-vs-agents.md` — orthogonal ruling; inherited by Track A
- `plans/steward_platform/adrs/006-auto-mode.md` §"Model tier interaction" — G-A2/A3 permission-mode coordination
- `plans/steward_platform/adrs/003-token-economy-native-vs-bespoke.md` (SEEDED by F Packet 11; PROMOTED at Phase 0 close) — G-C1 scoping reference
- `plans/steward_platform/adrs/004-hook-migration-boundary.md` (SEEDED at Phase 0 close, per rework_spec §5 hook catalog) — G-B2 + G-A3 + Track E hook decisions
- `plans/steward_platform/1_primitive_A/shaping.md` §4 event schema — consumed by G-B1 (worktree events) + G-B2 (lane_idle events)
- `plans/steward_platform/6_primitive_F/shaping.md` §2.2 F-debt boundary — G-C1 upstream
- `plans/steward_platform/verification_contract/shaping.md` §2 / §3 / §4 — Pattern 10 surface-class defaults, V1–V6 precheck, per-lane prompt-policy
- `plans/steward_platform/verification_contract/map.md` — Primitive G coverage rows (to be added by Track E docs packet and/or per-packet PR bodies)
- `plans/steward_platform/claude_code_changelog_implications.md` §2 Tier S — native features gating G-A3 / G-B1 / G-B2 dispatch
- `.claude/rules/75_worktree_protection.md` — protected worktree list consumed by G-B1 + G-D2
- `.claude/rules/80_permission_model.md` — auto-mode / permission-model context consumed by G-A2 / G-D1
- `.claude/rules/prompt_policy/analyst.md` — analyst-lane shaping obligation (this doc complies)
- `src/bid_euchre/ops/worktrees.py` — G-B1 target surface
- `src/bid_euchre/ops/token_economy.py` — G-C1 target surface
- `src/bid_euchre/ops/dashboard.py` — G-B2 target surface (heartbeat classifier block)
- `src/bid_euchre/ops/lane_heartbeat.py` — G-B2 target surface (retire)
- `src/bid_euchre/ops/idle_detector.py` — G-B2 target surface (retire)
- `.claude/tmux/steward-session.sh` — G-A2 + G-A3 target surface
- `scripts/internal/review_lane_runner.py::invoke_review` — G-A2 target surface
- `scripts/internal/audit_portability.py` — G-C1 verification surface; `rework_spec.md` §4 reframing target
- PR #2765 — ADR G10 merged
- PR #2768 — G13 mapping sub-plan merged
- PR #2779 — B.9a pilot merged (empirical verification)
- PR #2766 — baseline.md skeleton merged
- PR #2725 — lane × model × effort rollups shipped (preserved through G-C1)
- PR #2743 — heartbeat classifier shipped (retired by G-B2)
- PR #2739 — pure-shell heartbeat hook shipped (retired by G-B2)
- PR #2741 — lane-id dedup library (preserved through G hook consolidation)
- PR #2762 — prompt-policy registry (initial) shipped (cited by G-A1 archetype prompts)
- PR #2778 — model-tier-aware permission-mode launch flags (Fixes #2767; G-A2 upstream unblocker)
- PR #2780 — Primitive B-exec.α merged (B.3 prompt-policy versioning + PP0-PP4 lint; B.6 tool-risk registry; B.10 effort policy; B.11 orchestration-recipe archive incl. `shape_then_execute_pattern11.md`)
- Issue #2767 — CLOSED by PR #2778 (historical reference)
- Task packet: `c7c6a25ee902` (this shaping work)
