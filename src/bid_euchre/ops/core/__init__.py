"""Core ops framework — project-agnostic abstract interfaces.

This package defines the abstract base classes (ABCs) for the steward ops
platform.  Repo-specific adapters implement these contracts, enabling the
core orchestration loop to be reused across different projects.

The four pillars:

- **AbstractController** — reconciles fleet status from multiple input sources
- **AbstractMonitor** — runs monitoring sweeps and produces structured findings
- **AbstractTaskQueue** — manages durable task packet lifecycle
- **AbstractWorkerPool** — manages worker lane lifecycle and dispatch

Usage::

    from bid_euchre.ops.core import (
        AbstractController,
        AbstractMonitor,
        AbstractTaskQueue,
        AbstractWorkerPool,
    )
"""

from bid_euchre.ops.core.interfaces import (
    AbstractController,
    AbstractMonitor,
    AbstractTaskQueue,
    AbstractWorkerPool,
)

__all__ = [
    "AbstractController",
    "AbstractMonitor",
    "AbstractTaskQueue",
    "AbstractWorkerPool",
]
