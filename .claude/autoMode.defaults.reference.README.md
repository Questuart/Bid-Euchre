# autoMode.defaults.reference.json — Versioned Classifier Baseline

## What this file is

`autoMode.defaults.reference.json` is a committed, versioned snapshot of the
**default** auto-mode classifier rules shipped with the current Claude Code
release. It captures the three top-level keys the classifier reads:

- `allow` — phrasings the classifier treats as auto-approve triggers
- `soft_deny` — phrasings the classifier treats as block triggers (unless
  overridden by user intent)
- `environment` — the trust envelope (trusted repo, source-control orgs,
  domains, buckets, internal services)

It is **not** a live config. Live auto-mode behavior is assembled from
user-scope `~/.claude/settings.json` (our project's source of custom
environment entries) merged with these defaults. This file exists purely as
a baseline for drift detection.

## Why we keep it

Claude Code ships new classifier defaults with every release. A silent
change to the default `soft_deny` set (for example, adding a new phrasing
that blocks a fleet workflow we rely on) would otherwise go unnoticed until
a lane stalled. Committing the snapshot means:

1. `git log --follow .claude/autoMode.defaults.reference.json` shows every
   change we have observed.
2. `git diff` on the file, after regeneration, surfaces exactly which
   allow/soft_deny/environment phrasings moved.
3. Reviewers on an upgrade PR see the classifier-rule delta alongside the
   code change that triggered the regeneration.

The shared project `.claude/settings.json` is **intentionally** excluded
from the classifier's `environment` merge — Anthropic chose user scope so
that shared repo settings cannot silently broaden the trust envelope. This
file therefore records defaults only; it is not where we add trusted infra.

## How to regenerate

```bash
claude auto-mode defaults | jq --sort-keys . > .claude/autoMode.defaults.reference.json
jq . .claude/autoMode.defaults.reference.json > /dev/null   # validate
```

`jq --sort-keys` gives a deterministic ordering so future diffs show only
semantic changes, not key-order churn.

## When to regenerate

- After any Claude Code upgrade (the CLI release notes call out classifier
  changes; regenerate to confirm and record the delta).
- Before an audit of current classifier defaults — regenerate first so the
  audit reads the latest snapshot.
- When debugging an unexpected `PermissionDenied` event, to confirm the
  soft_deny phrasings the classifier actually sees.

Do **not** regenerate this file as part of unrelated PRs. A drift-detection
artifact is only useful if its changes are intentional and reviewed.

## Related

- `.claude/rules/80_permission_model.md` — fleet permission model and where
  custom environment entries are configured (user scope only).
- `~/.claude/settings.json` — the user-scope `autoMode.environment` block
  that Claude Code actually reads. Not committed; out of git scope by design.
