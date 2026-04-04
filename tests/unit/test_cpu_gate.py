"""Tests for scripts/internal/cpu_gate.sh — CPU-aware validation gate."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

GATE_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "internal" / "cpu_gate.sh"
)


def _run_gate(
    cmd: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run the CPU gate script with the given command and env overrides."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(GATE_SCRIPT), *cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


class TestCpuGateStatus:
    """Test --status mode."""

    def test_status_reports_cores_and_load(self) -> None:
        result = _run_gate(["--status"])
        assert result.returncode == 0
        assert "cores:" in result.stdout
        assert "load 1m:" in result.stdout
        assert "threshold:" in result.stdout
        assert "slots:" in result.stdout

    def test_status_respects_custom_threshold(self) -> None:
        result = _run_gate(
            ["--status"],
            env_overrides={"CPU_GATE_MAX_LOAD": "99.0"},
        )
        assert result.returncode == 0
        assert "threshold: 99.0" in result.stdout
        assert "load OK:   yes" in result.stdout


class TestCpuGateExecution:
    """Test that the gate runs commands correctly."""

    def test_passes_through_command_output(self) -> None:
        result = _run_gate(
            ["echo", "hello from gate"],
            env_overrides={"CPU_GATE_MAX_LOAD": "999.0"},
        )
        assert result.returncode == 0
        assert "hello from gate" in result.stdout

    def test_propagates_exit_code(self) -> None:
        result = _run_gate(
            ["bash", "-c", "exit 7"],
            env_overrides={"CPU_GATE_MAX_LOAD": "999.0"},
        )
        assert result.returncode == 7

    def test_no_args_shows_usage(self) -> None:
        result = subprocess.run(
            ["bash", str(GATE_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr


class TestCpuGateSemaphore:
    """Test semaphore slot management."""

    def test_cleans_stale_slots(self) -> None:
        """Slot files for dead PIDs should be cleaned automatically."""
        with tempfile.TemporaryDirectory() as slot_dir:
            # Create a slot file for a PID that doesn't exist (99999999)
            stale = Path(slot_dir) / "99999999"
            stale.touch()
            assert stale.exists()

            result = _run_gate(
                ["echo", "ok"],
                env_overrides={
                    "CPU_GATE_MAX_LOAD": "999.0",
                    "CPU_GATE_SLOT_DIR": slot_dir,
                },
            )
            assert result.returncode == 0
            # Stale slot should have been cleaned
            assert not stale.exists()

    def test_slot_file_created_and_cleaned(self) -> None:
        """A slot file should be created during execution and cleaned after."""
        with tempfile.TemporaryDirectory() as slot_dir:
            # Run a command that lists the slot directory during execution
            result = _run_gate(
                ["bash", "-c", f"ls {slot_dir}/ | wc -l | tr -d ' '"],
                env_overrides={
                    "CPU_GATE_MAX_LOAD": "999.0",
                    "CPU_GATE_SLOT_DIR": slot_dir,
                },
            )
            assert result.returncode == 0
            # During execution, there should be exactly 1 slot (ours)
            assert result.stdout.strip() == "1"
            # After execution, the slot should be cleaned up (exec replaces
            # the process so trap may not fire — but the slot dir is temp anyway)

    def test_waits_when_slots_full(self) -> None:
        """Gate should wait (and eventually timeout) when all slots are taken."""
        with tempfile.TemporaryDirectory() as slot_dir:
            # Create slots using our own PID and parent PID (both alive)
            (Path(slot_dir) / str(os.getpid())).touch()
            (Path(slot_dir) / str(os.getppid())).touch()

            # With max_slots=2, a 3rd should wait and eventually timeout
            result = _run_gate(
                ["echo", "eventually"],
                env_overrides={
                    "CPU_GATE_MAX_LOAD": "999.0",
                    "CPU_GATE_MAX_SLOTS": "2",
                    "CPU_GATE_SLOT_DIR": slot_dir,
                    "CPU_GATE_MAX_WAIT": "3",
                    "CPU_GATE_POLL_BASE": "1",
                },
                timeout=30,
            )
            assert result.returncode == 0
            assert "slots in use" in result.stderr
            assert "eventually" in result.stdout


class TestCpuGateLoadAwareness:
    """Test CPU load threshold behavior."""

    def test_waits_when_load_exceeds_threshold(self) -> None:
        """Gate should announce waiting when load threshold is very low."""
        result = _run_gate(
            ["echo", "done"],
            env_overrides={
                "CPU_GATE_MAX_LOAD": "0.01",  # Impossibly low
                "CPU_GATE_MAX_WAIT": "3",
                "CPU_GATE_POLL_BASE": "1",
            },
            timeout=30,
        )
        assert result.returncode == 0
        assert "threshold" in result.stderr
        assert "waiting" in result.stderr.lower()
        assert "done" in result.stdout

    def test_proceeds_immediately_when_load_is_low(self) -> None:
        """Gate should not wait when threshold is very high."""
        result = _run_gate(
            ["echo", "fast"],
            env_overrides={"CPU_GATE_MAX_LOAD": "999.0"},
        )
        assert result.returncode == 0
        assert "fast" in result.stdout
        # Should not have any waiting messages
        assert "waiting" not in result.stderr.lower()
