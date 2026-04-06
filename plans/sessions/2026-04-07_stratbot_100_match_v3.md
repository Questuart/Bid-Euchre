# StratBot 100-Match V3 Strategic Run — Defense-First, Targeting Positive EPPD

**Date:** 2026-04-07
**Lane:** flex-a
**Predecessors:**
- V1: `plans/sessions/2026-04-05_stratbot-100-match-strategic-run.md`
- V2: `plans/sessions/2026-04-06_stratbot-100-match-v2-positive-eppd.md`

**Target:** `https://bideuchre-web.onrender.com` (AI opponent: `bud_bot`)
**Player:** `StratBot` (link_uuid `f0ada160-74ec-41db-ab4b-ac213a36da47`)
**Task packet:** `dfb825f19ded`
**Related issue:** #2537 (StratBot defense investigation)

## Goal

Run a third 100-match StratBot session aimed at pushing the
**within-session net EPPD above zero** (V1 = −0.713, V2 = −0.420).
Do it **without cheating** or violating any game rule — every bot
decision must use only information a seated human player would have at
seat 0.

## Why V3 Exists

Per the V2 report decomposition (1,033 hands):

| Phase | Hands | Net swing | Per-hand |
|-------|------:|----------:|---------:|
| Offense (we bid)  |   333 | **+423** | **+1.270** |
| Defense (we pass) |   700 |  −857 |   **−1.224** |
| **TOTAL**         | 1,033 |  −434 |   −0.420 |

- V2 offense is strongly profitable (+1.27/hand across all bid levels).
- V2 defense bleeds −1.22/hand over 700 hands — this is the whole loss.
- The bot currently passes on ~68% of hands, so defense **dominates** the
  aggregate EPPD.

Because offense is small but positive and defense is large but negative,
the highest-leverage changes for V3 are defense heuristics. Even a
+0.30/hand defense improvement (closing ~25% of the gap) would add
roughly +0.20 to session EPPD, which would push V3 comfortably above
zero even if bid variance stays the same as V2.

## V3 Strategy Changes (vs V2)

The V3 bot is a strict superset of V2 — no V2 heuristic is removed. The
additions are:

### Defense-First Heuristics (biggest expected impact)

1. **Trump tracker** — maintain a per-hand set of trump cards already
   played (right bower, left bower, off-bowers, A/K/Q/10 of trump). Used
   to estimate how many top trumps are still outstanding when choosing
   follow cards and leads. The data source is `card--played` spans in
   the already-public trick area + `completed_tricks` region of the
   page — **no information beyond what a human at the table would see.**

2. **Position-aware 2nd-hand-low on defense** — when following in 2nd
   seat and a suit contract is declared against us, always dump the
   lowest card in the led suit unless we are holding both bowers or
   can guarantee the trick alone. Rationale: 2nd seat should preserve
   high cards for moments when partner or the information picture
   makes the play obvious (classic Whist/Euchre maxim, per #2537).

3. **Position-aware 3rd-hand-high on defense when declarer leads** —
   when declarer (bidder) leads and we are in 3rd seat on defense,
   play the **highest** non-trump card that is still a legal follower,
   forcing declarer to spend a high trump or waste a high side card.
   Current V2 logic only plays a winner if it's a top-tier card
   (R/L/A); V3 escalates this to the highest follow in 3rd seat on
   defense.

4. **Partner-overtake guard (reinforced)** — V2 already avoids
   overtaking a winning partner when following in suit, but on
   defense when void in the led suit and partner is winning on an
   ace/bower, V3 also avoids **ruffing** partner's trick (dump a low
   off-suit card instead of wasting a trump).

5. **Side-suit preservation when declarer runs trumps** — detect when
   declarer is leading trumps repeatedly ("drawing"). When void in
   that suit, prefer to discard low off-suit cards and **keep** aces
   and protected kings in our long side suits as later winners.
   V2 sorted by `RANK_ORDER` only; V3 also avoids discarding an ace
   or a protected king (K paired with another card of the same suit
   in hand).

6. **Defensive opening lead** — when we are on lead as a defender
   (i.e., the opponent declared), V3 leads:
   - **Off-suit aces** first (take sure winners before they're ruffed);
   - then from our **longest non-trump side suit**, pulling out the
     king/queen to force declarer's hand;
   - then, if we have only junk, **lead a low side suit** (not trump —
     never lead trump to the opponents' bidder).

   V2 defensive lead was the same routine as offense: aces → high →
   longest suit. V3 formalizes the "never lead trump to opponent"
   maxim and adds an explicit defender-on-lead branch.

### Offense Refinement (small tweak, bounded risk)

7. **Slightly lower bid 6 floor** — V2 bid 6 on evaluations in the
   range 6.0 to 7.0; V3 bids 6 on 5.8 to 7.0. V2 bid 6 profit was still strong
   at +1.34/hand with 20.6% set rate. A 0.2-point shift captures a
   small population of borderline 5.8–6.0 hands as bid 6 instead of
   bid 5. V2 bid 5 profit was only +0.09/hand, so moving these hands
   up is expected value positive.

   **Explicitly bounded:** V3 does NOT lower the bid 5 floor (still
   pass below 5.0), does NOT reintroduce bid 4, does NOT stretch bid
   to 4. All of those were unprofitable in V1/V2.

### Preserved from V2 (unchanged)

- Pass threshold at `eval < 5.0`.
- Bid 5 range `[5.0, 5.8)` — unchanged floor, narrower top.
- Bid 7 cap and range `[7.0, ∞)`.
- Stretch-bid rule (only stretch for natural bid 5+, by max 1 step).
- Suit-lead choice on offense: bowers > high trump > off aces > long
  suit K > longest suit.
- High/Low contract lead: aces/10s first, then kings/jacks.
- Moon exchange handler (select 2 low indices, then advance).

## Robust JSONL Logging

Every hand produces one JSONL record with full provenance. Schema:

```json
{
  "match_id": "<seq>",
  "match_num": 1-100,
  "hand_num": 1-12,
  "dealer_seat": 0-3,
  "contract_type": "suit|high|low|null",
  "trump": "H|D|C|S|null",
  "winning_bid_n": 4-10,
  "bidder_seat": 0-3,
  "our_hand_before": ["KH", "QH", ...],
  "hand_eval": 5.8,
  "eval_contract": "H|HIGH|LOW|null",
  "our_bid_decision": "pass|bid_5_H|bid_6_low|...",
  "our_bid_rationale": "eval=5.83 bowers=2 trump_len=4",
  "tricks_we_won": 0-10,
  "tricks_opp_won": 0-10,
  "our_team_points": -10..20,
  "opp_team_points": -10..20,
  "net_swing": -30..30,
  "phase": "offense|defense",
  "defender_on_lead": true|false,
  "plays": [
    {
      "trick_num": 1,
      "our_position": 1-4,
      "led_suit": "H",
      "card": "KH",
      "legal_options": ["KH", "QH", "JH"],
      "chosen_rationale": "2nd hand low on defense",
      "trump_played_count": 3
    },
    ...
  ]
}
```

One JSONL file per session: `data/local_smoke/stratbot_v3/stratbot_v3_100match_<timestamp>.jsonl`. The log is streamed (append-per-hand) so a crash mid-session does not lose data.

## Anti-Cheating Audit (pre-run)

Conducted before any matches were played. Cited sources:

- `web/routes.py` — the only endpoints the bot touches are:
  `GET  /play/{link_uuid}` (game page / board)
  `POST /play/{link_uuid}/bid`
  `POST /play/{link_uuid}/play-card`
  `POST /play/{link_uuid}/next`
  `POST /play/{link_uuid}/skip`
  `POST /play/{link_uuid}/exchange`
  `POST /play/{link_uuid}/next-hand`
  `POST /play/{link_uuid}/new-match`
  `POST /play/{link_uuid}/nickname`
  `POST /play/{link_uuid}/onboarding/skip`
  `POST /play/{link_uuid}/select-ai`

- `web/routes.py::_build_game_context` calls
  `engine.get_visible_state(state)` which only exposes:
  - `human_hand` — our own hand at `HUMAN_SEAT` (seat 0) only
  - `auction` — public auction transcript
  - `contract_type`, `trump` — publicly announced after auction
  - `current_trick`, `completed_tricks` — cards already played (public)
  - `tricks_team0`, `tricks_team1` — public scoreboard
  - `sitting_out_seat`, `exchange_given`, `exchange_received` — only
    for moon/loner phases (visible to participants)

  **It never exposes opponent hand cards, deck order, seed, or AI
  internal state.** See `src/bid_euchre/hosted_play/engine.py`
  lines 465–523.

- `web/templates/partials/game_board.html` renders opponent seats
  using only a count of card-backs (lines 77–152), never actual
  card titles or indices:
  ```jinja
  {% for _ in range(partner_count | default(0)) %}
  <div class="card-back" aria-hidden="true"></div>
  {% endfor %}
  ```
  The only `title="K♠"` attributes present in the DOM are on
  `id="hand-card-N"` elements for seat 0 (our hand) and on
  `card--played` elements (already played to the trick — public
  information).

- The V3 bot parses:
  - `id="hand-card-N"` with `title="X♠"` → **only our seat 0 cards**
  - `card--played[...]aria-label="Name played X of Suit"` → the
    cards already played in the current trick, visible to everyone
  - `contract-bar__suit--X` → the publicly declared trump/contract
  - `score-*` and `Current high bid` text → public scoreboard

  **No endpoint or page-parse step reads opponent cards, deck
  order, or seeds.** This is the same surface the V1 and V2 bots
  used; V3 adds **no** new information sources.

- Rule legality: the server exposes `legal_plays` via the
  `card--legal` CSS class on our hand during trick play. The V3
  bot **restricts every play to cards present in `legal_cards`**
  (the parsed `card--legal` set). If no legal cards are detectable,
  the bot falls back to the server-provided legal index. Thus no
  illegal play is ever submitted — the server would reject it
  anyway, but V3 also makes the contract defensively at the
  client.

## Execution Plan

1. ✅ Read V1 and V2 session reports.
2. ✅ Read issue #2537 for defense-investigation context.
3. ✅ Draft this V3 strategy changelog (pre-run).
4. ⏳ Implement V3 bot in `/tmp/stratbot_v3_player.py` (Python HTTP
   client, not committed to repo — same convention as V1 and V2).
5. ⏳ Run a 5-match smoke to catch crashes, illegal-play rejections,
   moon hangs.
6. ⏳ Run the 100-match session, streaming JSONL to
   `data/local_smoke/stratbot_v3/`.
7. ⏳ Analyze the JSONL log: offense/defense decomposition, per-bid
   make/set table, rolling 20-match EPPD, per-heuristic contribution.
8. ⏳ Fill in the Results section of this document with the analysis,
   integrity assertion, and V4 recommendations.
9. ⏳ Open PR (doc-only) for this session report.

## Hard Constraints (from task packet)

1. **No cheating.** No opponent-hand inspection, no seed exploits, no
   endpoint that leaks unseated information.
2. **No game rule violations.** Every play restricted to the server's
   legal set. See legality section above.
3. **No `src/bid_euchre/` or `web/` strategy modifications.** V3 is a
   client-side strategy iteration, not a server-side bot change.
4. **Use the FlexBot-A player linkage** (`f0ada160-74ec-41db-ab4b-ac213a36da47`).

## Scope

| Path | Status |
|------|--------|
| `/tmp/stratbot_v3_player.py` | Ephemeral (not committed — client tool, same convention as V1/V2) |
| `data/local_smoke/stratbot_v3/*.jsonl` | Gitignored (log output) |
| `plans/sessions/2026-04-07_stratbot_100_match_v3.md` | This report — committed |

**Not touched** (by policy):
- `src/bid_euchre/**`
- `web/**`
- `tests/**`
- Any production data or DB outside the FlexBot-A session itself.

## Success Criteria

| Criterion | Bar |
|-----------|-----|
| **Primary** — session net EPPD | **> 0** |
| **Secondary** — JSONL provenance | Complete per-trick log |
| **Tertiary** — integrity | No cheating or illegal play |

If the primary goal is not reached, the report still delivers:
- Which heuristic changes moved the needle
- Which heuristics had no measurable effect
- A prioritized V4 backlog

---

## Results

_(Filled after the run completes.)_
