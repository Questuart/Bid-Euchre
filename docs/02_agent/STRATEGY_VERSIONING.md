# Strategy Versioning

`src/bid_euchre/strategy/greedy.py` is the live hosted-play strategy for
both OLSa and Bud Bot. `GLUTTON_STRATEGY_VERSION` (exposed as `VERSION`
on both `GluttonStrategy` and `GluttonIsolatedStrategy`) is the on-disk
record of which behavior cohort produced any given hosted match.

`web/routes.py` reads `type(engine.play_strategy).VERSION` at match
creation and stamps it onto `matches.play_strategy_version` (one write
per match). Pre-versioning rows remain `NULL` — the honest "unknown
cohort" marker. Full rationale:
`plans/sessions/2026-04-06_strategy_versioning_plan.md`.

## Semver rules (relaxed MAJOR.MINOR.PATCH)

| Component | Bump when |
|-----------|-----------|
| MAJOR | Strategy interface change (rename, signature change, removed flag). |
| MINOR | New behavioral priority added or removed (e.g., Cash-A). |
| PATCH | Bug fix that changes play in a narrow class of states. |

Counts toward a bump: changes inside `_choose_lead`, `_choose_discard`,
`choose_card`, `_is_sure_winner`, `observe_play`, feature-flag defaults,
or `card_value_for_dump`. Does **not** count: docstrings, comments, log
lines, ruff cleanups, new helpers that are added but never called.

## PR changelog template

Every PR that touches `src/bid_euchre/strategy/greedy.py`'s decision
logic must include the following block in its description:

```markdown
## Strategy Version

| Field | Value |
|-------|-------|
| Old version | "0.7.0" |
| New version | "0.8.0" |
| Bump category | MINOR (added sure-winner-lead priority) |
| Behavior delta | <what plays change, in what game states> |
| Affected functions | `_choose_lead`, `choose_card` |
| Unaffected functions | `_is_sure_winner` |
```

## Enforcement

Social / reviewer responsibility for now. A future CI lint that fails
any PR touching the decision functions without bumping the constant is
tracked as a deferred enhancement in the plan above (§2.6).
