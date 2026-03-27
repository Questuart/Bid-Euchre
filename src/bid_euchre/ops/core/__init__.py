"""Core ops framework — abstract interfaces and concrete implementations.

This package defines the abstract base classes (ABCs) for the steward ops
platform, plus concrete implementations that delegate to the existing
module-level functions.  Repo-specific adapters implement these contracts,
enabling the core orchestration loop to be reused across different projects.

The four pillars:

- **AbstractController** — reconciles fleet status from multiple input sources
- **AbstractMonitor** — runs monitoring sweeps and produces structured findings
- **AbstractTaskQueue** — manages durable task packet lifecycle
- **AbstractWorkerPool** — manages worker lane lifecycle and dispatch

Concrete implementations:

- **ControlPlaneController** — wraps ``bid_euchre.ops.control_plane``
- **MonitorService** — wraps ``bid_euchre.ops.monitor``

Service provider:

- **ServiceProvider** — constructs and holds all four adapters as a cohesive
  unit, providing a single entry point for the orchestration loop.

Usage::

    from bid_euchre.ops.core import (
        AbstractController,
        AbstractMonitor,
        AbstractTaskQueue,
        AbstractWorkerPool,
        ControlPlaneController,
        MonitorService,
        ServiceProvider,
    )

    # Construct the default Bid-Euchre adapter set
    provider = ServiceProvider.default()
    status = provider.controller.reconcile(monitor_findings=findings)
"""

from bid_euchre.ops.core.controller import ControlPlaneController
from bid_euchre.ops.core.interfaces import (
    AbstractController,
    AbstractMonitor,
    AbstractTaskQueue,
    AbstractWorkerPool,
)
from bid_euchre.ops.core.monitor import MonitorService
from bid_euchre.ops.core.provider import ServiceProvider

__all__ = [
    "AbstractController",
    "AbstractMonitor",
    "AbstractTaskQueue",
    "AbstractWorkerPool",
    "ControlPlaneController",
    "MonitorService",
    "ServiceProvider",
]
