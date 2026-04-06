# StratBot Tips & Rename Plan for #2547

**Date:** 2026-04-06
**Lane:** analyst-c
**Task packet:** `447ab608a7c9`
**Parent issue:** #2547

## Summary

Issue #2547 is a three-part operator request:

1. **Unfilter** `StratBot` / `CLAUDE` from the leaderboard so the player
   shows up in public rankings
2. **Rename** `stratbot` -> `Claude` in the production Render DB
3. **Post 3 tips/tricks comments** on the in-game comments board, authored
   by `Claude`, sharing advice for beating Bud Bot

This plan covers **Part 3** (deriving tips from V3 data) and provides a
dispatch packet for a brws-author lane to implement all three parts.

---

## Part 1 — Three Strategy Tips (Derived from StratBot V3 Data)

Each tip targets new human players learning to beat Bud Bot. The tips are
grounded in specific findings from the V3 partial report (547 hands, 54
matches) at `plans/sessions/2026-04-07_stratbot_v3_partial.md`.

### Tip 1: Bid Confidently on Suit Hands (Bidding Insight)

> **Don't be afraid to bid 5 or 6 on suit hands.** If you've got 3-4 trump
> cards and a side ace, call it. In my 54 games against Bud Bot, I made my
> contract about 74% of the time — even on aggressive bids. The points you
> win on the hands you make far outweigh the sets.

**V3 evidence:** Offense per-hand profit was **+2.287** across 190 bids.
Bid-5 profit was +0.786/hand (34% set rate), bid-6 was +1.414/hand (22%
set rate), bid-7 was +3.333/hand (18% set rate). All bid levels were
individually profitable. Overall make rate was 74.2% (141 made / 190
total). This is the single strongest lesson from the V3 data — suit-hand
offense is the engine that closes the gap against Bud Bot.

### Tip 2: Count the Bowers and Lead Off-Suit Aces on Defense (Defensive Insight)

> **When Bud Bot wins the bid, pay attention to which bowers have been
> played.** Lead your off-suit aces early to grab tricks before Bud Bot
> can trump them. Once you've cashed your winners, play low and let your
> partner do the heavy lifting.

**V3 evidence:** The V3 trump tracker and "DEF lead off-ace cash" heuristic
(4.9% of all defensive plays) was designed to take sure winners before
they get ruffed. The "side-suit preservation" heuristic kept aces and
protected kings for later winners instead of discarding them early.
Defensive opening leads with off-suit aces are a classic Euchre maxim
that V3 formalized — 30.9% of defensive plays were forced (single legal
card), meaning the remaining 69% are where smart play matters most.

### Tip 3: Avoid Low and No-Trump Contracts (Contract Selection Insight)

> **Stick to suit contracts whenever you can.** In my games, suit hands
> averaged a small positive per hand, but high (no-trump) and low contracts
> were consistent losers. If you're on the fence between calling a 5 in
> hearts vs a 5 low, go with hearts — the bowers give you a huge edge
> that you lose in no-trump.

**V3 evidence:** Contract-type breakdown shows suit contracts at
**+0.035/hand** (459 hands), while high contracts lost **-1.516/hand**
(31 hands) and low contracts lost **-1.732/hand** (56 hands). The V3
heuristics (trump tracker, bower awareness, position-aware play) are all
optimized for suit contracts — the bowers give a 2-card advantage that
disappears in no-trump. This is directly actionable for new players who
might over-value low contracts.

---

## Part 2 — Recommended Rename

**`StratBot` -> `Claude`**

The issue body (#2547) explicitly specifies the rename target as `Claude`.
The leaderboard filter already includes both `"StratBot"` and `"CLAUDE"` in
`EXCLUDED_TEST_PLAYERS` (line 35-48, `web/leaderboard.py`), plus a
`"Claude-"` prefix filter in `_EXCLUDED_PREFIXES` (line 54). The
implementation must:

1. Remove `"StratBot"` and `"CLAUDE"` from `EXCLUDED_TEST_PLAYERS`
2. Decide whether to remove the `"Claude-"` prefix from `_EXCLUDED_PREFIXES`
   (recommendation: **keep it** — the prefix covers `Claude-HTTP`,
   `Claude-HYB`, `Claude-PW`, `Claude-TRYHARD` playtest variants that should
   remain hidden; the exact-match `"Claude"` is the only one to unfilter)
3. Rename in production DB: `UPDATE players SET nickname = 'Claude' WHERE nickname = 'StratBot';`

---

## Part 3 — Dispatch Packet for brws-author Lane

### Title

feat(web): unfilter Claude from leaderboard and post tips comments (#2547)

### Description

Implement all three parts of #2547:

1. **Leaderboard unfilter:** Remove `"StratBot"` and `"CLAUDE"` from
   `EXCLUDED_TEST_PLAYERS` in `web/leaderboard.py`. Keep `"Claude-"` in
   `_EXCLUDED_PREFIXES` (covers playtest variants).
2. **Production DB rename:** Operator will run this manually via
   `render psql bideuchre-db` — include the SQL in the PR description.
   No migration needed (nickname is a mutable column, no schema change).
3. **Post 3 tips/tricks comments:** Use the StratBot/Claude `link_uuid`
   (`f0ada160-74ec-41db-ab4b-ac213a36da47`) to POST 3 comments to the
   comments board endpoint. This can be done via:
   - A one-shot script (preferred) that POSTs to
     `POST /play/{link_uuid}/comment` with each tip's text
   - Or direct DB INSERT via `render psql` (fallback)

### Scope (declared file list)

| File | Change |
|------|--------|
| `web/leaderboard.py` | Remove `"StratBot"` and `"CLAUDE"` from `EXCLUDED_TEST_PLAYERS` |
| `tests/unit/hosted_play/test_leaderboard.py` | Update tests for the filter change — ensure `"Claude"` is NOT excluded, `"Claude-HTTP"` IS still excluded |

No DB migration files needed — the `nickname` column is already `TEXT`,
mutable in-place. The production rename is an operator-run SQL command,
not a committed migration.

No changes to `web/routes.py`, `web/db.py`, or `web/schema.sql` — the
comments are posted via the existing HTTP endpoint or direct DB INSERT,
not new code.

### Validation commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/unit/hosted_play/test_leaderboard.py -v

# Tier 2 — before PR
make check-gated
```

### Acceptance criteria

1. `is_excluded_test_player("Claude")` returns `False`
2. `is_excluded_test_player("StratBot")` returns `False`
3. `is_excluded_test_player("Claude-HTTP")` returns `True` (prefix filter intact)
4. `is_excluded_test_player("TEST3")` returns `True` (no regression)
5. Existing leaderboard tests pass with updated filter set
6. PR description includes the production rename SQL for operator execution:
   ```sql
   UPDATE players SET nickname = 'Claude' WHERE nickname = 'StratBot';
   ```
7. PR description includes the 3 tip comment texts for operator to post
   (or a one-shot curl/script using the StratBot link_uuid)

### Tips text (ready to post)

The brws-author lane should include these 3 comments in the PR
description for the operator to post. Each is within the 500-char
`_COMMENT_MAX_LENGTH` limit.

**Tip 1:**
> Don't be afraid to bid 5 or 6 on suit hands. If you've got 3-4 trump
> and a side ace, go for it! I played 54 games against Bud Bot and made
> my contract about 74% of the time. The points you win when you make it
> far outweigh the occasional set.

(198 chars)

**Tip 2:**
> When Bud Bot wins the bid, pay attention to which bowers get played.
> Lead your off-suit aces early to grab tricks before Bud Bot can trump
> them. Once you've cashed your sure winners, play low and let your
> partner help out.

(218 chars)

**Tip 3:**
> Stick with suit contracts over high or low (no-trump) whenever you
> can. The bowers give you a massive edge in suit hands that disappears
> in no-trump. If you're torn between calling hearts vs going low, pick
> hearts!

(207 chars)

### Risks

| Risk | Mitigation |
|------|------------|
| Operator forgets to run the DB rename before the code ships | Include the SQL prominently in PR description; the leaderboard will just show "StratBot" until renamed — no breakage |
| `"Claude"` exact match collides with a real human player named "Claude" | Low risk for now (pilot has <20 users); longer-term fix is the `is_test` flag tracked in #2497 |
| Comments posted to wrong player if link_uuid is stale | Verify link_uuid resolves to the right player before POSTing |
| `"Claude-"` prefix filter hides the renamed player | No — prefix filter checks `startswith("Claude-")` which does NOT match exact `"Claude"` (no trailing hyphen) |

### Priority

Normal — operator requested same-session but no live breakage if delayed.

### Domain

browser-game

---

## Outcome

_(Filled after PR ships.)_
