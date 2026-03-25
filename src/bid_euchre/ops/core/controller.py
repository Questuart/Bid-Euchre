"""Concrete controller implementing AbstractController.

Wraps the existing ``bid_euchre.ops.control_plane`` module functions behind
the ABC-compliant interface defined in :mod:`bid_euchre.ops.core.interfaces`.

This is the first step of the Platform-10 core-vs-adapter split. The
underlying implementation remains in ``control_plane.py``; this class
provides the object-oriented entry point that the orchestration loop
(and future repo adapters) program against.

Usage::

    from bid_euchre.ops.core.controller import ControlPlaneController

    ctrl = ControlPlaneController()
    status = ctrl.reconcile(monitor_findings=findings)
    ctrl.ack_item("abc123")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bid_euchre.ops.core.interfaces import AbstractController


class ControlPlaneController(AbstractController):
    """Concrete controller backed by the control_plane module.

    Encapsulates a ``runtime_dir`` and delegates to the existing
    module-level functions in ``bid_euchre.ops.control_plane``.

    Args:
        runtime_dir: Path to the runtime directory (defaults to
            ``.claude/runtime``).
    """

    def __init__(self, runtime_dir: Path | None = None) -> None:
        self._runtime_dir = runtime_dir

    # -- AbstractController interface ----------------------------------------

    def reconcile(
        self,
        *,
        monitor_findings: list[dict[str, Any]] | None = None,
        task_packets: list[dict[str, Any]] | None = None,
        unacked_messages: list[dict[str, Any]] | None = None,
        audit_records: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Run one reconciliation cycle.

        Delegates to :func:`bid_euchre.ops.control_plane.reconcile`.
        """
        from bid_euchre.ops.control_plane import reconcile as _reconcile

        return _reconcile(
            runtime_dir=self._runtime_dir,
            monitor_findings=monitor_findings,
            task_packets=task_packets,
            unacked_messages=unacked_messages,
            audit_records=audit_records,
        )

    def load_status(self) -> Any | None:
        """Load the last persisted fleet status projection.

        Delegates to :func:`bid_euchre.ops.control_plane.load_fleet_status`.
        """
        from bid_euchre.ops.control_plane import load_fleet_status

        return load_fleet_status(self._runtime_dir)

    def save_status(self, status: Any) -> None:
        """Persist the fleet status projection.

        Delegates to :func:`bid_euchre.ops.control_plane.save_fleet_status`.
        """
        from bid_euchre.ops.control_plane import save_fleet_status

        save_fleet_status(status, self._runtime_dir)

    def ack_item(self, item_id: str) -> bool:
        """Acknowledge an actionable item.

        Loads the current fleet status, applies the ack transition, and
        persists the result.
        """
        from bid_euchre.ops.control_plane import ack_item as _ack_item

        status = self.load_status()
        if status is None:
            return False
        result = _ack_item(status, item_id)
        if result:
            self.save_status(status)
        return result

    def clear_item(self, item_id: str) -> bool:
        """Clear an actionable item.

        Loads the current fleet status, applies the clear transition, and
        persists the result.
        """
        from bid_euchre.ops.control_plane import clear_item as _clear_item

        status = self.load_status()
        if status is None:
            return False
        result = _clear_item(status, item_id)
        if result:
            self.save_status(status)
        return result

    def suppress_item(self, item_id: str) -> bool:
        """Suppress an actionable item.

        Loads the current fleet status, applies the suppress transition, and
        persists the result.
        """
        from bid_euchre.ops.control_plane import suppress_item as _suppress_item

        status = self.load_status()
        if status is None:
            return False
        result = _suppress_item(status, item_id)
        if result:
            self.save_status(status)
        return result
