---
name: review-claude-changelog
description: Scrape the Claude Code changelog + ecosystem sources, cross-check against knowledge/harness_assumptions.md, and write a dated candidate file under knowledge/_candidates/<date>_changelog.md for operator review. Use /loop 3d to catch changelog updates routinely, or ad-hoc when Claude Code ships a material release.
---

# /review-claude-changelog — Changelog Signal Intake

Scrape the 7-source changelog + ecosystem list, extract candidate
entries for each new feature, flag staleness against
`knowledge/harness_assumptions.md`, and write a dated candidate file
for operator review. The candidate file is the operator-review surface
for deciding whether each new Claude Code feature is:

- **Tier S / A** (native-substrate-signal = `yes`) — consider adopting
  and retiring the steward's synthesized equivalent
- **Tier B / C** — note in KB; defer or skip

See `plans/steward_platform/4_primitive_D/shaping.md` §4.5 for the full
design (source list, output schema, native-substrate-signal integration,
harness-assumption staleness detection).

## When to Use

- **Routine cadence** — `/loop 3d /review-claude-changelog` (session-scoped
  cron; operator re-arms after fleet restart per §6.4.2)
- **Ad-hoc** — after Claude Code ships a material update (release notes
  mention a new primitive, a flag semantics change, or an ecosystem
  announcement the fleet tracks)
- **After editing `knowledge/external_signal_sources.md`** — re-run to
  pick up newly added operator-curated sources

## Arguments

- `--since <ISO-date>` — look back from this date; default is the
  last-run watermark in `knowledge/_candidates/.last_run_changelog`
- `--sources-file <path>` — override the default 7-source list
  (one URL per line; `#`-comments OK)
- `--dry-run` — print scraped-source count + candidate count; no write
- `--fixture-dir <path>` — test-only; read HTML from a fixture
  directory instead of WebFetch
- `--candidates-dir <path>` — override
  (default: `knowledge/_candidates`)
- `--assumptions-path <path>` — override harness-assumptions path
  (default: `knowledge/harness_assumptions.md`)

## Workflow

### Step 1 — Invoke the CLI

```bash
# Routine: scan since watermark, live WebFetch path (Phase 1+).
uv run python scripts/internal/changelog_review.py

# Phase 0 fixture-driven smoke:
uv run python scripts/internal/changelog_review.py \
    --fixture-dir tests/fixtures/changelog_review

# Ad-hoc with an explicit source list:
uv run python scripts/internal/changelog_review.py \
    --sources-file knowledge/external_signal_sources.md
```

Exit codes:

- `0` — success (candidates written or dry-run listed)
- `1` — empty scan (sources reachable but produced zero candidates)
- `2` — source-unreachable class (all sources failed, malformed
  `--since`, or missing / empty `--sources-file`)
- `3` — write failure

### Step 2 — Open the dated candidate file

Output lands at
`knowledge/_candidates/<YYYY-MM-DD>_changelog.md`. The header lists
**Sources scraped**, **Source results** (URL → OK/404/timeout), and
**Candidate count**. Each candidate is a
`## Candidate N — <feature name>` section with:

- **Source URL:** canonical link
- **Affected primitive(s):** one or more of A–H
- **Stales harness assumption:** `no` or `yes — entry_id: <id>`
- **Tier recommendation:** S / A / B / C
- **Native-substrate-signal:** `yes` or `no` (see §Native-Substrate-Signal-Tag)
- **Operator decision:** `_(pending)_` → fill with accept / defer / reject
- **Decision date:** `_(pending)_` → fill with ISO-date on decision
- **Follow-up:** `n/a` → fill with a PR or issue link

### Step 3 — Review candidates and fill decision fields

For each candidate, edit the file in place:

- Replace `_(pending)_` on **Operator decision** with one of
  `accept` / `defer` / `reject`
- Replace `_(pending)_` on **Decision date** with today's ISO-date
- Replace `n/a` on **Follow-up** with a PR link (for accept),
  a future-sprint issue link (for defer), or leave `n/a` (for reject)

Staleness flags deserve priority review. If a candidate is
`Stales harness assumption: yes — entry_id: Entry N`, the operator
decides whether to:

- (a) retire the assumption + adopt native, or
- (b) refresh the assumption with an updated "still synthesizes
  because..." justification, or
- (c) defer (note the decision explicitly in the candidate's
  **Follow-up** field).

### Step 4 — Commit decisions

```bash
git add knowledge/_candidates/<YYYY-MM-DD>_changelog.md
git commit -m "changelog-review: <N> decisions (Refs #<issue if any>)"
```

Promotions (tier S/A native-adoption decisions) typically also ship a
follow-up PR that updates the affected primitive's implementation and
retires the staleness assumption — link that PR in the candidate's
**Follow-up** field.

## Harness Assumption Integration

`changelog_review.py` reads `knowledge/harness_assumptions.md` on every
run (shape §4.8.3). Each harness-assumption entry has a heading
(`## Entry N — <title>`) whose tokens become keyword matchers.
A scraped feature whose name or body contains any assumption's
keywords is flagged:

- `stales_harness_assumption=True`
- `stale_entry_id` set to the matching `Entry N` handle
- The candidate's **Stales harness assumption** bullet renders as
  `yes — entry_id: Entry N`

When `knowledge/harness_assumptions.md` is absent or unreadable, the
scraper degrades gracefully — no staleness flags, all candidates get
`Stales harness assumption: no`. This is the Phase 0 coordination
pattern with Primitive C (`knowledge/harness_assumptions.md` is owned
by C.2; D reads only).

## Native-Substrate-Signal Tag

Shape §4.5.5 defines two rules for setting
`Native-substrate-signal: yes`:

1. `stales_harness_assumption` is `True` (the candidate names a
   native capability the steward currently synthesizes via bespoke code)
2. `tier_recommendation` is `S` or `A` (explicit native-first
   preference per `plans/steward_platform/claude_code_changelog_implications.md` §5)

The rendered bullet in the dated candidate file is the literal string
`- Native-substrate-signal: yes` (unbolded, to keep it grep-friendly).
The upstream digest compiler (`compile_decision_inputs.py`, §15.4)
greps for this exact string when computing the "next-phase digest" for
operator review.

## Gotchas

- **WebFetch quota.** 7 sources × `/loop 3d` ≈ 14 calls/week. If
  per-host quotas kick in, sources short-circuit on the first cache-hit;
  individual failures are logged in **Source results**. A sustained
  all-unreachable signal exits 2 and is visible in run logs.
- **Source reachability variance.** Community URLs (Boris Cherny
  thread, davidad thread) 404 or move; per-source failures do not block
  the run — surviving sources still produce candidates.
- **Phase 0 production fetcher is null.** Without `--fixture-dir`, the
  Phase 0 CLI uses the null fetcher (all sources unreachable → exit 2).
  This is an intentional operator-visible signal that the WebFetch
  fetcher is not wired yet. Phase 1+ swaps in the live fetcher.
- **`--since` is accepted but not filtered in Phase 0.** The CLI
  validates ISO-8601 format (malformed → exit 2) but the scraper does
  not yet filter extracted features by date. The watermark file is
  still maintained so Phase 1 can land date-filtering without a CLI
  contract change.
- **Cron re-arm on restart.** `/loop 3d /review-claude-changelog`
  is session-scoped. Re-arm after fleet restart is an ops-runbook
  item (§6.4.2).
- **Native-substrate-signal flag rendering.** The `- Native-substrate-signal:`
  bullet is intentionally unbolded. Do not reformat it to match the
  other bullets' markdown bold style — it would break the §15.4
  digest compiler grep.

## References

- `plans/steward_platform/4_primitive_D/shaping.md` §4.5 (this skill),
  §4.8 (external_signal_sources.md seed), §4.5.5 (native-substrate-signal)
- `plans/steward_platform/governing_plan.md` §5-D — Primitive D
  Phase 0 Readiness + §15.3 (digest compiler grep surface)
- `plans/steward_platform/claude_code_changelog_implications.md` §5 —
  Tier rubric consumed by the scraper
- `src/bid_euchre/ops/changelog_review/` — library
- `scripts/internal/changelog_review.py` — CLI wrapper
- `knowledge/harness_assumptions.md` — C-owned assumption register
- `knowledge/external_signal_sources.md` — operator-curated source seed
- `.claude/skills/run-archivist/SKILL.md` — sibling skill for event-
  driven candidate intake
