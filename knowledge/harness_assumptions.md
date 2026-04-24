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

---

## Entry 1 — `--system-prompt-file` replaces the default in interactive + print modes

**Recorded:** 2026-04-24 (B.9a pilot, author-d)
**Claude Code version:** 2.1.114 (Opus 4.7, 1M context)
**Scope:** fleet system-prompt activation mechanism (B.9a, B.9b)

**Assumption.** Passing `--system-prompt-file <path>` on a `claude` invocation
replaces Claude Code's default system prompt with the file's contents verbatim,
in both interactive sessions (the steward lane deployment model) and `-p` /
`--print` mode. This is a stronger claim than the `--help` listing of
`--system-prompt <prompt>` — the `-file` variant is mentioned only in
`--bare`'s help text (`--system-prompt[-file]`) but exists and behaves as the
replacement flag.

**Observation supporting.**

_Print-mode probe (B.9a pilot, 2026-04-24)._

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

_Interactive-mode probe (B.9a pilot, 2026-04-24)._ Spawned
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

**Brittleness signal.** Any of the following would falsify this entry:

1. `claude -p --system-prompt-file X "describe your role"` returns generic
   "I am an AI assistant..." voice instead of the file's content.
2. Interactive session with `--system-prompt-file X` returns generic default
   voice (the ClaudeLog claim becomes true on a future release).
3. `claude --help` removes `--system-prompt` entirely, or the `--bare` help
   text drops the `[-file]` variant mention.
4. An active `.claude/system_prompts/<archetype>.md` file is present yet the
   archetype-keyword grep on a lane's paste buffer fails the B.9b Phase 1
   Validation launch-smoke.

**Refresh trigger.**

- Claude Code release notes (release-notes page, changelog, `claude --version`
  bump) mentioning changes to `--system-prompt`, `--system-prompt-file`,
  `--append-system-prompt-file`, `--agent`, or `--bare` semantics.
- B.9b Phase 1 Validation telemetry (prompt-policy-cited-in-trace rate) drops
  unexpectedly after a Claude Code upgrade.
- Any operator report of a lane "sounding default" after restart despite
  `.claude/system_prompts/<archetype>.md` being current on origin/main.

**Re-run procedure.** Re-execute the three print-mode probes above + the
tmux interactive probe. Expected: responses paraphrase the analyst.md
opening and Operating Rules. Observed ≠ expected → file a blocker,
re-shape B.9b activation.

---

_Additional entries will be recorded here as other harness assumptions
surface during proving and fleet operation. Keep entries grep-able:
each `## Entry N —` header is the handle._
