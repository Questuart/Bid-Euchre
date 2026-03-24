# Browser Game Hosting and Human Data Capture — Governing Plan

**Date:** 2026-03-14
**Status:** COMPLETE
**Scope:** Build a hosted async browser game for Bid Euchre that uses this repo as the rules and AI source of truth. V1 supports one human seat against three AI seats, multi-hand match scoring to `+52` or `-52`, private-link access, selectable opponent model, and default-on decision logging suitable for future training-data export.
**Supersedes:** None

---

## 1. Decision

This initiative will ship a narrow, production-usable product in a few days by reusing the existing Python game engine and adding only the minimal new layers required for browser play: a stepwise hosted-play domain engine, a thin FastAPI web app, persistent match storage, and action logging. The implementation will not re-create rules in the web tier, will not add real-time multiplayer, and will not take on extra product scope such as leaderboards, accounts, or shadow-inference infrastructure before the core product works end to end.

## 2. Goals

1. Ship a private-link async browser game where one human plays both bidding and card play against three AI opponents.
2. Let the player choose the single bidding model used by all three AI seats for a match.
3. Preserve repo rules and determinism as the source of truth for bidding legality, card legality, trick resolution, and hand scoring.
4. Add match-level state for running score, with match termination at `team_human >= 52` or `team_human <= -52`.
5. Capture human and AI decisions in a durable format suitable for later supervised/offline training workflows.
6. Make the plan simple for autonomous execution by defining concrete package boundaries, PR slices, validation commands, and deferrals.

## 3. Non-Goals (V1)

The following are explicitly out of scope until the hosted product works end to end:

- Multi-human rooms or social play
- Accounts, authentication, or player profiles
- Leaderboards, public stats pages, or ranking systems
- Real-time websockets or live spectators
- Card-play ML artifacts beyond the existing `GluttonStrategy`
- Shadow-decision infrastructure or parallel AI counterfactual logging
- Dual-write primary persistence schemes such as `SQLite + JSONL` in production
- Native mobile apps or advanced frontend polish

## 4. Key Definitions

- **Hosted play mode:** The browser-game product introduced by this initiative. It extends current hand-scoped simulation with persistent match state and web delivery.
- **Match:** A sequence of hands with running score. V1 ends when the human player's team reaches `+52` or `-52`.
- **Hand state:** The persisted, resumable state for one hand: dealer, hands, auction transcript, current trick, leader, legal actions, and per-hand outcome fields.
- **AI lineup:** The single selected bidding artifact used by all three AI seats in a match, combined with `GluttonStrategy.choose_card(hand, plays_so_far, contract_type, trump_suit, player_index) -> int` from [greedy.py](../../src/bid_euchre/strategy/greedy.py).
- **Bidding interface:** `BiddingPolicy.choose_bid(obs: BiddingObservation) -> BidAction` with `BiddingObservation(hand, seat, dealer_seat, current_high_bid, auction_transcript, allowed_contracts)` from [bidding.py](../../src/bid_euchre/strategy/bidding.py).
- **Hosted-play domain package:** The new reusable engine layer expected under `src/bid_euchre/hosted_play/`.
- **Web app package:** The new interface layer expected under `web/`, containing the FastAPI app, templates, and static assets. This layer imports from `src/bid_euchre/` but not vice versa.
- **Decision event:** A persisted bid or card action taken by a human or AI seat, recorded with enough context to reconstruct legal alternatives and replay the hand deterministically. Decision events are a new logging domain for hosted play — they are independent of the existing simulation JSONL logging contract defined in [DATA_CONTRACT.md](../../docs/01_core/DATA_CONTRACT.md), but share the same principle of capturing enough context for deterministic replay. The Phase 2 persistence contract (§7.4 item 4) must define the decision-event schema explicitly.
- **Future extraction boundary:** The package seam that should allow the hosted-play domain layer to move into a separate repo later without pulling FastAPI, templates, or SQLAlchemy concerns with it.
- **MVP cut line:** The smallest hosted product that satisfies the user’s stated goal. Features outside the MVP cut line must not block shipping.
- **Plan review rounds:** While this plan remains `PROPOSED`, revisions may be made directly to this file. Once status changes to `ACTIVE`, the governing plan becomes immutable during execution and all changes flow through `plans/browser_game/amendments.md`.

## 5. Architecture Decisions

### 5.1 Package Layout

The initiative will use a two-layer layout:

- `src/bid_euchre/hosted_play/`
  - Domain engine for stepwise hand progression, match progression, AI turn execution, persistence-facing schemas, and replay/export helpers.
  - Reuses existing rule and strategy interfaces from `core/`, `strategy/`, `sim/`, and `scoring.py`.
- `web/`
  - FastAPI app, route handlers, request/response schemas, Jinja2 templates, and minimal UI assets.
  - Imports the hosted-play domain package and existing `src/bid_euchre/*` modules.

This layout keeps canonical rules in `src/`, keeps the browser app thin, and avoids circular imports.

### 5.2 Hosting and Persistence

- **Local/dev persistence:** SQLite via SQLAlchemy is allowed for local development and tests.
- **Production persistence:** Postgres is the source of truth for deployed hosted play.
- **Primary hosting target:** Render web service + managed Postgres.
- **Export format:** JSONL or parquet exports may be generated from database records later. They are not a primary store for V1.
- **Dependency packaging:** Hosted-app dependencies live in the `hosted` optional dependency group in [pyproject.toml](../../pyproject.toml), separate from the research/dev stack.

### 5.3 UI Transport

The browser app will use server-rendered HTML with standard forms and HTMX-style partial refreshes where helpful. The app must still function through plain POST/redirect flows if an HTMX enhancement is absent or removed.

### 5.4 AI Policy Composition

- AI bidding uses approved artifact-backed bidders from the existing repo.
- AI card play uses `GluttonStrategy`.
- V1 launch scope requires a model registry that lists which bidding artifacts are product-approved and how they are surfaced in UI.
- Initial approved launch roster:
  - `heuristic` → `HeuristicSuitBidder` with no artifact dependency
  - `hybrid_olsa` → `HybridOLSaBidder` when the configured artifact path exists
  - `gbt_action_value` → `GBTActionValueBidder` when the configured artifact path exists
- Artifact discovery must be environment-driven through a centralized model directory/configuration path, not hardcoded into route handlers or templates.

### 5.5 Future Extraction Boundary

The implementation must preserve a clean seam for later repo extraction without
forcing that extraction now.

- `src/bid_euchre/hosted_play/` must remain web-framework-free.
- `src/bid_euchre/hosted_play/` must not import from `web/`.
- `src/bid_euchre/hosted_play/` should own match state transitions, legal-action
  derivation, AI turn execution, serialization, and replay/export helpers.
- `web/` should own FastAPI wiring, request parsing, HTML rendering, and
  persistence integration.
- Web handlers should call a small public domain surface exposed from
  `src/bid_euchre/hosted_play/__init__.py` rather than reaching into many
  internal modules.
- Model discovery and artifact path resolution should be centralized in one
  module, not scattered across route handlers or templates.
- Persistence rows may store serialized domain state, but ORM models must not
  become the domain model.

This boundary is a design constraint for Phase 0 and all later implementation
sub-plans.

## 6. MVP Cut Line and Delivery Strategy

### 6.1 MVP Must-Haves

The following define the MVP:

1. Match creation via private link
2. AI lineup selection from an approved model registry
3. Human bidding and card play
4. AI auto-play until the next human decision point
5. Running match score to `+52 / -52`
6. Durable persistence so refresh/resume works
7. Decision logging for human and AI actions
8. Hosted deployment with a smoke-tested vertical slice

### 6.2 Deferred Until After MVP

These items are intentionally deferred and must not block the first hosted release:

- Replay viewer UI
- Analytics dashboards
- Leaderboards
- Bulk human-data ingestion jobs
- Automated shadow inference against alternate bidders
- Multi-device session management or invite management UI

### 6.3 PR Boundaries

The implementation is expected to land in at most five PRs:

| PR | Scope | Phases Covered | Ship Blocker |
|----|-------|----------------|--------------|
| PR-1 | Foundation contracts, package skeleton, dependency additions, model inventory, hosted-play rules doc | Phase 0 | Yes |
| PR-2 | Stepwise hosted-play domain engine with tests | Phase 1 | Yes |
| PR-3 | FastAPI app, persistence layer, action-event storage, private-link APIs | Phase 2 | Yes |
| PR-4 | Browser UI, AI loop integration, end-to-end local vertical slice | Phase 3 | Yes |
| PR-5 | Export tooling, deployment config, smoke validation, launch docs | Phases 4-5 | Yes |

If a PR grows beyond one coherent concept, split it and update this table before implementation proceeds.

### 6.4 Two-Day Execution Bias

To maximize the chance of a working product in a couple of days:

- Prefer existing abstractions over general frameworks
- Prefer server-rendered pages over frontend build tooling
- Prefer one vertical slice that works locally before adding exports or polish
- Prefer simple SQLAlchemy models over event-sourcing or distributed orchestration
- Prefer idempotent HTTP actions over websockets
- Treat Phase 4 exports as launch support, not a reason to delay the playable product

## 6.5 Relationship to Autonomous-Ops Redesign

> **Reference:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`

The autonomous-ops redesign is **foundational infrastructure for browser-game execution** but **not a blocker**. The browser-game initiative involves more parallel tracks than Arc D (domain engine, backend API, frontend product, replay/export, deployment), which creates real multi-agent coordination pressure that the ops redesign is designed to address.

**Sequencing relative to this initiative:**

| Browser-game phase | Ops infrastructure available | Benefit |
|--------------------|------------------------------|---------|
| Phase 0-2 (foundation → backend API) | Ops PRs 1-2 (workflow scaffold, tmux, VS Code audit) | Role-based worktrees and audit surface for parallel domain + API work |
| Phase 3 (frontend product) | Ops PRs 3-4 landing (operator CLI, health checks, memory/index) | `ops.py status` for monitoring parallel backend + frontend agents |
| Phase 5 (deployment and launch) | Ops PR-5 (rollout, safety, recovery) | Recovery templates and context safety before external exposure |

The ops PRs are not prerequisites for starting browser-game work. Phases 0-2 can proceed with the informal workflow improvements (Ghostty, tmux, role worktrees) already adopted. The heavier ops infrastructure lands progressively as coordination complexity grows.

## 7. Execution Structure

### 7.1 Phases / Milestones

| Phase | Name | Description | Depends On | MVP Status |
|-------|------|-------------|------------|------------|
| 0 | Foundation | Lock hosted-play rules extension, package layout, dependency stack, test strategy, persistence contracts, and model publication policy. | None | Must-have |
| 1 | State Engine | Add stepwise hand/match state transitions that reuse existing rules and strategy interfaces instead of full-hand batch simulation. | Phase 0 | Must-have |
| 2 | Backend API | Add FastAPI app, persistence layer, model registry, private-link match lifecycle APIs, and core action logging. | Phase 1 | Must-have |
| 3 | Frontend Product | Add browser UI for match setup, bidding, trick play, score display, replay-safe refresh, and async resume. | Phase 2 | Must-have |
| 4 | Export and Replay Validation | Add hosted-play event export tooling and deterministic replay/export validation for training use. | Phase 2 | Must-have for launch support, not for local vertical-slice proof |
| 5 | Deployment and Launch Validation | Add production configuration, deploy flow, smoke tests, and launch-readiness validation. | Phases 3 and 4 | Must-have |

### 7.2 Step Template (per phase)

Each phase follows this sequence:

1. **Scope lock**
   - Commands: `sed -n '1,260p' plans/browser_game/governing_plan.md`, `sed -n '1,220p' plans/browser_game/<phase>/checkpoints.md`
   - Validates: The next step is unambiguous and any implementation-heavy work has a registered sub-plan.
   - Error recovery: If the step requires new design choices or >3 files changed, create a sub-plan and register it before editing code.
   - Outputs: Updated checkpoint target and, when needed, a registered sub-plan.
2. **Implementation**
   - Commands: `uv run ruff check src tests web`, `uv run ruff format src tests web`, targeted `uv run pytest ...` commands for touched modules, and any phase-specific command listed in the sub-plan.
   - Validates: New code compiles, tests cover contract changes, and no new import-boundary violations are introduced.
   - Error recovery: Stop and amend only if the governing plan is materially wrong; otherwise record blocker details in checkpoints/sub-plan and continue within scope.
   - Outputs: Code, tests, docs, migrations, and any generated artifacts declared for the phase.
3. **Verification**
   - Commands: targeted `uv run pytest ...`, `make check` before PR creation, plus phase-specific manual/browser validation where applicable.
   - Validates: Contract behavior matches the governing plan and persistent state can resume correctly after each user action.
   - Error recovery: Add or tighten tests before proceeding; do not defer core state-correctness verification.
   - Outputs: Passing validation record in the checkpoint/session log.
4. **Handoff**
   - Commands: update `plans/browser_game/<phase>/checkpoints.md`, `plans/browser_game/sub_plan_registry.md`, and any sub-plan outcome section.
   - Validates: A future session can determine the next runnable unit without rereading the whole codebase.
   - Error recovery: If incomplete, record exact blocker, current branch/PR context, and next action.
   - Outputs: Durable state for the next iteration.

### 7.3 Autonomous Execution Rules

To keep this initiative simple to orchestrate autonomously:

1. Each phase starts with exactly one primary sub-plan unless a blocker forces a split.
2. An agent should always target the smallest end-to-end proof before widening the scope of a phase.
3. No agent should invent a second source of truth for rules, scoring, or decision logs.
4. If artifact availability is unclear, stop in Phase 0 and inventory actual files before coding UI around them.
5. If a later-phase requirement can be stubbed without invalidating the MVP, stub it and record the follow-up rather than blocking the vertical slice.
6. If a change weakens the future extraction boundary, prefer a small adapter in `web/` over pushing web or ORM concerns into `src/bid_euchre/hosted_play/`.

### 7.4 Phase 0 Dependencies

The following must be resolved before Phase 1 is considered runnable:

1. **Hosted-play rules contract**
   - Create a browser-game rules contract document at `docs/01_core/HOSTED_PLAY_RULES.md`.
   - It must explicitly define match scoring to `+52 / -52`, private-link access assumptions, human logging defaults, and any divergence from [RULES.md](../../docs/01_core/RULES.md), which currently treats match-level scoring as out of scope.
2. **Dependency stack**
   - Add and pin web-serving dependencies in [pyproject.toml](../../pyproject.toml).
   - Dependencies live in the `hosted` optional dependency group.
   - Minimum expected set: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `sqlalchemy`, `httpx`, and a Postgres driver.
3. **State engine boundary**
   - Phase 1 must not drive browser play through `play_single_hand(...)` in [simulation.py](../../src/bid_euchre/sim/simulation.py), because that function resolves a full hand in one call.
   - A new stepwise engine must reuse `get_legal_indices(...)`, `trick_winner(...)`, `compute_points(...)`, `BiddingPolicy.choose_bid(...)`, and `Strategy.choose_card(...)` rather than duplicating game rules.
4. **Persistence contract**
   - Lock the initial schema for matches, hands, action events, model registry, and replay/export metadata before API implementation begins.
5. **Model publication policy**
   - Inventory which bidding artifact files actually exist, whether they are committed or generated, and which ones are approved for hosted play.
   - Initial launch policy is:
     - always expose `heuristic`
     - expose `hybrid_olsa` and `gbt_action_value` only when configured artifact files are present
6. **Testing contract**
   - Lock the test layout and required commands before any web code is written.
7. **Authoritative rules-doc path**
   - `plans/browser_game/hosted_play_rules.md` may exist as a planning draft, but
     the authoritative hosted-play rules extension for implementation must live
     at `docs/01_core/HOSTED_PLAY_RULES.md`.

## 8. Testing Strategy

### 8.1 Test Layout

- `tests/unit/hosted_play/`
  - Stepwise engine, scoring transitions, AI loop helpers, replay helpers
- `tests/integration/hosted_play/`
  - Persistence, FastAPI routes, request handling, match resume, action submission
- `tests/integration/hosted_play/test_browser_flow.py` or equivalent
  - End-to-end local vertical slice using FastAPI test client

### 8.2 Required Validation by PR

- **PR-1**
  - Rules doc check
  - `uv sync --extra hosted` succeeds
  - Artifact inventory documented
- **PR-2**
  - Unit tests for bidding progression, legal cards, trick winners, hand termination, match score transitions
- **PR-3**
  - Integration tests for create/resume/bid/play/advance routes and persistence writes
- **PR-4**
  - End-to-end integration test for one match flow through multiple human decisions
  - Manual browser smoke on local server
- **PR-5**
  - Export/replay determinism tests
  - Deployment smoke checklist

### 8.3 Repo Integration

- All new Python tests must live under `tests/` so they run under existing pytest invocations.
- `make check` remains required before a PR is considered ready.
- If template/static validation needs extra tooling, add a targeted command in the relevant sub-plan rather than a new mandatory repo-wide gate unless clearly justified.

## 9. Sub-Plan Governance

Sub-plans are required for implementation-heavy steps (>3 files changed, new code, or design choices not fully specified here).

### 9.1 Sub-Plan Registry

Maintained in: `plans/browser_game/sub_plan_registry.md`

Each sub-plan entry tracks:

| Field | Description |
|-------|-------------|
| `id` | Stable identifier: `SP-<phase>-<seq>` |
| `parent` | Parent plan section reference |
| `status` | `proposed`, `in_progress`, `blocked`, `completed`, `abandoned`, `superseded` |
| `owner` | Agent session ID or human name |
| `file` | Path to the sub-plan document |

### 9.2 When to Create a Sub-Plan

- The step requires >3 files changed
- The step involves new code
- The step introduces schema, API, UI, or deployment decisions not locked in this governing plan

### 9.3 Sub-Plan Lifecycle

`proposed -> in_progress -> completed`, with `blocked`, `abandoned`, and `superseded` transitions as defined in the repo-wide plan framework.

## 10. Checkpoint Contract

Each phase maintains a `checkpoints.md` file at:

- `plans/browser_game/0_foundation/checkpoints.md`
- `plans/browser_game/1_state_engine/checkpoints.md`
- `plans/browser_game/2_backend_api/checkpoints.md`
- `plans/browser_game/3_frontend_product/checkpoints.md`
- `plans/browser_game/4_data_pipeline/checkpoints.md`
- `plans/browser_game/5_deployment_launch/checkpoints.md`

These checkpoint files are the durable session-resume mechanism for this initiative.

## 11. Evidence / Output Contract

Each phase must produce the following evidence:

- **Phase 0**
  - `docs/01_core/HOSTED_PLAY_RULES.md`
  - locked package-layout decision
  - locked dependency stack
  - initial schema sketch
  - artifact inventory and approved-model list
  - first executable Phase 1 sub-plan
- **Phase 1**
  - new `src/bid_euchre/hosted_play/` engine module(s)
  - unit tests covering bidding legality, card legality, trick progression, hand completion, and match score transitions
  - explicit proof that the new engine delegates rule evaluation to existing core functions rather than forking logic
- **Phase 2**
  - `web/` application entrypoint
  - persistence models/migrations
  - API tests for match creation, private-link resume, bid submission, card submission, AI auto-advance, and action-event storage
- **Phase 3**
  - browser pages/templates and any required static assets
  - end-to-end local vertical slice proof
  - replay-safe refresh/resume behavior demonstration
- **Phase 4**
  - export script(s) mapping hosted-play data to training-ready artifacts
  - deterministic replay/export validation tests
- **Phase 5**
  - deployment configuration and startup command
  - production environment variable contract
  - smoke validation for deploy, match creation, full hand flow, and data capture

No phase is complete until its checkpoint file records validation evidence and the sub-plan registry reflects final statuses.

## 12. Risks

| Risk | Mitigation |
|------|------------|
| Reimplementing rules in the web layer causes logic drift | Require Phase 1 to delegate legality and trick resolution to existing `core/` functions. |
| Full-hand simulator is reused directly and prevents resumable UI state | Treat `play_single_hand(...)` as a reference/oracle, not the browser runtime loop. |
| Match-level scoring conflicts with current authoritative rules docs | Add a dedicated hosted-play rules contract in Phase 0 before engine work. |
| Artifact-backed bidding is underspecified for product use | Lock a model registry and publication policy before API/UI work. |
| Human data is incomplete for training use | Persist every action with legal set, actor provenance, match/hand IDs, and replay metadata. |
| Async browser play introduces state corruption on refresh/retry | Use idempotent action submission and persisted hand snapshots with explicit turn ownership. |
| Deployment complexity causes early thrash | Keep the app server-rendered and thin; defer non-essential product features. |
| Package sprawl or scope creep slows autonomous execution | Enforce the five-PR boundary and the explicit non-goals list. |

## 13. Success Criteria

1. A player can open a private link, select an AI lineup, and complete an async browser match to `+52` or `-52`.
2. The human player performs both bidding and card play; AI seats use the selected bidding artifact plus `GluttonStrategy` card play.
3. Hosted play reuses existing repo rule functions for legal actions and trick outcomes.
4. Every human and AI decision is persisted with enough context for deterministic replay and future dataset export.
5. The hosted product can be run locally and in a deployed environment with the same core engine and persistence contract.
6. The initiative remains governable across later sessions through checkpoints, sub-plans, and amendments without re-scoping from scratch.

## Outcome

- Result: **ALL PHASES COMPLETE** (Phases 0-5 shipped)
- PRs:
  - **Phase 0 (Foundation):** PR #1300 (package skeleton)
  - **Phase 1 (State Engine):** PRs #1354, #1357, #1361, #1368, #1370, #1379, #1381, #1388, #1393, #1422
  - **Phase 2 (Backend API):** PRs #1397, #1398, #1400, #1401, #1406, #1407, #1409, #1412, #1414, #1416, #1419, #1421, #1424, #1427, #1429, #1430, #1431, #1432, #1434, #1447
  - **Phase 3 (Frontend Product):** PRs #1475, #1489, #1495, #1498, #1501
  - **Phase 4 (Data Pipeline):** PRs #1529, #1533, #1535, #1538, #1545
  - **Phase 5 (Deployment & Launch):** PRs #1622, #1625, #1627, #1629, #1634, #1636, #1637, #1638, #1642, #1644, #1646
- Notes: All code artifacts, deployment configuration, and launch documentation shipped. Render deployment execution is an operational activity outside governed plan scope. The browser game is ready for production deployment using the launch checklist (PR #1644) and deployment guide (PR #1646).
