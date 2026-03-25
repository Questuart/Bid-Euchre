"""Shared fixtures for browser E2E tests.

This module provides the foundation for browser-based end-to-end testing
of the hosted Bid Euchre game.  Phase 4 of the browser game expansion
will populate this with Playwright fixtures, server lifecycle helpers,
and Claude-direct browser testing support.

Current state (Phase 0): scaffold only.  The directory structure and
marker registration establish the repo-owned E2E test path so later
phases can add browser tests without structural decisions.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def base_url() -> str:
    """Base URL for the local test server.

    Phase 4 will replace this with a fixture that starts a real FastAPI
    server and returns its URL.  For now, return a placeholder that
    makes the test path importable and discoverable.
    """
    return "http://localhost:8000"
