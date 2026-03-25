"""Abstract base classes for the steward ops platform.

These ABCs define the project-agnostic contract that repo-specific adapters
must implement.  The existing concrete implementations in
``bid_euchre.ops.{control_plane,monitor,task_queue,worker_pool}`` will be
refactored to implement these interfaces in later Platform-10 PRs.

Design principles:

1. **Minimal surface** — each ABC captures the essential operations that the
   orchestration loop depends on, not every helper or formatter.
2. **Data-model neutral** — ABCs reference generic types (dicts, strings)
   rather than concrete dataclasses.  Concrete adapters define their own
   data models and return them from these methods.
3. **Side-effect boundary** — ABCs mark which methods are pure (return data
   only) vs. side-effecting (persist state, send messages).
4. **Testability** — ABCs can be instantiated via trivial in-memory stubs
   for testing the orchestration loop without filesystem or tmux.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# ---------------------------------------------------------------------------
# AbstractController
# ---------------------------------------------------------------------------


class AbstractController(ABC):
    """Reconciles fleet status from multiple input sources.

    The controller is the single source of truth for actionable fleet state.
    It ingests findings from the monitor, task queue state, message bus
    records, and audit trails, then produces a merged projection that hooks,
    dashboards, and remote adapters consume.

    Concrete implementations:
        ``bid_euchre.ops.control_plane`` (current repo adapter)
    """

    @abstractmethod
    def reconcile(
        self,
        *,
        monitor_findings: list[dict[str, Any]] | None = None,
        task_packets: list[dict[str, Any]] | None = None,
        unacked_messages: list[dict[str, Any]] | None = None,
        audit_records: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Run one reconciliation cycle.

        Derives actionable items from all input sources, merges with
        previously persisted state (preserving ack/clear/suppress), persists
        the result, and returns the new fleet status projection.

        Args:
            monitor_findings: Findings from the most recent monitor sweep,
                as serialized dicts.
            task_packets: Current task packet state, as serialized dicts.
            unacked_messages: Unacknowledged message bus records.
            audit_records: Audit trail records for exchange detection.

        Returns:
            The updated fleet status projection (adapter-defined type).
        """

    @abstractmethod
    def load_status(self) -> Any | None:
        """Load the last persisted fleet status projection.

        Returns:
            The fleet status projection, or ``None`` if no projection has
            been persisted yet.
        """

    @abstractmethod
    def save_status(self, status: Any) -> None:
        """Persist the fleet status projection.

        Args:
            status: The fleet status projection to persist.
        """

    @abstractmethod
    def ack_item(self, item_id: str) -> bool:
        """Acknowledge an actionable item.

        Transitions the item from ``open`` to ``acked``, signaling that the
        operator has seen it but has not yet resolved it.

        Args:
            item_id: The stable identifier of the item to acknowledge.

        Returns:
            ``True`` if the item was found and transitioned, ``False``
            otherwise.
        """

    @abstractmethod
    def clear_item(self, item_id: str) -> bool:
        """Clear an actionable item.

        Transitions the item to ``cleared``, signaling that the underlying
        condition has been resolved.

        Args:
            item_id: The stable identifier of the item to clear.

        Returns:
            ``True`` if the item was found and transitioned, ``False``
            otherwise.
        """

    @abstractmethod
    def suppress_item(self, item_id: str) -> bool:
        """Suppress an actionable item.

        Transitions the item to ``suppressed``, hiding it from active
        displays without resolving the underlying condition.

        Args:
            item_id: The stable identifier of the item to suppress.

        Returns:
            ``True`` if the item was found and transitioned, ``False``
            otherwise.
        """


# ---------------------------------------------------------------------------
# AbstractMonitor
# ---------------------------------------------------------------------------


class AbstractMonitor(ABC):
    """Runs monitoring sweeps and produces structured findings.

    The monitor is a read-only observer that probes lane health, PR status,
    task queue state, and other subsystems.  It returns findings — it does
    not take corrective action itself (that is the controller's job).

    Concrete implementations:
        ``bid_euchre.ops.monitor`` (current repo adapter)
    """

    @abstractmethod
    def run_cycle(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Run a single monitoring sweep.

        Collects findings from all configured checks (lane health, PR
        status, stale dispatches, idle lanes, stall detection, etc.).

        Keyword args are adapter-specific (e.g., ``skip_pr_check``,
        ``no_recovery``, ``no_auto_dispatch``).

        Returns:
            A list of finding dicts, each containing at minimum:
            ``category``, ``severity``, ``summary``.
        """

    @abstractmethod
    def check_lane_health(self) -> list[dict[str, Any]]:
        """Check lane pool health.

        Returns:
            Findings about lane health (degraded, critical, capacity).
        """

    @abstractmethod
    def check_stale_dispatches(self) -> list[dict[str, Any]]:
        """Check for stale dispatched packets.

        Returns:
            Findings about dispatched packets with no progress.
        """

    @abstractmethod
    def check_idle_lanes(self) -> list[dict[str, Any]]:
        """Check for idle lanes available for dispatch.

        Returns:
            Findings about idle lanes.
        """


# ---------------------------------------------------------------------------
# AbstractTaskQueue
# ---------------------------------------------------------------------------


class AbstractTaskQueue(ABC):
    """Manages durable task packet lifecycle.

    The task queue is the durable contract between the orchestrator and
    author lanes.  Packets flow through a defined state machine
    (pending -> approved -> dispatched -> completed) with side-car
    acknowledgment and result records.

    Concrete implementations:
        ``bid_euchre.ops.task_queue`` (current repo adapter)
    """

    @abstractmethod
    def create_packet(
        self,
        title: str,
        description: str,
        *,
        owner: str | None = None,
        scope_declared: list[str] | None = None,
        validation: list[str] | None = None,
        priority: str = "normal",
        domain: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Create a new task packet.

        Args:
            title: Human-readable task title.
            description: Full task description with acceptance criteria.
            owner: Target lane identifier, if pre-assigned.
            scope_declared: File patterns the task is expected to touch.
            validation: Commands to run before declaring done.
            priority: One of ``low``, ``normal``, ``high``.
            domain: Execution domain for routing (e.g., ``platform``).
            metadata: Additional structured data.

        Returns:
            The created task packet (adapter-defined type).
        """

    @abstractmethod
    def save_packet(self, packet: Any) -> Any:
        """Persist a task packet to durable storage.

        Args:
            packet: The task packet to persist.

        Returns:
            The storage path or identifier.
        """

    @abstractmethod
    def load_packet(self, packet_id: str) -> Any | None:
        """Load a task packet by ID.

        Args:
            packet_id: The unique packet identifier.

        Returns:
            The task packet, or ``None`` if not found.
        """

    @abstractmethod
    def list_packets(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
    ) -> list[Any]:
        """List task packets with optional filtering.

        Args:
            status: Filter by packet status (e.g., ``dispatched``).
            owner: Filter by owning lane.

        Returns:
            List of matching task packets.
        """

    @abstractmethod
    def transition_status(
        self,
        packet_id: str,
        new_status: str,
        *,
        owner: str | None = None,
    ) -> Any:
        """Transition a packet to a new status.

        Enforces the valid state machine transitions.

        Args:
            packet_id: The packet to transition.
            new_status: The target status.
            owner: Lane to assign as owner (for dispatched status).

        Returns:
            The updated task packet.

        Raises:
            ValueError: If the transition is not valid.
        """

    @abstractmethod
    def archive_packet(self, packet_id: str) -> bool:
        """Archive a completed/rejected packet.

        Moves the packet from the active queue to the archive.

        Args:
            packet_id: The packet to archive.

        Returns:
            ``True`` if archived successfully, ``False`` if not found.
        """

    @abstractmethod
    def complete_packet(
        self,
        packet_id: str,
        *,
        summary: str = "",
        pr_number: int | None = None,
        completed_by: str = "",
    ) -> Any:
        """Complete a packet with a result record.

        Transitions to ``completed`` status, writes a result sidecar,
        and optionally archives.

        Args:
            packet_id: The packet to complete.
            summary: Completion summary.
            pr_number: Associated PR number, if any.
            completed_by: Lane that completed the work.

        Returns:
            The completion result (adapter-defined type).
        """

    @abstractmethod
    def queue_summary(self) -> dict[str, Any]:
        """Get a summary of queue state.

        Returns:
            Dict with counts by status, total, etc.
        """


# ---------------------------------------------------------------------------
# AbstractWorkerPool
# ---------------------------------------------------------------------------


class AbstractWorkerPool(ABC):
    """Manages worker lane lifecycle and dispatch.

    The worker pool tracks which lanes are active, idle, parked, or retired,
    and handles the mechanics of dispatching task packets to lanes —
    including branch setup, pane creation, and nudging.

    Concrete implementations:
        ``bid_euchre.ops.worker_pool`` (current repo adapter)
    """

    @abstractmethod
    def take_snapshot(self) -> Any:
        """Build a point-in-time worker pool snapshot.

        Reads from lane registry, supervisor, and runtime environment
        to produce a complete picture of pool state.

        Returns:
            The pool snapshot (adapter-defined type).
        """

    @abstractmethod
    def select_worker(
        self,
        snapshot: Any,
        *,
        preferred_lane: str | None = None,
        domain: str | None = None,
    ) -> str | None:
        """Choose the best lane for new work.

        Uses the pool snapshot to find an available worker, preferring
        same-domain lanes and honoring explicit preferences.

        Args:
            snapshot: A pool snapshot from :meth:`take_snapshot`.
            preferred_lane: Explicitly preferred lane, if any.
            domain: Target execution domain for routing.

        Returns:
            The selected lane identifier, or ``None`` if no lane is
            available.
        """

    @abstractmethod
    def dispatch_to_worker(
        self,
        packet_id: str,
        lane_id: str,
    ) -> Any:
        """Dispatch a task packet to a worker lane.

        Handles the full dispatch sequence: status transition, branch
        setup, inbox message, pane nudge.

        Args:
            packet_id: The task packet to dispatch.
            lane_id: The target lane.

        Returns:
            The dispatch action result (adapter-defined type).
        """

    @abstractmethod
    def wake_worker(self, lane_id: str) -> Any:
        """Wake a parked or retired worker lane.

        Ensures the lane has a live runtime environment (pane, session,
        worktree) ready to accept work.

        Args:
            lane_id: The lane to wake.

        Returns:
            The wake action result (adapter-defined type).
        """

    @abstractmethod
    def park_worker(self, lane_id: str) -> Any:
        """Park an idle worker lane.

        Preserves state but signals the lane is not actively processing
        work.  Parked lanes can be woken quickly.

        Args:
            lane_id: The lane to park.

        Returns:
            The park action result (adapter-defined type).
        """

    @abstractmethod
    def nudge_pane(self, lane_id: str, text: str) -> bool:
        """Send a text nudge to a lane's tmux pane.

        Used to inject slash commands (e.g., ``/start-task <id>``) into
        author lane sessions.

        Args:
            lane_id: The target lane.
            text: The text to send to the pane.

        Returns:
            ``True`` if the nudge was sent successfully, ``False``
            otherwise.
        """
