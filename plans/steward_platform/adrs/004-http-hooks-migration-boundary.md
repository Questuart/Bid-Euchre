# ADR 004 — Hook Migration Boundary

**Status:** FILED (Primitive E Phase 0 Packet E1 — A-independent subset)
**Primitive:** E (messaging + active triage closeout)
**Supersedes:** none
**Seed source:** `plans/steward_platform/5_primitive_E/shaping.md` §7 (analyst-d, 2026-04-24); governing plan §14 Open Item 14

---

## Context

Governing plan §14 Open Item 14 enumerates four possible destinations for each
of steward's hook files:

1. **Native lifecycle subscription** — Claude Code grows a first-class hook for
   the surface, replacing a bespoke shell/Python script.
2. **Conditional hook (matcher narrowing)** — the hook stays shell/Python but
   its settings.json matcher narrows from `*` to a specific tool set.
3. **HTTP hook** — the hook moves to an out-of-process HTTP endpoint the
   Claude runtime calls via JSON request/response.
4. **Bespoke** — the hook remains as-is; no migration.

Primitive E §5-E Work bullet 6 tasks Packet E1 with authoring this ADR. The
shaping doc (§7) specifies a four-axis rubric, a sum-band destination mapping,
and a Phase 0-vs-Phase-1 scope split (§7.4) — **Phase 0 produces the ADR;
zero HTTP migrations execute.**

The concrete inventory (35 hooks total: 34 under `.claude/hooks/` + 1 under
`scripts/internal/hooks/`) is enumerated in `.claude/hooks/README.md`
§Conditional-Hook Migration Disposition Table, which is the conditional-hook
(destination 2) surface of this ADR.

## Decision

**Adopt the four-axis rubric from shaping §7.2 verbatim. Apply it to all 35
hooks. Populate the disposition table below. Commit to migrating zero hooks
to HTTP in Phase 0; execute the top 3–5 HTTP candidates in Phase 1 proving-run
as §7.4 specifies.**

### §1. Rubric

Score each hook 0–3 on each of four axes. Sum → destination:

| Axis | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Portability** | Hook is steward-specific; HTTP-ization confers no cleanup | Minor Bid-Euchre literals (a grep pattern, an env name) | Several literals; cleanup would aid extraction | Hook is almost fleet-generic; only literals block extraction |
| **Latency** | Hook runs <10 ms; cost is negligible | 10–30 ms; measurable but not hot-path | 30–100 ms; measurable on every relevant tool-call | >100 ms OR runs on every tool call (hot-path) |
| **Observability** | No reusable signal | Local log only | Log + summary for operator | Produces a reusable HTTP-hook substrate signal |
| **Risk** | Stable surface; no upstream change risk | Minor forward-compat risk | Payload may mutate between Claude versions | Payload-sensitive and load-bearing on upstream |

Sum-band → destination:

- Sum ≥9 → **HTTP hook** (high-priority migration candidate)
- Sum 6–8 → **Conditional hook** (matcher narrowing)
- Sum 3–5 → **Bespoke** (status quo)
- Sum <3 → **Delete** (hook has decayed to dead weight)

### §2. Per-hook disposition

Rows are grouped by current destination to keep the ADR readable. Every row
cites the scoring rationale in the Notes column. The **Destination** column
is the chosen bucket per the sum band; the **Current** column is what's in
place today.

Abbreviations: P = Portability, L = Latency, O = Observability, R = Risk.

| # | Hook | Current | P | L | O | R | Σ | Destination | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `alert-inject.sh` | Conditional (event-scoped) | 1 | 1 | 1 | 1 | 4 | Bespoke | UserPromptSubmit-scoped; low volume; fleet-specific alert format. |
| 2 | `alert-inject.py` | Helper (invoked by #1) | — | — | — | — | — | Bespoke (helper) | Not a hook; implementation detail of #1. |
| 3 | `attention-broker-autostart.sh` | Conditional (event-scoped) | 0 | 0 | 0 | 0 | 0 | Delete-candidate | Runs once per SessionStart; spawns a daemon. If native TeammateIdle lands, the broker is superseded. Keep until native arrives; re-audit. |
| 4 | `block-runtime-writes.sh` | Conditional (already-narrow) | 0 | 1 | 0 | 2 | 3 | Bespoke | PreToolUse Edit\|Write; exit-2 guard. Steward-specific path list. Payload-sensitive to `tool_input.file_path` shape. |
| 5 | `compact-context.sh` | Conditional (already-narrow) | 2 | 0 | 2 | 0 | 4 | Bespoke | SessionStart matcher=`compact`; one-shot. Fleet-generic enough to extract eventually; no latency pressure. |
| 6 | `fleet-check-autostart.sh` | Conditional (event-scoped) | 0 | 0 | 0 | 0 | 0 | Delete-candidate | Steward-fleet-specific autostart; once per SessionStart. Evaluate for deletion if `/fleet-check` becomes a durable cron. |
| 7 | `inbound-channel-audit.sh` | Conditional (event-scoped) | 2 | 1 | 2 | 1 | 6 | Conditional hook | UserPromptSubmit; already narrow. Portable audit pattern (log inbound messages by channel); could become a reusable HTTP hook if volume rises. Currently fleet-acceptable. |
| 8 | `inbound-channel-audit.py` | Helper (invoked by #7) | — | — | — | — | — | Bespoke (helper) | Not a hook. |
| 9 | `inbox-completion-inject.sh` | Conditional (event-scoped) | 1 | 1 | 1 | 1 | 4 | Bespoke | UserPromptSubmit; lane-scoped guard inside script. Steward-specific inbox format. |
| 10 | `inbox-completion-inject.py` | Helper (invoked by #9) | — | — | — | — | — | Bespoke (helper) | Not a hook. |
| 11 | `lane-heartbeat-post-tool.sh` | Retained-universal-justified (`*`) | 1 | 3 | 3 | 1 | 8 | Conditional hook | Runs on every PostToolUse. Post-#2739 pure-shell rewrite is ~20 ms; still top-of-band for latency. Substrate HTTP migration would save the shell fork but adds a network hop — net-neutral. Keep shell; revisit if Claude Code ships a native idle-detection surface (delete candidate). |
| 12 | `permission-denied-log.sh` | Conditional (event-scoped) | 2 | 0 | 3 | 2 | 7 | Conditional hook | PermissionDenied is rare; latency cost is tiny. Observability value is high (§9.7 events consume this). Payload-sensitive to `tool_name`/`reason` shape. Keep shell for now; HTTP migration is a reasonable Phase 1 candidate if payload churn persists. |
| 13 | `post-bash-dispatch.sh` | Conditional (already-narrow) | 0 | 2 | 1 | 1 | 4 | Bespoke | Bash-only dispatcher; dispatches to sub-hooks. Fleet-specific sub-hook routing. |
| 14 | `post-merge-ci-check.sh` | Dispatched (via #13) | 1 | 0 | 1 | 1 | 3 | Bespoke | Early-exits when command != `gh pr merge`. |
| 15 | `post-merge-notify.sh` | Dispatched (via #13) | 1 | 0 | 2 | 1 | 4 | Bespoke | Updates message-bus task lifecycle after merge. Steward-bus-specific. |
| 16 | `post-merge-review.sh` | Dispatched (via #13) | 1 | 0 | 2 | 1 | 4 | Bespoke | Spawns background post-merge reviewer. Steward-specific. |
| 17 | `post-monitor-push-relay.sh` | Dispatched (via #13) | 1 | 0 | 2 | 1 | 4 | Bespoke | Monitor-state-delta detection for Telegram push; steward-specific state file. |
| 18 | `post-plan-review.sh` | Deprecated | — | — | — | — | — | Delete | No active registration; superseded by `/review-plan` skill. Remove file in a follow-up cleanup PR. |
| 19 | `post-pr-review-loop.sh` | Dispatched (via #13) | 1 | 0 | 2 | 1 | 4 | Bespoke | Launches review driver after `gh pr create`. Steward-bus-specific. |
| 20 | `post-pr-review.sh` | Dispatched (via #13) | 1 | 0 | 2 | 1 | 4 | Bespoke | Enqueues review request after `gh pr create`. Steward-bus-specific. |
| 21 | `post-push-ci-check.sh` | Dispatched (via #13) | 1 | 0 | 1 | 1 | 3 | Bespoke | Launches CI poller after `git push`. |
| 22 | `post-task-event.sh` | Dispatched (via #13) | 2 | 0 | 3 | 1 | 6 | Conditional hook | Emits §9.7 events on task-relevant commands. Observability-high. Payload-sensitive post-Primitive-A. **Revisit after A merges:** if Primitive A's dispatcher subsumes the event emission, this hook may delete. |
| 23 | `post-telegram-audit.sh` | Conditional (already-narrow) | 2 | 1 | 2 | 1 | 6 | Conditional hook | Already narrow on 4 specific MCP Telegram tools. Audit JSONL is fleet-generic pattern. |
| 24 | `post-tool-daemon-notify.sh` | Dispatched (via #13) | 1 | 1 | 1 | 1 | 4 | Bespoke | Checks for background daemon failures; steward-specific state files. |
| 25 | `post-write-check.sh` | Conditional (already-narrow) | 2 | 1 | 1 | 1 | 5 | Bespoke | Advisory anti-pattern detection for Python. Post-migrated to consolidated `Edit\|Write` matcher in Packet E1. |
| 26 | `pre-bash-dispatch.sh` | Conditional (already-narrow) | 0 | 2 | 1 | 1 | 4 | Bespoke | Bash-only dispatcher; dispatches to sub-hooks. |
| 27 | `pre-merge-review-guard.sh` | Dispatched (via #26) | 1 | 0 | 2 | 2 | 5 | Bespoke | **Keep bespoke — explicit per §7.3:** enforces the merge-guard contract; HTTP-ization would add network latency to `gh pr merge`. Steward-specific verdict check. |
| 28 | `pre-worktree-cleanup.sh` | Dispatched (via #26) | 1 | 0 | 1 | 1 | 3 | Bespoke | Blocks `git worktree remove` on protected paths per `.claude/rules/75_worktree_protection.md`. |
| 29 | `rule-loader.sh` | Conditional (already-narrow) | 2 | 2 | 2 | 1 | 7 | Conditional hook | Runs on every PreToolUse Edit\|Write\|Read. Substantive context-injection latency on every read/edit. HTTP migration would add a round-trip on every Read — net-negative. Keep shell; evaluate for native substrate if Claude Code ships context-injection API. |
| 30 | `scope-drift-guard.sh` | Dispatched (via #26, not registered in settings) | 1 | 0 | 1 | 1 | 3 | Bespoke | Advisory-only; sub-hook invoked by dispatcher. |
| 31 | `session-sync-worktree.sh` | Conditional (event-scoped) | 1 | 0 | 1 | 1 | 3 | Bespoke | SessionStart; cwd-gated. Fleet-specific worktree sync. |
| 32 | `urgent-state-guard.py` | Helper (not directly registered) | — | — | — | — | — | Bespoke (helper) | Not a hook; imported by other hooks. |
| 33 | `worktree-guard.sh` | Conditional (event-scoped, in `.claude/settings.local.json`) | 1 | 0 | 1 | 1 | 3 | Bespoke | Registered in gitignored local settings. |
| 34 | `worktree-reminder.sh` | Conditional (event-scoped, in `.claude/settings.local.json`) | 1 | 0 | 1 | 1 | 3 | Bespoke | Registered in gitignored local settings. |
| 35 | `permission_denied_alert.sh` (under `scripts/internal/hooks/`) | Retained-universal-justified (`*`) | 2 | 0 | 3 | 2 | 7 | Conditional hook | PermissionDenied matcher=`*`; rare event. HTTP migration is a reasonable Phase 1 candidate paired with #12. |

### §3. Destination summary

| Destination | Count | Hooks |
|---|---|---|
| HTTP hook (Σ ≥9) | **0** | — |
| Conditional hook (Σ 6–8) | **7** | #7 `inbound-channel-audit.sh`, #11 `lane-heartbeat-post-tool.sh`, #12 `permission-denied-log.sh`, #22 `post-task-event.sh`, #23 `post-telegram-audit.sh`, #29 `rule-loader.sh`, #35 `permission_denied_alert.sh` |
| Bespoke (Σ 3–5) | **24** | #1, #4, #5, #9, #13–#17, #19–#21, #24–#28, #30, #31, #33, #34 (+ 5 helpers not scored: #2, #8, #10, #32) |
| Delete (Σ <3 or deprecated) | **3** | #3 `attention-broker-autostart.sh` (delete-candidate), #6 `fleet-check-autostart.sh` (delete-candidate), #18 `post-plan-review.sh` (deprecated — remove file in cleanup PR) |

**No HTTP migrations in the Σ ≥9 band.** This is a material finding: the hooks
that currently run in steward are either low-latency (shell is fine), rare-event
(volume not justifying HTTP), or payload-sensitive (migration risk outweighs
portability gain). HTTP migration remains available as a Phase 1+ option for
specific hooks that develop pressure (e.g., if `rule-loader.sh` grows a cross-
fleet context-injection API).

### §4. Migration sequence

**Phase 0 (Packet E1 — A-independent subset):**

1. Zero HTTP migrations.
2. `post-write-check.sh` consolidated `Write`+`Edit` → `Edit|Write` (done in
   Packet E1).
3. Retained-universal-justified sentinel added to 2 `*` matchers per the §6.5
   contract test (`lane-heartbeat-post-tool.sh`, `permission_denied_alert.sh`).
4. Disposition table in `.claude/hooks/README.md` tracks this ADR.

**Phase 1 (after Primitive A merges, proving run):**

- Re-audit Conditional-hook band (7 hooks) for HTTP candidates based on
  observed latency + portability pressure.
- Re-audit Delete-candidate band (#3, #6) against native substrate options
  (TeammateIdle, durable cron).
- Delete #18 `post-plan-review.sh` in a dedicated cleanup PR.
- Candidate Phase 1 HTTP migrations (in priority order):
  - #12 `permission-denied-log.sh` + #35 `permission_denied_alert.sh` —
    pair them: single HTTP endpoint receives the denial payload, logs +
    alerts in one place.
  - #22 `post-task-event.sh` — if Primitive A's native dispatcher doesn't
    subsume it.

**Phase 2+ (post-proving-run):**

- Execute whichever Phase 1 candidates prove net-positive.
- Re-audit: the §9 governing-plan improvement-mechanism discipline requires
  proving each HTTP migration is net-positive before the next lands.

### §5. Explicit keep-bespoke subset

Per shaping §7.3, the ADR calls out the "keep bespoke" subset with explicit
rationale:

- **#27 `pre-merge-review-guard.sh`** — enforces merge-guard contract.
  HTTP-ization would add network latency to `gh pr merge`, and the guard is
  on the hot path for every merge. Steward-specific verdict shape makes
  cross-fleet reuse unlikely. **Keep bespoke, Phase 0 and Phase 1.**
- **#4 `block-runtime-writes.sh`** — steward-specific runtime-path list
  (`.claude/runtime/**` allowlist). PreToolUse on every Edit\|Write already
  narrow; HTTP-ization adds latency on every file edit with no observability
  gain. **Keep bespoke.**
- **#29 `rule-loader.sh`** — runs on every Read; HTTP migration would add a
  round-trip per Read. Net-negative even though portability score is high.
  **Keep bespoke until Claude Code ships a native context-injection API.**

### §6. Relationship to other ADRs and patterns

- **Pattern 2 (§10.9 native-substrate-first preference):** ADR 004 applies the
  preference: delete-candidate hooks (#3, #6) are flagged for re-audit against
  native substrate (TeammateIdle, durable cron).
- **Pattern 7 (§10.9 reversibility-as-default):** every conditional-hook
  migration is a single-file diff (`.claude/settings.json` matcher change); the
  Disposition Table row is the revert target. ADR 004 §4 treats each migration
  as independently revertible.
- **Pattern 8 (§10.9 observable-by-default):** hooks in the Conditional-hook
  band (O = 2 or 3) are observability-surface candidates for Primitive A's
  event schema. Post-A-merge, each emits §9.7 events.
- **Pattern 9 (§10.9 load-bearing-ownership lint):** every row in the §2
  disposition table names a current destination + hook owner (the hook
  file) + a rationale. `.claude/hooks/README.md` §Conditional-Hook
  Migration is the companion lint surface.
- **ADR 007 (observability plugin evaluation):** post-Primitive-A, #22
  `post-task-event.sh` may become redundant; that merge re-audits this ADR's
  §2 row 22.
- **B8 (task system evaluation):** task-lifecycle emission currently lives in
  #22; native task-queue merge (deferred per B8) would likewise re-audit.

## Consequences

- Primitive E Phase 0 ships with a zero-HTTP-migration policy and a committed
  rubric. Phase 1 proving-run has a pre-scored candidate list to reference.
- Deletion-candidate hooks (#3, #6, #18) have explicit decay markers; a
  follow-up cleanup PR removes #18 and re-audits #3, #6 after native
  substrate availability.
- The Conditional-hook band (7 hooks) is the primary Phase 1 HTTP-migration
  fodder. If none prove net-positive in Phase 1, HTTP hooks remain a tool in
  the toolbox for later — but steward is not committed to HTTP-izing
  universally.
- `.claude/hooks/README.md` §Disposition Table is kept in sync with this ADR.
  Future hook additions must update both surfaces atomically; the
  `tests/unit/test_hooks_inventory.py` lint enforces the README side.

## Alternatives considered

1. **Migrate all Σ ≥6 hooks to HTTP in Phase 0.** Rejected. Shaping §7.4
   explicitly scopes Phase 0 to "ADR authored; disposition table populated;
   zero migrations to HTTP executed." Moving migrations to Phase 0 would
   overrun the packet budget and couple Phase 0 acceptance to HTTP substrate
   maturity.
2. **Raise the sum-band thresholds (e.g., Σ ≥11 for HTTP).** Rejected. The
   shaping rubric thresholds are calibrated against the fleet's observed
   bespoke-hook load-pattern; raising thresholds would silence real signals.
3. **Delete the Σ <3 band hooks in Packet E1.** Rejected. Deletion is a
   destructive change; best handled in a dedicated cleanup PR with its own
   review gate. The ADR flags #18 for deletion; the cleanup PR ships
   separately.
4. **Migrate only `lane-heartbeat-post-tool.sh` to HTTP as a pilot.** Rejected
   for Phase 0. Its Σ=8 does not meet the ≥9 HTTP threshold; post-#2739
   pure-shell is already ~20 ms, which is an acceptable floor. Revisit in
   Phase 1 alongside native TeammateIdle-substrate availability.

## Open questions

1. **Phase 1 revisit cadence.** When do we re-score? Proposal: after Primitive
   A's §9.7 event emission lands, re-score the Conditional-hook band using
   observed per-hook latency + emission rate from the first 2 weeks of
   A-emitted data. If three consecutive re-scores show no movement across the
   Σ ≥9 line, freeze the scoring and treat the rubric as decided.
2. **Delete-candidate (#3, #6) disposition after native TeammateIdle lands.**
   Explicit proposal: file a follow-up ADR once TeammateIdle is available,
   comparing the bespoke autostart surface to the native surface with a
   per-hook decision. Non-blocking for Phase 0.

## References

- `plans/steward_platform/5_primitive_E/shaping.md` §7 (rubric + scope split)
- `plans/steward_platform/governing_plan.md` §5-E (Primitive E work)
- `plans/steward_platform/governing_plan.md` §14 Open Item 14 (this ADR)
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 2 / 7 / 8 / 9
- `.claude/hooks/README.md` §Conditional-Hook Migration (companion disposition)
- `tests/unit/test_hooks_inventory.py` + `tests/unit/test_settings_hooks_contract.py` (lint surface)
- `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` (Primitive A relationship)
- `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` (task-system relationship)
