# Harness Assumptions

> Load-bearing assumptions about the Claude Code harness that the steward
> fleet depends on. Each entry follows the format
> `assumption → observation supporting → brittleness signal → refresh trigger`
> per ADR G10 lines 172–177 and the B.9a pilot shape §7.3 step 5.
>
> The goal is to make harness behavior that the fleet assumes *falsifiable*:
> if a Claude Code release changes the behavior, we catch it by re-running
> the recorded probe, not by observing a mysterious behavioral regression
> weeks later.
>
> **Commit policy (ADR 010):** promoted assumptions only. Session-level
> observations land in `_candidates/` until promoted.
>
> **Schema.** Each H3 entry (`### Entry N — <name>`) carries four required
> fields:
>
> - **Assumption:** one sentence claim about harness behavior
> - **Observation:** evidence the assumption currently holds
> - **Brittleness signal:** machine-observable trigger for "assumption
>   may have broken"; must contain a backtick-quoted grep/command, a
>   `make <target>` / CI job name, or a named `.claude/hooks/<file>`
>   precondition
> - **Refresh trigger:** when to re-verify (e.g., Claude Code upgrade,
>   tmux version change, every Phase 0 Readiness pass)
>
> The lint rule `HA1` in `scripts/internal/agent_readability_lint.py`
> verifies each `Brittleness signal` field contains at least one
> machine-observable form.

---

## Active entries

### Entry 1 — `--system-prompt-file` replaces the default in interactive + print modes

**Recorded:** 2026-04-24 (B.9a pilot, author-d)
**Claude Code version:** 2.1.114 (Opus 4.7, 1M context)
**Scope:** fleet system-prompt activation mechanism (B.9a, B.9b)

**Assumption:** Passing `--system-prompt-file <path>` on a `claude` invocation
replaces Claude Code's default system prompt with the file's contents verbatim,
in both interactive sessions (the steward lane deployment model) and `-p` /
`--print` mode. This is a stronger claim than the `--help` listing of
`--system-prompt <prompt>` — the `-file` variant is mentioned only in
`--bare`'s help text (`--system-prompt[-file]`) but exists and behaves as the
replacement flag.

**Observation:** Print-mode probe (B.9a pilot, 2026-04-24).

Control (no flag):
```
$ claude -p --permission-mode auto "describe your role in one sentence"
I'm the steward-author-d lane — a bounded implementation lane for the
Bid Euchre steward platform that executes one delegated task packet
at a time.
```

With `--system-prompt-file`:
```
$ claude -p --permission-mode auto \
    --system-prompt-file .claude/system_prompts/analyst.md \
    "describe your role in one sentence"
I shape ambiguous, multi-lane, or flagged work into dispatch-ready
artifacts — sub-plans, execution briefs, issue packages, and shaping
documents with named verification surfaces — so the orchestrator can
delegate execution cleanly without mixing shaping and implementation.
```

With both `--agent steward-analyst` and `--system-prompt-file` (B.9b target
shape, model-tier fleet launch):
```
$ claude -p --agent steward-analyst --permission-mode auto \
    --system-prompt-file .claude/system_prompts/analyst.md \
    "describe your role in one sentence"
I shape ambiguous, multi-lane, or flagged work into dispatch-ready
packages — sub-plans, execution briefs, issue packages, and restart
handoffs — for the orchestrator to route, without ever editing
product code or dispatching authors directly.
```

Interactive-mode probe (B.9a pilot, 2026-04-24). Spawned
`claude --permission-mode auto --system-prompt-file /tmp/b9a_analyst.md`
in a tmux-isolated session from `Bid-Euchre-steward-author-scratch`:
```
❯ describe your role in one sentence

⏺ I shape ambiguous or multi-lane work into dispatch-ready packages —
  investigating, drafting durable artifacts (sub-plans, execution
  briefs, issue packages), and returning them to the orchestrator
  with a named verification surface.
```

All three responses paraphrase the analyst.md opening one-liner + content
from its Operating Rules + Constraints sections. The control response
(no flag) is audibly different — it reflects the author-d agents-file
description instead. Replacement fires in both modes. ClaudeLog's
unverified claim that `--system-prompt-file` is print-only (shape §7.3)
does **not** hold on Claude Code 2.1.114.

**Brittleness signal:** `grep -c '\-\-system-prompt-file' .claude/tmux/steward-session.sh`
tracks B.9b rollout (absent until B.9b lands); once present the count
should match the lane-launch count. CI check:
`tests/unit/test_steward_session.py::TestSystemPromptFile` (to be added
in B.9b Phase 1) asserts the flag threads through per-lane launch paths.
Any of the following would falsify the entry:

1. `claude -p --system-prompt-file X "describe your role"` returns
   generic "I am an AI assistant..." voice instead of the file's content.
2. Interactive session with `--system-prompt-file X` returns generic
   default voice (the ClaudeLog claim becomes true on a future release).
3. `claude --help` removes `--system-prompt` entirely, or the `--bare`
   help text drops the `[-file]` variant mention.
4. An active `.claude/system_prompts/<archetype>.md` file is present
   yet the archetype-keyword grep on a lane's paste buffer fails the
   B.9b Phase 1 Validation launch-smoke.

**Refresh trigger:** Claude Code release notes (release-notes page,
changelog, `claude --version` bump) mentioning changes to
`--system-prompt`, `--system-prompt-file`, `--append-system-prompt-file`,
`--agent`, or `--bare` semantics; B.9b Phase 1 Validation telemetry
(prompt-policy-cited-in-trace rate) drops unexpectedly after a Claude
Code upgrade; any operator report of a lane "sounding default" after
restart despite `.claude/system_prompts/<archetype>.md` being current
on origin/main.

**Re-run procedure.** Re-execute the three print-mode probes above + the
tmux interactive probe. Expected: responses paraphrase the analyst.md
opening and Operating Rules. Observed ≠ expected → file a blocker,
re-shape B.9b activation.

### Entry 2 — Session-death threshold — spawned agents die silently at ~15 min / ~700 KB

**Assumption:** A spawned agent (via `Agent` tool) that accumulates
more than ~700 KB of output OR runs for more than ~15 minutes
silently exits with no error surfaced to the parent. This is a
platform property, not a configurable limit.

**Observation:** Recorded in `.claude/rules/70_agent_reliability.md`;
observed during Arc D v2 nightly dataset builds (2025-Q4) and during
`agent_ops` Phase 3 experiment runs (session 2026-03-15 postmortem).

**Brittleness signal:** `grep -n '15 min\|700KB\|700 KB' .claude/rules/70_agent_reliability.md`
returns ≥1 match. If Claude Code publishes an official limit that
differs, the rule file must be updated; drift detection via
`make check-gated` failing a rule-freshness assertion (to be added in
Primitive G rework spec).

**Refresh trigger:** Every Claude Code upgrade; every time a spawned
agent is observed to hang for >10 min without producing output.

### Entry 3 — Bracketed paste mode — tmux `send-keys` with Enter bundled drops submission

**Assumption:** When `tmux send-keys -t <pane> 'text' Enter` is issued,
the terminal wraps the payload in bracketed-paste escapes and the
`Enter` is consumed inside the paste bracket — text is pasted but never
submitted.

**Observation:** Issue #1834 (paste bracketing diagnosis); issue #2352
(escape-before-send fix). Reproduced repeatedly during orchestrator
→ author-lane nudges until the three-step pattern (Escape → text →
sleep → Enter) was codified in `src/bid_euchre/ops/worker_pool.py`.

**Brittleness signal:** `grep -c 'nudge_pane\|send-keys.*Enter' src/bid_euchre/ops/worker_pool.py`
should report the three-step pattern (Escape + text + Enter as
separate sends). CI check: `tests/unit/test_worker_pool.py::TestNudge`
asserts the three calls are separate.

**Refresh trigger:** Any tmux major-version change; any macOS Terminal
/ iTerm2 / Ghostty update that modifies paste-bracketing behavior.

### Entry 4 — Auto-mode activation — `--permission-mode auto` required at launch

**Assumption:** The Sonnet 4.6 classifier only gates tool calls when
the Claude Code CLI is launched with `--permission-mode auto`. Setting
`defaultMode: "auto"` in `.claude/settings.json` without the flag at
launch leaves the session in `bypassPermissions`.

**Observation:** Issue #2685 (discovery during review-lane restart
2026-04-20). The review lane respawned as `bypassPermissions` despite
the committed `defaultMode: "auto"`; launching with the flag restored
classifier gating.

**Brittleness signal:** `grep -n '\-\-permission-mode auto' .claude/tmux/steward-session.sh`
returns ≥19 hits (one per lane launch). CI check:
`tests/unit/test_steward_session.py::TestPermissionModeAuto` and
`tests/unit/test_review_lane_runner.py::TestInvokeReviewPermissionMode`
assert the flag is present in every launch path.

**Refresh trigger:** Any Claude Code release that changes auto-mode
activation semantics; any lane-launcher refactor.

### Entry 5 — Review-verdict SHA binding — merge guard blocks on SHA mismatch

**Assumption:** The pre-merge hook `pre-merge-review-guard.sh` reads
the review queue verdict and compares the verdict's recorded SHA
against the PR HEAD. If they differ, the merge is blocked — so review
must re-run after every push.

**Observation:** Implemented in `scripts/internal/pre_merge_guard.py`
per `.claude/rules/deferred/60_review_gate.md` § Status Contexts.
Reviewed PRs must have a matching SHA or the merge is refused.

**Brittleness signal:** `grep -n 'verdict_sha\|head_sha' scripts/internal/pre_merge_guard.py`
returns ≥1 match per comparison path; `tests/unit/test_pre_merge_guard.py`
exercises the SHA-mismatch refusal branch.

**Refresh trigger:** Any review-queue schema change; any review-driver
refactor that modifies verdict persistence.

### Entry 6 — GitHub CI context — `tests` aggregation gate always posts

**Assumption:** Docs-only / plans-only PRs pass the `tests` branch
protection check because the `tests` aggregation gate always posts a
status even when upstream jobs are skipped by `dorny/paths-filter`.
Without this, a docs-only PR would hang indefinitely on "Expected —
waiting for status to be reported."

**Observation:** PR #635 introduced paths-filter; PR #1086 fixed the
aggregation-gate wiring. Described in `.claude/rules/deferred/60_review_gate.md`
§ Known Issue: Docs-Only PRs and CI.

**Brittleness signal:** `grep -n 'tests:' .github/workflows/ci.yml`
returns the aggregation-gate job definition; integration test:
`gh pr checks <docs-only-PR>` shows `tests: success` within 5 min of
opening.

**Refresh trigger:** Any `.github/workflows/ci.yml` edit that
reorganizes job dependencies; any paths-filter upgrade.

### Entry 7 — Persistent worktrees — steward lanes never deleted

**Assumption:** Steward author/analyst/ops/review/flex/browser-author
worktrees are persistent infrastructure; `git worktree remove` is
never run against them regardless of branch or PR state. The cleanup
policy enumerates protected paths explicitly.

**Observation:** Documented in `.claude/rules/75_worktree_protection.md`
with full protected list. PR #2238 codified the protection policy
after an earlier session nearly removed a lane worktree.

**Brittleness signal:** `grep -c 'steward' .claude/rules/75_worktree_protection.md`
≥19 (one per protected lane); hook:
`.claude/hooks/pre-worktree-remove.sh` rejects removal of any path
matching the protected list.

**Refresh trigger:** Any change to the fleet lane layout (adding /
removing lane pools); any new persistent role worktree.

---

_Additional entries are appended here as other harness assumptions
surface during proving and fleet operation. Keep entries grep-able:
each `### Entry N —` header is the handle. HA1 lint verifies every
entry has a machine-observable **Brittleness signal** field._
