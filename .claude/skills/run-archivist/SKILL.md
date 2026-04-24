---
name: run-archivist
description: Run the Primitive D archivist in lessons, GC, or postmortem mode. Scans event streams + KB state, writes a dated candidate file under knowledge/_candidates/ for operator review, and (when the emission flag is on) emits archivist_candidate_proposed events. Use nightly via cron, at session-end via the session-end skill, or ad-hoc when curating the candidate queue.
---

# /run-archivist — Archivist Candidate Generator

Run one archivist pass and produce a dated candidate file for operator
review. Phase 0 supports three modes:

- **lessons** — scan recent events (incidents, token outliers, explicit
  lesson annotations, repeated patterns) and propose lesson candidates
- **gc** — scan KB snapshot for stale / dead / obsolete / orphan /
  expired entries and propose GC actions
- **postmortem** — at session-end, snapshot session signals into both
  `MEMORY.md` and `knowledge/_candidates/<date>_lessons.md`

See `plans/steward_platform/4_primitive_D/shaping.md` §4.1 (lessons),
§4.2 (gc), §4.4 (postmortem), §4.3 (promotion workflow), and §5-D of
the governing plan for the full design.

## When to Use

- **Nightly cron** — `/loop 24h /run-archivist --mode lessons`
  (session-scoped cron; operator re-arms after fleet restart per §6.4.2)
- **End-of-session hook** — `.claude/skills/session-end/SKILL.md`
  Phase 4.5 runs `/run-archivist --mode postmortem --session-id <id>`
  just after the MEMORY.md handoff commit is authored
- **Ad-hoc curation** — operator runs `/run-archivist --mode lessons`
  or `/run-archivist --mode gc` from any lane when they want to
  inspect the current candidate state
- **GC code-path smoke** — operator runs `/run-archivist --mode gc
  --fixture-dir tests/fixtures/archivist/fake_kb` to exercise the GC
  path without a real KB snapshot

## Arguments

- `--mode lessons|gc|postmortem` — archivist run mode (default: `lessons`)
- `--dry-run` — compute candidates but do not write output or advance
  watermarks
- `--since <ISO-8601>` — lessons mode only; override the last-run
  watermark as the lower bound of the scanned event window
- `--fixture <path>` — lessons mode test-only; read events from a JSONL
  fixture instead of `data/events/`
- `--fixture-dir <path>` — gc mode test-only; read a fake-KB snapshot
  from this directory
- `--candidates-dir <path>` — override the candidates directory
  (default: `knowledge/_candidates`)
- `--session-id <id>` — postmortem mode; required session identifier
- `--memory-md <path>` — postmortem mode; override `MEMORY.md` path

## Workflow

### Step 1 — Invoke the CLI

```bash
# Nightly / ad-hoc lessons mode
uv run python scripts/internal/archivist_candidates.py --mode lessons

# GC-mode smoke (fixture-backed; Phase 0 has no live-load)
uv run python scripts/internal/archivist_candidates.py --mode gc \
    --fixture-dir tests/fixtures/archivist/fake_kb

# End-of-session postmortem
uv run python scripts/internal/archivist_candidates.py --mode postmortem \
    --session-id <session-id>
```

> **Two archivist CLIs:** the **candidate-generator** (this skill) lives
> at `scripts/internal/archivist_candidates.py`. The complementary
> **promotion/rollback surface** (Primitive C Packet C-Exec) lives at
> `scripts/internal/archivist.py` — invoked as `--promote <candidate>`
> or `--unpromote <archive>`. Both cooperate via
> `knowledge/_candidates/` per the C↔D interface contract.

Exit codes:

- `0` — success (candidates written or dry-run listed)
- `1` — empty scan (no candidates — not an error)
- `2` — source unreachable (e.g., fixture unreadable)
- `3` — write failure
- nonzero from argparse — invocation error

### Step 2 — Review the output file

The dated candidate file lands at
`knowledge/_candidates/<YYYY-MM-DD>_{lessons,gc}.md`. Open it and read:

- **Lessons mode** — 4 sections: repeated patterns, token outliers,
  incident candidates, explicit lessons
- **GC mode** — 5 sections: stale, dead-skill, obsolete-policy, orphan,
  expired
- **Postmortem mode** — section appended to the dated lessons file
  with header `## Postmortem — session <id> — <date>`; MEMORY.md also
  receives a `### Session <id> — <date>` handoff entry

Each candidate lists: proposed text, evidence (trace_id / PR URL /
event_id), and a proposed promotion path.

### Step 3 — Promote, reject, or skip per candidate

Per shape §4.3, decisions are operator-driven:

- **Promote** — copy the candidate entry into
  `knowledge/_promoted/{lessons,gc}/<slug>.md`; commit with
  `Refs #<candidate-file>`. Emits `archivist_candidate_promoted` when
  `ENABLE_D_EVENT_EMISSION=1`.
- **Reject** — annotate the candidate file inline with
  `**Operator decision:** reject — <reason>`; commit. Emits
  `archivist_candidate_rejected` when flag is on.
- **Skip (this cycle)** — leave the candidate untouched; it will
  re-appear next run, compounding evidence until promoted or rejected.

### Step 4 — Commit the decision

```bash
git add knowledge/_candidates/<YYYY-MM-DD>_lessons.md  # if edited inline
git add knowledge/_promoted/lessons/<slug>.md           # if promoted
git commit -m "archivist: promote <slug> (Refs #<N>)"
```

## Promotion Workflow

Canonical location per shape §4.3. Promotion is:

1. **Review the candidate file** in `knowledge/_candidates/` (section
   structure per §4.1.3 / §4.2.3 / §4.4.1).
2. **For each candidate, decide**:
   - Promote → copy into `knowledge/_promoted/<class>/<slug>.md`
   - Reject → inline annotate with
     `**Operator decision:** reject — <reason>`
   - Skip → leave for next cycle
3. **Commit the decision** with a `Refs #<candidate-file>` trailer so
   the audit trail is complete.
4. **Events fire** (when `ENABLE_D_EVENT_EMISSION=1`):
   - `archivist_candidate_promoted` with `{candidate_path,
     promoted_path, operator}`
   - `archivist_candidate_rejected` with `{candidate_path,
     rejection_reason, operator}`

Rollback path (Pattern 7): every action is a git commit; `git revert`
restores the pre-decision state. No non-reversible steps.

## Gotchas

- **`ENABLE_D_EVENT_EMISSION` flag state.** Default is `"0"` (off). Flag
  flip is a 1-line PR after Primitive A's event-writer registers the
  archivist event types in `VALID_EVENT_TYPES`. Running with flag off
  still produces the candidate file — only the event emission is
  suppressed. Do **not** flip the flag before A has shipped.
- **Re-run-same-day behavior.** Running `--mode lessons` twice in a day
  appends to the same dated file (separated by `---`). The second run
  re-scans the event window from the last watermark, so identical
  signals reappear. Skip or reject duplicates explicitly.
- **GC Phase 0 is fixture-only.** `--mode gc` without `--fixture-dir`
  returns exit 1 (empty). Live KB snapshotting is Phase 1+ work.
- **Postmortem dual-write is best-effort.** A write failure on one of
  `MEMORY.md` or the candidate file does not block the other; partial
  success logs a warning but still returns exit 0. Inspect the result
  dataclass (`memory_appended`, `candidate_path`) to confirm both
  landed.
- **Cron re-arm on restart.** `/loop 24h /run-archivist --mode lessons`
  is session-scoped. Fleet restarts lose the cron. Operator re-arms as
  part of the ops post-restart runbook.

## References

- `plans/steward_platform/4_primitive_D/shaping.md` §4.1 (lessons),
  §4.2 (gc), §4.3 (promotion), §4.4 (postmortem), §4.6.1 (this skill)
- `plans/steward_platform/governing_plan.md` §5-D — Primitive D
  Phase 0 Readiness
- `src/bid_euchre/ops/archivist/` — library
- `scripts/internal/archivist_candidates.py` — CLI wrapper (D inflow)
- `scripts/internal/archivist.py` — Primitive C promote/unpromote surface
- `.claude/skills/session-end/SKILL.md` Phase 4.5 — postmortem
  invocation hook
- `.claude/skills/review-claude-changelog/SKILL.md` — sibling skill
  for ecosystem signal intake
