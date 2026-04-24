# Durable Lessons (NOTES.md)

> Freeform promoted lessons captured from session postmortems, operator
> review, or direct authorship. This is the canonical reading surface for
> "lessons agents should remember" — agents load this file (plus
> PLAYBOOKS.md and anti_patterns.md) to recover tacit project knowledge.
>
> **Commit policy (ADR 010):** only promoted entries live here. Unpromoted
> archivist candidates sit in `knowledge/_candidates/` (gitignored).
> Promotion is operator-gated via `/run-archivist --promote` or direct
> edit + `git add`.
>
> **Schema:** each entry is a `### <title>` heading followed by three
> fields:
>
> - **Context:** what situation / PR / session produced the lesson
> - **Lesson:** one sentence — the durable takeaway
> - **Source:** PR number, commit SHA, session date, or ADR reference

---

## Worked example

### Tmux paste bracketing drops Enter when sent with command text

**Context:** 2026-03 orchestrator nudge-to-author-lane dispatch. A
`tmux send-keys -t <pane> '/start-task <id>' Enter` call pasted the
command into the target pane but never submitted it. Lane appeared
stuck; operator had to press Enter manually.

**Lesson:** Modern terminals wrap `tmux send-keys` payloads in bracketed
paste escapes. When `Enter` is bundled in the same `send-keys` call, it
is consumed inside the paste bracket instead of submitting the line.
Always send command text and `Enter` in separate `send-keys` calls with
a small delay (~1s) between them. Send an `Escape` before the command
text to cancel any in-progress input on the target pane.

**Source:** issue #1834 (paste bracketing); issue #2352 (escape-before-send);
`src/bid_euchre/ops/worker_pool.py::nudge_pane`.

---

## Promoted entries

_(promoted entries accumulate below; the worked example above is the
file-head schema exemplar and is not removed)_
