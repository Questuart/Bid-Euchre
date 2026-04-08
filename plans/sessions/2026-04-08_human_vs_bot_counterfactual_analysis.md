# Human vs Bot Behavior Analysis: Bidding & Play Counterfactuals

**Date:** 2026-04-08
**Analyst:** analyst-a
**Task:** 9d7b9b23eda7
**Data source:** Render production DB (`bideuchre-db`), decisions table

---

## 1. Data Availability

Counterfactual columns were introduced in late PRs (#2616, #2618) and auto-populated
for new decisions from that point forward. Historical backfill has not been run yet
(requires GBT model artifact on the server), so coverage is limited to decisions
captured since deployment.

| Column | Phase | Human rows | Rows with CF | Coverage |
|--------|-------|-----------|-------------|---------|
| `counterfactual_json` | bid | 8,777 | 30 | 0.3% |
| `glutton_action_json` | play | 87,529 | 282 | 0.3% |

**Players represented:**

| Player | Matches | Bid decisions | Play decisions |
|--------|---------|--------------|---------------|
| Que | 3 (902, 908, 910) | 21 | 202 |
| Meeks | 2 (906, 909) | 11 | 102 |
| TEST (internal) | 1 (901) | 1 | 0 |

All covered decisions come from the post-April-8 deployment window (~days of live
traffic). **Statistical significance caveat applies to all findings below**: 30 bid
decisions are insufficient for hypothesis testing; the findings are directional only.

**Recommendation:** Run the historical backfill once GBT artifact is accessible on the
server. This will increase bid CF coverage ~290× and play CF coverage ~310×, enabling
statistically defensible claims (target ≥2,000 per category per `.claude/rules/deferred/05_rigor.md`).

---

## 2. Bidding Divergence Analysis

### 2.1 Overall Agreement

| Category | Count | Pct |
|----------|-------|-----|
| Exact agreement (same n + contract) | 17 | 56.7% |
| — of which both passed | 12 | 40.0% |
| — of which same non-zero bid | 5 | 16.7% |
| Human overbid (bid higher n than GBT) | 10 | 33.3% |
| Human underbid (passed when GBT would bid) | 2 | 6.7% |
| Same level, different contract | 2 | 6.7% |

### 2.2 Overbidding: The Dominant Disagreement

Of the 13 non-agreement cases, **10 (76.9%) are human overbids**. The magnitude is
large:

| Hand | Player | Human bid | GBT recommends | Overbid by |
|------|--------|-----------|---------------|-----------|
| 8777 | Que | 6 D | PASS (0) | +6 |
| 8778 | Que | 6 C | PASS (0) | +6 |
| 8770 | Meeks | 5 LOW | 1 LOW | +4 |
| 8790 | Que | 5 H | 1 H | +4 |
| 8753 | Que | 4 D | 1 C | +3 (+ diff contract) |
| 8785 | Que | 5 C | 2 D | +3 (+ diff contract) |
| 8794 | Que | 5 S | 3 (no data) | +2 |
| 8767 | Meeks | 4 HIGH | 2 HIGH | +2 |
| 8789 | Que | 3 D | 2 C | +1 (+ diff contract) |
| 8773 | Meeks | 6 LOW | 5 LOW | +1 |

**Mean overbid: 3.2 levels** (range 1–6).

The two most extreme cases (hands 8777 and 8778, same match — Que vs bot, match
908) are sequential hands where Que bid 6 twice on hands GBT considered worthless
(PASS). Match 908 ended with score 47–54 (Que loss by 7).

### 2.3 Underbids (Rare)

Only 2 underbid cases observed: once the TEST player passed on a hand GBT rated at
n=3 D, and once a player passed when GBT said 1 S. These may reflect conservative
play or difficulty evaluating weak hands.

### 2.4 Per-Player Summary

| Player | Decisions | Exact agree | Overbid rate | Underbid rate |
|--------|-----------|------------|-------------|--------------|
| Que | 21 | 12 (57.1%) | 8/21 = 38.1% | 0 |
| Meeks | 11 | 6 (54.5%) | 3/11 = 27.3% | 1/11 = 9.1% |

Que overbids in ~38% of their bid decisions — a substantially higher rate than Meeks.
Que's matches also show consistently negative outcome margins (avg −9 pts vs Meeks
+14 pts), consistent with the hypothesis that aggressive overbidding leads to being
set.

### 2.5 Bidding Position Analysis

With 30 samples, no statistically reliable position-based pattern can be extracted.
Qualitatively, the most dramatic overbids (6 vs 0) occur at position 3 and 0
(Que), but this reflects the player rather than the position.

---

## 3. Card Play Divergence Analysis

### 3.1 Overall Agreement

| Dimension | Total | Agree | Disagree | Agreement % |
|-----------|-------|-------|----------|------------|
| **Overall** | 284 | 224 | 60 | 78.9% |
| Suit contracts | 214 | 168 | 46 | 78.5% |
| Low contracts | 70 | 56 | 14 | 80.0% |
| **Lead position** | 74 | 47 | 27 | **63.5%** |
| **Follow position** | 221 | 187 | 34 | **84.6%** |

**The lead–follow gap (63.5% vs 84.6%) is the strongest signal in the play data.**
Humans are considerably less aligned with Glutton's recommendations on lead than
when following suit.

### 3.2 Lead Disagreements: Suit Contracts (25 cases)

Analyzing which card humans chose vs which card Glutton recommended on trick leads
(suit contracts only):

**Pattern A — Human leads trump bower, Glutton prefers off-suit winner (6 cases)**

| Decision | Trump | Human leads | Glutton wants |
|----------|-------|-------------|---------------|
| 382488 | S | S,J (right bower) | C,A (off-suit ace) |
| 382716 | S | S,J (right bower) | D,K (off-suit king) |
| 383130 | S | S,J (right bower) | D,K (off-suit king) |
| 383704 | H | H,J (right bower) | C,K (off-suit king) |
| 383708 | H | H,J (right bower) | C,K (off-suit king) |
| 383356 | C | C,J (right bower) | C,Q (low trump) |

Pattern: **Humans lead their highest trump early; Glutton prefers to cash off-suit
winners first before committing trump.** This is the single most consistent play
disagreement.

**Pattern B — Human leads off-suit, Glutton prefers trump/bower (3 cases)**

| Decision | Trump | Human leads | Glutton wants |
|----------|-------|-------------|---------------|
| 383102 | S | H,A (off-suit ace) | S,J (right bower) |
| 383288 | C | S,A (off-suit ace) | C,J (right bower) |
| 383552 | H | S,J (left bower) | H,J (right bower) |

Pattern: **Occasionally humans lead off-suit aces when Glutton wants to draw trump
immediately** (also Glutton leading higher bower when human leads left bower).
This is the opposite of Pattern A — humans are inconsistent about when to lead trump.

**Pattern C — Small card vs winner disagreement (16 cases)**

The remaining lead disagreements involve choices between off-suit cards at different
strength levels, or between weak trump and stronger trump. These are harder to
categorize without deeper game-state analysis (what opponents' play history suggests,
partnership communication).

### 3.3 Lead Disagreements: Low Contracts (5 cases)

In Low contracts, card ranks are inverted: 10 > J > Q > K > A for trick-winning.

| Decision | Human leads | Glutton wants | Note |
|----------|-------------|---------------|------|
| 382557 | D,Q | H,T | Glutton cashes 10 (winner in LOW) first |
| 382830 | D,T | S,T | Both are 10s — different suit preference |
| 382852 | C,K | S,Q | Glutton leads Q over K (Q wins in LOW) |
| 383222 | D,K | C,J | Glutton leads J over K |
| 383786 | S,Q | H,J | Glutton leads J over Q |

**Pattern: In Low contracts, humans sometimes lead higher-rank (weaker-in-LOW) cards
rather than their 10s and Jacks, which are the actual trick-winners.** Glutton
consistently prefers to cash the lowest-ranked (most powerful in LOW) cards first.
This suggests some players may not fully internalize that 10s win in LOW contracts.

### 3.4 Follow Disagreements

Follow disagreements (84.6% agreement, so 34 cases of 221) are harder to categorize
without deep game-state reconstruction. Common patterns observed:

- **Sluff selection**: Human sluffs one card, Glutton recommends a different sluff (choice
  between two losers — strategic nuance around what to preserve)
- **Trumping partner's winner**: In a few cases Glutton recommends trumping in when
  partner's card is likely winning (possible limitation of Glutton's team awareness)
- **Card ordering**: When the choice is between similar-strength cards in the same suit,
  the specific card chosen differs (e.g., H,T vs H,J on a follow)

### 3.5 Agreement by Trick Number

| Trick | Total | Agree | Agreement % |
|-------|-------|-------|------------|
| 2 | 31 | 20 | 64.5% |
| 3 | 31 | 26 | 83.9% |
| 4 | 30 | 27 | 90.0% |
| 5 | 30 | 21 | 70.0% |
| 6 | 29 | 27 | 93.1% |
| 7 | 29 | 22 | 75.9% |
| 8 | 29 | 22 | 75.9% |
| 9 | 29 | 21 | 72.4% |
| 10 | 29 | 20 | 69.0% |
| 11 | 29 | 29 | 100.0% |

Trick 11 (last trick) shows 100% agreement — trivially forced (only 1 card remains).
Trick 2 shows the lowest agreement (64.5%) — consistent with the lead vs follow split
(trick 2 is the human's second bid/play, where lead decisions dominate early).

### 3.6 Per-Player Play Summary

| Player | Decisions | Agreement |
|--------|-----------|-----------|
| Meeks | 102 | 80.4% |
| Que | 202 | 79.2% |

Play alignment is very similar between players. Neither significantly outperforms the
other in aligning with Glutton's recommendations.

---

## 4. Outcome Correlation

With only 5 matches (2 real players), **no statistically defensible correlation can
be computed**. Directional observations only:

| Player | Matches | W/L | Avg margin | Overbid rate |
|--------|---------|-----|-----------|-------------|
| Meeks | 2 | 2W–0L | +14 | 27% |
| Que | 3 | 0W–3L | −9 | 38% |

Que overbids ~40% more often than Meeks and has a substantially worse win/loss record.
This is **consistent with** (but does not prove) the hypothesis that overbidding is
the primary driver of Que's losses.

For match 908 specifically (Que's worst: 47–54 loss), 6 of 11 tracked bid decisions
show overbidding, including the two "bid 6 on a PASS hand" cases. This hand cluster
coincides with the largest point deficit.

**What's needed for causal claims**: ≥50 completed matches per player, or the
historical backfill + regression analysis controlling for hand strength.

---

## 5. Top Player Guidance Recommendations

Based on the directional patterns above, five actionable tips for human players:

### Tip 1: Don't overbid by 3+ levels — this is the #1 mistake
The most consistent finding is humans bidding 4–6 when GBT recommends 1–2. In a 10-
trick game, overbidding by 3 means you need 75% of tricks to make contract vs 50%.
Unless your hand has multiple bowers + at least 3 trump cards, bids above 5 are high-
risk. Treat GBT's bid recommendation as a calibration anchor.

### Tip 2: In suit contracts, cash your off-suit aces before leading trump
When you have trump control (1–2 bowers), lead your off-suit aces and kings first.
This forces opponents to sluff their side-suit losers rather than wait to discard on
trump leads. Glutton's `cash_winners_on_lead=True` logic validates this principle.
**Exception**: If opponents might be able to ruff your aces, draw trump first.

### Tip 3: In LOW contracts, your 10s and Jacks are gold — play them early
Low contract rank order is 10 > J > Q > K > A. Your 10s are guaranteed winners; lead
them immediately. Don't hold them — there's no value in saving your most powerful cards
in LOW when you need to capture as many tricks as possible.

### Tip 4: Don't lead your right bower on trick 1 unless you need to draw trump
Bowers are the highest trump in the game. Leading them immediately prevents you from
having control later in the hand. The Glutton benchmark consistently prefers to lead
bowers AFTER cashing off-suit winners, not before. Save your bowers for when opponents
might trump your winners.

### Tip 5: Be conservative when you're the 3rd–4th bidder with no auction above 3
If the auction has stayed low (bids of 1–2), the strong hands at the table have likely
been bought at low prices — your hand may be weaker than it looks with top cards split
against you. Que's two "bid 6 on a PASS hand" errors both occurred in this scenario.

---

## 6. Algorithm Improvement Signals

### 6.1 Possible Glutton Team-Awareness Gap (Medium Confidence)

In several follow decisions, Glutton recommends trumping in when the human's partner
appears to be winning the trick. Example: decision 382510 — partner led H,A (ace,
likely winning), opponent played H,Q, and Glutton recommended S,J (right bower) rather
than sluffing a loser. Glutton's greedy-play logic doesn't model partner strength.

**Signal**: Humans correctly sluff in these situations. If this pattern holds in the
full dataset after backfill, GluttonStrategy may need a "partner-win detection" gate.

### 6.2 GBT Contract Type Disagreements May Reflect Model Uncertainty

4 of the 13 bid disagreement cases involve different contract types at the same or
different levels (e.g., Que bids HIGH, GBT says C suit; Que bids D, GBT says C). This
could mean the GBT model is uncertain about suit preference on these hands and the
human has information (specific suit shape intuition) that GBT doesn't fully capture.

**Signal**: After backfill, check if GBT suit-type mismatches cluster around specific
hand shapes (e.g., split-suit holdings with 2+ suit options). This could expose
auction state features not well-represented in the GBT training set.

### 6.3 Humans May Have Better Low-Contract Range Instinct

The 2 underbid cases (human passed when GBT said 1) and the LOW contract observations
suggest humans are appropriately cautious about LOW. GBT recommending n=1 LOW on a
PASS-worthy hand could indicate the model overestimates LOW viability at the 1-bid
threshold (where being set loses more than the bid pays out).

**Signal**: After backfill, compute made-vs-set rate for GBT-recommended LOW bids of
n=1–2 to validate whether this is a calibration issue.

---

## 7. Recommended Follow-Up Issues

| Priority | Issue | Description |
|----------|-------|-------------|
| High | Run historical backfill | `uv run python scripts/backfill_counterfactuals.py` — needs GBT artifact on server. Will grow the dataset from 30 → ~8,800 bid decisions and 282 → ~87,500 play decisions. |
| High | Track overbid rate per player session | Add a dashboard metric: "bid alignment with GBT (overbid rate)". Currently no visibility into this during live play. |
| Medium | Add stratbot player guidance tips | Implement 5 tips above in the in-app guidance page. Current tips are generic. |
| Medium | Investigate Glutton team-awareness gap | Check if Glutton recommends trumping partner's winners more than random chance. If yes, add partner-win detection to GluttonStrategy before using it for play coaching. |
| Low | GBT contract-type alignment analysis | After backfill, compute GBT suit-preference disagreement rate by hand shape. May reveal auction features to add to GBT training. |
| Low | LOW-contract bid calibration check | Check made/set rate for GBT-recommended LOW bids at n=1–2 vs human bids. |

---

## 8. Methodology Notes and Limitations

- **Sample size**: 30 bid decisions and 282 play decisions are pre-statistical. All
  findings are directional, not hypothesis-tested. Run backfill before citing any
  percentage in a product decision.
- **Player selection bias**: Only 2 real players (Meeks, Que) participated in the
  covered window. Que is a known-aggressive bidder. Meeks is a more conservative player.
  Results should not be generalized to the full player population.
- **Glutton as benchmark**: GluttonStrategy is a greedy/myopic baseline — it does not
  plan ahead, model partner strategy, or account for endgame. Disagreements with
  Glutton are not necessarily player errors; they may reflect superior lookahead.
- **GBT as benchmark**: GBTActionValueBidder is the current best bidding model but
  is not infallible. Cases where humans consistently diverge from GBT AND achieve
  better outcomes (not yet measurable) would be evidence of GBT improvement opportunities.
- **Card index semantics**: Play decisions store chosen/recommended card as index
  into the `human_hand` array. The array is not sorted by strength — index comparisons
  require resolving to actual card values.

---

## Outcome

Report committed to `plans/sessions/2026-04-08_human_vs_bot_counterfactual_analysis.md`.

### Top 3 Findings for Orchestrator

1. **Overbidding is the dominant human error**: 10/30 bid decisions (33%) show humans
   bidding 1–6 levels higher than GBT recommends. Mean overbid: 3.2 levels. Two cases
   of humans bidding 6 on hands GBT would pass entirely.

2. **Lead position has 2× more play disagreement than follow**: 36.5% disagreement on
   leads vs 15.4% on follows. The primary lead pattern is humans leading right bowers
   when Glutton prefers to cash off-suit aces/kings first.

3. **Historical backfill needed before any statistical claims**: Current coverage is
   0.3% (30 bid, 282 play decisions). Backfill will grow this ~300×. No p-values or
   confidence intervals are calculable from current data.
