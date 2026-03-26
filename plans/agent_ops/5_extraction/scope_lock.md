# Platform-13: Second-Project Extraction Proof — Scope Lock

**Status:** SCOPE-LOCKED
**Author:** analyst lane, revised with operator feedback
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

## Core Principle

> "Platform-13 proves the boundary by running on a second project."
>
> Not docs, not architecture diagrams — execution in a foreign environment. If
> this works, you've built a reusable orchestration system. If it fails, you've
> exposed hidden coupling. Both are wins.
>
> — Operator feedback

## Success Criteria (Non-Negotiable)

Platform-13 is **DONE** when all four conditions are met:

1. **A second repo runs steward without modifying `core/`** — zero patches to
   core modules to make the second project work
2. **Adapter is ≤ ~150–250 LOC** — if it balloons past this, the abstraction
   boundary is wrong (too much leaked from core, or adapter is compensating for
   missing core features)
3. **No Bid-Euchre strings appear in core runtime logs** — runtime log output
   from core modules must be project-agnostic when running the second project
4. **System survives failure cases** — at minimum: 1 failed test cycle, 1
   rejected PR, 1 retry loop. If Platform-13 doesn't include failure cases,
   it certifies a brittle system

## Extraction Boundary (from Platform-10)

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

### Where the Boundary Will Break (Expected)

The adapter contract as designed is too clean. In practice, expect:

- **Hidden filesystem assumptions** — hardcoded paths, `.claude/` layout
  expectations, branch naming patterns baked into core
- **Implicit repo structure dependencies** — core modules that assume specific
  directory layouts, PR flow timing, or test output formats
- **Hardcoded expectations** — lane naming conventions, worktree base directory
  assumptions, CI check name patterns

These breakages are the point. They prove the boundary needs work.

### High-Risk Core Modules

Modules most likely to leak Bid-Euchre assumptions through the boundary:

| Module | Risk | Expected Leakage |
|--------|------|------------------|
| `task_queue.py` | High | Lane semantics and naming patterns |
| `monitor.py` | High | PR/CI expectations, check name parsing |
| `worker_pool.py` | High | Worktree + repo structure coupling |
| `watchdogs.py` | Medium | Plan/checkpoint path assumptions |
| `token_economy.py` | Medium | Project directory slug parsing |

**Better than grep audit:** Run the hello project and **log every adapter
call**. If core ever branches on project behavior or assumes structure not
provided by the adapter, that's a leak.

## Adapter Contract Specification

A project adapter must implement the base protocol, plus a **translation layer**
for real-world mismatches:

### Base Protocol

```python
class ProjectAdapter(Protocol):
    """Contract for project-specific steward configuration."""

    # Identity
    project_name: str                          # "bid-euchre", "rin-balance"
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

### Translation Layer (Required)

The clean protocol above won't survive contact with real projects. The adapter
must also handle format mismatches between what the project produces and what
core expects:

```python
class ProjectAdapter(Protocol):
    # ... base protocol above ...

    # Translation — normalize project outputs into core-expected formats
    def normalize_test_output(self, raw_output: str) -> TestResult: ...
    def resolve_repo_paths(self) -> RepoLayout: ...
    def pr_creation_strategy(self) -> PRStrategy: ...
```

Without the translation layer, Bid-Euchre assumptions sneak back into `core/`
as "generic" parsing logic that only works for one project.

## Second-Project Candidates (Decided)

### Step 1 — Smoke Test: `hello-steward`

Synthetic proof project. Create a minimal repo with:
- A trivial test suite
- A Makefile with `check`, `test`, `lint` targets
- 2–3 source files

**Purpose:** Proves the adapter interface works without real project overhead.
Fast fail (~2h). Catches structural problems (boot, dispatch, PR loop) before
investing in a real project.

**What it proves:** Boot works, dispatch works, PR loop works.

**What it does NOT prove:** Monitoring robustness, failure handling, scheduling,
concurrency edge cases.

### Step 2 — Full Test: RIN Commodities Balance Sheet

**Project:** A commodities balance sheet built from publicly available RIN
(Renewable Identification Number) data.

- Operator will define data sources and methodology
- Only need an MVP for proving — scrape, build balance sheet, etc. is enough
- 20–50 files, non-trivial tests, at least one failing edge case
- This is where abstractions crack under real-world pressure

**Purpose:** Forces the adapter to handle a "slightly annoying" real project.
Stresses monitoring, failure handling, and the translation layer in ways the
hello project cannot.

### Step 3 — Outside Validation

Ship to a friend to see if they can use the steward for their project by
downloading from GitHub.

**Purpose:** The ultimate extraction proof. If a third party can boot the
steward against their own project using only published adapter docs + the
GitHub repo, the extraction is real. If they can't, the extraction is
self-referential.

### Two-Step Proof (Non-Negotiable)

Both the smoke test AND the full test are required. Skipping the full test
and declaring victory from hello-steward alone would certify a brittle system.

## Multi-Repo Runtime Isolation

> **Biggest hidden risk:** Claude Code multi-repo operation is more serious
> than initially treated.

The system assumes one repo context, one working directory, one
`.claude/runtime`. Cross-repo introduces path ambiguity and state separation
problems.

### Requirements

| Requirement | Description |
|-------------|-------------|
| **Explicit repo root scoping** | Core modules must accept a `repo_root: Path` parameter, never derive it from assumptions |
| **Strict runtime isolation** | Each project gets its own `.claude/runtime/` — no shared state files across projects |
| **No reliance on `cwd`** | Core must never call `os.getcwd()` or `Path(".")` to infer project identity |

### Anti-Leak Testing

Beyond grep audits, the primary leak detection method is **runtime logging**:

1. Boot the hello project
2. Log every adapter call from core → adapter
3. Assert: core never branches on project-specific behavior or assumes
   structure not provided through the adapter protocol
4. Assert: core runtime logs contain zero Bid-Euchre strings

Any adapter call that requires project-specific knowledge not in the protocol
is a leak that must be fixed in core, not worked around in the adapter.

## Packaging Strategy (Simplified)

Per operator guidance: premature to think about PyPI/git install/versioning.

**The only question now:** Can core run outside the original repo without hacks?

**Recommendation:** `pip install -e ../core`. Hardcode the editable install
path. Ignore distribution concerns for Platform-13. Packaging is a
Platform-14+ concern.

### Analyst Note

The original scope lock proposed a tiered packaging strategy (PyPI, git
submodule, monorepo workspace, etc.). The operator correctly identifies this as
premature. The extraction proof's value is in proving the boundary, not in
solving distribution. An editable install is the minimum viable packaging that
doesn't add noise to the signal we're measuring.

## Open Questions — Resolved

| # | Question | Operator Answer | Implication |
|---|----------|-----------------|-------------|
| 1 | Which ops modules are truly project-agnostic? | Agent should audit and assess the bid-euchre assumptions built into the platform boundary | Post-Platform-10 audit required; don't trust the module split until runtime-proven |
| 2 | What adapter interface does a second project need? | Use judgement — refine and tweak once established | Protocol is a starting point; expect it to evolve during hello/RIN proving |
| 3 | Mono-repo or multi-repo extraction? | Agree (multi-repo) | Confirmed: multi-repo is the proof topology |
| 4 | How to share tmux session layouts? | Option B — auto-generated from adapter | Core generates layout from `lane_pools()`; no manual layout maintenance |
| 5 | CI/CD: shared workflows or per-project? | Makes sense for reusable workflows | Core provides callable workflow templates; projects invoke with adapter config |
| 6 | Which second project? | Hello-steward (smoke) + RIN balance sheet (full) + outside GH validation | Three-tier proving: synthetic → real → external |

## Implementation Plan (Tightened)

The original scope lock proposed a 5-PR / ~9h implementation estimate with a
linear structure. The operator's feedback tightens this to a 4-phase plan that
front-loads the risky work:

### Phase 1 — Brutal Extraction (2–3h)

Move everything "probably generic" into `core/`. Don't overthink the interface.
Just make Bid-Euchre work via its adapter.

**Key constraint:** This is a mechanical move, not a design exercise. The
interface will be wrong — that's expected. Get the split done so Phases 2–3
can break it.

- Extract core modules from `src/bid_euchre/ops/` → `src/bid_euchre/ops/core/`
- Create `adapters/bid_euchre.py` with all project-specific config
- Verify Bid-Euchre steward still boots and operates correctly via adapter
- PRs: 1–2 (extraction + adapter wiring)

### Phase 2 — Hello Project (2h)

Create `hello-steward` repo. Write minimal adapter. Expect it to break.
Patch the interface until it runs clean.

- Create hello-steward repo on GitHub
- Implement `HelloAdapter` (2 author lanes, 1 orchestrator lane)
- Boot steward, dispatch a task, verify lifecycle: task → dispatch → PR → merge
- Log every adapter call; check for leaks
- PRs: 1 (adapter) + external repo setup

### Phase 3 — Stress Test (3–4h)

RIN balance sheet project. Force: failure, retry, PR rejection.

- Operator provides data sources and methodology
- Build MVP: scrape + balance sheet (enough to have real tests)
- Create `RINAdapter` and boot steward against it
- **Mandatory failure cases:**
  - 1 failed test cycle (test suite breaks, steward handles recovery)
  - 1 rejected PR (review finds issues, steward retries)
  - 1 retry loop (transient failure, steward recovers)
- Document every adapter call that required protocol expansion
- PRs: 1–2 (adapter + core fixes from leak discoveries)

### Phase 4 — Formalize Interface (1–2h)

Only now, after Phases 1–3 have beaten the interface into shape, lock the
`ProjectAdapter` protocol.

- Finalize protocol with translation layer methods proven needed
- Document adapter implementation guide
- Write extraction experience report: what was easy, what broke, what's missing
- PRs: 1 (protocol lock + docs)

**Total estimate:** ~8–11h across 5–7 PRs (this repo) + 2 external repos

### Analyst Pushback

The operator's 4-phase plan is stronger than the original linear structure. Two
areas where the analyst perspective adds nuance:

1. **Phase 1 "brutal extraction" vs. Platform-10 dependency.** The governing
   plan places Platform-13 after Platform-10. If Platform-10 has already
   performed the core/adapter split, Phase 1 becomes "verify and extend" rather
   than "move everything." If Platform-10 has NOT landed, Phase 1 becomes the
   extraction itself, which is Platform-10's job. Recommendation: Platform-13
   Phase 1 should adapt to whatever state Platform-10 leaves the codebase in,
   not re-do the split.

2. **Phase 3 scope.** The RIN balance sheet project requires operator input
   (data sources, methodology). This creates a dependency that could block
   Phase 3. Recommendation: Phase 2 (hello-steward) should be considered the
   minimum viable proof for Platform-13 COMPLETE status. Phase 3 can proceed
   as a strengthening exercise once operator provides the RIN project spec, but
   should not gate completion of the platform step if it's blocked on operator
   availability.

## Shared Infrastructure Requirements

| Infrastructure | Shared or Per-Project | Notes |
|----------------|----------------------|-------|
| tmux session layout | Per-project (generated from adapter `lane_pools()`) | Template in core, customized by adapter |
| CI workflows | Per-project (from core templates) | Core provides callable workflows, project customizes |
| Review loop | Shared (core) | Same review machinery, different repo target |
| Message bus | Per-project (separate `.claude/runtime/`) | Same code, isolated runtime directory |
| Token economy | Shared aggregation, per-project data | Cross-project dashboard possible |
| Skill files | Per-project (`.claude/skills/`) | Core promotion pipeline, project-specific skills |

## Dependencies

- **Platform-10 (required):** Core-vs-adapter split must be at least partially
  complete before extraction can be validated. Platform-13 depends on
  Platform-10's output. If Platform-10 has already landed the split, Phase 1
  is verification. If not, Phase 1 must be sequenced after Platform-10.
- **Platform-11 (optional):** Learning loop data portability would strengthen
  the proof but is not required for MVP.
- **Platform-12 (optional):** Cross-model routing portability would strengthen
  the proof but is not required for MVP.
- **Operator (Phase 3):** RIN balance sheet data sources and methodology
  definition. Phase 3 cannot start without this.

## Risks

1. **Platform-10 boundary is wrong.** If the core-vs-adapter split from
   Platform-10 doesn't cleanly separate concerns, Platform-13 will discover
   leaky abstractions. This is the desired outcome — the extraction proof is
   specifically designed to find these leaks. But it means Platform-13 may
   generate follow-up work for Platform-10/14.

2. **External repo management overhead.** Two external repos (hello-steward,
   RIN balance sheet) add operational burden. Mitigation: hello-steward is
   minimal (3 source files, 10 tests). RIN balance sheet is MVP only.

3. **Claude Code multi-repo limitations.** Claude Code sessions are typically
   scoped to one repo. Running steward across two repos may require creative
   worktree management or multiple Claude instances. Mitigation: explicit repo
   root scoping and runtime isolation (see Multi-Repo Runtime Isolation above).

4. **Adapter interface instability.** The protocol will change during Phases
   2–3. This is expected and correct — the interface should be shaped by
   contact with real projects, not by upfront design.

5. **Operator dependency for Phase 3.** The RIN balance sheet project requires
   operator-provided data sources and methodology. If operator availability is
   limited, Phase 3 may be delayed. Mitigation: Phase 2 (hello-steward) is the
   minimum viable proof; Phase 3 strengthens but does not gate completion.

6. **"Core is generic" — probably not yet.** The most dangerous risk is
   believing the abstraction is clean before proving it. The anti-leak testing
   methodology (log every adapter call, assert no project-specific branching in
   core) is the primary mitigation. Don't fall into: "We designed a clean
   abstraction, therefore it is clean."
