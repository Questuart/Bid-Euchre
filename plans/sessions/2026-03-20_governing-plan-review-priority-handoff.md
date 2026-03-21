# Governing Plan Review-Priority Update Handoff

**Lane Direction:** Use a free `author-*` lane for this docs-only PR. Keep the branch isolated and commit only the governing-plan change. Do not include the local redesign session plans or handoff files from this checkout.

**Date:** 2026-03-20
**Goal:** Commit, push, and open a PR for the governing-plan update that moves the primary PR review architecture to the front of platform work and defers `SendMessage`-style lane delivery as a later convenience layer.

## Scope

Only ship:

- `plans/agent_ops/governing_plan.md`

## Explicitly Out Of Scope

Do not include:

- `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
- `plans/sessions/2026-03-20_pre-merge-review-redesign-*.md`
- any review-runtime code
- any hook or settings changes

## Required Content

The PR should preserve these decisions:

1. primary PR review architecture moves into early platform work (`Platform-2` / `Platform-3`)
2. `Platform-3` owns durable review request / verdict state and merge-safety substrate
3. `Platform-12` is later second-model extension work on top of that substrate
4. `SendMessage`-style lane delivery is explicitly deferred as a convenience layer, not review truth

## Execution Guidance

1. Start from a fresh worktree / branch off `origin/main`.
2. Reproduce only the `governing_plan.md` diff.
3. Review the final diff carefully to ensure no session-plan files are staged.
4. Commit and push.
5. Open a docs-only PR with a concise summary of the roadmap change.

Suggested commit message:

- `docs: front-load primary PR review architecture`

## Validation

Minimum:

- `git diff --stat origin/main...HEAD`
- `git diff -- plans/agent_ops/governing_plan.md`
- `rg -n "Platform-3|Platform-12|SendMessage|review substrate|merge safety" plans/agent_ops/governing_plan.md`

Optional:

- `make docs-check`

## PR Notes

The PR body should call out:

- primary PR review substrate now belongs to early platform work
- second-model review remains later and advisory-first
- `SendMessage` integration is intentionally deferred on top of the durable review bus

## Exit Criteria

- one docs-only PR is opened
- only `plans/agent_ops/governing_plan.md` is included
- the roadmap now clearly front-loads primary PR review architecture
