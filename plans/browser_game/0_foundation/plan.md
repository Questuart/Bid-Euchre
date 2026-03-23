# Phase 0 Plan — Foundation

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase:** `0_foundation`
**Status:** COMPLETE

---

## Objective

Lock the minimal decisions that unblock autonomous implementation without
re-arguing architecture during code work.

## Decisions To Lock

1. Package layout: `src/bid_euchre/hosted_play/` plus `web/`
2. Hosting target: Render primary, Postgres in production, SQLite for local dev/tests
3. Rules extension path: `docs/01_core/HOSTED_PLAY_RULES.md`
4. Persistence contract: `players`, `matches`, `hands`, `decisions`; no V1 database `model_registry`
5. Model publication policy: `heuristic` always, `hybrid_olsa` when configured artifact exists; `gbt_action_value` deferred until post-MVP
6. Model serving contract: approved bidders preload once at FastAPI startup and are cached in `app.state`
7. Testing contract: where tests live and which commands are mandatory
8. PR cut line: no more than five PRs for MVP
9. Future extraction boundary: what must stay in `src/bid_euchre/hosted_play/` vs `web/`
10. Dependency packaging: hosted app deps live in `[project.optional-dependencies].hosted`

## Deliverables

- A foundation sub-plan with exact files and validation commands
- A rules extension doc path locked in the repo plan
- A recommended initial schema sketch
- A config-backed approved model roster and startup preload contract
- An artifact inventory task for actual bidder files
- An explicit extraction-boundary contract so later repo split remains possible
- A locked hosting/dependency strategy so Phase 1 does not reopen platform choices

## Exit Criteria

- Phase 1 can begin without reopening package-layout or hosting debates
- A future agent can start PR-1 directly from the registered sub-plan

## Outcome

_To be filled after execution._

- Status: COMPLETE
- Notes: Phase 0 closed on 2026-03-23 after recording the V1 model-serving amendment and adding `web/schema.sql` as the initial hosted-play persistence contract.
