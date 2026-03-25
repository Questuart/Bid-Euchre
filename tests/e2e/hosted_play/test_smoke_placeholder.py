"""Placeholder E2E smoke test for the hosted Bid Euchre game.

This file establishes the repo-owned browser E2E test path at
``tests/e2e/hosted_play/``.  The actual browser tests will be added
in Phase 4 (PR-7) of the browser game expansion initiative.

The placeholder test validates that:
1. The E2E test directory is discoverable by pytest.
2. The ``e2e`` marker is registered and usable.
3. The conftest fixtures are importable.

See ``docs/01_core/HOSTED_PLAY_PROVING_CHECKLIST.md`` for the full
validation matrix.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_e2e_scaffold_discoverable() -> None:
    """Verify the E2E test directory is discoverable by pytest."""
    # This test exists to prove the scaffold is wired correctly.
    # Phase 4 will replace it with real browser tests.
    assert True


@pytest.mark.e2e
def test_conftest_base_url_fixture(base_url: str) -> None:
    """Verify the base_url fixture is available from conftest."""
    assert base_url.startswith("http")
