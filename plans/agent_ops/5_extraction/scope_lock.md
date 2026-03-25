# Platform-13: Second-Project Extraction Proof — Scope Lock

**Status:** DRAFT (pending morning review)
**Author:** analyst lane
**Date:** 2026-03-25
**Parent:** `plans/agent_ops/governing_plan.md` — Phase 6, Platform-13
**Registry ID:** (to be assigned)

---

## Problem Statement

The steward platform was built inside the Bid-Euchre repo. All ops modules live
under `src/bid_euchre/ops/` and carry implicit Bid-Euchre assumptions:

- `task_queue.py` references `KNOWN_AUTHOR_LANES` with Bid-Euchre-specific lane
  names (author-a, brws-author-a, etc.)
- `worker_pool.py` assumes the Bid-Euchre worktree naming convention
- `monitor.py` calls `gh pr` with hardcoded repo assumptions
- `watchdogs.py` checks Bid-Euchre-specific plan/checkpoint structures
- `token_economy.py` parses Bid-Euchre-specific project directory slugs
- CI checks (`make check`) assume the full Bid-Euchre test suite

The platform can't be used for another project without either forking the entire
ops directory or performing a careful extraction. Platform-10 begins the
core-vs-adapter split; Platform-13 proves that split actually works by running
the steward on a second project.

**Governing plan done-when:**
> - A second project can adopt the core orchestration model without copying the
>   entire Bid-Euchre control plane
> - At least one adapter seam is validated against a real non-Bid-Euchre use

## Proposed Solution

### Extraction Boundary (from Platform-10)

Platform-10 splits `src/bid_euchre/ops/` into:

```
src/bid_euchre/ops/core/          # Project-agnostic orchestration
    controller.py                 # Actionable-state projection
    events.py                     # Event log (generic)
    message_bus.py                # Lane-to-lane messaging
    task_queue.py                 # Task packet lifecycle
    worker_pool.py                # Lane management (generic)
    monitor.py                    # Monitoring framework (generic checks)
    supervisor.py                 # Health assessment
    scheduler.py                  # Cron/scheduling primitives
    idle_detector.py              # Fleet idle detection

src/bid_euchre/ops/adapters/      # Bid-Euchre-specific policy
    bid_euchre.py                 # Lane names, repo paths, CI commands,
                                  # plan/checkpoint paths, worktree conventions
```

Platform-13 proves this boundary by implementing a **second adapter** for a
different project and booting the steward against it.

### Adapter Contract Specification

A project adapter must implement:

```python
class ProjectAdapter(Protocol):
    """Contract for project-specific steward configuration."""

    # Identity
    project_name: str                          # "bid-euchre", "chess-engine"
    repo_url: str                              # GitHub URL

    # Lane topology
    def known_lanes(self) -> frozenset[str]: ...
    def control_plane_lanes(self) -> frozenset[str]: ...
    def lane_pools(self) -> dict[str, list[str]]: ...

    # Validation
    def validation_command(self) -> str: ...    # "make check", "cargo test"
    def lint_command(self) -> str: ...          # "make lint", "cargo clippy"

    # CI / PR
    def ci_required_checks(self) -> list[str]: ...
    def pr_template_path(self) -> Path | None: ...
    def worktree_base_dir(self) -> Path: ...

    # Plans / Checkpoints (optional — not all projects use governed plans)
    def plans_dir(self) -> Path | None: ...
    def checkpoint_pattern(self) -> str | None: ...

    # Watchdogs (project-specific health checks)
    def custom_watchdogs(self) -> list[WatchdogCheck]: ...
```

### Second-Project Candidate Evaluation

| Candidate | Complexity | Existing Tests | CI | Benefit |
|-----------|-----------|---------------|-----|---------|
| **Chess engine (Python)** | Medium | Yes | GitHub Actions | Similar to Bid-Euchre (game domain, Python, experiments) |
| **Data pipeline (Python)** | Low-Medium | Partial | GitHub Actions | Different domain, proves non-game portability |
| **Web scraper (Python)** | Low | Minimal | None | Minimal, doesn't stress orchestration features |
| **Rust CLI tool** | Medium-High | Yes | GitHub Actions | Proves language-agnosticism but adds complexity |
| **Bid-Euchre browser game (subproject)** | Low | Yes | Shared CI | Already exists, minimal extraction proof |

**Recommendation:** A small-to-medium Python project with existing tests and
GitHub Actions CI. A chess engine or data pipeline provides the strongest proof
because:
- Different domain (non-game or different game)
- Similar toolchain (Python, pytest, GitHub)
- Enough complexity to exercise dispatch, review, and monitoring
- Not so complex that the extraction proof becomes a multi-week project

**Alternative: Synthetic proof project.** Create a minimal "hello-steward"
project with a trivial test suite, a Makefile, and 2-3 source files. This
proves the adapter interface works without the overhead of a real second project.
Faster (~2h) but weaker proof.

### Packaging Strategy

| Strategy | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **PyPI package** | Clean distribution, versioning, pip install | Requires publish infra, semver discipline | Phase 2 |
| **Git submodule** | Simple, no publish step | Submodule UX is painful, version pinning is fragile | Not recommended |
| **Monorepo workspace** | Single repo, unified CI | Doesn't prove extraction at all | Not recommended |
| **Copy + adapt** | Fastest to prove, zero infra | Diverges immediately, no shared updates | MVP proof only |
| **pip install from git** | Moderate setup, works without PyPI | Slower installs, no proper versioning | Acceptable MVP |

**Recommended MVP:** `pip install from git` — the core ops package is
installable directly from the Bid-Euchre repo's `src/bid_euchre/ops/core/`
path. The second project's `pyproject.toml` includes:

```toml
[project.optional-dependencies]
steward = ["bid-euchre-steward-core @ git+https://github.com/..."]
```

**Recommended production:** PyPI package (`steward-core`) once the API stabilizes
post-Platform-14.

### Proof-of-Concept Plan

**Minimal viable extraction proof (MVP):**

1. Create a `steward-hello` repo with:
   - 3 Python source files (a simple calculator library)
   - `pytest` test suite (10 tests)
   - `Makefile` with `check`, `test`, `lint` targets
   - GitHub Actions CI
   - `.claude/` directory with steward config

2. Implement a `HelloAdapter` that satisfies the `ProjectAdapter` protocol:
   - 2 lanes: `hello-author-a`, `hello-author-b`
   - 1 control-plane lane: `hello-orchestrator`
   - Validation: `make check`
   - No governed plans or checkpoints (optional features)

3. Boot the steward with the hello adapter:
   - `steward-session.sh` with 3 tmux panes
   - Dispatch a simple task ("add a new function + test")
   - Verify: task packet created, dispatched to lane, PR opened, review runs,
     merge completes

4. Document adapter implementation experience:
   - What was easy? What was confusing?
   - Which core assumptions leaked through?
   - What docs were missing?

### Shared Infrastructure Requirements

| Infrastructure | Shared or Per-Project | Notes |
|----------------|----------------------|-------|
| tmux session layout | Per-project (generated from adapter) | Template in core, customized by adapter |
| CI workflows | Per-project | Core provides workflow templates, project customizes |
| Review loop | Shared (core) | Same Codex CLI review, different repo target |
| Message bus | Per-project (separate `.claude/runtime/`) | Same code, different runtime directory |
| Token economy | Shared aggregation, per-project data | Cross-project dashboard possible |
| Skill files | Per-project (`.claude/skills/`) | Core promotion pipeline, project-specific skills |

## Open Questions (for operator)

1. **Which ops modules are truly project-agnostic?**
   - Needs an audit against Platform-10's boundary. Some modules that seem
     generic may have subtle Bid-Euchre assumptions.
   - **Action:** After Platform-10 lands, run a grep-based dependency audit
     of core/ imports to verify no adapter leakage.

2. **What adapter interface does a second project need to implement?**
   - The `ProjectAdapter` protocol above is a proposal. Needs review against
     actual core module consumption patterns.
   - **Action:** Draft the protocol, then validate by checking every place
     core modules access project-specific config.

3. **Mono-repo or multi-repo extraction?**
   - **Recommendation:** Multi-repo. The whole point is proving the boundary
     works across repo boundaries. A mono-repo extraction proves nothing.

4. **How to share tmux session layouts across projects?**
   - Option A: Template in core, project fills in lane names/counts
   - Option B: Core generates layout from adapter's `lane_pools()` method
   - **Recommendation:** Option B — auto-generated from adapter config. Less
     manual maintenance, proves the adapter contract covers layout needs.

5. **CI/CD: shared workflows or per-project?**
   - Core can provide reusable GitHub Actions (workflow_call) that projects
     invoke with project-specific inputs
   - **Recommendation:** Reusable workflows. The core provides
     `.github/workflows/steward-ci.yml` as a callable workflow. Projects
     invoke it with their adapter config.

6. **Candidate second project — which one?**
   - This is the biggest decision. Determines the scope and duration of the
     extraction proof.
   - **Recommendation:** Start with synthetic `steward-hello` (2h proof),
     then graduate to a real project if the hello proof passes. This avoids
     spending days on extraction proof only to find the adapter interface is
     wrong.

## Dependencies

- **Platform-10 (required):** Core-vs-adapter split must be complete before
  extraction can be validated. Platform-13 literally depends on Platform-10's
  output.
- **Platform-11 (optional):** Learning loop data portability would be nice to
  prove but not required for MVP.
- **Platform-12 (optional):** Cross-model routing portability would strengthen
  the proof but is not required for MVP.

## Implementation Estimate

| Slice | PRs | Lane-hours | Description |
|-------|-----|------------|-------------|
| Adapter protocol definition | 1 | 1.5h | `ProjectAdapter` protocol, type stubs, validation |
| Bid-Euchre adapter (extract from inline) | 1 | 2h | Move hardcoded values to `adapters/bid_euchre.py` |
| steward-hello repo setup | 0 (external) | 1h | Create the proof-of-concept repo |
| Hello adapter implementation | 1 | 1.5h | `adapters/hello.py` implementing full protocol |
| E2E boot + dispatch proof | 1 | 2h | Boot steward-hello, dispatch task, verify lifecycle |
| Extraction experience report | 1 | 1h | Document gaps, pain points, missing docs |
| **Total** | **5 PRs** (this repo) + external repo | **~9h** | |

## Risks

1. **Platform-10 boundary is wrong.** If the core-vs-adapter split from
   Platform-10 doesn't cleanly separate concerns, Platform-13 will discover
   leaky abstractions. This is actually the desired outcome — the extraction
   proof is specifically designed to find these leaks. But it means Platform-13
   may generate follow-up work for Platform-10/14.

2. **External repo management overhead.** Creating and maintaining a second repo
   adds operational burden. Mitigation: keep `steward-hello` minimal (3 source
   files, 10 tests). It's a proof, not a real project.

3. **Claude Code multi-repo limitations.** Claude Code sessions are typically
   scoped to one repo. Running steward across two repos may require creative
   worktree management or multiple Claude instances. Mitigation: the steward
   already manages multiple worktrees within one repo — cross-repo is an
   extension of the same pattern.

4. **Adapter interface instability.** The protocol may change as Platform-10
   evolves, invalidating early Platform-13 work. Mitigation: Platform-13
   should wait until Platform-10 reaches COMPLETE before starting
   implementation.

5. **Scope creep into a real second project.** The extraction proof should be
   minimal and bounded. A real chess engine or data pipeline has its own
   complexity that could distract from the extraction signal. Mitigation: start
   with `steward-hello`, only escalate to a real project if the hello proof
   passes cleanly.
