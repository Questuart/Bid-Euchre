# Anti-Patterns (anti_patterns.md)

> Patterns observed to fail in this repo. Each entry names the trigger
> condition, the harm produced, and the preferred alternative. Agents
> scan this file before implementing load-bearing or reversible-policy
> surfaces.
>
> **Commit policy (ADR 010):** promoted anti-patterns only. Session
> discoveries that merit anti-pattern status land in
> `knowledge/_candidates/` first; promotion is operator-gated.
>
> **Schema:** each entry is a `### <anti-pattern name>` heading followed
> by three fields:
>
> - **Trigger:** the condition under which this anti-pattern appears
> - **Harm:** what goes wrong when the anti-pattern is committed
> - **Preferred alternative:** the pattern to adopt instead

---

## Worked example

### Running `make check` as a background task

**Trigger:** Lane queues `make check-gated` (or `make check-quiet`) via
`Bash(run_in_background=true)` because it is "about to take a while and
we don't want to block."

**Harm:** Both gated variants redirect all output to a tmpfile. The
background capture sees 0 bytes of output because the log file grows
out-of-band. The lane then interprets the silent stream as "nothing is
happening" and starts a *second* foreground `make check`. Two
concurrent check processes double CPU/IO load and inflate validation
from ~8 min to 28+ min (PR #2271 incident report).

**Preferred alternative:** Always run `make check-gated` / `make
check-quiet` as foreground `Bash` calls. Use the progress spinner (the
task system shows spinner while `in_progress`) as the "work is
happening" signal. If you genuinely cannot block the session, use the
interactive `make check` variant which streams to stdout.

---

### Using `Fixes #N` for multi-PR issue resolution

**Trigger:** Author opens a PR that partially addresses a Tier 2 issue
(acceptance criteria beyond "PR merged") and writes `Fixes #N` in the
PR body because "this is my PR for that issue."

**Harm:** GitHub auto-closes the issue when the PR merges. The
remaining acceptance work (production verification, follow-up PR,
evidence posting) has no issue to land on. Agents in subsequent
sessions cannot find the unfinished work because the issue is closed.

**Preferred alternative:** Use `Refs #N` for any PR that is not itself
the complete resolution. Add the `needs-verification` label on the
merged PR. Verify in production, post evidence as an issue comment,
then close manually. See `.claude/rules/deferred/55_issue_closure.md`
and the `proving-issues` skill.

---

## Promoted anti-patterns

_(promoted entries accumulate below)_
