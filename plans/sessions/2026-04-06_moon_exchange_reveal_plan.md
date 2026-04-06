# Moon Exchange Reveal at End of Hand

**Issue:** #2554
**Date:** 2026-04-06
**Author:** analyst-b
**Status:** READY FOR DISPATCH

## Problem Statement

When a moon is bid and the exchange happens, the partner's AI exchange
decisions are invisible at end of hand. The user cannot evaluate whether
the partner AI made good card-selection choices. The existing exchange
interstitial shows what was given/received before trick play starts, but
the post-hand result screen does not surface partner's full hand.

**Operator request (Telegram msg 502):** Show partner's final hand at end
of moon hands with exchanged cards highlighted.

## Architecture Analysis

### Exchange Data Flow

The moon exchange is a 2-card swap (not 3 as the issue mentions; the code
uses `n_cards=2` throughout `src/bid_euchre/sim/exchange.py`). The mooner gives their
2 worst cards to partner, and receives partner's 2 best.

**Exchange data storage** (`src/bid_euchre/hosted_play/state.py:102-107`):

```python
exchange_given: list[list[str]] | None = None    # mooner's 2 worst (given to partner)
exchange_received: list[list[str]] | None = None  # partner's 2 best (received by mooner)
exchange_phase: str | None = None                 # "selecting" during interactive phase
```

All exchange fields are stored **from the mooner's perspective**, serialized
correctly in `to_dict()`/`from_dict()`, and exposed in `get_visible_state()`
(`src/bid_euchre/hosted_play/engine.py:495-497`).

### Key Discovery: Partner's Hand is Available at End of Hand

**Moon trick play uses 3-player tricks.** The mooner's partner sits out:

```python
# src/bid_euchre/hosted_play/engine.py:378-380, 870-872
hand.sitting_out_seat = (hand.bidder_seat + 2) % _NUM_PLAYERS
```

Cards are `.pop()`-ed from `hand.hands[seat]` during trick play
(`src/bid_euchre/hosted_play/engine.py:946`). Since the partner sits out and plays zero cards, their
10-card post-exchange hand **remains intact** in `hand.hands[sitting_out_seat]`
at end of hand. No reconstruction or snapshot field is needed.

### Current End-of-Hand UI

The `web/templates/partials/hand_result.html` template
already renders a moon exchange summary section (lines 115-127):

```jinja2
{% if hand_bid_type == "moon" and exchange_given_cards and exchange_received_cards %}
    <div class="result-exchange">
        <p>Given {{ exchange_given_cards|length }} to partner: [cards]</p>
        <p>Received {{ exchange_received_cards|length }} from partner: [cards]</p>
    </div>
{% endif %}
```

This shows the exchange as text-only cards. The new feature adds partner's
full hand with visual card components and highlight styling.

### Template Context Pipeline

1. `engine.get_visible_state()` (`src/bid_euchre/hosted_play/engine.py:465-523`)
   builds the visible state dict. Currently exposes `human_hand` (line 489) but
   **explicitly excludes other players' hands** (line 470 docstring).

2. `_build_game_context()` (`web/routes.py:489-643`) merges visible state into
   the Jinja2 context dict. The `hand_result` phase is dispatched by
   `_game_phase()` (`web/routes.py:347-348`) when `hand.phase == "complete"`.

3. `web/templates/partials/game_content.html` (line 33-34) includes
   `web/templates/partials/hand_result.html` when `phase == "hand_result"`.

### Exchange Perspective Mapping

From mooner's perspective (how data is stored):

| Field | Mooner perspective | Partner perspective |
|-------|-------------------|-------------------|
| `exchange_given` | Cards mooner gave away (worst) | Cards partner received |
| `exchange_received` | Cards mooner received (best) | Cards partner sent away |

In partner's post-exchange hand at end of hand:
- Cards matching `exchange_given` = received from mooner (highlight as "received")
- `exchange_received` values = sent to mooner (NOT in partner's hand; show separately)

### Moon Scenarios by Bidder Seat

| Bidder | Partner (sits out) | Human role | Feature value |
|--------|-------------------|------------|---------------|
| Seat 0 (human) | Seat 2 (AI) | Mooner | **High** - user wants to evaluate AI partner's exchange choices |
| Seat 2 (AI partner) | Seat 0 (human) | Partner (sits out) | **Low** - user already knows their own hand; still useful as summary |
| Seat 1 (AI opponent) | Seat 3 (AI opponent) | Spectator | **Low** - opponent's partner, not human's partner |
| Seat 3 (AI opponent) | Seat 1 (AI opponent) | Spectator | **Low** - opponent's partner, not human's partner |

**Recommendation:** Show partner's hand reveal for ALL moon hands (any
bidder), since the exchange data is always available and the rendering cost
is minimal. Conditionally gate on `bid_type == "moon"` only.

## Implementation Approach

### Change 1: Expose partner's hand in visible state (engine.py)

In `get_visible_state()` (`src/bid_euchre/hosted_play/engine.py:465-523`), when the hand is complete
and was a moon bid, include the sitting-out seat's hand:

```python
# After line 494 (sitting_out_seat assignment)
# Reveal partner's hand at end of moon hand for exchange review
if (
    hand.phase == "complete"
    and hand.bid_type == "moon"
    and hand.sitting_out_seat is not None
):
    result["partner_exchange_hand"] = [
        [c.suit, c.rank] for c in hand.hands[hand.sitting_out_seat]
    ]
    result["partner_exchange_seat"] = hand.sitting_out_seat
```

**File:** `src/bid_euchre/hosted_play/engine.py`
**Lines:** ~494 (after `sitting_out_seat` assignment in `get_visible_state`)
**Risk:** Low. New fields only added when phase is "complete" + moon. No
existing code reads these fields, so no regression path.

### Change 2: Render partner's hand in hand_result.html

Expand the existing exchange section in `web/templates/partials/hand_result.html`
(after line 127) to render partner's full hand with card components:

```jinja2
{% set partner_hand = partner_exchange_hand | default([], true) %}
{% set partner_seat_num = partner_exchange_seat | default(None, true) %}
{% if hand_bid_type == "moon" and partner_hand %}
    <div class="result-partner-hand" aria-label="Partner hand after exchange">
        <h3 class="result-partner-hand__title">
            {{ partner_seat_label }}'s Hand (after exchange)
        </h3>
        <div class="result-partner-hand__cards" role="list">
            {% for card in partner_hand %}
                {% set is_received = [card[0], card[1]] in exchange_given_cards %}
                <div class="card card--{{ suit_classes.get(card[0], 'spades') }}
                            {% if is_received %}card--exchange-received{% endif %}"
                     role="listitem">
                    <span class="card__rank">{{ card[1]|display_rank }}</span>
                    <span class="card__suit">{{ suit_symbols.get(card[0], card[0]) }}</span>
                    {% if is_received %}
                        <span class="card__exchange-badge">from {{ seat_labels.get(bidder_seat, "Mooner") }}</span>
                    {% endif %}
                </div>
            {% endfor %}
        </div>
        <p class="result-partner-hand__sent">
            Sent to {{ seat_labels.get(bidder_seat, "Mooner") }}:
            {% for card in exchange_received_cards %}
                <span class="card-text">
                    <span class="suit-icon suit-icon--{{ suit_classes.get(card[0], 'spades') }}">
                        {{ suit_symbols.get(card[0], card[0]) }}
                    </span> {{ card[1]|display_rank }}
                </span>{% if not loop.last %}, {% endif %}
            {% endfor %}
        </p>
    </div>
{% endif %}
```

**File:** `web/templates/partials/hand_result.html`
**Lines:** After line 127 (end of existing exchange section)
**Risk:** Low. New section is gated on `partner_hand` being truthy. Renders
nothing for non-moon hands or when partner hand is not available.

### Change 3: CSS for partner hand section

Add styles for `.result-partner-hand` and the exchange highlight classes.
Reuse existing `.card--exchange-received` styles from
`web/templates/partials/moon_exchange.html`.

**File:** `web/static/style.css`
**Risk:** Low. Additive CSS only.

### Change 4: Tests

Add tests in `tests/unit/hosted_play/test_partials.py`:

1. `test_moon_result_shows_partner_hand` — partner hand renders with cards
2. `test_moon_result_highlights_received_cards` — cards from exchange_given
   get the exchange-received CSS class
3. `test_moon_result_shows_sent_cards` — exchange_received shown as "sent" text
4. `test_non_moon_no_partner_hand` — regular hands don't render partner section
5. `test_partner_hand_missing_graceful` — template handles missing partner_exchange_hand

Add a test in `tests/unit/hosted_play/test_engine.py`:

6. `test_visible_state_includes_partner_hand_on_moon_complete` — verify
   `get_visible_state()` includes `partner_exchange_hand` when phase is
   "complete" and bid_type is "moon"
7. `test_visible_state_excludes_partner_hand_non_moon` — verify field absent
   for regular hands

## Dispatch Packet for brws-author Lane

```yaml
title: "feat(web): show partner hand with exchange highlights at end of moon hand (#2554)"
description: |
  Add partner's full hand reveal to the hand result screen after moon hands.
  The partner (who sits out during trick play) has their 10-card post-exchange
  hand intact in state. Expose it through get_visible_state() and render it
  in web/templates/partials/hand_result.html with visual highlights on exchanged cards.

  Plan: plans/sessions/2026-04-06_moon_exchange_reveal_plan.md

scope_declared:
  - src/bid_euchre/hosted_play/engine.py     # get_visible_state() — add partner_exchange_hand
  - web/templates/partials/hand_result.html   # render partner hand section
  - web/static/style.css                       # additive CSS for partner hand display
  - tests/unit/hosted_play/test_partials.py   # template tests
  - tests/unit/hosted_play/test_engine.py     # visible state tests

validation:
  tier1: |
    uv run python -m pytest tests/unit/hosted_play/test_partials.py -k "partner_hand or exchange" -v
    uv run python -m pytest tests/unit/hosted_play/test_engine.py -k "partner_hand" -v
  tier2: make check-gated

acceptance_criteria:
  - get_visible_state() returns partner_exchange_hand and partner_exchange_seat
    when hand.phase == "complete" and hand.bid_type == "moon"
  - hand_result.html renders partner's 10-card hand with card components
  - Cards matching exchange_given (mooner's discards that went to partner) are
    visually highlighted with card--exchange-received class
  - Cards partner sent to mooner (exchange_received) shown as text below the hand
  - Non-moon hands render NO partner hand section (no regression)
  - Template handles missing partner_exchange_hand gracefully (default empty)
  - Mobile viewport (iPhone 14 Pro) renders cleanly (visual check via playtest)

refs: "#2554"
priority: normal
domain: browser-game
```

## Issue Clarification: 2-Card Exchange, Not 3

The issue #2554 body says "3-card exchange" but the implementation uses
**2-card exchange** throughout:

- `src/bid_euchre/sim/exchange.py:200-264` — `perform_exchange()` swaps 2 cards each way
- `src/bid_euchre/hosted_play/engine.py:317-318` — validation requires exactly 2 card indices
- `src/bid_euchre/sim/exchange.py:238-239` — `_select_mooner_discards` and `_select_partner_gifts`
  both use `n_cards=2`

The acceptance criteria in the issue that reference "3 cards" should be
read as "2 cards." No code change needed for this — it's an issue
description error.

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Double-deck card matching in template (same card appears twice) | Medium | Use list containment check `[suit, rank] in exchange_given_cards` — works for double deck since both copies would match |
| Partner hand empty at end of hand | Very Low | Only possible if partner was NOT sitting out, which contradicts `bid_type == "moon"`. Gate on `sitting_out_seat is not None` |
| Existing exchange tests break | Very Low | New section is additive, gated on new template variable. Existing tests don't set `partner_exchange_hand` |
| CSS conflicts with `web/templates/partials/moon_exchange.html` styles | Low | Reuse existing `.card--exchange-received` class, scope new styles under `.result-partner-hand` |

## Out of Scope

Per issue #2554:
- Showing all 4 hands at end of hand (only partner's, only for moon)
- Changing moon exchange logic (reveal only, not behavior change)
- Showing exchange during real-time play (only at end of hand)

## Outcome

_To be filled after implementation PR merges._
