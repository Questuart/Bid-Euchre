# SP-2-01: FastAPI App & Persistence

**ID:** SP-2-01
**Parent:** Phase 2 — Backend API
**Status:** proposed
**Governing plan:** `plans/browser_game/governing_plan.md`
**Created:** 2026-03-14

---

## Goal

Build a FastAPI web application with SQLAlchemy persistence, model loading,
and route handlers for the full match lifecycle. Actions are idempotent
and state survives browser refresh.

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `web/__init__.py` | ~1 | Package marker |
| `web/app.py` | ~50 | FastAPI app setup, startup/shutdown, middleware |
| `web/config.py` | ~30 | Environment settings (DB path, model dir, etc.) |
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
    player_id: int (FK → players)
    ai_model: str
    status: str  # "active" | "complete" | "abandoned"
    score_human: int (default 0)
    score_ai: int (default 0)
    hands_played: int (default 0)
    seed: int
    match_state_json: str  # serialized MatchState
    created_at: str
    completed_at: str (nullable)

class Hand(Base):
    __tablename__ = "hands"
    id: int (PK)
    match_id: int (FK → matches)
    hand_number: int
    # ... per governing plan schema

class Decision(Base):
    __tablename__ = "decisions"
    id: int (PK)
    hand_id: int (FK → hands)
    turn_number: int
    seat: int
    phase: str  # "bid" | "play"
    decision_source: str  # "human" | model name
    game_state_json: str
    legal_actions_json: str
    chosen_action_json: str
    decision_time_ms: int (nullable)
    timestamp: str
```

**Note:** V1 uses SQLite locally and Postgres in deployed environments.
SQLAlchemy abstracts the difference. The `match_state_json` column stores the
full serialized `MatchState` for resume — this avoids complex ORM mapping of
nested game state.

## AI Manager (`ai_manager.py`)

```python
class AIManager:
    """Loads bidding policies and play strategies from model roster."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.available_models: dict[str, ModelInfo] = {}
        self._discover_models(models_dir)

    def _discover_models(self, models_dir):
        """Register heuristic always; register hybrid_olsa and gbt_action_value when configured artifacts exist."""

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
3. `gbt_action_value` — available if `GBT_ACTION_VALUE_ARTIFACT` or equivalent configured path exists

Model discovery is driven by environment configuration rooted at a centralized
models directory/path config, not by hardcoded paths in routes or templates.

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
5. Log the human decision to `decisions` table
6. Log each AI decision to `decisions` table
7. Serialize updated `MatchState` back to `match.match_state_json`
8. Update `match` row (score, hands_played, status)
9. If hand completed, insert `hands` row with outcome
10. Return HTMX partial with updated game board

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
    # 2. Load AI models via AIManager
    # 3. Store AIManager in app.state
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

_To be filled after implementation._
