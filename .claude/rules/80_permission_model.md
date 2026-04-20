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
