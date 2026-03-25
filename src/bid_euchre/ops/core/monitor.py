"""Concrete monitor implementing AbstractMonitor.

Wraps the existing ``bid_euchre.ops.monitor`` module functions behind
the ABC-compliant interface defined in :mod:`bid_euchre.ops.core.interfaces`.

This is part of the Platform-10 core-vs-adapter split.  The underlying
implementation remains in ``bid_euchre.ops.monitor``; this class provides
the object-oriented entry point that the orchestration loop (and future
repo adapters) program against.

Usage::

    from bid_euchre.ops.core.monitor import MonitorService

    mon = MonitorService()
    findings = mon.run_cycle(skip_pr_check=True)
    health = mon.check_lane_health()
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from bid_euchre.ops.core.interfaces import AbstractMonitor


class MonitorService(AbstractMonitor):
    """Concrete monitor backed by the monitor module.

    Encapsulates a ``runtime_dir`` and delegates to the existing
    module-level functions in ``bid_euchre.ops.monitor``.

    Args:
        runtime_dir: Path to the runtime directory (defaults to
            ``.claude/runtime``).
    """

    def __init__(self, runtime_dir: Path | None = None) -> None:
        self._runtime_dir = runtime_dir

    @staticmethod
    def _findings_to_dicts(findings: list[Any]) -> list[dict[str, Any]]:
        """Convert MonitorFinding dataclasses to plain dicts.

        The ABC contract returns ``list[dict[str, Any]]`` rather than
        dataclass instances, so we convert here at the boundary.
        """
        return [asdict(f) for f in findings]

    # -- AbstractMonitor interface -------------------------------------------

    def run_cycle(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Run a single monitoring sweep.

        Delegates to :func:`bid_euchre.ops.monitor.run_monitoring_cycle`.

        Keyword args are forwarded directly and may include:
        ``skip_pr_check``, ``no_recovery``, ``no_auto_dispatch``,
        ``stale_minutes``, ``notify_orchestrator``, ``now``.
        """
        from bid_euchre.ops.monitor import run_monitoring_cycle

        findings = run_monitoring_cycle(runtime_dir=self._runtime_dir, **kwargs)
        return self._findings_to_dicts(findings)

    def check_lane_health(self) -> list[dict[str, Any]]:
        """Check lane pool health.

        Delegates to :func:`bid_euchre.ops.monitor.check_lane_health`.
        """
        from bid_euchre.ops.monitor import check_lane_health as _check

        return self._findings_to_dicts(_check(self._runtime_dir))

    def check_stale_dispatches(self) -> list[dict[str, Any]]:
        """Check for stale dispatched packets.

        Delegates to :func:`bid_euchre.ops.monitor.check_stale_dispatches`.
        """
        from bid_euchre.ops.monitor import check_stale_dispatches as _check

        return self._findings_to_dicts(_check(self._runtime_dir))

    def check_idle_lanes(self) -> list[dict[str, Any]]:
        """Check for idle lanes available for dispatch.

        Delegates to :func:`bid_euchre.ops.monitor.check_idle_lanes`.
        """
        from bid_euchre.ops.monitor import check_idle_lanes as _check

        return self._findings_to_dicts(_check(self._runtime_dir))
