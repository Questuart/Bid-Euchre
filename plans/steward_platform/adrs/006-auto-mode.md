# ADR 006 — Auto Mode Codification

**Status:** SEEDED at Phase 0 kickoff
**Primitive:** meta (affects every lane); cross-cutting with B (dispatch) and G (debt closeout / native-substrate migration)
**Supersedes:** the `bypassPermissions` + Claude Code sensitive-file-dialog era (implicit; no prior ADR)
**Seed source:** `.claude/rules/80_permission_model.md` (operator-facing spec) + issue #2685 discovery (auto mode inactive without `--permission-mode auto` activation flag)

---

## Context

The fleet runs 19 concurrent Claude Code lanes (orchestrator, ops, review, plus author/analyst/browser/flex pools). Every lane issues Bash, Edit, Write, and MCP tool calls autonomously against a shared repo, GitHub org, and production infrastructure. Prior to this decision, every lane ran with `permissions.defaultMode: "bypassPermissions"` — all tool calls auto-approved except those blocked by Claude Code's hard-coded sensitive-file dialog (see #2249).

Under `bypassPermissions` the only runtime gate against destructive or exfiltrating actions was the per-file glob pattern in `permissions.allow`. That model has known failure modes:

- **Force-push, prod deploys, and `curl | bash` are all allowed** as long as they match a Bash allow pattern (or bypass it entirely). The shape of the command is invisible to the allowlist.
- **Exfiltration is allowed** — `git push` to an unexpected remote, or outbound HTTP to a non-trusted host, passes the allowlist if the binary is allowed.
- **Self-modification of `.claude/settings.json`** fell back to Claude Code's built-in sensitive-file dialog (#2249), which was a modal hard-block with no intent signal and caused repeated lane stalls.
- **Irreversible local destruction** (`rm -rf` of untracked work, `git reset --hard` on uncommitted diffs) was auto-approved if the Bash pattern matched.

The only safety nets under `bypassPermissions` were the post-merge git audit trail and the post-merge background review. Both are strictly post-hoc; neither can stop a destructive or exfiltrating call before it executes.

Anthropic released Claude Code auto mode on 2026-03-24. Auto mode replaces the glob-based allowlist with a **per-call Sonnet 4.6 classifier gate**: every Bash / Edit / Write / MCP invocation not matching a fast-path `permissions.allow` entry is scored against the configured `autoMode.environment` trust envelope. Destructive or exfiltrating actions are soft-denied and surfaced as `PermissionDenied` events. Routine actions (reads, local writes, `git push` to working branch, `pytest`, `ruff`, repo-declared installs) are auto-approved.

Critically, soft-denies can be cleared by **User Intent**: when the conversation context (task packet, user turn, plan step) names the exact action, the classifier treats it as sanctioned. This is the mechanism that lets the fleet keep moving under a genuine runtime policy check — the trust model is "sanctioned by conversation evidence," not "sanctioned by glob match."

During the rollout, the review lane respawned as `bypassPermissions` despite `defaultMode: "auto"` being set in the committed shared settings (session 2026-04-20, issue #2685). Investigation revealed that while `permissions.defaultMode` is documented as the enablement flag, the actual CLI activation requires `--permission-mode auto` on the launch command. Without the flag, auto mode's `defaultMode` value is a **routing default only, not an enablement flag** — the classifier gate does not engage, and `PermissionDenied` events are never emitted. This is a load-bearing discovery: without the activation flag, every settings-level artifact, rule file, ADR, and operator guideline codifying "auto mode" is silently ineffective on any lane that does not launch with the flag.

## Decision

**Adopt Claude Code auto mode as the fleet-wide permission model for every Claude Code lane — author, analyst, orchestrator, review, ops, browser, flex — replacing `bypassPermissions` entirely.**

Adoption has two load-bearing components, both mandatory:

1. **`permissions.defaultMode: "auto"` in the shared `.claude/settings.json`** — routing default.
2. **`--permission-mode auto` on every CLI launch surface** — activation flag, without which `defaultMode: "auto"` is silently ineffective.

Both surfaces are locked down with structural tests:

- `tests/unit/test_steward_session.py::TestPermissionModeAuto` asserts every `$CLAUDE_BIN` launch line in `.claude/tmux/steward-session.sh` carries `--permission-mode auto`. Adding a new lane without the flag fails the test.
- `tests/unit/test_review_lane_runner.py::TestInvokeReviewPermissionMode` mocks `subprocess.run` and asserts the argv list passed to `claude` from `scripts/internal/review_lane_runner.py::invoke_review` contains `--permission-mode auto`. Any future headless launch surface (plan-review adapters, one-shot `claude --print` invocations, batch review harnesses) must add a parallel structural test.

The decision codifies five supporting choices:

- **Trust envelope lives in user scope only.** `autoMode.environment` is read from `~/.claude/settings.json`; shared project settings are treated as untrusted input and cannot extend the envelope. The operator maintains the user-scope block manually on each lane host.
- **`permissions.allow` fast path retained.** The hot set of infrastructure files (`.claude/skills/**`, `.claude/rules/**`, `.claude/settings.json`, `.claude/hooks/**`, `MEMORY.md`, `plans/**`, repo source trees) and the narrow-Bash toolchain (`git *`, `gh *`, `make *`, `uv run *`, `python -m pytest *`) skip the classifier entirely. Open-ended interpreters (`python *`, `tmux *`) are intentionally excluded from the fast path per #2304.
- **`PermissionDenied` event hook wired.** `.claude/hooks/permission-denied-log.sh` logs denials locally. Ops-alert integration for denial spikes is a tracked follow-up (TODO in rule 80, not gated on this ADR).
- **Post-hoc safety nets retained.** Auto mode is a runtime gate, not a replacement. Git audit trail (`git log --follow .claude/settings.json .claude/autoMode.defaults.reference.json`), Codex CLI pre-merge review + `reviewing-changes` advisory status, and the `post-merge-review` background Explore agent all continue to run. The combination of runtime classifier + durable git history + post-merge review is strictly stronger than any layer alone.
- **Classifier-default drift snapshot committed.** `.claude/autoMode.defaults.reference.json` is the committed snapshot of classifier defaults; it is regenerated after Claude Code upgrades and reviewed as a security-relevant diff.

Operator-facing guidance (how to extend the trust envelope, how to read denials, when to file a follow-up rule) lives in `.claude/rules/80_permission_model.md`. This ADR does not duplicate that text; the rule is the canonical operator spec and remains load-bearing on any permission-model change.

## Consequences

**Runtime behavior:**

- Force-push, prod deploys, `curl | bash`, exfiltrating writes, and irreversible local destruction are **soft-denied unless explicitly intended**. Under `bypassPermissions` all four were allowed.
- Self-modification of `.claude/settings.json` is **classifier-gated using conversation intent** instead of routed through the legacy sensitive-file dialog (#2249). Task packets that name the exact settings change clear the soft-deny via User Intent.
- Routine reads, local writes, `pytest`, `ruff`, and `git push` to working branch remain auto-approved (either via fast-path allow patterns or classifier auto-approval).

**Cost and latency tradeoff:**

- Per-call Sonnet 4.6 classifier invocation for every gated tool call not on the fast path. Anthropic currently documents auto mode as "not recommended for production"; the fleet accepts the cost given the scale of autonomous multi-lane operation, and the tradeoff is reassessed at pricing inflection points.
- The `permissions.allow` fast path exists precisely to contain classifier cost for the hot set of infrastructure edits.

**Surface-specific consequences:**

- **Sensitive-file prompts (#2249) are obsolete.** Auto mode does not use the legacy dialog; self-modification is classifier-gated. The classifier's "Self-Modification" soft_deny is cleared via task-packet intent.
- **`acceptEdits` and `dontAsk` remain rejected.** `acceptEdits` stalls on unlisted Bash/MCP; `dontAsk` causes silent failures (#2254). Neither is a viable fallback.
- **Shared-settings override is not available.** User-scope `autoMode` soft-denies cannot be cleared from shared project settings — the classifier treats shared files as untrusted input. Fixes route to user scope per the operator guideline in rule 80.
- **Rollout requires fleet restart.** Landing the activation flag alone does not activate auto mode on running lanes. Existing sessions continue in their launched mode until respawn. Restart discipline is the operator's responsibility; see #2685 for the discovery context that made this explicit.

**Structural-test consequences:**

- Every new fleet lane (whether added to `steward-session.sh` or a new headless launch surface) must be covered by a `TestPermissionModeAuto`-family test before the surface ships. The tests are the load-bearing enforcement; the rule-80 text alone is not sufficient (the #2685 discovery proved this).

**Observability and governance:**

- `PermissionDenied` denial rate is an ops-alert candidate. Rule 80 recommends opening a follow-up to extend `autoMode.allow` if denial rate exceeds ~5% of tool calls sustained. That follow-up is tracked outside this ADR.
- Any future PR touching `permissions.allow`, `defaultMode`, or `.claude/autoMode.defaults.reference.json` is a security-relevant diff and reviewed accordingly.

## Alternatives considered

1. **Keep `bypassPermissions`.** Rejected. No runtime gate on destructive or exfiltrating actions; self-modification routed through the legacy sensitive-file dialog (#2249) caused repeated lane stalls. The combined post-hoc safety nets (git history, post-merge review) are strictly weaker than auto mode + those same post-hoc nets.
2. **`acceptEdits` mode.** Rejected. Stalls on unlisted Bash/MCP invocations — the fleet's autonomous throughput depends on wide tool-call coverage, and `acceptEdits` does not cover that surface.
3. **`dontAsk` mode (trialed #2254).** Rejected. Silent failures on unrecognized patterns caused undiagnosable lane stalls and wedged PRs without surfacing the denial reason.
4. **`--dangerously-skip-permissions` + operator-mandated denial audit.** Rejected. No runtime gate at all; equivalent to `bypassPermissions` minus the sensitive-file dialog. Explicitly forbidden by the operator guideline in rule 80 ("never add `--dangerously-skip-permissions`... to work around a denial").
5. **Adopt auto mode but rely solely on `permissions.defaultMode: "auto"` without the CLI activation flag.** Rejected after #2685 discovery. `defaultMode` is a routing default only; without `--permission-mode auto` the classifier gate does not engage. Omitting the flag produces the worst outcome: settings artifacts and ADRs encode "auto mode" discipline, but the runtime gate is silently inactive.
6. **Extend `autoMode.environment` via shared project settings.** Rejected (Anthropic-side). The classifier refuses to merge `autoMode` blocks from shared files because they are writable by any lane or PR. User-scope only is the correct trust boundary.

## Open questions

1. **Ops-alert wiring for `PermissionDenied` events.** Currently local-log only via `.claude/hooks/permission-denied-log.sh`. Wiring denials through to Telegram / ops alert channel so operators see spikes in near-real-time is a tracked follow-up. Not blocking on this ADR. Rule 80 records the TODO.
2. **Custom `autoMode.allow` and `autoMode.soft_deny` rules.** Out of scope for this ADR. Adding lane-specific or project-specific overrides is a separate decision deferred to operator until a concrete false-positive pattern emerges post-rollout.
3. **Pricing-inflection reassessment.** Per-call Sonnet 4.6 classifier cost is accepted for now. If Anthropic promotes auto mode from research preview to production-supported (or conversely, if pricing shifts make per-call classifier economically unattractive at fleet scale), the tradeoff is re-evaluated. No hard trigger; operator discretion.

## Source evidence

- **Operator-facing spec:** `.claude/rules/80_permission_model.md` (this ADR is the decision-capture peer; rule 80 is the operator guidance).
- **Activation-flag discovery:** issue #2685 ("fix(ops): auto mode inactive — launch commands missing `--permission-mode auto` flag"; closed 2026-04-21T02:30:55Z). Discovery surfaced during review-lane restart in session 2026-04-20.
- **Structural tests:**
  - `tests/unit/test_steward_session.py::TestPermissionModeAuto` — enforces flag on every tmux-script `$CLAUDE_BIN` launch.
  - `tests/unit/test_review_lane_runner.py::TestInvokeReviewPermissionMode` — enforces flag on headless `subprocess.run` launch from `scripts/internal/review_lane_runner.py::invoke_review`.
- **Classifier-defaults snapshot:** `.claude/autoMode.defaults.reference.json` + sibling README.
- **Historical alternatives evidence:**
  - #1708 — original permission stall fix (SKILL.md) under `bypassPermissions`.
  - #1927 — expanded auto-accept to full infrastructure set under `bypassPermissions`.
  - #2249 — sensitive-file dialog stalls on `.claude/settings.json` self-modification.
  - #2254 — `dontAsk` trial + revert (silent failures).
  - #2304 — narrow broad Bash auto-accept patterns (open-ended interpreters excluded from fast path).
- **Related infrastructure protection:** `.claude/rules/75_worktree_protection.md`.

## Phase 2 Decision Inputs

**Portability readiness:** Neutral. Auto mode is a Claude Code substrate feature — it travels with the harness to any target repo that adopts Claude Code, but the `autoMode.environment` user-scope block is operator-host-specific and must be re-installed per host. The structural tests (`TestPermissionModeAuto`, `TestInvokeReviewPermissionMode`) are a portable pattern — any target-repo launch surface gets the same enforcement discipline for free.
**Meta-layer need:** no change. The permission model is a substrate primitive; no steward meta-layer is required to use it.
**Kill signal for primitive(s) named:** no. Auto-mode adoption does not kill any primitive; it is a prerequisite for every primitive operating under a runtime policy gate.
**Re-evaluation needed in Phase 3:** yes, soft trigger on two conditions: (a) Anthropic promotes auto mode from research preview to production-supported (pricing and SLA posture may change); or (b) classifier default drift observed via `.claude/autoMode.defaults.reference.json` exceeds a material threshold (e.g., soft_deny categories expand meaningfully). Recommended evaluation window: 6 months post Phase 2 close, or immediately when upstream changes land, whichever sooner.
**Surprise finding:** `defaultMode: "auto"` in settings is a routing default, not an enablement flag — without `--permission-mode auto` on the CLI activation surface, auto mode is silently inactive. The discovery (#2685) reinforces the load-bearing-ownership lint pattern (§10.9 Pattern 9 / 9a): a single settings artifact encoding a policy is insufficient if the activation path is not structurally tested. The `TestPermissionModeAuto` / `TestInvokeReviewPermissionMode` coverage is the correct codification of this lesson; any future load-bearing policy flag should carry a parallel structural test at every launch surface.
**Disposition:** open (pending Phase 0 kickoff filing)
