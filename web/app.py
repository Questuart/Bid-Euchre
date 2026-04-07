"""FastAPI application setup for the Bid Euchre browser game.

Handles startup/shutdown lifecycle:
1. Load configuration from environment
2. Initialize database (create tables if needed, auto-seed invite code)
3. Preload approved V1 AI models via :class:`AIManager`
4. Store manager and session factory in ``app.state``

Routes are defined in :mod:`web.routes` and registered via ``include_router``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.templating import Jinja2Templates

from .ai_manager import AIManager
from .cleanup import expire_stale_matches
from .config import HostedPlayConfig, get_config, override_config
from .db import (
    Base,
    InviteCode,
    create_tables,
    generate_invite_code,
    init_engine,
    make_session_factory,
)
from .middleware import RequestLoggingMiddleware
from .routes import router as game_router
from .template_filters import display_rank, effective_suit, is_bower

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"


def _run_self_test(engine, templates_dir: Path, static_dir: Path) -> None:
    """Verify critical resources are available at startup.

    Checks:
    1. Database tables exist (migrations applied).
    2. Static assets directory exists and contains ``style.css``.
    3. Template directory exists and key templates render without error.

    Raises :class:`RuntimeError` if any check fails — the application
    should not start in a broken state.
    """
    errors: list[str] = []

    # 1. DB tables
    try:
        inspector = sa_inspect(engine)
        existing_tables = set(inspector.get_table_names())
        required_tables = {t.name for t in Base.metadata.sorted_tables}
        missing = required_tables - existing_tables
        if missing:
            errors.append(f"Missing DB tables: {sorted(missing)}")
    except Exception as exc:
        errors.append(f"DB inspection failed: {exc}")

    # 2. Static assets
    if not static_dir.is_dir():
        errors.append(f"Static assets directory missing: {static_dir}")
    else:
        if not (static_dir / "style.css").is_file():
            errors.append("style.css not found in static directory")

    # 3. Templates
    if not templates_dir.is_dir():
        errors.append(f"Templates directory missing: {templates_dir}")
    else:
        try:
            test_templates = Jinja2Templates(directory=str(templates_dir))
            # Verify key templates can be loaded (not full render — just load)
            for name in (
                "base.html",
                "landing.html",
                "errors/404.html",
                "errors/500.html",
                "errors/htmx_error.html",
            ):
                test_templates.get_template(name)
        except Exception as exc:
            errors.append(f"Template load failed: {exc}")

    if errors:
        msg = "Startup self-test FAILED:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info("Startup self-test passed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    config = get_config()

    # 1. Database
    engine = init_engine(config.database_url)
    create_tables(engine)
    session_factory = make_session_factory(engine)

    # 1b. Migrate: add onboarding_complete column for existing databases.
    # create_tables only creates new tables — it does not ALTER existing ones.
    # On a fresh DB the column already exists; on an existing DB we add it
    # and mark all players who already have a nickname as onboarding-complete
    # so they are not forced through the onboarding flow.
    inspector = sa_inspect(engine)
    player_cols = {c["name"] for c in inspector.get_columns("players")}
    if "onboarding_complete" not in player_cols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE players "
                    "ADD COLUMN onboarding_complete INTEGER NOT NULL DEFAULT 0"
                )
            )
            conn.execute(
                text(
                    "UPDATE players SET onboarding_complete = 1 "
                    "WHERE nickname IS NOT NULL"
                )
            )
        logger.info("Migration: added onboarding_complete column to players")

    # 1c. Migrate: add play_strategy_version column for existing databases.
    # Rows created before this migration carry NULL as the honest
    # "unknown cohort" marker — see docs/02_agent/STRATEGY_VERSIONING.md.
    match_cols = {c["name"] for c in inspector.get_columns("matches")}
    if "play_strategy_version" not in match_cols:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE matches " "ADD COLUMN play_strategy_version TEXT")
                )
            logger.info("Migration: added play_strategy_version column to matches")
        except OperationalError:
            # Column already exists — concurrent startup or stale inspector cache (#2532)
            logger.info(
                "Migration: play_strategy_version column already present (concurrent)"
            )

    # 2. Auto-seed invite code on fresh database (atomic: skip if another
    #    instance already seeded between our check and insert)
    seed_session = session_factory()
    try:
        if seed_session.query(InviteCode).count() == 0:
            code = generate_invite_code()
            seed_session.add(InviteCode(code=code, status="active", label="auto-seed"))
            try:
                seed_session.commit()
            except IntegrityError:
                # Another instance already seeded — safe to ignore
                seed_session.rollback()
                logger.info(
                    "Auto-seed invite code skipped — already seeded by another instance"
                )
            else:
                logger.info("Auto-seeded invite code (label=auto-seed)")
    except Exception:
        seed_session.rollback()
        logger.warning("Invite code auto-seed failed — continuing", exc_info=True)
    finally:
        seed_session.close()

    # 3. Cleanup stale matches from previous runs
    cleanup_session = session_factory()
    try:
        expired = expire_stale_matches(cleanup_session)
        cleanup_session.commit()
        if expired:
            logger.info("Startup cleanup: expired %d stale match(es)", expired)
    except Exception:
        cleanup_session.rollback()
        logger.warning("Startup cleanup failed — continuing", exc_info=True)
    finally:
        cleanup_session.close()

    # 4. Startup self-test — fail fast on broken deployment
    _run_self_test(engine, _TEMPLATES_DIR, _STATIC_DIR)

    # 5. AI models
    ai_manager = AIManager(config)

    # 6. Templates
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    # Expose app_url as a Jinja2 global so templates can build absolute
    # URLs (required for og:image and other meta tags that crawlers fetch).
    templates.env.globals["app_url"] = config.app_url.rstrip("/")
    # Custom filter: display_rank converts internal 'T' to user-facing '10'
    templates.env.filters["display_rank"] = display_rank
    # Custom filter: effective_suit resolves bower suits in suit contracts
    templates.env.filters["effective_suit"] = effective_suit
    # Custom filter: is_bower returns 'left', 'right', or '' for bower status
    templates.env.filters["is_bower"] = is_bower

    # 7. Stash on app.state for route access
    app.state.config = config
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.ai_manager = ai_manager
    app.state.templates = templates
    app.state.started_at = datetime.now(timezone.utc)

    yield

    # Shutdown — dispose engine connections
    engine.dispose()


def create_app(config: HostedPlayConfig | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    If *config* is provided it replaces the environment-derived default.
    This is the primary entry point for tests and programmatic usage.
    """
    if config is not None:
        override_config(config)

    app = FastAPI(
        title="Bid Euchre Browser Game",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — honor configured origins (defaults to ["*"] for dev)
    cfg = get_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging — structured request_start/request_complete events
    # with per-request correlation IDs.  Must be added *after* CORS so
    # that the logging middleware wraps the inner app and sees the final
    # response status (Starlette middleware order is LIFO).
    app.add_middleware(RequestLoggingMiddleware)

    # Serve static assets (CSS, JS) from web/static/
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

    # Register game routes
    app.include_router(game_router)

    # ---- Custom error pages ----

    _error_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    def _is_htmx(request: Request) -> bool:
        """Return True when the request was initiated by HTMX."""
        return request.headers.get("HX-Request") == "true"

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException) -> HTMLResponse:
        """Render game-themed 404 page (partial for HTMX, full for browser).

        HTMX 1.x ignores non-2xx responses by default, so HTMX partials
        are returned with status 200 to ensure the swap occurs.  The error
        content itself conveys the problem to the user.
        """
        if _is_htmx(request):
            detail = getattr(exc, "detail", "Not found")
            return HTMLResponse(
                _error_templates.get_template("errors/htmx_error.html").render(
                    {"request": request, "status_code": 404, "message": str(detail)}
                ),
                status_code=200,
            )
        return HTMLResponse(
            _error_templates.get_template("errors/404.html").render(
                {"request": request}
            ),
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc: Exception) -> HTMLResponse:
        """Render game-themed 500 page (partial for HTMX, full for browser).

        HTMX 1.x ignores non-2xx responses by default, so HTMX partials
        are returned with status 200 to ensure the swap occurs.
        """
        logger.exception("Unhandled server error on %s %s", request.method, request.url)
        if _is_htmx(request):
            return HTMLResponse(
                _error_templates.get_template("errors/htmx_error.html").render(
                    {
                        "request": request,
                        "status_code": 500,
                        "message": "Something went wrong. Please try again.",
                    }
                ),
                status_code=200,
            )
        return HTMLResponse(
            _error_templates.get_template("errors/500.html").render(
                {"request": request}
            ),
            status_code=500,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> HTMLResponse | JSONResponse:
        """Return an HTML error for HTMX requests, JSON for API clients.

        FastAPI's default 422 handler returns JSON, which HTMX swaps into
        the game board as raw text.  This handler intercepts validation
        errors and returns a user-friendly HTML partial for HTMX
        requests (#2219).
        """
        if _is_htmx(request):
            return HTMLResponse(
                _error_templates.get_template("errors/htmx_error.html").render(
                    {
                        "request": request,
                        "status_code": 422,
                        "message": "Invalid request. Please refresh the page.",
                    }
                ),
                status_code=200,
            )
        return JSONResponse(
            {"detail": exc.errors()},
            status_code=422,
        )

    return app
