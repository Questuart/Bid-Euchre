"""FastAPI application setup for the Bid Euchre browser game.

Handles startup/shutdown lifecycle:
1. Load configuration from environment
2. Initialize database (create tables if needed)
3. Preload approved V1 AI models via :class:`AIManager`
4. Store manager and session factory in ``app.state``

Routes are defined in :mod:`web.routes` and registered via ``include_router``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .ai_manager import AIManager
from .config import HostedPlayConfig, get_config, override_config
from .db import create_tables, init_engine, make_session_factory
from .routes import router as game_router

_WEB_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _WEB_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    config = get_config()

    # 1. Database
    engine = init_engine(config.database_url)
    create_tables(engine)

    # 2. AI models
    ai_manager = AIManager(config)

    # 3. Templates
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # 4. Stash on app.state for route access
    app.state.config = config
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.ai_manager = ai_manager
    app.state.templates = templates

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

    # Serve static assets (CSS, JS) from web/static/
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

    # Register game routes
    app.include_router(game_router)

    return app
