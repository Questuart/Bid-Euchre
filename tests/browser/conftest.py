"""Shared fixtures for Playwright browser E2E tests.

Provides:
- A live FastAPI server running on a random port with a temp SQLite DB
- Invite code and player creation helpers
- Skip logic when Playwright is not installed

These tests are NOT included in ``make check``.  Run via ``make browser-smoke``.
"""

from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import pytest

from tests.unit.hosted_play.conftest import create_browser_ai_test_artifacts

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

if TYPE_CHECKING:
    from playwright.sync_api import Page

# ---------------------------------------------------------------------------
# Auto-skip everything in tests/browser/ when playwright is absent
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Skip browser tests when playwright is not installed."""
    if HAS_PLAYWRIGHT:
        return
    skip_marker = pytest.mark.skip(reason="Playwright not installed")
    for item in items:
        if "browser" in str(item.fspath):
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    """Find an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout: float = 10.0) -> None:
    """Poll the health endpoint until the server is ready."""
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{url}/health", timeout=2.0)
            if resp.status_code == 200:
                return
        except (httpx.ConnectError, httpx.ReadError):
            pass
        time.sleep(0.2)
    raise TimeoutError(f"Server at {url} did not become ready within {timeout}s")


# ---------------------------------------------------------------------------
# Session-scoped fixtures: live server + DB
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _db_path() -> Generator[str, None, None]:
    """Create a temporary SQLite database file for the test session."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="browser_test_")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope="session")
def live_server(_db_path: str) -> Generator[str, None, None]:
    """Start a FastAPI server on a random port and yield the base URL.

    The server runs in a daemon thread and shuts down when the test
    session ends.  It uses a file-based SQLite database so that both the
    server and test code can access the same data.
    """
    import uvicorn

    from web.app import create_app
    from web.config import HostedPlayConfig, override_config

    port = _find_free_port()
    db_url = f"sqlite:///{_db_path}"
    artifact_root = tempfile.mkdtemp(prefix="browser_ai_artifacts_")
    olsa_artifact, gbt_artifact = create_browser_ai_test_artifacts(Path(artifact_root))

    config = HostedPlayConfig(
        database_url=db_url,
        secret_key="test-browser-secret",
        allowed_origins=["*"],
        app_url=f"http://127.0.0.1:{port}",
        default_model_id="bud_bot",
        olsa_artifact=olsa_artifact,
        gbt_artifact=gbt_artifact,
        debug=True,
        test_seed=42,
    )

    app = create_app(config)
    uv_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(uv_config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    _wait_for_server(base_url)

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)

    # Reset config override so other tests are unaffected
    override_config(None)


@pytest.fixture(scope="session")
def db_session_factory(_db_path: str):
    """Session factory connected to the same DB as the live server."""
    from web.db import init_engine, make_session_factory

    db_url = f"sqlite:///{_db_path}"
    engine = init_engine(db_url)
    # Tables are already created by the live server's lifespan
    return make_session_factory(engine)


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def invite_code(db_session_factory) -> str:
    """Create a fresh active invite code and return the code string."""
    from web.db import InviteCode, generate_invite_code

    session = db_session_factory()
    try:
        code_str = generate_invite_code()
        invite = InviteCode(code=code_str, status="active")
        session.add(invite)
        session.commit()
        return code_str
    finally:
        session.close()


@pytest.fixture()
def game_page(page: Page, live_server: str) -> Page:
    """Navigate to the landing page and return the Playwright Page."""
    page.goto(live_server)
    page.wait_for_load_state("domcontentloaded")
    return page


def enter_game(page: Page, live_server: str, code: str, nickname: str) -> Page:
    """Helper: enter invite code and set nickname, returning the page
    positioned at model selection.

    Not a fixture — call explicitly in tests that need a fully
    authenticated game page.
    """
    page.goto(live_server)
    page.wait_for_load_state("domcontentloaded")

    # Enter invite code
    page.fill("#invite-code-input", code)
    page.click("button:has-text('Enter Game')")

    # Wait for navigation to play page
    page.wait_for_url("**/play/**", timeout=5000)

    # Set nickname
    page.fill("#nickname-input", nickname)
    page.click("button:has-text('Set Nickname')")

    # Wait for model select to appear
    page.wait_for_selector("#game-board", timeout=5000)
    return page
