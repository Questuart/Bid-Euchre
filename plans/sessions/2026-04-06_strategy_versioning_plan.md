# Strategy Versioning + Future Ablation Methodology

> **Task:** analyst-b / packet `e97204e1bf12`
> **Refs:** #2519, #2502, #2504, #2506
> **Date:** 2026-04-06
> **Status:** Investigation + plan only — no implementation
> **Author:** analyst-b

## Scope (per orchestrator scope refinements 2026-04-06)

This document is the system of record for **two** clearly separated phases
of work. Both are complete and durable so future-us can resume each
independently.

| Phase | Section | Status | Goal |
|-------|---------|--------|------|
| **MVP** | §1 | **BLOCKING for Cash-A** — ship now | Minimum versioning + DB capture so Cash-A can land in the live game with clean cohort boundaries. |
| **Future Research Methodology** | §2 | **DEFERRED** — documented only | Full ablation harness, paired H2H matrix, statistical acceptance gates. Will be resumed when we revisit research-quality model retraining. |

> **Operator directive (verbatim):** "OK to edit browser deployment glutton
> without retraining bidder artifacts BUT versioning and logging must be
> diligent — future research needs clean cohort data. Improvement evaluation
> and ablation between model iterations must be measurable."
>
> **Refining message (verbatim, 2026-04-06):** "Optimize the plan for shortest
> path to shipping Cash-A safely, not for research thoroughness. … Your plan
> document should have a clearly labeled 'Future Research Methodology' section
> that captures the full ablation framework design now, so we don't lose
> context when we revisit it later. Treat the doc as the system of record
> for both the MVP shipping plan AND the deferred research methodology."

## Background

### Motivating problem (#2519)

`src/bid_euchre/strategy/greedy.py` is the play strategy for **both** hosted
browser models (OLSa "Easy" and Bud Bot — see `web/ai_manager.py:141,177`).
Since the Arc D v2 finalization on 2026-03-19, the file has accumulated
seven behavioral edits with **no on-disk record** of which version of the
strategy produced any given hosted-play hand:

| PR | Commit | Behavior change |
|----|--------|-----------------|
| #2108 | `3a61919b` | Lead weak on low contracts to conserve strong cards (#2098) |
| #2141 | `5e63f02c` | Defense-in-depth contract sync in Glutton.choose_card (#2133 Bug B) |
| #2172 | `46e3026d` | Clear stale inference on contract change in Glutton.choose_card (#2139) |
| #2190 | `15c3d97f` | Lead right bower when holding both bowers + 5+ trump (#2167) |
| #2245 | `65f4e923` | Preserve bower leads for smart_leads configs (#2201) |
| #2396 | `c5274e2c` | Remove void-suit sort from Glutton discard (#2300) |
| #2397 | `d4695c1c` | Lead strongest card in low contracts (#2300 fix-up) |

(Plus convention follow-ups in #2189 and #2199 which do not change behavior.)

The hosted DB (`Match`, `Hand`, `Decision` tables in `web/db.py`) records
the bidder identity (`Match.ai_model = 'olsa' | 'bud_bot'`) and a freeform
`Decision.decision_source` (currently set to the same `ai_model` string at
`web/routes.py:2635`), but **nothing about which version of the play
strategy was active**. As a result, hand-decision data captured during
the pilot **mixes cohorts silently** — Olive Juice, Pete, Marg, and the
other early players have hands recorded against an unknown mix of pre-#2300,
post-#2300, post-#2397, and (soon) post-Cash-A play strategies.

The Cash-A PR (sure-winner lead + draw-trump-first + draw-trump-from-the-top)
is the next behavior bump on the queue. Operator wants the versioning
infrastructure landed **before** Cash-A so:

1. Cash-A produces a clean cohort boundary in the hosted DB.
2. Pre-Cash-A hands remain identifiable for future analysis.
3. The next behavior bump after Cash-A (e.g., Cash-B or GluttonV2) does
   not re-create the same loss-of-history problem.

### What is *not* the problem

- **The bidder artifacts (OLSa, Bud Bot) are already versioned implicitly**
  by their on-disk artifact filenames + the `arc_d_rung_bundle_v1` schema.
  `web/ai_manager.py:_try_load_olsa` and `_try_load_bud_bot` load each
  artifact from a versioned filename (`hybrid_r{N}.json`,
  `gbt_high.joblib`, etc.). Operator confirmed bidders do **not** need
  retraining for Cash-A — only the play strategy changes — so the
  versioning gap is exclusively on the play side.
- **The research pipeline (`experiments/run_experiment.py`) already records
  `git_sha`** in `meta.json` (`run_experiment.py:1193`, schema v2). Each
  research run is one git_sha and the JSONL log's `strategy_id` field
  identifies the strategy. The research path is adequately versioned for
  its single-run cohort model. The gap is the **hosted path**, where hands
  accumulate across deployments and a single SHA does not describe a row.

### What the existing infrastructure already provides

- **`Match.ai_model`** identifies which bidder was active.
- **`Match.seed`** identifies the deal seeding.
- **`Decision.created_at`** + git history would let us reconstruct the
  active git_sha for each match by binary-searching deploy timestamps,
  but this is brittle and assumes one deployment per commit.
- **`web/app.py` already has an idempotent `ALTER TABLE ADD COLUMN`
  migration pattern** at lines 118–139 (the `onboarding_complete` column).
  We can reuse this pattern verbatim.
- **`MatchEngine` already deep-copies the play_strategy per match**
  (`web/routes.py:_build_engine`, fix from #2168). So a per-match version
  read at construction time is the natural attach point.

---

# Section 1 — MVP Shipping Plan (BLOCKING for Cash-A)

## 1.1 STRATEGY_VERSION constant

### Where it lives

A module-level constant in `src/bid_euchre/strategy/greedy.py`:

```python
# Module-level version constant — bump on every behavior change to
# GluttonStrategy or GluttonIsolatedStrategy. See docs/02_agent/STRATEGY_VERSIONING.md.
GLUTTON_STRATEGY_VERSION = "0.7.0"
```

The constant is **read by the hosted match creation path** at
`web/routes.py:_build_engine` and stamped onto `Match.play_strategy_version`
(see §1.2). It is **not** read by the strategy itself — there is no
runtime branch on version. The constant exists purely for provenance.

The version is also exposed as a class attribute on both classes for
convenience:

```python
class GluttonStrategy(Strategy):
    VERSION = GLUTTON_STRATEGY_VERSION
    ...

class GluttonIsolatedStrategy(Strategy):
    VERSION = GLUTTON_STRATEGY_VERSION
    ...
```

This lets `MatchEngine` and `_build_engine` read
`type(play_strategy).VERSION` polymorphically without importing the
constant directly.

### Semantic versioning rules

The constant follows a relaxed `MAJOR.MINOR.PATCH` convention chosen to
match `pyproject.toml`'s `version = "0.1.0"` style and to keep humans (not
tooling) in charge of bumps:

| Component | Bump when |
|-----------|-----------|
| MAJOR | Strategy interface change (rename, signature change, removed feature flag). Rare. |
| MINOR | New behavioral priority added or removed (e.g., Cash-A adds sure-winner-lead priority → MINOR bump). |
| PATCH | Bug fix that changes which card is played in a *narrow* class of states (e.g., the #2300 dump-fix). |

### What goes in the version vs. what is auxiliary

| Counts toward version | Does **not** count |
|----------------------|-------------------|
| Changes inside `_choose_lead`, `_choose_discard`, `choose_card`, `_is_sure_winner`, `observe_play` (the actual decision logic) | Docstrings, comments, log lines, type hints |
| New class attributes, feature flags, helper methods that change behavior | Reformatting, ruff cleanups, import reordering |
| Changes to `card_value_for_dump` ordering or `rank_strength` calls | Test-only fixtures |
| Changes to feature-flag defaults (because production behavior shifts) | Dead-code removal |
| Renames of helper methods that are only called internally | New helper methods that are *added but not yet called* |

The discipline is **enforced socially**, not by tooling. The PR description
must include a `## Strategy Version` section (see §1.4) that states the
old version, the new version, and a one-line justification. The reviewer
checks that the bump category matches the actual change.

> **Why no source-hash auto-bump?** A behavioral source-hash (e.g.,
> `hashlib.sha256` over the AST of the decision-logic functions) was
> considered. It is rejected for the MVP because:
>
> 1. It would auto-bump on cosmetic refactors that do not change behavior,
>    creating noise cohorts.
> 2. It would NOT bump on a `_void_suits_by_seat = {0:set(), ...}` →
>    `_void_suits_by_seat = defaultdict(set)` refactor that **does** change
>    semantics in subtle edge cases.
> 3. It would conflict with the social-discipline reviewer check that the
>    bump category matches the change.
>
> A future evolution could pair manual bumps with a CI lint that **fails**
> any PR touching `greedy.py`'s decision functions without bumping
> `GLUTTON_STRATEGY_VERSION`. That is in §2.6 (Future Research Methodology).

### Backfill: how to handle the existing 7 unversioned edits

The cleanest answer is also the cheapest: **call the current state v0.7.0
and start fresh**. Concretely:

- The constant lands on the next merge to `greedy.py` after this plan.
  That merge is **Cash-A**.
- Cash-A bumps `GLUTTON_STRATEGY_VERSION` from `"0.7.0"` (the constant
  introduced by the versioning PR itself) to `"0.8.0"` as part of its diff.
- All hosted-play hands recorded **after** the versioning PR deploys are
  stamped with the actual version that produced them.
- All hosted-play hands recorded **before** the versioning PR deploys
  carry `Match.play_strategy_version = NULL`. The migration sets the
  column nullable; any analysis that needs cohort boundaries on
  pre-versioning data must reconstruct them via `Match.created_at` +
  git deploy log (out of scope for the MVP — see deferred work register
  §2.8).

> **Why not retroactively backfill `0.1.0` … `0.7.0`?** It would require
> mapping each pre-versioning `Match.created_at` to a deploy timestamp,
> which assumes one deploy per behavioral PR. The pilot has had bursty
> deploys (multiple PRs in a single Render redeploy window), so the
> mapping is not 1-to-1. The `NULL` cohort marker is honest; a
> reconstructed-but-wrong version label would silently corrupt future
> analysis. (Operator preference confirmed via the "be diligent" directive.)

### File scope for the constant

Single file: `src/bid_euchre/strategy/greedy.py`. No imports cross
`web/`. The constant is read from `greedy.py` by name from
`web/routes.py` (or via `type(play_strategy).VERSION` as noted above) —
either is fine; the latter is preferred because it polymorphs to the
isolated twin without an extra import.

## 1.2 Hosted DB schema change — `Match.play_strategy_version`

### Why Match (not Hand or Decision)

The play strategy is bound to a `MatchEngine` instance at match
construction (`web/routes.py:_build_engine`, lines 111–123). Within a
single match the version cannot change — the engine holds one
`play_strategy` deepcopy for the entire match's lifetime. So the natural
column granularity is **per-match**, not per-hand and not per-decision.

| Column granularity | Cost | Benefit |
|--------------------|------|---------|
| Per-match (`matches.play_strategy_version`) | 1 column add, 1 write per match | Captures exactly what the engine had |
| Per-hand (`hands.play_strategy_version`) | 1 column add, 10x writes per match | No new info — version is constant within a match |
| Per-decision (`decisions.play_strategy_version`) | 1 column add, ~30–50x writes per hand | No new info, plus bloats the densest table |
| Reuse `decisions.decision_source` | 0 schema, but invasive parsing | Makes `decision_source` ambiguous |

Per-match is the right answer.

### Schema change

```sql
-- web/schema.sql additions (informative; the canonical migration runs in
-- web/app.py via the existing ALTER TABLE pattern)
ALTER TABLE matches ADD COLUMN play_strategy_version TEXT;
```

`web/db.py` Match model gains:

```python
class Match(Base):
    __tablename__ = "matches"
    ...
    play_strategy_version = Column(String, nullable=True)  # NULL for pre-versioning rows
```

The column is **nullable** so the rolling migration leaves pre-versioning
rows as `NULL` (the honest "unknown cohort" marker — see §1.1 backfill
discussion).

### Migration plan — reuse the existing in-process pattern

`web/app.py` lifespan handler at lines 118–139 already implements the
exact migration shape we need for the `onboarding_complete` column. We
copy the pattern verbatim:

```python
# web/app.py — inside lifespan(), immediately after the existing
# onboarding_complete migration block.

match_cols = {c["name"] for c in inspector.get_columns("matches")}
if "play_strategy_version" not in match_cols:
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE matches "
                "ADD COLUMN play_strategy_version TEXT"
            )
        )
    logger.info("Migration: added play_strategy_version column to matches")
```

**Why no Alembic?** Alembic is not currently used by `web/`. The
in-process `ALTER TABLE` pattern has shipped twice without incident
(`onboarding_complete`, and the invite-codes table via `create_all`).
Introducing Alembic for one column is not justified for the MVP and
would expand scope significantly. (See §2.8 deferred work register —
the future-research section captures Alembic adoption as a deferred
nice-to-have, not a blocker.)

**SQLite vs. Postgres:** The vanilla `ALTER TABLE matches ADD COLUMN
play_strategy_version TEXT` syntax is supported by both SQLite (since 3.2)
and Postgres without modification. The existing `onboarding_complete`
migration uses the same syntax and runs on both.

**Idempotency:** The `inspector.get_columns(...)` check ensures the
ALTER runs at most once per database. Safe to re-run on every startup.

**Rollback:** SQLite cannot drop columns without rebuilding the table.
Rollback strategy is to leave the column in place and ignore it from the
read path (the column is nullable so it costs nothing if unused). Postgres
supports `ALTER TABLE matches DROP COLUMN play_strategy_version` if a
true rollback is ever needed.

## 1.3 Logging hook — where the version is read at runtime

### Single insertion point

`web/routes.py` is where `Match` rows are created. The match-create code
path goes through:

1. User calls `POST /matches` (or equivalent route — see
   `_create_match` in `web/routes.py`).
2. Route handler builds the engine via `_build_engine(ai_manager, model_id)`.
3. Route handler constructs a `Match` ORM row and persists.

The version read happens at step 2 (we have the engine in hand) or
step 3 (we have the model_id in hand). The cleanest insertion point is
**step 3, immediately before `db.add(match)`**:

```python
# web/routes.py — inside _create_match() (or wherever the Match row is
# constructed). Today the relevant lines are around match construction;
# the precise line numbers will be confirmed by the implementer.

engine = _build_engine(ai_manager, model_id)
play_strategy_version = type(engine.play_strategy).VERSION  # NEW

match = Match(
    match_uuid=match_uuid,
    player_id=player.id,
    ai_model=model_id,
    play_strategy_version=play_strategy_version,  # NEW
    status="active",
    seed=seed,
    ...
    match_state_json=match_state_json,
)
db.add(match)
```

The `type(engine.play_strategy).VERSION` form polymorphs naturally to
both `GluttonStrategy` and `GluttonIsolatedStrategy` and any future
subclasses. If the strategy class lacks a `VERSION` attribute (e.g., a
non-Glutton strategy in the future), the read raises `AttributeError`,
which fail-loud-loud is the right behavior — better than silently
recording `NULL`.

### Decision-level recording (NOT in MVP scope)

The `Decision.decision_source` field is currently set to `ai_model`
(`web/routes.py:2635`) for AI plays. We **do not** modify this field in
the MVP. If a future investigation needs per-decision version
attribution, it can:

1. Switch to a structured format like `f"{ai_model}@{play_strategy_version}"`,
   or
2. Add a new `decisions.play_strategy_version` column (rejected above as
   redundant).

This is documented in §2.8 (deferred work register) for the future-research
phase.

### MatchEngine instrumentation (NOT in MVP scope)

`MatchEngine` itself does not currently emit any per-decision provenance
hook. Adding one would be wider scope (touching `engine.py`, `hooks.py`,
the post-merge hook contract). The MVP keeps the entire change inside
`web/routes.py` + `web/db.py` + `web/app.py` + `src/bid_euchre/strategy/greedy.py`.

## 1.4 PR changelog convention

Every PR that touches `src/bid_euchre/strategy/greedy.py`'s decision
logic must include a `## Strategy Version` section in the PR description
with the following shape:

```markdown
## Strategy Version

| Field | Value |
|-------|-------|
| Old version | `0.7.0` |
| New version | `0.8.0` |
| Bump category | MINOR (added sure-winner-lead priority) |
| Behavior delta | <one paragraph: what plays change, in what game states, by how much> |
| Affected functions | `_choose_lead`, `choose_card` |
| Unaffected functions | `_is_sure_winner` (helper, no signature change) |
```

This block is the only durable record outside the git history of *what
changed*. It feeds the post-merge review hook (which can grep PR bodies
for `## Strategy Version` sections) and the future ablation methodology
(§2.6) which uses these blocks to label cohorts in retrospective analysis.

The convention is enforced socially in code review for the MVP. A CI
lint that fails any PR touching `greedy.py`'s decision functions without
a `## Strategy Version` block is a §2.6 future enhancement.

### Where the convention is documented

A new short doc lives at:

```
docs/02_agent/STRATEGY_VERSIONING.md
```

Contents (≤ 50 lines):

1. Why the version exists (one paragraph + link back to this plan).
2. The semver rules from §1.1.
3. The PR template snippet from §1.4.
4. Which files trigger a bump (just `greedy.py` for now; expand later
   to other strategies as they get versioned).
5. Pointer to `web/db.py` and `web/routes.py` for the DB capture path.

This doc is created as part of **PR-1** (versioning constant + DB column).
It is the canonical reference for future Cash-* and Glutton* PRs.

## 1.5 PR decomposition — minimum-PR path to unblock Cash-A

The MVP ships in **two PRs**, sequenced. Both should land **before**
Cash-A is dispatched.

### PR-1: Versioning infrastructure

**Title:** `feat(strategy): add GLUTTON_STRATEGY_VERSION + per-match capture in hosted DB`

**Scope (`scope_declared`):**
- `src/bid_euchre/strategy/greedy.py` — add `GLUTTON_STRATEGY_VERSION` constant, set it to `"0.7.0"`, add `VERSION` class attr to both Glutton classes
- `web/schema.sql` — informative addition of the `play_strategy_version` column to the `matches` table
- `web/db.py` — add `play_strategy_version` to the `Match` ORM model (nullable)
- `web/app.py` — add the in-process `ALTER TABLE ... ADD COLUMN` block, modeled after the existing `onboarding_complete` migration at lines 118–139
- `web/routes.py` — read `type(engine.play_strategy).VERSION` and stamp `Match.play_strategy_version` at match-create time
- `tests/unit/hosted_play/test_db.py` — assert `Match.play_strategy_version` round-trips through the ORM
- `tests/unit/hosted_play/test_app.py` — assert the migration is idempotent on a fresh DB and on a pre-existing DB
- `tests/integration/hosted_play/test_data_capture.py` — assert a freshly created match records the current `GLUTTON_STRATEGY_VERSION`
- `docs/02_agent/STRATEGY_VERSIONING.md` — new doc (≤ 50 lines per §1.4)

**Validation (PR template fields):**
- `make check-gated`
- Targeted: `uv run python -m pytest tests/unit/hosted_play/ tests/integration/hosted_play/test_data_capture.py -x`
- Manual: spin up `make web` locally, create a match, assert
  `select play_strategy_version from matches order by id desc limit 1` returns `'0.7.0'`

**Behavior bump:** **none.** PR-1 touches only the constant declaration
+ the data-capture wiring; it does not change which card is played in
any state. `GLUTTON_STRATEGY_VERSION` is set to `"0.7.0"` because that
is the version of the file *before* PR-1 lands (i.e., the version that
captures the seven 2026-03-19 → 2026-04-05 edits as one cohort). PR-1
does **not** itself bump the version — it labels the existing state.

### PR-2: Cash-A (existing plan, now unblocked)

**Title:** `fix(strategy): cash sure winners + draw trump first + draw trump high (Cash-A)`

**Scope (unchanged from `plans/sessions/2026-04-06_ai_play_strategy_investigation.md` §Recommended PR Decomposition):**
- `src/bid_euchre/strategy/greedy.py` — Fix 1, Fix 1b, Fix 2 behind the
  `cash_winners_on_lead` flag, **plus** bump
  `GLUTTON_STRATEGY_VERSION` from `"0.7.0"` to `"0.8.0"`
- `tests/unit/test_greedy.py` — new behavior tests
- (Optional, per Cash-A plan) `experiments/configs/glutton_cash_winners_paired.yaml`

**Behavior bump:** MINOR (`0.7.0` → `0.8.0`). Two new lead priorities
introduced; one existing priority's tie-break direction reversed.

**PR description:** must include the `## Strategy Version` block per §1.4
with bump category MINOR.

**Depends on:** PR-1 merged. (Otherwise the live DB has no column to
record the bumped version.)

### PR-3 onward (future)

Cash-B (sure-winner follow + 2nd-hand-low fallback) bumps to `"0.8.1"` —
PATCH because it changes one branch of the follow path with a tightly
scoped condition. GluttonV2 (when it ships) bumps to `"0.9.0"` or
`"1.0.0"` depending on whether `on_hand_start` signature changes
(MAJOR if yes).

## 1.6 Validation summary

| Layer | Command | Pass criteria |
|-------|---------|---------------|
| Lint | `make lint` | clean |
| Unit (impacted) | `uv run python -m pytest tests/unit/hosted_play/ tests/unit/test_greedy.py -x` | all green |
| Tier 2 | `make check-gated` | all green |
| Migration idempotency | New test in `test_app.py`: run lifespan twice on the same SQLite file, assert no error and one column | green |
| Round-trip | New test in `test_db.py`: create Match with `play_strategy_version="0.7.0"`, fetch, assert equality | green |
| Manual smoke (post-deploy) | Create one match in the hosted app, query `matches.play_strategy_version` | returns `'0.7.0'` |

## 1.7 Acceptance criteria (PR-1)

1. `GLUTTON_STRATEGY_VERSION = "0.7.0"` exists in
   `src/bid_euchre/strategy/greedy.py` and is exposed as `VERSION` on
   both `GluttonStrategy` and `GluttonIsolatedStrategy`.
2. `matches.play_strategy_version` column exists in `web/schema.sql`,
   the ORM model, and is migrated in by `web/app.py` lifespan on existing
   databases.
3. Every new `Match` row created via the hosted-app match-create route
   has `play_strategy_version = '0.7.0'` (the value of
   `type(engine.play_strategy).VERSION` at the time of construction).
4. All existing `Match` rows have `play_strategy_version = NULL` (the
   honest "unknown cohort" marker per §1.1 backfill).
5. `make check-gated` passes.
6. `docs/02_agent/STRATEGY_VERSIONING.md` exists with the §1.1 semver
   rules + the §1.4 PR template snippet.
7. Manual smoke: starting a match in `make web` and querying the DB
   returns `play_strategy_version = '0.7.0'` for the new row.

## 1.8 MVP Risk register

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `type(play_strategy).VERSION` raises `AttributeError` because a future strategy class forgets the attribute | LOW | Documented in `docs/02_agent/STRATEGY_VERSIONING.md`. Fail-loud is correct — silently recording `NULL` for new strategies would be worse. |
| Render redeploy runs the migration on Postgres before the new code reaches all instances | LOW | The migration is `IF NOT EXISTS`-equivalent (we check via `inspector.get_columns` first). Mid-deploy reads from older instance pods see `Match.play_strategy_version` not exist on the model and ignore it. |
| Pre-versioning rows have `NULL` and confuse retrospective analysis | LOW (by design) | `NULL` is the honest marker. §2 ablation methodology reads this as "unknown cohort, exclude from per-version comparison." |
| Operator misses the §1.4 changelog block on a future PR | MEDIUM | Documented in `docs/02_agent/STRATEGY_VERSIONING.md` and included in the PR template. Reviewer responsibility until §2.6 lint exists. |
| `_build_engine` gets a non-Glutton strategy and `VERSION` is wrong type | LOW | `play_strategy_version` is a `String` column; any non-string raises a SQLAlchemy `StatementError` at insert time. Fail-fast. |
| Cash-A author lane forgets to bump the constant | MEDIUM | PR-1 adds the §1.4 doc *and* the §1.4 PR template snippet. The reviewing-changes hook can be enhanced to grep for `GLUTTON_STRATEGY_VERSION = ` in any diff that touches `greedy.py`'s decision functions (this is a §2.6 future enhancement). For now: dispatch packet for Cash-A explicitly cites the bump in `scope_declared`. |
| SQLite + Postgres syntax divergence on `ALTER TABLE` | LOW | Vanilla `ALTER TABLE … ADD COLUMN` works on both. The existing `onboarding_complete` migration is precedent. |
| `web/routes.py` has multiple match-create paths and we miss one | MEDIUM | A grep for `Match(` in `web/routes.py` enumerates all construction sites. PR-1 must wire `play_strategy_version` at every site or refactor to a single helper. |

---

# Section 2 — Future Research Methodology (DEFERRED)

> **Status:** Captured here so future-us can resume the ablation framework
> work without re-deriving the design. Do **not** build this now.
> Operator's "Optimize for shortest path to shipping Cash-A" directive
> (2026-04-06) defers everything in this section.

## 2.1 Goals of the ablation framework

When we revisit research-quality model retraining, we will need to answer:

1. Did Cash-A's behavioral changes improve play quality vs. v0.7.0?
2. Did Cash-B's follow-phase changes improve play quality vs. v0.8.0?
3. Does GluttonV2's bid-aware logic improve over v0.8.x?
4. For any future version v0.N+1, is the change a **strict improvement**
   (no scenario regresses), an **average improvement** (some scenarios
   regress but mean is positive), or a **trade-off** (clear winners and
   losers across scenarios)?

The framework must be:

- **Reproducible** — seed-bound, deterministic, runnable by any future
  agent from a single command.
- **Statistically sound** — paired bootstrap CI on matched deals, not
  visual inspection or independent-sample t-tests.
- **Cheap to invoke** — single config file, single CLI invocation,
  output committed to the repo as a tracked artifact.

## 2.2 Paired H2H matrix on matched deals (reuse the prior plan)

The mechanics are already designed in the prior plan:
`plans/sessions/2026-04-06_ai_play_strategy_investigation.md` §Validation
Commands and §Acceptance Criteria item 4. The summary:

- **Mode:** `mode: self_play` (the default in `experiments/run_experiment.py`)
  with `pair_deals: true` so both strategies see the same physical deals.
- **Two strategies** declared in the same config — `glutton_baseline_v0_7_0`
  (GluttonIsolatedStrategy with both feature flags off) and
  `glutton_candidate_v0_8_0` (both flags on).
- **Six scenarios** — high, low, suit×{H,D,C,S} — at 50,000 deals each
  for the production gate; 2,000 for the smoke variant.
- **Output shape:** one JSONL per strategy under
  `data/runs/<run_id>/logs/<run_id>_<strategy_name>.jsonl`. The
  per-strategy output naming is the path that
  `src/bid_euchre/analysis/paired.py::load_paired_data` requires.
- **Why not `mode: head_to_head_matrix`:** that mode emits a single JSONL
  per matchup with `strategy_id=matchup_id`, collapsing both sides into
  one log. `load_paired_data` would not be able to glob per-strategy.

## 2.3 Statistical acceptance gates

`src/bid_euchre/analysis/paired.py::compute_paired_deltas` returns a
dict with key `deltas` (a `list[float]`, **not** a NumPy array — this
trip-up cost the prior investigation half a session). The bootstrap CI
is computed via `src/bid_euchre/analysis/stats.py::bootstrap_ci(data,
statistic=np.mean, n_bootstrap=10000, seed=42)`.

The acceptance gate has two layers:

1. **Pooled gate:** the 95% bootstrap CI lower bound of the pooled
   per-deal delta must satisfy `lo >= 0`. (The candidate strategy must
   not lose tricks per matched deal in expectation.)
2. **Per-scenario gate:** at least 5 of 6 scenarios independently pass
   the same `lo >= 0` test. (No single scenario regresses materially.)

The exact runnable form of both gates is documented in the prior plan
at lines 1206–1258 of
`plans/sessions/2026-04-06_ai_play_strategy_investigation.md`. That
block is the source of truth — copy-paste it directly when resuming.

> **Anti-pattern reminders** (also from the prior plan):
> - **Do not use `scripts/compare_runs.py`** — it compares two
>   independently-sampled runs on bootstrap distributions of summary
>   statistics, **not** per-deal paired deltas.
> - **Do not use `paired_t_ci`** — it is a t-distribution interval, not
>   a bootstrap, and does not match the gate language.
> - **Do not use `mode: head_to_head_matrix`** — it collapses both
>   strategies into one JSONL.

## 2.4 Standard config template

When the framework is built, the canonical config lives at:

```
experiments/configs/glutton_ablation_<from>_vs_<to>.yaml
```

With the shape:

```yaml
experiment_name: glutton_ablation_v0_7_0_vs_v0_8_0
mode: self_play
parameters:
  seed: 42
  n_per: 50000
  pair_deals: true
strategies:
  - name: glutton_v0_7_0
    class_name: GluttonIsolatedStrategy
    params:
      cash_winners_on_lead: false
      cash_winners_on_follow: false
  - name: glutton_v0_8_0
    class_name: GluttonIsolatedStrategy
    params:
      cash_winners_on_lead: true
      cash_winners_on_follow: false
scenarios:
  - { contract_type: high }
  - { contract_type: low }
  - { contract_type: suit, trump_suit: H }
  - { contract_type: suit, trump_suit: D }
  - { contract_type: suit, trump_suit: C }
  - { contract_type: suit, trump_suit: S }
```

The naming convention is `glutton_ablation_<from-version>_vs_<to-version>.yaml`
where versions match `GLUTTON_STRATEGY_VERSION` strings. One config per
ablation comparison; commits are reproducible because the config + the
seed + the pinned `GluttonIsolatedStrategy` flags fully describe the run.

The runner emits one JSONL per strategy named after `policy.name` (see
`experiments/run_experiment.py:1031`), which produces the
`<run_id>_<strategy_name>.jsonl` shape that `load_paired_data` requires.
No code changes to the runner are needed.

## 2.5 Where ablation results live

Recommendation (when the framework lands):

- **Run output:** `data/runs/<run_id>/...` (gitignored, per
  `docs/01_core/DATA_CONTRACT.md`).
- **Decision artifact:** `data/reports/glutton_ablations/glutton_ablation_<from>_vs_<to>.json`
  containing the pooled CI, per-scenario CIs, n_matched, seed, run_id,
  pass/fail flags. This is the ONE committed file per ablation.
- **Narrative report:** `plans/sessions/<date>_glutton_ablation_<from>_vs_<to>.md`
  embedding the actual numbers (per the notebook boundary rule in
  `.claude/rules/deferred/45_notebook_boundary.md` — the report must
  cite the committed JSON, not "see notebook").

> **Why not a new top-level docs/ section?** The existing
> `plans/sessions/` and `data/reports/` shapes already serve this. Adding
> a new directory would create a sixth place to look for evaluation
> artifacts. The `glutton_ablations/` subdirectory under `data/reports/`
> is the minimum new convention.

## 2.6 Future enhancement — CI lint enforcing the version bump

A `scripts/internal/lint_strategy_version.py` (or a hook in
`scripts/internal/review_driver.py`) can implement:

1. Detect any PR that modifies one of the decision-logic functions in
   `greedy.py` (`_choose_lead`, `_choose_discard`, `choose_card`,
   `_is_sure_winner`, `observe_play`, `on_hand_start`).
2. Detect whether `GLUTTON_STRATEGY_VERSION` is also modified in the
   same diff.
3. Detect whether the PR description contains a `## Strategy Version`
   block per §1.4.
4. **Block** the PR (BLOCK severity per `.claude/rules/deferred/60_review_gate.md`)
   if (1) is true and (2) is false.
5. **Warn** the PR (WARN severity, follow-up issue) if (1) is true and
   (3) is false.

This is a §2 deferred enhancement because:
- The MVP relies on social discipline + reviewer attention, which is
  acceptable for a 2-author cadence.
- The lint requires identifying which functions are "decision logic" —
  a list that grows as new strategies get versioned. The MVP punts this
  to a hand-written list in `STRATEGY_VERSIONING.md`; the lint would
  formalize the list as a constant in the script.
- Adding the lint to the pre-commit hook chain (`.claude/hooks/`) is
  cross-cutting work that should happen alongside other review-gate
  enhancements, not as part of the versioning landing.

## 2.7 Cross-cutting concerns

### Notebook reproducibility

`notebooks/` contains analysis notebooks that load JSONL logs and
compute metrics. None of them currently filter by
`Match.play_strategy_version` because the column does not exist. After
PR-1 lands:

- New analysis notebooks targeting hosted-play data should include a
  cohort filter at the top of the loader cell:
  `df = df[df['play_strategy_version'].notna() &
  (df['play_strategy_version'] >= '0.8.0')]` or similar.
- Existing notebooks that read research data (`data/runs/...`) are
  unaffected — the research path is versioned by `meta.json:git_sha`.

This is documented in `docs/02_agent/STRATEGY_VERSIONING.md` (PR-1
deliverable) and is **not** a notebook code change in the MVP.

### Promotion pipeline

The promotion pipeline (`src/bid_euchre/validation/arc_d_gate.py`,
`arc_d_bundle.py`) operates on bidder artifacts, not play strategies.
It is **unaffected** by the play-strategy versioning. The Arc D rung
bundle schema (`arc_d_rung_bundle_v1`) does not need a
`play_strategy_version` field because rungs are about the bidder.

If a future research direction couples the play strategy to the bidder
training pipeline (e.g., training a bidder against a specific play
version), that future work would extend the rung bundle schema. Out of
scope for the MVP.

### Post-merge review

The post-merge review hook (`post-merge-review.sh`) runs an Explore
agent on every merged PR. After PR-1 lands, the hook prompt could be
extended to **specifically check** that PRs touching `greedy.py`
include the §1.4 changelog block. This is a §2.6 enhancement, not a
PR-1 deliverable.

### Hosted-play export

`web/export.py` (`export_decisions` CLI) emits JSONL of all hosted-play
decisions for downstream analysis. After PR-1, the exporter should
**include `match.play_strategy_version`** in its output records. This
is a one-line change in the SELECT projection inside `web/export.py`
and could either:

- **Land as part of PR-1** (recommended — it is the read-side companion
  to the write-side change, and `tests/unit/hosted_play/test_export.py`
  is already in scope).
- **Land as a §2 deferred follow-up.**

The MVP recommendation is to **include the export change in PR-1** because
the entire round-trip (write column → read column → export column) is
the verifiable acceptance criterion. Splitting it across PRs would leave
PR-1 in a state where the column is written but invisible to downstream
analysis until PR-1.5 lands.

> **Scope adjustment:** This adds `web/export.py` and
> `tests/unit/hosted_play/test_export.py` to PR-1's `scope_declared`.
> See §1.5 PR decomposition for the updated file list.

## 2.8 Deferred work register

When future-us resumes the research methodology track, these are the
work items captured here so they don't have to be re-derived:

| # | Item | Reason deferred | Source |
|---|------|----------------|--------|
| D1 | Build the ablation harness CLI (`scripts/run_ablation.py` wrapping the §2.4 config + §2.3 gates) | MVP narrowed by orchestrator 2026-04-06 to shipping Cash-A. | §2.4 |
| D2 | Backfill `Match.play_strategy_version` for pre-versioning rows via deploy-timestamp reconstruction | Brittle (multi-PR deploys), and the `NULL` cohort marker is honest. | §1.1 backfill |
| D3 | CI lint enforcing `GLUTTON_STRATEGY_VERSION` bump on decision-logic edits | Social discipline acceptable for current cadence; lint is cross-cutting. | §2.6 |
| D4 | Per-decision version recording via `decisions.play_strategy_version` or structured `decision_source` | Per-match granularity is sufficient because the engine binds one strategy per match. | §1.3 |
| D5 | Adopt Alembic for hosted-play schema migrations | In-process `ALTER TABLE` pattern is shipping; one-column migration does not justify the dependency. | §1.2 |
| D6 | Extend `arc_d_rung_bundle_v1` schema with a `play_strategy_version` field | Promotion pipeline is bidder-side only; no current need. | §2.7 promotion |
| D7 | Post-merge review prompt enhancement to check for `## Strategy Version` block on `greedy.py` PRs | Cross-cutting with other review-gate enhancements; lint precedes prompt. | §2.7 post-merge |
| D8 | Notebook cohort-filter helper module (`bid_euchre.analysis.cohorts`) | No current notebook needs hosted-play cohort filtering. | §2.7 notebook |
| D9 | First retrospective ablation run (v0.7.0 vs v0.8.0) once Cash-A merges | Requires Cash-A landed AND the harness from D1. | §2.1 goal 1 |
| D10 | Standard report template for `plans/sessions/<date>_glutton_ablation_*.md` | One-time when D9 runs. | §2.5 |

---

## Outcome

*(To be filled after PR-1 merges.)*

## References

### Repository code
- `src/bid_euchre/strategy/greedy.py` — target of versioning constant
- `web/ai_manager.py:141,177` — strategy instantiation sites
- `web/routes.py:_build_engine` (lines 111–123) — per-match engine construction
- `web/routes.py:2635` — `decision_source = ai_model` (read-side, not modified by MVP)
- `web/db.py:Match` — target of new `play_strategy_version` column
- `web/schema.sql` — informative schema
- `web/app.py` lifespan (lines 118–139) — existing migration pattern (template)
- `experiments/run_experiment.py:1192–1196` — existing `git_sha` provenance
- `src/bid_euchre/__init__.py:8` — package `__version__ = "0.1.0"` (precedent)

### Prior work
- `plans/sessions/2026-04-06_ai_play_strategy_investigation.md` — Cash-A
  fix design (the work this versioning unblocks)
- `plans/sessions/2026-03-27_glutton-strategy-revamp-experiment-design.md` —
  GluttonV2 bid-aware plan (downstream consumer)
- PR #2168 — `MatchEngine` deepcopy fix (the per-match isolation that
  makes per-match versioning correct)
- `docs/01_core/DATA_CONTRACT.md` — JSONL log schema (research path)
- `docs/01_core/REPRODUCIBILITY.md` — `meta.json` schema (research path)
- `.claude/rules/deferred/30_data_contract.md` — output policy
- `.claude/rules/deferred/45_notebook_boundary.md` — committed-evidence rule
- `.claude/rules/deferred/55_issue_closure.md` — Tier 2 verified-close

### Issues
- #2519 — operator request for diligent versioning + ablation framework
- #2502, #2504, #2506 — the play-strategy bugs Cash-A fixes (cohort
  boundary motivation)
- #2300, #2167, #2139, #2133, #2098, #2201, #2396 — the seven unversioned
  edits since Arc D v2 finalization

## Orchestrator Handoff

**Dispatch recommendation:** dispatch **PR-1** (versioning infrastructure)
to a single author lane (author-a or author-b) immediately. PR-1 is a
~150 LoC change with clear scope and tight validation. ETA: ~1.5 hours.

**Required execution sequence (`AGENTS.md §12.4` / Implementation Handoff
Protocol):** the receiving author lane must, in order:

1. Refresh this plan plus the prior Cash-A plan
   (`plans/sessions/2026-04-06_ai_play_strategy_investigation.md`).
2. Draft a concrete execution plan inline in the task packet (file list,
   exact diffs against `web/db.py`, `web/app.py`, `web/routes.py`,
   `web/export.py`, `src/bid_euchre/strategy/greedy.py`, plus the new
   `docs/02_agent/STRATEGY_VERSIONING.md`).
3. Spawn at least one reviewer agent to review the execution plan before
   editing `web/routes.py` (the densest file in scope).
4. Create a TUI task list covering the column add, the migration, the
   route wiring, the export wiring, the unit tests, the integration test,
   the doc, and `make check-gated`.
5. Assess parallelism — the schema/model edits, the migration block, the
   route wiring, and the export wiring are all on disjoint code regions
   and can be implemented in any order; the tests must wait for the
   wiring. The doc can land in parallel with everything else.
6. Execute end to end: implement → unit tests → `make check-gated` →
   commit → open PR with the `## Strategy Version` block per §1.4 →
   include validation evidence in the PR body.

**Cash-A dispatch is BLOCKED until PR-1 merges.** After PR-1 lands, dispatch
Cash-A as already specified in
`plans/sessions/2026-04-06_ai_play_strategy_investigation.md` §Orchestrator
Handoff, with the additional explicit instruction in the task packet:

> "Bump `GLUTTON_STRATEGY_VERSION` from `'0.7.0'` to `'0.8.0'` as part of
> this PR. Include a `## Strategy Version` block in the PR description per
> `docs/02_agent/STRATEGY_VERSIONING.md`."

**Do not dispatch** the Section 2 Future Research Methodology work until
the operator explicitly opens that track. The deferred work register
(§2.8) is the resumption point.
