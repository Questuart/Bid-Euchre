# Permission Model — Auto Mode

> The fleet runs under Claude Code **auto mode** (released 2026-03-24). Each
> tool call is gated through a Sonnet 4.6 classifier that blocks destructive
> or exfiltrating actions and auto-approves routine work. This document
> describes the model, why we chose it, and how to extend the trust envelope.

## Summary

- `permissions.defaultMode` in the shared `.claude/settings.json` is `"auto"`.
- Every `Bash`/`Edit`/`Write`/MCP call is scored by a classifier that reads
  the task transcript and the configured `autoMode.environment`.
- Routine actions (reads, local file writes, `git push` to working branch,
  `pytest`, `ruff`, repo-declared installs) are auto-approved.
- Destructive and exfiltrating actions (force-push, prod deploys, `curl |
  bash`, self-modification without intent, credential exfil, scope escalation
  outside the repo) are soft-denied and surfaced as `PermissionDenied`
  events.
- Soft-denies can be overridden by **User Intent** — if the conversation
  context (a task packet, a user turn, a plan step) names the exact action,
  the classifier treats it as sanctioned.
- Committed defaults snapshot lives at
  `.claude/autoMode.defaults.reference.json` for drift detection — see the
  sibling README.

## Activation — how auto mode actually turns on

While auto mode is still in research preview, `defaultMode: "auto"` in
`.claude/settings.json` is a **routing default**, not an **enablement flag**.
The CLI only activates auto mode when the launch command includes
`--permission-mode auto`. Without the flag, a session whose `defaultMode` is
`"auto"` still starts in `bypassPermissions` — the classifier gate does not
engage and `PermissionDenied` events are never emitted.

Two consequences for the fleet (#2685):

1. **Every tmux pane launched by `steward-session.sh` must include
   `--permission-mode auto`.** The launcher script (`.claude/tmux/steward-session.sh`)
   passes the flag to each `$CLAUDE_BIN` invocation — orchestrator, ops, review,
   all four analyst/author/browser/flex panes, 19 launches total. On
   orchestrator restarts the flag is placed before `$ORCH_CHANNEL_FLAGS` so the
   channel-flags expansion is deterministic.
2. **Every headless subprocess launch must include the flag explicitly.**
   The autonomous review coordinator spawns `claude` via `subprocess.run` in
   `scripts/internal/review_lane_runner.py::invoke_review`. That argv list
   must carry `--permission-mode auto` alongside `--agent steward-review`.
   Any future headless launch surface (plan-review adapters, one-shot
   `claude --print` invocations, batch review harnesses) must carry the flag
   too — there is no implicit inheritance from shared settings.

Both surfaces are locked down with structural tests:

- `tests/unit/test_steward_session.py::TestPermissionModeAuto` asserts every
  `$CLAUDE_BIN` launch line in the tmux script contains the flag. Adding a
  new lane without the flag fails the test.
- `tests/unit/test_review_lane_runner.py::TestInvokeReviewPermissionMode`
  mocks `subprocess.run` and asserts the argv list passed to `claude`
  contains `--permission-mode auto`.

**Rollout note:** Landing the flag alone does not activate auto mode on
running lanes — existing sessions continue in their launched mode until they
restart. The operator must restart the fleet (or individual lanes) for the
fix to take effect. See #2685 for discovery context; the discovery was made
during review-lane restart in session 2026-04-20, when the lane respawned as
`bypassPermissions` despite `defaultMode: "auto"` being set in the committed
settings.

### Model-tier activation constraint

`--permission-mode auto` only engages the Sonnet 4.6 classifier when the
lane's active session is Opus-tier (Claude Opus 4.6 or 4.7+). A Sonnet-tier
or Haiku-tier session launched with `--permission-mode auto` either ignores
the flag or silently falls back to `bypassPermissions`; in either case, the
classifier does not gate tool calls and `PermissionDenied` events are never
emitted.

The launch-flag choice is therefore a **function of the lane's model tier**,
not a fleet-wide constant:

| Model tier | Required launch flag | Effective permission mode |
|------------|---------------------|---------------------------|
| Opus 4.6+ | `--permission-mode auto` | `auto` (classifier-gated) |
| Sonnet 4.6+ | `--dangerously-skip-permissions` | `bypassPermissions` |
| Haiku 4.5+ | `--dangerously-skip-permissions` | `bypassPermissions` |

**Launch-script implication.** `.claude/tmux/steward-session.sh` and
`scripts/internal/review_lane_runner.py::invoke_review` currently hardcode
`--permission-mode auto` for every lane (the structural tests above lock
this in). That is correct for the current fleet — 100% Opus 4.7 — but is a
pending fix when any lane moves to Sonnet or Haiku for token-economy or
dispatch reasons. The fix must read per-lane model-tier config and emit the
correct flag. This change is tracked as Primitive G Phase 0 closeout under
the 7-surfaces inventory (issue #2767).

**Structural-test implication.** `TestPermissionModeAuto` and
`TestInvokeReviewPermissionMode` both assert `--permission-mode auto`
unconditionally. When the launch scripts gain model-tier conditioning, the
tests must be rewritten as `TestPermissionModeByModelTier` asserting the
correct flag per lane's declared model. Landing launch-script conditioning
without the test rewrite will break CI; landing the test rewrite without
the launch-script conditioning silently regresses enforcement on the
current Opus fleet. **The two changes must ship together.**

**Never substitute launch flags for model-tier intent.** Passing
`--permission-mode auto` to a non-Opus lane is the worst outcome: the flag
and settings encode auto-mode discipline, but the runtime gate is silently
inactive. The explicit `--dangerously-skip-permissions` launch makes the
reduced safety envelope legible at every observation point (log output,
`gh pr checks`, operator-readable launch command). Operators MUST NOT
cross-wire these flags to mask model-tier selection.

**Cross-reference:** ADR 006 §"Model tier interaction" captures the
decision record and the safety envelope per-tier comparison table.

## Why auto mode over `bypassPermissions`

The fleet previously ran `bypassPermissions`, which auto-approves everything
except Claude Code's built-in "sensitive file" prompts. This kept lanes
moving but provided no runtime gate on destructive actions — the only
safety net was the post-merge git audit trail.

Auto mode is strictly safer along the axes that matter for autonomous
multi-lane operation:

| Axis | `bypassPermissions` | `auto` |
|------|--------------------|--------|
| Force-push, prod deploys, `curl \| bash` | Allowed; relies on hook gates | Soft-denied unless explicitly intended |
| Exfiltration (push to external repo, unexpected outbound HTTP) | Allowed | Soft-denied |
| Self-modification of `.claude/settings.json` | Hard-coded sensitive-file prompt (`#2249`) | Gated by classifier using conversation intent |
| Irreversible local destruction (`rm -rf` of untracked files, `git reset --hard` on uncommitted work) | Allowed | Soft-denied |
| Routine reads, local writes, `pytest`, `git push` to working branch | Allowed | Auto-approved |

The tradeoff is per-call classifier latency and cost; in exchange we get a
runtime policy check that understands *what* the action is, not just which
glob pattern it matches. `allow` patterns in `permissions.allow` still
function as fast-path approvals for the hot set of tools.

Historical alternatives (`acceptEdits` stalls on unlisted Bash/MCP; `dontAsk`
causes silent failures per `#2254`) remain rejected for the same fleet
throughput reasons documented in those PRs.

## Where `autoMode.environment` lives

The classifier reads its trust envelope (`environment`) from **user scope
only** — `~/.claude/settings.json`. This is deliberate on Anthropic's side:
a shared project settings file is writable by any lane or PR, so the
classifier treats shared settings as untrusted input and refuses to merge
its `autoMode` block into the trust envelope.

Our user-scope block configures:

- **Trusted repo**: Questuart/Bid-Euchre (the fleet home).
- **Source control**: the Questuart GitHub org (PRs, issues, pushes).
- **Trusted internal domains / services**: Telegram Bot API (operator
  channel), Render (deploy platform), Codex CLI review endpoint.
- **Worktree/PR conventions**: persistent worktrees under
  `~/Projects/Bid-Euchre-meta/Bid-Euchre-steward-*`, branch push targets.

That block was installed by the orchestrator before this rule landed and is
**not** visible in any PR diff. Inspect it locally with:

```bash
claude auto-mode config    # merged view: user settings + defaults
claude auto-mode defaults  # defaults only (also snapshotted in this repo)
```

## Extending the environment when new trusted infra is added

When a new trusted endpoint is introduced (a new internal service, a new
cloud bucket, a new GitHub org), the operator edits `~/.claude/settings.json`
on each lane host to extend `autoMode.environment`. Because the file is
user-scoped it is outside git — keep a shared reference copy in operator
notes if the fleet spans multiple machines.

Do **not** attempt to add environment entries in the shared
`.claude/settings.json`. The classifier will ignore them, and the diff
creates a misleading impression that the trust envelope was widened.

Adding a custom `autoMode.allow` or `autoMode.soft_deny` rule is a separate
decision and out of scope for this rule's first cut — see Known Limitations
below.

## PermissionDenied events

When the classifier soft-denies a tool call, Claude Code emits a
`PermissionDenied` event. The fleet currently logs these locally via
`.claude/hooks/permission-denied-log.sh` (registered in
`.claude/settings.json`).

As of Primitive B-exec.α (B.6), each logged record is enriched with
three registry-lookup fields:

| Field | Source | Purpose |
|---|---|---|
| `approval_class_auto_mode` | `.claude/rules/tool_risk_registry.md` lookup | What the registry says the auto-mode gate is |
| `approval_class_bypass` | `.claude/rules/tool_risk_registry.md` lookup | What the registry says the bypass gate is |
| `registry_row_id` | `<file>:<line>` of the matched row | Back-pointer into the registry |

If no row matches the denied tool, all three fields are `null`. This
is the signal the B.6 lint (`agent_readability_lint.py check tool-risk`
rule TR4) uses to flag missing coverage.

> **TODO (follow-up PR):** wire `PermissionDenied` events through to the
> ops alert channel so operators see denial spikes in near-real-time. That
> PR is tracked separately from this mode flip — no change to
> `.claude/settings.json` hook registration is made in this PR beyond what
> was already in place.

## Tool-risk registry

The dual-envelope classification of every allow-listed tool lives in
`.claude/rules/tool_risk_registry.md`. That file is the *cross-envelope
classification table* — this file (`80_permission_model.md`) is the
*operational guide to auto mode*. They coexist and serve different
audiences:

- Read `80_permission_model.md` when you need to understand *why* auto
  mode is the chosen default, *how* the classifier gates tool calls,
  what `PermissionDenied` means, or operator guidelines for extending
  the `autoMode.environment`.
- Read `tool_risk_registry.md` when you need to know *what
  classification* a specific tool has under auto-mode and under bypass,
  or to identify destructive/exfil patterns that are never sanctioned.

**B.1 adaptive dispatch** (Primitive B.1) consumes
`tool_risk_registry.md` at dispatch-time to filter out lanes whose
envelope fails a task's required-tool set — that is the *only*
load-bearing runtime consumer of the registry; everything else is
documentation. Runtime tool-invocation gating remains with the
classifier.

**Lint enforcement:** `agent_readability_lint.py check tool-risk`
runs in CI and BLOCKs when:

- the registry file is missing (rule TR0),
- the registry has zero rows (rule TR1),
- a row has an empty or non-taxonomy envelope column (rule TR2),
- (WARN) a `reject`-under-bypass row lacks a Notes explanation (rule
  TR3),
- a `permissions.allow` entry has no covering registry row (rule TR4).

## Safety net: git audit trail + post-merge review

Auto mode is a runtime gate; it does not replace the project's existing
post-hoc safety nets. Both still apply:

- Every change to `.claude/settings.json` (and adjacent infra) is committed
  and pushed. `git log --follow .claude/settings.json` shows the full
  history, and `git log --follow .claude/autoMode.defaults.reference.json`
  shows every observed classifier-default change.
- PRs require CI and review before merge; `reviewing-changes` (advisory)
  and the review queue verdict (merge-gating) both run Codex CLI review.
- `post-merge-review` runs a background Explore agent on every merged PR;
  CRITICAL findings trigger immediate fix PRs.
- The orchestrator can revert any problematic change.

The combination of runtime classifier gating (auto mode) + durable git
history + post-merge review is strictly stronger than any one layer alone.

## Known limitations

- **Per-call latency and cost.** The classifier is a Sonnet 4.6 call per
  gated tool invocation. Anthropic currently documents auto mode as
  "not recommended for production"; for our fleet the cost is acceptable
  given the scale of autonomous operation, but it is a real tradeoff and
  worth reassessing at pricing inflection points.
- **Shared project settings cannot override a user-scope block.** If the
  user-scope `autoMode` block soft-denies a phrasing, no shared
  `.claude/settings.json` entry will unblock it. Fixes must go to user
  scope.
- **Sensitive-file prompts (`#2249`) are no longer relevant** — auto mode
  does not use the legacy sensitive-file dialog; self-modification is
  classifier-gated instead. The classifier's "Self-Modification" soft_deny
  can be cleared via User Intent (e.g., a task packet that names the exact
  `.claude/settings.json` change).
- **Classifier defaults may shift silently on upgrade.** Mitigated by the
  snapshot at `.claude/autoMode.defaults.reference.json`; regenerate after
  Claude Code upgrades and review the diff.

## Auto-accept `permissions.allow` scope (fast path)

The `permissions.allow` list is retained as a fast path: matching patterns
skip the classifier entirely. The list is scoped to the hot set of
infrastructure files agents routinely edit, plus standard toolchain Bash
patterns. Changes to this list remain a security-relevant diff regardless
of auto mode.

| Pattern | Purpose |
|---------|---------|
| `.claude/skills/**` | Skill definitions (workflow guidance) |
| `.claude/rules/**` | Rule files (this file, conventions) |
| `.claude/settings.json` | Hook config and permissions (self-modifying) |
| `.claude/hooks/**` | Hook scripts |
| `MEMORY.md` | Cross-session project memory |
| `plans/**` | Plan files (governing plans, sub-plans, sessions) |
| `src/**`, `tests/**`, `scripts/**`, `experiments/**`, `docs/**` | Project source, tests, and docs |
| Narrow Bash (`git *`, `gh *`, `make *`, `uv run *`, `python -m pytest *`, etc.) | Core toolchain, already gated by CI and branch protection |

Everything else routes through the classifier. Bash patterns intentionally
excluded (e.g., `python *`, `tmux *`) reflect a decision to keep
open-ended interpreters out of the fast path — see `#2304`.

## Operator guidelines

- **Monitor** permission-model changes via
  `git log .claude/settings.json .claude/rules/80_permission_model.md
  .claude/autoMode.defaults.reference.json`.
- **Review** any PR that touches `permissions.allow`, `defaultMode`, or
  the defaults reference snapshot — all are security-relevant diffs.
- **Observe denial rate after rollout.** If `PermissionDenied` exceeds ~5%
  of tool calls, open follow-up PRs adding `autoMode.allow` entries for
  the most common false positives.
- **Never add `--dangerously-skip-permissions` or flip `defaultMode` back
  to `bypassPermissions` to work around a denial.** Surface the denial to
  the orchestrator and let the User Intent override clear it, or file a
  follow-up to extend user-scope rules.

## References

- `#1708` — original permission stall fix (SKILL.md) under bypassPermissions
- `#1927` — expanded auto-accept to full infrastructure set under bypassPermissions
- `#2254` — dontAsk trial + revert (silent failures)
- `#2304` — narrow broad Bash auto-accept patterns
- `.claude/autoMode.defaults.reference.json` + sibling README — snapshot of
  classifier defaults for drift detection
- `.claude/rules/75_worktree_protection.md` — related infrastructure protection
