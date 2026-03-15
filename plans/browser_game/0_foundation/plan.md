# Phase 0 Plan — Foundation

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase:** `0_foundation`
**Status:** PROPOSED

---

## Objective

Lock the minimal decisions that unblock autonomous implementation without
re-arguing architecture during code work.

## Decisions To Lock

1. Package layout: `src/bid_euchre/hosted_play/` plus `web/`
2. Hosting target: Render primary, Postgres in production, SQLite for local dev/tests
3. Rules extension path: `docs/01_core/HOSTED_PLAY_RULES.md`
4. Persistence contract: matches, hands, action events, model registry
5. Model publication policy: `heuristic` always, `hybrid_olsa` and `gbt_action_value` when configured artifacts exist
6. Testing contract: where tests live and which commands are mandatory
7. PR cut line: no more than five PRs for MVP
8. Future extraction boundary: what must stay in `src/bid_euchre/hosted_play/` vs `web/`
9. Dependency packaging: hosted app deps live in `[project.optional-dependencies].hosted`

## Deliverables

- A foundation sub-plan with exact files and validation commands
- A rules extension doc path locked in the repo plan
- A recommended initial schema sketch
- An artifact inventory task for actual bidder files
- An explicit extraction-boundary contract so later repo split remains possible
- A locked hosting/dependency strategy so Phase 1 does not reopen platform choices

## Exit Criteria

- Phase 1 can begin without reopening package-layout or hosting debates
- A future agent can start PR-1 directly from the registered sub-plan

## Outcome

_To be filled after execution._

- Status: --
- Notes: --
