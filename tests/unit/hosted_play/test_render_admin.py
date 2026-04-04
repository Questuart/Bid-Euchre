"""Tests for scripts/internal/render_admin.py — production DB admin CLI.

Uses subprocess calls and importlib to avoid sys.path pollution.
Validates URL masking, session creation with RENDER_DATABASE_URL fallback,
and CLI subcommand routing.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
RENDER_ADMIN = REPO_ROOT / "scripts" / "internal" / "render_admin.py"


def _import_render_admin():
    """Import render_admin module via importlib spec loader."""
    spec = importlib.util.spec_from_file_location("render_admin", RENDER_ADMIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_render_admin_help():
    """render_admin.py --help exits 0 and prints expected subcommands."""
    result = subprocess.run(
        [sys.executable, str(RENDER_ADMIN), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "players" in result.stdout
    assert "matches" in result.stdout
    assert "codes" in result.stdout
    assert "db" in result.stdout


def test_render_admin_url_masking():
    """_mask_url hides the password in a Postgres connection string."""
    mod = _import_render_admin()

    masked = mod._mask_url("postgresql://user:s3cret@host:5432/db")
    assert "s3cret" not in masked
    assert "****" in masked
    assert "user" in masked
    assert "host" in masked


def test_render_admin_url_masking_no_password():
    """_mask_url returns URL unchanged when no password is present."""
    mod = _import_render_admin()

    url = "sqlite:///hosted_play.db"
    assert mod._mask_url(url) == url


def test_render_database_url_env_priority(monkeypatch):
    """RENDER_DATABASE_URL takes priority over DATABASE_URL."""
    mod = _import_render_admin()

    monkeypatch.setenv("RENDER_DATABASE_URL", "postgresql://render-host/db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///local.db")

    url = mod._get_database_url()
    assert url == "postgresql://render-host/db"


def test_database_url_fallback(monkeypatch):
    """Falls back to DATABASE_URL when RENDER_DATABASE_URL is unset."""
    mod = _import_render_admin()

    monkeypatch.delenv("RENDER_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///fallback.db")

    url = mod._get_database_url()
    assert url == "sqlite:///fallback.db"


def test_no_url_exits(monkeypatch):
    """Exits with error when no database URL is set."""
    mod = _import_render_admin()

    monkeypatch.delenv("RENDER_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit):
        mod._get_database_url()


def test_get_session_does_not_call_create_tables(monkeypatch):
    """_get_session must NOT call create_tables — schema is managed via deployment."""
    mod = _import_render_admin()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("RENDER_DATABASE_URL", raising=False)

    # Patch create_tables into web.db so we can detect if it's called
    call_count = 0

    def _spy_create_tables(engine):
        nonlocal call_count
        call_count += 1

    monkeypatch.setattr("web.db.create_tables", _spy_create_tables)

    session, url = mod._get_session()
    session.close()
    assert call_count == 0, "create_tables() must not be called by _get_session()"


def test_manage_invite_codes_render_url_priority(monkeypatch):
    """manage_invite_codes.py _get_session uses RENDER_DATABASE_URL when set."""
    monkeypatch.setenv("RENDER_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.internal.manage_invite_codes import _get_session

    session = _get_session()
    assert session is not None
    session.close()
