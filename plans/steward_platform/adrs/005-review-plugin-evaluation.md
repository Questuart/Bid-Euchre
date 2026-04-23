# ADR 005 — Review Plugin Evaluation

**Status:** SEEDED (draft 8); filing at Phase 0 kickoff
**Primitive:** C (KB / ADR discipline), E (messaging/triage overlap)
**Supersedes:** none
**Seed source:** `plans/steward_platform/plugin_source_evaluation.md` §2 + §6.1 (analyst-a, 2026-04-23)

---

## Context

Anthropic's official `anthropics/claude-code/plugins/code-review` plugin overlaps steward's `scripts/internal/review_driver.py`. Draft 8 B.8 / ADR 005 commits to an ADR-level evaluation. Source read (2026-04-23 by analyst-a) shows the plugin is a 4-parallel-reviewer + Nx-validator-subagent orchestration in ~109 lines of command prompt at `plugins/code-review/commands/code-review.md`, not the "5 specialized reviewers with 0-100 confidence scoring" marketing framing the README implies.

Key source-derived observations:

- **4 parallel reviewers, not 5:** two redundant Sonnet CLAUDE.md-compliance reviewers + two Opus bug-detection agents. No "git history analyzer" reviewer in source despite README claim.
- **No 0-100 confidence scoring in source.** The README's "threshold 80 default" framing is post-hoc documentation. The actual noise-suppression mechanism is a two-pass flag→validate filter implemented via Nx parallel validator subagents.
- **Plugin has no SHA-bound verdict, no merge-guard, no scope-lock, no auto-fix commit loop, no status-context publication** — steward's `review_driver.py` carries all six.

See analyst-a's §2 for full source snippets.

## Decision

**Retain `review_driver.py` as the sole review orchestrator.** Cherry-pick two patterns into it as Phase-1+ improvements (not Phase-0 blockers):

1. **Parallel-reviewer fan-out** with Codex CLI + N Opus subagent reviewers on different foci (e.g., "scan diff for bugs", "verify scope lock", "audit CLAUDE.md compliance"). Feature-flagged; rollback via flag flip (Pattern 7 reversibility).
2. **Validator-subagent pass for false-positive suppression** before writing findings to the review report. Addresses the 50-106 precheck false-positive pattern recent plan PRs keep hitting.

**Do not install the plugin.**

Draft 8 language around "0-100 confidence scoring" (if any survives) should be amended to "validator-subagent filter pass" since the former is post-hoc documentation, not source behavior.

## Consequences

- `review_driver.py` gains an optional multi-reviewer mode (feature-flagged; single-Codex-CLI remains Phase 0 baseline).
- Phase 1+ experimentation can land the parallel-reviewer + validator-subagent pattern without blocking Phase 0 kickoff.
- SHA-bound verdict, merge-guard, scope-lock, auto-fix loop, and status-context publication — all steward-specific — are preserved.
- Cloud `/autofix-pr` remains evaluate-only (separate consideration; operator-dependent since it moves PR fix loop to cloud and changes operator-presence model).

## Alternatives considered

1. **Install the plugin + delete `review_driver.py`.** Rejected. Plugin does not carry SHA-bound verdicts, merge-guard integration, auto-fix commit loop, scope-lock enforcement, or `reviewing-changes` status-context publication. Retrofitting all six is more work than the status quo.
2. **Leave `review_driver.py` unchanged.** Rejected. The validator-subagent pass is a clean noise-reduction win worth implementing given the recurring precheck false-positive pattern.
3. **Cloud `/autofix-pr` as replacement for local review_driver.** Deferred to operator; out of scope for this ADR.

## Open questions

1. Should the validator-subagent cherry-pick ship during Phase 0 or strictly Phase 1+? Analyst-a's recommendation: defer to operator; not a Phase 0 blocker and neutral against kill criteria.

## Source evidence

- Plugin repo: `https://github.com/anthropics/claude-code/tree/main/plugins/code-review`
- Command file read: `plugins/code-review/commands/code-review.md` (109 lines)
- Plugin manifest: `.claude-plugin/plugin.json` (v1.0.0, author Boris Cherny, MIT license via `anthropics/claude-code` repo license)
- Evaluation artifact: `plans/steward_platform/plugin_source_evaluation.md` §2 (analyst-a, 2026-04-23)

## Phase 2 Decision Inputs

**Portability readiness:** Improved (rejecting wholesale adoption keeps the review pipeline seam thin).
**Meta-layer need:** no change.
**Kill signal for primitive(s) named:** no.
**Re-evaluation needed in Phase 3:** no (Phase 1+ cherry-pick is an enhancement, not a re-evaluation).
**Surprise finding:** README 0-100 scoring / 5-specialized-reviewers framing exceeds actual source behavior — reinforces ADR discipline requiring source-snippet citations for Tier S adoption decisions.
**Disposition:** open (pending Phase 0 kickoff filing)
