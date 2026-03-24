"""Tests for web.start — production startup entrypoint."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

import pytest

from web.start import main


class TestMain:
    """Verify main() reads environment and calls uvicorn correctly."""

    def test_default_settings(self):
        """Default env → host=0.0.0.0, port=8000, workers=1, log_level=info."""
        with patch.dict("os.environ", {}, clear=True), patch("uvicorn.run") as mock_run:
            main()
            mock_run.assert_called_once_with(
                "web.app:create_app",
                factory=True,
                host="0.0.0.0",
                port=8000,
                workers=1,
                log_level="info",
            )

    def test_env_override(self):
        """Environment variables override defaults."""
        env = {
            "HOST": "127.0.0.1",
            "PORT": "9090",
            "WEB_WORKERS": "4",
            "LOG_LEVEL": "WARNING",
        }
        with (
            patch.dict("os.environ", env, clear=True),
            patch("uvicorn.run") as mock_run,
        ):
            main()
            mock_run.assert_called_once_with(
                "web.app:create_app",
                factory=True,
                host="127.0.0.1",
                port=9090,
                workers=4,
                log_level="warning",
            )

    def test_invalid_workers_exits(self):
        """WEB_WORKERS < 1 should exit with code 1."""
        env = {"WEB_WORKERS": "0"}
        with (
            patch.dict("os.environ", env, clear=True),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 1

    def test_module_runnable(self):
        """``python -m web.start --help`` equivalent: module is importable."""
        # Just verify the module can be imported without side effects
        result = subprocess.run(
            [sys.executable, "-c", "from web.start import main; print('OK')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "OK" in result.stdout
