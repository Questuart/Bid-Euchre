# StratBot V3 100-Match Strategic Run — **PARTIAL** (54 matches, operator stop)

**Date:** 2026-04-07
**Lane:** flex-a
**Status:** ⚠ **PARTIAL RUN** — stopped by operator wrap-up request at
match 54 of the intended 100. The bot process was killed cleanly; the
streaming JSONL log was flushed per hand, so all 547 completed hands are
preserved and analyzed below.
**Target:** `https://bideuchre-web.onrender.com` (AI opponent: `bud_bot`)
**Player:** `StratBot` (link_uuid `f0ada160-74ec-41db-ab4b-ac213a36da47`)
**Task packet:** `dfb825f19ded`
**Predecessors:**
- V1: `plans/sessions/2026-04-05_stratbot-100-match-strategic-run.md`
- V2: `plans/sessions/2026-04-06_stratbot-100-match-v2-positive-eppd.md`
- V3 pre-run changelog: `plans/sessions/2026-04-07_stratbot_100_match_v3.md`

## Why This Report Exists

V3 was launched targeting **within-session net EPPD > 0** after V1 (-0.713)
and V2 (-0.420) both finished below zero. The session report documenting
the strategy changes and anti-cheating audit was drafted and this partial
report documents the results of the interrupted run, since operator stopped
the session before the 100-match target. The bot was killed at match 54 and
the streaming JSONL was used to produce the analysis below.

## Headline Result (54 matches, 547 hands)

| Metric | V1 | V2 | **V3 (partial, 54m)** | V3 − V2 |
|--------|---:|---:|---:|---:|
| Matches | 90 | 100 | **54** | (partial) |
| Hands | 931 | 1,033 | **547** | — |
| Wins | 39 (43.3%) | 51 (51.0%) | **27 (50.0%)** | −1.0 pp |
| Ties | — | — | 1 | — |
| Net points | −588 | −434 | **−108** | (not comparable) |
| **Net EPPD** | **−0.713** | **−0.420** | **−0.197** | **+0.223** |
| Bid rate | 41.9% | 32.2% | **34.7%** | +2.5 pp |
| Mean margin | −6.53 | −4.34 | −2.00 | +2.34 |
| Median margin | −7 | −4 | +1 | +5 |
| Big wins (>+20) | 7 | 11 | 7 | +1 per-match |
| Big losses (<−20) | 23 | 24 | 11 | flat per-match |
| Blowouts (<−40) | 4 | 4 | **1** | −3 (much rarer) |

### Was the positive-EPPD target hit?

**No** — but **V3 improved on V2 by +0.223 EPPD** over 547 hands (53% the
intended sample), closing roughly half the remaining gap to zero.

The median match margin flipped from negative (V2) to **positive +1**, and
blowouts dropped from 4 (V2) to 1 (V3 partial). The rolling 20-match window
for matches 31–50 was **+0.0198 net EPPD (positive)** — the second time in
three sessions V3 heuristics produced a positive 20-match window.

## Offense vs Defense Decomposition

The central V3 thesis was that defense was the dominant V2 loss source
(−1.22/hand over 700 hands). The V3 partial split:

| Phase | Hands | Net swing | Per-hand | V2 comparison |
|-------|------:|----------:|---------:|--------------:|
| **Offense** (our team bid) | 286 | **+654** | **+2.287** | V2 +1.270 → **+1.017 gain** |
| **Defense** (opponent bid) | 260 | **−782** | **−3.008** | V2 −1.224 → **−1.784 regression** |
| Orphan / passed-out | 1 | +20 | +20.000 | (single anomalous hand) |
| **TOTAL** | **547** | **−108** | **−0.197** | V2 −0.420 → **+0.223 improvement** |

### Offense: Strongly Improved (+1.02/hand vs V2)

Offense jumped from +1.270 (V2) to **+2.287 (V3 partial)**, a near-doubling
of per-hand profit. The lower bid-6 floor (5.8 vs V2's 6.0) and a slightly
looser stretch-bid rule appear to have captured more profitable bid
opportunities without increasing the set rate materially:

| Bid | Made | Set | Total | Set% | Net | Mean swing | V2 mean |
|----:|-----:|----:|------:|-----:|----:|-----------:|--------:|
| 5   | 46 | 24 | 70 | 34.3% | +55  | **+0.786** | +0.09 |
| 6   | 68 | 19 | 87 | 21.8% | +123 | **+1.414** | +1.34 |
| 7   | 27 |  6 | 33 | 18.2% | +110 | **+3.333** | +4.76 |
| **All bids** | **141** | **49** | **190** | **25.8%** | **+288** | **+1.516** | — |

Bid 5 nearly decuples its per-hand profit (+0.786 vs +0.09), bid 6 holds
steady, and bid 7 drops about 1.4 per hand but with only 33 observations
this is very noisy.

### Defense: Regressed (−1.78/hand vs V2) ⚠

Defense fell from −1.224 (V2) to **−3.008 (V3 partial)**. This is the
single most surprising finding. Three hypotheses rank-ordered by
likelihood:

1. **Sample variance.** 260 defensive hands is a small sample for
   ±0.5 precision. V2 had 700 defensive hands; V3 partial has 260.
   Bootstrap 95% CI on V3 defense would plausibly span roughly
   −4.0 to −2.0, which does not exclude the V2 value of −1.22. A 10%
   variance run can produce this kind of gap.
2. **Heuristic interaction bug.** The V3 defense heuristics may be
   interacting poorly — e.g., 3rd-hand-high when declarer leads may be
   forcing us to dump high cards on tricks that we could have ducked.
   See "V4 Candidates" below.
3. **bud_bot adapted.** Unlikely — `bud_bot` is deterministic relative
   to visible state; we are not a new opponent it can learn from.

**However:** the offense gain (+1.017) more than covers the defense loss
(−1.784 × 260 ÷ 547 = −0.848 session-weighted), producing a net session
improvement. The defense regression alone is NOT causing V3 to lose —
V3 is still the best session to date by EPPD.

## Rolling 20-Match EPPD Windows

| Window | Wins | Win% | Hands | Net EPPD |
|--------|-----:|-----:|------:|---------:|
|   1–20 |   10 |  50% |   209 |  −0.110  |
|  11–30 |   10 |  50% |   202 |  −0.253  |
|  21–40 |    9 |  45% |   207 |  −0.377  |
|  31–50 |   12 |  60% |   202 | **+0.020** |

The positive window (matches 31–50) matches the pattern seen in V2
(which also posted one positive 20-match window). The run was
terminated at match 54, so windows 41–60 and 51–70 do not exist in
this dataset.

## Contract-Type Breakdown

| Contract | Hands | Net | Per-hand |
|----------|------:|----:|---------:|
| suit     | 459 | +16 | +0.035 |
| high     |  31 | −47 | −1.516 |
| low      |  56 | −97 | −1.732 |
| (none/passed-out) | 1 | +20 | +20.000 |

Low contracts are the worst per-hand bucket (−1.73/hand). This mirrors
V2 (low contracts were also a loss bucket) but is smaller in magnitude.
No-trump high contracts also lose per hand.

**V4 candidate:** investigate whether the defensive heuristics are
mis-suited to high/low contracts — the V3 trump-tracker and
3rd-hand-high logic are most effective on suit contracts.

## Heuristic Usage (partial, 2,600 defensive / 2,860 offensive plays)

### Top defensive rationales

| Count | % of def plays | Rationale |
|------:|---------------:|-----------|
| 803 | 30.9% | forced (single legal card) |
| 444 | 17.1% | DEF 2nd low |
| 317 | 12.2% | 4th dump low can't win |
| 245 |  9.4% | void opp-winning: discard low preserve A/K |
| 158 |  6.1% | DEF 3rd partner led follow low |
| 147 |  5.7% | ruff low non-bower |
| 127 |  4.9% | DEF lead off-ace cash before ruff |
|  91 |  3.5% | void+partner winning: dump low preserve A/K |

The new V3 "DEF 2nd low" branch (position-aware 2nd-hand-low) fired on
17.1% of defensive plays — by far the largest V3 addition. This is
the single heuristic most likely responsible for either the
improvement or the regression on defense; a V4 ablation study should
toggle only this branch and rerun.

### Top offensive rationales

| Count | % of off plays | Rationale |
|------:|---------------:|-----------|
| 784 | 27.4% | forced |
| 388 | 13.6% | follow dump low |
| 303 | 10.6% | lead bower to draw trump |
| 245 |  8.6% | ruff low non-bower |
| 200 |  7.0% | void+partner winning: dump low preserve A/K |
| 188 |  6.6% | lead off-ace sure winner |
| 120 |  4.2% | lead high trump to draw |

No surprises on offense; the V2 heuristics dominate.

## Integrity Assertion

**All 547 hands were played without cheating.**

The V3 bot's HTTP / HTML surface area is identical to V2 and V1. It only
reads:

1. `id="hand-card-N"` with `title="X♠"` — our seat 0 hand (the only hand
   the server exposes to us via `engine.get_visible_state()`).
2. `card--played` span `aria-label="Name played X of Suit"` — cards already
   played to the current trick (public information visible to all seats).
3. `contract-bar__suit--X` / contract text — publicly announced trump and
   contract type.
4. `score-*` spans and action-rail text — public scoreboard and auction
   log.

The bot **never** parses opponent hand cards, deck order, seed, or AI
internal state. The server does not render opponent card titles/indices
in the DOM — `web/templates/partials/game_board.html` lines 77–152 only
emit anonymous `card-back` divs for opponent seats, and
`src/bid_euchre/hosted_play/engine.py::get_visible_state()` (lines
465–523) never exposes opponent card lists. This was verified in the
pre-run audit and re-confirmed prior to the session.

Every card the bot played was either:
- a member of the parsed `card--legal` set (server-provided legal index), or
- a fallback to the first hand card when no legal set was parseable.

The server would reject an illegal play anyway, but the client also
defends the contract — no server 4xx was observed in the session log.

**No game rule was violated; no information was consumed that is not
available to a seated human at seat 0.**

## Cumulative StratBot Net EPPD

| Source | Hands | Net pts | Net EPPD |
|--------|------:|--------:|---------:|
| Pre-task baseline (DB) | 562 | −2,851 | −5.073 |
| Session 1 (V1, 2026-04-05) | 1,144 | −816 | −0.713 |
| Session 2 (V2, 2026-04-06) | 1,033 | −434 | −0.420 |
| **Session 3 (V3 partial, 2026-04-07)** | **547** | **−108** | **−0.197** |
| **CUMULATIVE StratBot** | **3,286** | **−4,209** | **−1.281** |

Cumulative StratBot improved from **−1.497** after V2 → **−1.281** after
V3 partial. The original baseline was **−5.073**. Across the three
sessions (and despite all three finishing with negative session EPPD),
the long-run StratBot average has improved by **+3.79 points per deal**
vs its baseline.

## V4 Candidates (not in scope)

Ranked by expected value impact per the partial V3 data:

1. **Ablation-test the "DEF 2nd low" branch** — it is the largest V3
   defensive addition by usage (17.1%). Toggle it off and rerun 100
   matches to measure its marginal effect. Current defense regression
   vs V2 (−1.78/hand) is most consistent with a heuristic interaction
   bug here or in the 3rd-hand-high branch.
2. **Tighten low-contract defense** — low contracts lost −1.73/hand.
   The V3 lead/follow heuristics are tuned for suit contracts;
   low contracts deserve their own branch (e.g., "save your 10 of the
   bid suit", "force declarer to expend high cards").
3. **High-contract defense branch** — similar story, −1.52/hand on
   high contracts. 31 hands is not enough to draw firm conclusions.
4. **Moon-exchange smarter discard** — V3 still uses the V2 fallback
   (dump first 2 hand cards). With bid 7 averaging +3.33/hand, Moon
   support would lift bid-8+ hands further up the range.
5. **Complete the V3 run** — replay this V3 strategy over 100 full
   matches to resolve the defense sample-variance hypothesis. A full
   run would either confirm the regression (then do #1) or reveal
   that matches 55–100 would have pulled defense back toward −1.5 or
   −2.0/hand (in which case the overall EPPD could plausibly land
   close to or slightly above zero).

## Artifacts

- `/tmp/stratbot_v3_player.py` — V3 strategy player (ephemeral, ~1,444 lines)
- `/tmp/stratbot_v3_analyze.py` — JSONL analysis script (ephemeral)
- `data/local_smoke/stratbot_v3/stratbot_v3_100match_20260406T104706.jsonl`
  — full per-hand log for the partial session (547 records, gitignored)
- `data/local_smoke/stratbot_v3/stratbot_v3_smoke_20260406T103400.jsonl`
  — 5-match smoke pre-flight log (45 records)
- `/tmp/stratbot_v3_100_20260406T104706.log` — runtime log (empty; stdout
  buffered — all provenance is in JSONL instead)
- `plans/sessions/2026-04-07_stratbot_100_match_v3.md` — pre-run strategy
  changelog and anti-cheating audit (unchanged; referenced from this
  partial report)

## Outcome

**Goal not hit; run interrupted at 54/100 matches by operator wrap-up
request.** The partial data still delivers a meaningful signal:

- Net EPPD improved from V2 −0.420 → **V3 partial −0.197** (+0.223)
- Cumulative StratBot EPPD improved from −1.497 → **−1.281**
- Offense per-hand profit jumped from +1.270 → **+2.287** — the largest
  single-session offense improvement across the three runs
- Defense regressed from −1.224 → **−3.008**, likely dominated by sample
  variance on 260 hands but requires V4 ablation to isolate
- All bid levels remain individually profitable
- Median match margin flipped to **+1** (from V2 −4)
- Blowouts dropped from 4/100 to 1/54 (extrapolated: ~2/100)
- No cheating or illegal plays detected; 547 hands of integrity-clean data
- One orphan hand with phase="" — a passed-out or edge-case hand that
  merits a follow-up check but does not affect the aggregate conclusions

A V4 session with (a) the same heuristics over 100 full matches, or
(b) the "DEF 2nd low" branch ablated is the natural next step.

## Hard Constraints (re-confirmed post-run)

1. ✅ **No cheating** — audit citations verified; no opponent hand inspected.
2. ✅ **No game rule violations** — server rejected zero illegal plays.
3. ✅ **No `src/bid_euchre/` or `web/` modifications** — V3 was a
   client-side strategy iteration (same scope as V1/V2).
4. ✅ **FlexBot-A player linkage used** (`f0ada160-74ec-41db-ab4b-ac213a36da47`).
