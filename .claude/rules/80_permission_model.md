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

**Activation is further conditioned on the lane's model tier** — see the
next section ("Model-tier activation constraint") for the canonical table
and the `.claude/lane_models.json` config that drives per-lane flag
selection. The short version: Opus lanes get `--permission-mode auto`,
Sonnet/Haiku lanes get `--dangerously-skip-permissions`. The two launch
surfaces below emit the tier-correct flag for each lane they launch.

Two consequences for the fleet (#2685, refined by #2767):

1. **Every tmux pane launched by `steward-session.sh` emits the
   tier-correct launch flag per `.claude/lane_models.json`.** The launcher
   script (`.claude/tmux/steward-session.sh`) routes every `$CLAUDE_BIN`
   invocation — orchestrator, ops, review, all four analyst/author/browser/
   flex panes, 19 launches total — through the
   `permission_mode_flag_for_lane` helper. The helper reads the canonical
   config and emits either `--permission-mode auto` (Opus) or
   `--dangerously-skip-permissions` (Sonnet/Haiku). On orchestrator restarts
   the helper invocation is placed before `$ORCH_CHANNEL_FLAGS` so the
   channel-flags expansion is deterministic.
2. **Every headless subprocess launch emits the tier-correct flag
   explicitly.** The autonomous review coordinator spawns `claude` via
   `subprocess.run` in `scripts/internal/review_lane_runner.py::invoke_review`.
   That argv list splices the fragment returned by
   `lane_models.permission_mode_args_for_lane(LANE_ID)` — `["--permission-mode",
   "auto"]` for Opus, `["--dangerously-skip-permissions"]` for Sonnet/Haiku —
   alongside `--agent steward-review`. Any future headless launch surface
   (plan-review adapters, one-shot `claude --print` invocations, batch
   review harnesses) must route through the same helper — there is no
   implicit inheritance from shared settings.

Both surfaces are locked down with structural tests:

- `tests/unit/test_steward_session.py::TestPermissionModeByModelTier`
  asserts every `$CLAUDE_BIN` launch line in the tmux script calls
  `permission_mode_flag_for_lane <lane-id>`, and functionally verifies the
  helper emits the tier-correct flag for Opus / Sonnet / Haiku / missing /
  invalid configs. A sibling `TestLaneModelsJson` validates the canonical
  `.claude/lane_models.json` config, and `TestLaneModelsLoader` validates
  the Python loader shared with the review runner.
- `tests/unit/test_review_lane_runner.py::TestInvokeReviewPermissionModeByModelTier`
  mocks `subprocess.run` and asserts the argv list passed to `claude`
  contains `--permission-mode auto` when the review lane is declared Opus
  and `--dangerously-skip-permissions` when declared Sonnet/Haiku — in
  both the mocked-helper case and an end-to-end case through the real
  `lane_models` loader against a tmp-path config.

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

**Canonical config file.** `.claude/lane_models.json` is the source of
truth for per-lane model tier. Schema:

```json
{
  "_schema_version": 1,
  "lanes": {
    "<lane-id>": {"model": "opus" | "sonnet" | "haiku"},
    ...
  }
}
```

Two loaders read this file and MUST stay behaviorally consistent:

- **Shell loader** — `permission_mode_flag_for_lane` in
  `.claude/tmux/steward-session.sh` (uses an inline `python3 -c` to parse
  the JSON; falls back to Opus on any error).
- **Python loader** — `scripts/internal/lane_models.py`, consumed by
  `scripts/internal/review_lane_runner.py::invoke_review`.

Unknown or missing lanes default to Opus. This is the safest failure mode
for the current 100%-Opus fleet; new lanes are expected to declare a tier
explicitly. Changing the default (e.g., to block launches on missing
entries) is itself a security-relevant diff and must be reviewed.

**Launch-script implementation (resolved by #2767).** Both launch surfaces
— `.claude/tmux/steward-session.sh` and `scripts/internal/review_lane_runner.py::invoke_review`
— now route every launch through a per-lane helper that reads
`.claude/lane_models.json` and emits the tier-correct flag. The shell and
Python loaders share the config file and the same invalid-tier coercion
semantics. Structural tests (`TestPermissionModeByModelTier`,
`TestInvokeReviewPermissionModeByModelTier`, `TestLaneModelsJson`,
`TestLaneModelsLoader`) lock in the helper wiring, the config schema, and
the emitted argv for each tier.

**Operator workflow for tier changes.** Moving a lane to Sonnet or Haiku
(for token-economy or dispatch reasons) is a one-file change:

```bash
# 1. Edit .claude/lane_models.json — set "model" to the desired tier.
# 2. Commit + merge via normal PR workflow (security-relevant diff).
# 3. Restart the lane so it relaunches with the new flag:
tmux respawn-pane -k -t steward:<window>.<pane> --continue
```

The tmux launcher re-reads the config on each launch; no cached state to
flush. `TestLaneModelsJson` enforces that every listed lane has a valid
model, so typos (e.g., `"sonet"`) fail CI before a lane can silently fall
back to Opus.

**Never substitute launch flags for model-tier intent.** Passing
`--permission-mode auto` to a non-Opus lane is the worst outcome: the flag
and settings encode auto-mode discipline, but the runtime gate is silently
inactive. The explicit `--dangerously-skip-permissions` launch makes the
reduced safety envelope legible at every observation point (log output,
`gh pr checks`, operator-readable launch command). Operators MUST NOT
cross-wire these flags to mask model-tier selection. The per-lane helper
pattern makes cross-wiring structurally impossible — edit the config, not
the launch command.

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

> **TODO (follow-up PR):** wire `PermissionDenied` events through to the
> ops alert channel so operators see denial spikes in near-real-time. That
> PR is tracked separately from this mode flip — no change to
> `.claude/settings.json` hook registration is made in this PR beyond what
> was already in place.

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
