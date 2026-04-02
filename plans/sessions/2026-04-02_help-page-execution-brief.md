# Execution Brief: Browser Game Help/Onboarding Page

**Task packet:** `f6326ba59665`
**Analyst:** analyst-b
**Date:** 2026-04-02

## Problem Statement

New players landing in the Bid Euchre browser game have no dedicated onboarding
resource. The existing in-game help is a collapsible `<details>` drawer inside
`game_controls.html` (7 bullet points, ~130 words). It only appears once the
player is in an active game — it's invisible on the landing page and absent from
the nav header. A standalone help page accessible from anywhere would improve
onboarding and reduce confusion about game-specific UI elements.

## Scope

**3 files modified, 1 file created:**

| File | Change | Lines (est.) |
|------|--------|-------------|
| `web/templates/help.html` | **NEW** — standalone help page template | ~250 |
| `web/routes.py` | Add `GET /help` route handler | ~10 |
| `web/templates/base.html` | Add "Help" link to `<header>` nav | ~3 |
| `tests/unit/hosted_play/test_routes.py` | Add test for `/help` route | ~15 |

**Explicitly out of scope:**
- Changes to the existing in-game help drawer (`game_controls.html`)
- CSS changes to `style.css` (the help page should use inline `<style>` in the
  `{% block head %}` block, matching the leaderboard pattern)
- Any game logic or engine changes
- Database changes

## Implementation Seam

### 1. Route: `GET /help` (in `web/routes.py`)

Add a simple route that renders `help.html`. The route needs **no auth gate**
(unlike leaderboard which requires `link_uuid`). This is intentional — help
should be accessible to anyone, including players who haven't entered an invite
code yet.

```python
@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Player-facing help and onboarding page."""
    templates = _get_templates(request)
    return templates.TemplateResponse("help.html", {"request": request})
```

**Placement:** After the `landing()` route (line ~557) and before `enter_code()`.
This groups standalone GET pages together.

### 2. Nav link: `base.html`

Currently the nav only renders when `link_uuid` is defined (inside a game).
The help link should be **always visible** — outside the conditional block.

Current structure (lines 27-36):
```html
<header role="banner">
    <div class="header-bar">
        <h1><a href="/" aria-label="Bid Euchre home">Bid Euchre</a></h1>
        {% if link_uuid is defined and link_uuid %}
        <nav class="header-nav" aria-label="Main navigation">
            <a href="/play/{{ link_uuid }}">Game</a>
            <a href="/leaderboard/{{ link_uuid }}">Leaderboard</a>
        </nav>
        {% endif %}
    </div>
</header>
```

**Change:** Add a nav that's always visible for the Help link, and keep the
game-specific nav inside the conditional:

```html
<header role="banner">
    <div class="header-bar">
        <h1><a href="/" aria-label="Bid Euchre home">Bid Euchre</a></h1>
        <nav class="header-nav" aria-label="Main navigation">
            {% if link_uuid is defined and link_uuid %}
            <a href="/play/{{ link_uuid }}">Game</a>
            <a href="/leaderboard/{{ link_uuid }}">Leaderboard</a>
            {% endif %}
            <a href="/help">Help</a>
        </nav>
    </div>
</header>
```

This ensures the Help link appears on every page (landing, game, leaderboard,
help itself) and the Game/Leaderboard links appear only when in a game context.

### 3. Template: `help.html`

Extends `base.html`. Uses the same BEM-like class naming and inline `<style>`
pattern established by `leaderboard.html`. Content sections:

#### Section A: How to Play Bid Euchre
Source material: `docs/01_core/RULES.md` §§1-6, simplified for casual players.

Key points to cover (in plain language):
- **Players & Teams:** 4 players, 2v2 partnerships (you + AI Partner vs AI Left + AI Right)
- **The Deck:** 40 cards — double deck with 10, J, Q, K, A in each suit (two copies of every card)
- **Dealing:** Each player gets 10 cards, 10 tricks per hand
- **Bidding:** Goes once around the table starting left of dealer. Bid a number of tricks you think your team can take, plus a contract type. Pass if you don't want to bid. Bids must go up.
- **Contract Types:**
  - **Suit** — pick a trump suit. Trump beats all non-trump cards.
  - **High** — no trump. Highest card of the led suit wins.
  - **Low** — no trump. Lowest card of the led suit wins.
- **Bowers** (suit contracts only): Jack of trump = Right Bower (highest trump). Jack of same color = Left Bower (second highest trump). Both count as trump for following suit.
- **Trick Play:** Must follow the suit that was led if you can. If you can't, play anything. Highest card in the led suit (or highest trump) wins the trick.
- **Duplicates:** Two copies of every card exist. If identical cards tie, the first one played wins.

#### Section B: Special Bids — Moon & Loner
- **Moon:** Must take all 10 tricks. Before play, you exchange cards with your partner. Worth +20 if made, -20 if set.
- **Loner:** Must take all 10 tricks alone — your partner sits out. Worth +40 if made, -40 if set.

#### Section C: Scoring
- **Match target:** First team to +52 or -52 points wins
- **Making the bid:** Your team scores the number of tricks you took
- **Getting set:** Your team loses points equal to your bid amount
- **Defending:** The defending team always scores the tricks they took
- Summary table for regular/moon/loner scoring

#### Section D: UI Guide — Game Board Markers
Explain the seat markers visible during gameplay:

| Marker | Color | Meaning |
|--------|-------|---------|
| **D** | Orange | Dealer for this hand |
| **X** | Gold/amber | Declarer (won the auction) |
| **L** | Blue | Leading the current trick |
| **▶** | Green | Whose turn it is |
| **SO** | Gray | Sitting out (loner bid) |

Also explain:
- **Card highlighting:** Green-bordered cards are legal plays
- **Trick history:** Collapsible "Cards Played" section shows all tricks played so far
- **Auction transcript:** Shows what each player bid during the auction

#### Section E: FAQ
- *What happens if everyone passes?* — Hand is redealt, dealer rotates.
- *Why can't I play a certain card?* — You must follow the suit that was led.
- *What are the red and black card colors?* — Hearts/diamonds are red, spades/clubs are black. Standard suit colors.
- *How does the Left Bower work?* — In suit contracts, the jack of the same-color suit becomes trump. So if trump is ♠, the J♣ is also trump (Left Bower).
- *What does "First to ±52 wins" mean?* — The match ends when either team reaches +52 or drops to -52 total points.

### 4. Test: `test_routes.py`

Add a test that verifies:
1. `GET /help` returns 200
2. Response contains key content markers (e.g., "How to Play", "Scoring")
3. Response is HTML

```python
def test_help_page(client):
    """GET /help returns the help page."""
    resp = client.get("/help")
    assert resp.status_code == 200
    assert "How to Play" in resp.text
    assert "Scoring" in resp.text
```

## Acceptance Criteria

1. `GET /help` returns 200 with the help page HTML
2. The help page is accessible from the landing page (no invite code required)
3. A "Help" nav link appears in the header on all pages
4. Content covers: rules overview, special bids, scoring, UI markers, FAQ
5. Template uses existing CSS variables and BEM naming convention
6. All existing tests still pass
7. `make lint` passes

## Validation Commands

```bash
# Tier 1 — targeted tests
uv run python -m pytest tests/unit/hosted_play/test_routes.py -v -k "help"
uv run python -m pytest tests/unit/hosted_play/ -v

# Tier 2 — full validation before PR
make check-quiet
```

## Risks and Scope Traps

1. **Scope creep into CSS:** The help page should use inline styles in
   `{% block head %}` (leaderboard pattern), not add new classes to `style.css`.
   This keeps the change contained.

2. **Nav link breaking mobile layout:** The header nav currently has 2 links
   (Game, Leaderboard). Adding a third ("Help") is low-risk but should be
   verified visually. The existing flexbox layout should accommodate it.

3. **Content accuracy:** The help page content must match RULES.md. In
   particular:
   - Moon exchange: declarer exchanges cards with partner (not picks from deck)
   - Loner: partner sits out (declarer plays alone, 3 players play tricks)
   - Scoring: defending team ALWAYS gets tricks won, declaring team gets tricks
     won if they make it or -bid if they don't

4. **Link from game_controls.html drawer:** The existing help drawer in
   `game_controls.html` could optionally link to the full help page, but this
   is NOT required for the initial PR. It can be a follow-up.

5. **`app.py` self-test:** The `_run_self_test()` function checks specific
   template names at startup. If `help.html` is added, consider whether it
   should be in the startup check list (lines 78-83). Recommendation: don't
   add it to the startup check — it's not critical infrastructure. The route
   test covers it.

## PR Decomposition

**Single PR** — this is a bounded, 3-file change with one new template. No
decomposition needed.

**Branch name:** `feat/web-help-page`

**PR title:** `feat(web): add player-facing help/onboarding page`

## File Ownership / Parallelism

All changes are in the `web/` directory. No overlap with:
- Engine/hosted_play changes
- Strategy changes
- Platform/ops changes

Safe to execute in parallel with any non-web PR. Within the web space, the
files touched (`routes.py`, `base.html`, new `help.html`) have low collision
risk with other active browser PRs unless they also modify `base.html` header
nav.

## Orchestrator Handoff

This brief is ready for dispatch to any author lane. The implementation is
straightforward: one new template (content-heavy but no logic), one route
(5 lines), one nav link edit (3 lines), one test (5-10 lines).

**Estimated implementation time:** 15-25 minutes for an author lane.

## Outcome

_To be filled after implementation._
