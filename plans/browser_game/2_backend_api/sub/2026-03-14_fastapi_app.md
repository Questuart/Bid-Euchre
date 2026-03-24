# SP-2-01: FastAPI App & Persistence

**ID:** SP-2-01
**Parent:** Phase 2 — Backend API
**Status:** completed
**Governing plan:** `plans/browser_game/governing_plan.md`
**Created:** 2026-03-14

---

## Goal

Build a FastAPI web application with SQLAlchemy persistence, model loading,
and route handlers for the full match lifecycle. Actions are idempotent
and state survives browser refresh. For V1, approved AI models are
configuration-backed and preloaded at app startup rather than discovered from a
database registry.

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `web/__init__.py` | ~1 | Package marker |
| `web/app.py` | ~50 | FastAPI app setup, startup/shutdown, middleware |
| `web/config.py` | ~30 | Environment settings (DB URL/path, `HYBRID_OLSA_ARTIFACT`, default model id, etc.) |
| `web/db.py` | ~120 | SQLAlchemy models + session management |
| `web/schema.sql` | ~60 | Raw SQL schema for reference/init |
| `web/ai_manager.py` | ~80 | Strategy loading from model roster |
| `web/routes.py` | ~250 | All route handlers |
| `web/templates/base.html` | ~40 | Base HTML template (Jinja2) |
| `tests/unit/hosted_play/test_routes.py` | ~200 | Route integration tests |

Total: 9 files, ~830 lines.

## Database Models (`db.py`)

SQLAlchemy models matching the schema in the governing plan §5.2:

```python
class Player(Base):
    __tablename__ = "players"
    id: int (PK)
    nickname: str
    link_uuid: str (unique)
    created_at: str

class Match(Base):
    __tablename__ = "matches"
    id: int (PK)
    match_uuid: str (unique)
    player_id: int (FK → players)
    ai_model: str
    status: str  # "active" | "complete" | "abandoned"
    score_human: int (default 0)
    score_ai: int (default 0)
    hands_played: int (default 0)
    current_hand_number: int (default 0)
    seed: int
    match_state_json: str  # serialized MatchState
    created_at: str
    completed_at: str (nullable)

class Hand(Base):
    __tablename__ = "hands"
    id: int (PK)
    match_id: int (FK → matches)
    hand_number: int
    deal_id: int
    dealer_seat: int
    status: str  # "in_progress" | "redeal" | "complete"
    hand_state_json: str
    # ... outcome fields per governing plan schema

class Decision(Base):
    __tablename__ = "decisions"
    id: int (PK)
    match_id: int (FK → matches)
    hand_id: int (FK → hands)
    turn_number: int
    seat: int
    phase: str  # "bid" | "play"
    actor_type: str  # "human" | "ai"
    decision_source: str  # "human" | model id
    game_state_json: str
    legal_actions_json: str
    chosen_action_json: str
    decision_time_ms: int (nullable)
    created_at: str
```

**Note:** V1 uses SQLite locally and Postgres in deployed environments.
SQLAlchemy abstracts the difference. The `match_state_json` column stores the
full serialized `MatchState` for resume — this avoids complex ORM mapping of
nested game state. The approved model roster is config-backed in V1, so there
is no database `model_registry` table in the initial schema.

## AI Manager (`ai_manager.py`)

```python
class AIManager:
    """Preloads approved bidding policies and play strategies at startup."""

    def __init__(self, config: HostedPlayConfig):
        self.available_models: dict[str, ModelInfo] = {}
        self.default_model_id = "heuristic"
        self._load_models(config)

    def _load_models(self, config):
        """Register and preload the approved V1 roster once per app process."""

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Return display name, description, and instantiated policy/strategy."""

    def list_available(self) -> list[ModelInfo]:
        """Models available for selection in UI."""

@dataclass
class ModelInfo:
    id: str
    name: str
    description: str
    bidding_policy: BiddingPolicy
    play_strategy: Strategy  # always GluttonStrategy
```

Model discovery at startup:
1. `heuristic` — always available (`HeuristicSuitBidder()`)
2. `hybrid_olsa` — available if `HYBRID_OLSA_ARTIFACT` or equivalent configured path exists
3. `gbt_action_value` — deferred until post-MVP

Model discovery is driven by environment configuration rooted at a centralized
path config, not by hardcoded paths in routes or templates. Routes read cached
model instances from `app.state.ai_manager`; they do not load artifacts on
demand.

## Route Handlers (`routes.py`)

| Method | Path | Handler | Response |
|--------|------|---------|----------|
| GET | `/` | `landing()` | HTML: create game form |
| POST | `/new` | `create_game()` | 302 → `/play/{uuid}` |
| GET | `/play/{uuid}` | `game_page()` | HTML: nickname prompt or game board |
| POST | `/play/{uuid}/nickname` | `set_nickname()` | HTMX partial: model selection |
| POST | `/play/{uuid}/select-ai` | `select_ai()` | HTMX partial: game board (first hand dealt) |
| POST | `/play/{uuid}/bid` | `submit_bid()` | HTMX partial: updated board |
| POST | `/play/{uuid}/play-card` | `submit_card()` | HTMX partial: updated board |
| POST | `/play/{uuid}/new-match` | `new_match()` | HTMX partial: model selection |

### Request/Response Flow

Every game-action POST (`/bid`, `/play-card`):

1. Load `MatchState` from DB (`match.match_state_json`)
2. Validate action (correct phase, correct seat, legal move)
3. **Idempotency check:** if `request.turn_number <= state.current_hand.turn_number`,
   return current visible state without modifying anything
4. Call `MatchEngine.submit_human_bid()` or `submit_human_card()`
   - Engine auto-advances all AI turns
5. Ensure the current `hands` row exists for the active hand
6. Log the human decision to `decisions` table
7. Log each AI decision to `decisions` table
8. Serialize updated `MatchState` back to `match.match_state_json`
9. Update `match` row (score, hands_played, status)
10. If the hand completed or redealt, update the current `hands` row with outcome fields
11. Return HTMX partial with updated game board

### Idempotent Submission

Each action POST includes `turn_number` (from the visible state).
If the submitted `turn_number` doesn't match the current state's expected
turn, the POST returns the current state without modification. This makes
browser refresh and double-click safe.

## Startup Sequence (`app.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize database (create tables if needed)
    # 2. Load approved V1 AI models once via AIManager
    # 3. Store AIManager in app.state
    # 4. Routes only look up cached model ids; no per-request artifact loading
    yield
    # Cleanup

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="web/static"))
templates = Jinja2Templates(directory="web/templates")
```

## Required Tests (`test_routes.py`)

Using FastAPI `TestClient`:

1. **Create game** — POST `/new` → 302 with UUID
2. **Set nickname** — POST `/play/{uuid}/nickname` → stores in DB
3. **Select AI model** — POST `/play/{uuid}/select-ai` → match created, first hand dealt
4. **Submit bid** — POST `/play/{uuid}/bid` → state advances
5. **Submit card** — POST `/play/{uuid}/play-card` → state advances
6. **Idempotent resubmission** — POST same turn_number twice → same response
7. **Invalid move rejected** — POST illegal card → error response
8. **Match resume** — GET `/play/{uuid}` after bid → shows correct state
9. **Match completion** — play to ±52 → status becomes complete
10. **Decision logging** — after a hand, verify `decisions` rows exist

## Validation Commands

```bash
uv run python -m pytest tests/unit/hosted_play/test_routes.py -v
# Manual: uvicorn web.app:app --reload, then curl lifecycle
```

## Outcome

- Result: COMPLETE
- PRs: #1430 (DB models, AI manager, schema), #1435 (routes, templates, tests)
- Notes: All 9 planned files created. 8 route handlers with HTMX partial responses. 17 integration tests covering all 10 required scenarios plus 7 edge cases. V1 limitation: AI decision logging uses placeholders for legal_actions/game_state. `make check-quiet` green.
