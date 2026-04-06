# Overnight Run Plan — UI/UX Polish + Glutton Revamp (2026-04-06)

> **Task packet:** `2ae0d0c421f1`
> **Drafted by:** analyst-a (investigation + shaping only, no dispatch)
> **Status:** PROPOSAL — awaiting operator approval before orchestrator dispatches any wave
> **Delivery mode:** PR (durable plan artifact)

---

## 0. Operator constraints (verbatim, non-negotiable)

1. "triage ui/ux issues and the glutton revamp for an overnight run"
2. "Do not perform any new research but ship as many improvements as you can"
3. "Dont deploy on render, do test locally via playwright"
4. "All ui/ux improvements must be approved by user proving run in the am before shipping"
5. "Propose overnight run here before dispatching"
6. "If there are easy win issues that can be dispatched alongside this work, triage those from the issues list"

### What the constraints mean in practice

| Constraint | Overnight implication |
|---|---|
| No new research | **Cash-A rescoped.** Drop the paired H2H self-play bootstrap gate. Keep unit tests + `make check-gated` + local Playwright smoke of a real match. Research-flavored #2521 item 1 is deferred. No new experiment runs. No ablation. No notebooks. |
| Ship as much as possible | Parallelize across 12 author/flex lanes where scopes are disjoint. Open PRs even when they must wait for AM proving — the operator wants to wake up to ready-for-review PRs, not empty branches. |
| No Render deploy | Every PR validated locally: `make check-gated` + `make web` smoke + Playwright smoke for UI-affecting changes. No `render` CLI anywhere. No touching `render.yaml`. |
| Track B needs AM proving | **Track B PRs must not auto-merge.** They open, CI runs, review coordinator runs, verdict lands — and then the PR waits in "ready for review" state until the operator manually merges each one in the AM after visual/gameplay verification. |
| Propose first | This doc. Orchestrator must not dispatch any wave until the operator signs off on the plan. |
| Easy wins | Track C exists. Scoped narrowly — convention follow-ups + safe docs/config changes, all auto-mergeable because they don't touch rendered UI or live AI behavior. |

---

## 1. Fleet state reconciliation (discovered during shaping)

Before any new dispatch, the orchestrator must reconcile existing lane state.
Eight worktrees have unpushed commits or stale branches. Half are rescue
opportunities (shipped work that never opened a PR). Half are stale branches
for already-closed issues (must be reset).

### 1.1 Wave 0-A — Rescue branches (ship shipped-but-unpushed work)

All four `brws-author` lanes have completed implementations of 2026-04-05
Wave 1 P0 items that **never opened PRs**. Push + open PR immediately.
These are Track B (UI/UX) — **NO auto-merge, wait for AM proving.**

| Lane | Branch | Commits ahead | Issue | Title |
|---|---|---|---|---|
| brws-author-a | `fix/web-black-suit-icons-cards-played` | 1 | **#2505** | Cards Played log: black suit icons invisible |
| brws-author-b | `fix/web-duplicate-auction-bid-log` | 1 | **#2508** | Duplicate auction bid log |
| brws-author-c | `fix/web-auction-next-autoadvance-guard` | 2 | **#2503** | Auction auto-advance guard |
| brws-author-d | `fix/remove-hand-details-dropdown` | 1 | **#2509** | Remove Hand Details dropdown |

**Action per lane:** `git fetch origin main && git rebase origin/main && make check-gated && git push -u origin HEAD && gh pr create --draft=false ... ` The PRs should **not** be marked draft (we want the review coordinator to run) but the task packet instruction must include "do not run `gh pr merge` — operator will merge manually in the AM after proving."

### 1.2 Wave 0-B — Reset stale platform lanes

Four platform `author*` lanes hold branches that target **already-closed** issues.
These are duplicates of shipped work (the issue closed on another PR) and the
local branches are dead code. Reset them so they can take new overnight work.

| Lane | Stale branch | Closed issue | Recovery |
|---|---|---|---|
| author   | `fix/remove-help-bar`             | #2454 CLOSED | Discard branch, `git checkout main`, pull |
| author-b | `fix/match-result-stale-2446`     | #2446 CLOSED | Discard branch, `git checkout main`, pull |
| author-c | `fix/trick-10-skip-to-endgame-2210`| #2210 CLOSED | Discard branch, `git checkout main`, pull |
| author-d | `feat/dedication-page`            | #2455 CLOSED | No commits ahead (just stale untracked files), checkout main + ignore the untracked artifacts |

**Reset protocol (per lane):**
```bash
git worktree list                           # verify path
git status --porcelain                      # should be empty (any untracked files are fleet debris, ignore)
git fetch origin main
# If the branch has unique commits unrelated to the closed issue, STOP and escalate.
# If the commits are duplicates of the closed PR's work, discard:
git checkout main
git pull
git branch -D <stale-branch>
```

`git worktree remove` must NOT be run — all four of these lanes are protected
per `.claude/rules/75_worktree_protection.md`.

### 1.3 Wave 0-C — flex-a screenshots cleanup

`flex-a` has uncommitted Playwright screenshots from a prior playtest
(`checklist-01-landing.png`, etc.). Not a branch issue, just debris. The lane
is effectively idle. Before dispatching new work: move the screenshots into
`/tmp` and check out `main`.

---

## 2. Track summary

| Track | Scope | Auto-merge | Lanes |
|---|---|---|---|
| **Track A — Glutton revamp** | Strategy versioning (PR-1) then Cash-A (behind flag) | PR-1 YES; Cash-A NO | author pool (platform) |
| **Track B — UI/UX polish** | Wave 0-A rescue + #2521 items 2/3/4 + #2288 items 1/2/3/5 | **NO** (AM proving required) | brws-author pool |
| **Track C — Easy wins** | Convention follow-ups + `.claude/settings.json` narrowing + doc updates | YES (where scope is single-file and non-UI) | flex pool |

Cash-B is **deferred** — see §8.

---

## 3. Wave structure + dependencies

```
Wave 0  (rescue + reset)       ─────────────┐
   │                                        │
   ├─ 0-A: 4× brws PR pushes (Track B)      │   ~15 min, all parallel
   ├─ 0-B: 4× platform lane reset           │   ~5 min, all parallel
   └─ 0-C: flex-a cleanup                   │
                                            │
Wave 1  (PR-1 versioning) ◄─────────────────┘
   │
   └─ author-a takes PR-1 (Track A, AUTO-MERGE)
      Blocks: Cash-A, #2520 rename
                                            │
Wave 2  (Cash-A + Track C)  ◄───────────────┘
   │
   ├─ author-a (after PR-1 merges) takes Cash-A (Track A, NO auto-merge)
   ├─ flex-b takes Track C convention batch (YES auto-merge)
   ├─ flex-c takes Track C #2304 Bash pattern narrow (YES auto-merge)
   └─ (parallel with Wave 3)
                                            │
Wave 3  (Track B polish, parallel with 2)   │
   │
   ├─ brws-author-a (after Wave 0-A merges its PR) takes #2521 items 2/3/4
   │     (NO auto-merge)
   └─ brws-author-b (after Wave 0-A merges its PR) takes #2288 items 1/2/3/5
         (NO auto-merge)
                                            │
Wave 4  (post-landing reports)  ◄───────────┘
   │
   └─ analyst-a drafts AM summary + risk notes
```

**Key ordering invariant:** Cash-A **cannot be dispatched until PR-1 is
merged** (the strategy version column must exist before Cash-A writes to it).
PR-1 is designed to be small and auto-mergeable, so the gate is operational,
not policy.

---

## 4. Per-wave, per-lane assignments

Each row below is a **packet-ready task description** the orchestrator can
drop into `scripts/internal/ops.py task create` with minimal editing.

### 4.1 Wave 0-A — Rescue ready-to-ship branches (Track B)

All four packets share this boilerplate:

> **Do not start fresh.** The branch already has the implementation. Your job:
> 1. `cd` into the lane's worktree and verify the branch is checked out.
> 2. `git fetch origin main && git rebase origin/main`
> 3. `make check-gated` (foreground, no background task).
> 4. `git push -u origin HEAD`
> 5. Open PR with `gh pr create`, cite the issue (`Refs #<N>` — not `Fixes`, this is Tier 2 per `.claude/rules/deferred/55_issue_closure.md`).
> 6. Include in the PR body: `> **Do not auto-merge.** Track B PR — waits for AM operator proving.`
> 7. Do NOT run `gh pr merge`. Report completion and stop.

| Packet | Lane | Branch | Issue | `scope_declared` |
|---|---|---|---|---|
| W0A-1 | brws-author-a | `fix/web-black-suit-icons-cards-played` | #2505 | `web/static/**`, `web/templates/**` |
| W0A-2 | brws-author-b | `fix/web-duplicate-auction-bid-log` | #2508 | `web/templates/**` |
| W0A-3 | brws-author-c | `fix/web-auction-next-autoadvance-guard` | #2503 | `web/templates/**`, `web/static/**`, possibly `web/routes.py` |
| W0A-4 | brws-author-d | `fix/remove-hand-details-dropdown` | #2509 | `web/templates/**` |

### 4.2 Wave 0-B — Reset stale lanes

| Packet | Lane | Action |
|---|---|---|
| W0B-1 | author   | Reset from `fix/remove-help-bar` (closed #2454). Verify commit is duplicate of shipped work, then `git checkout main && git pull && git branch -D fix/remove-help-bar`. |
| W0B-2 | author-b | Reset from `fix/match-result-stale-2446` (closed #2446). Same protocol. |
| W0B-3 | author-c | Reset from `fix/trick-10-skip-to-endgame-2210` (closed #2210). Same protocol. |
| W0B-4 | author-d | Reset from `feat/dedication-page` (closed #2455). No commits ahead, just `git checkout main && git pull` and move untracked files to `/tmp`. |

**If any reset finds unique non-duplicate commits, STOP and escalate** — do not
delete work. The orchestrator decides whether to rescue it into a new PR.

### 4.3 Wave 1 — PR-1: strategy versioning infrastructure (Track A, AUTO-MERGE)

**Packet W1-1 (author-a):**

- **Title:** `feat(strategy): add GLUTTON_STRATEGY_VERSION + per-match capture in hosted DB`
- **Branch:** `feat/strategy-versioning-pr1`
- **Plan reference:** `plans/sessions/2026-04-06_strategy_versioning_plan.md` §1 (MVP)
- **Scope (declared):**
  - `src/bid_euchre/strategy/greedy.py`
  - `web/schema.sql`
  - `web/db.py`
  - `web/app.py`
  - `web/routes.py`
  - `web/export.py`
  - `docs/02_agent/STRATEGY_VERSIONING.md` (new)
  - `tests/unit/hosted_play/test_db.py`
  - `tests/unit/hosted_play/test_app.py`
  - `tests/integration/hosted_play/test_data_capture.py`
  - `tests/unit/hosted_play/test_export.py`
- **Acceptance criteria:** Copy §1.7 from the plan (7 items).
- **Validation:**
  - `make check-gated`
  - Targeted: `uv run python -m pytest tests/unit/hosted_play/ tests/integration/hosted_play/test_data_capture.py -x`
  - Local smoke (no Render): `make web`, create one match via HTTP, query `SELECT play_strategy_version FROM matches ORDER BY id DESC LIMIT 1` → expect `'0.7.0'`.
- **Behavior change:** NONE (PR-1 only adds a constant + write-side capture; no card-play logic change).
- **Auto-merge:** **YES.** Pure infrastructure. Once `make check-gated` passes and the review coordinator verdict is `passed`, the orchestrator may run `gh pr merge --squash`.
- **Handoff protocol:** The receiving lane must follow `.claude/CLAUDE.md` Implementation Handoff Protocol — refresh plan, draft inline exec plan, spawn plan reviewer, create TUI task list, assess parallelism, execute end-to-end.
- **Blocks:** Cash-A (W2-1), #2520 rename (deferred).

### 4.4 Wave 2 — Cash-A + Track C (mixed auto-merge)

**Packet W2-1 (author-a, after PR-1 merges) — Cash-A:**

- **Title:** `fix(strategy): cash sure winners + draw trump first + draw trump high (Cash-A)`
- **Branch:** `fix/glutton-cash-winners-a`
- **Blocked by:** W1-1 merged.
- **Plan reference:** `plans/sessions/2026-04-06_ai_play_strategy_investigation.md` §Fix 1, §Fix 1b, §Fix 2
- **Scope (declared):**
  - `src/bid_euchre/strategy/greedy.py` — Fix 1, Fix 1b, Fix 2 behind feature flag `cash_winners_on_lead`
  - `tests/unit/test_greedy.py` — new behavior tests (at minimum: sure-winner lead in high/low; draw-trump-first on suit; lead highest trump on suit)
  - Bump `GLUTTON_STRATEGY_VERSION` from `"0.7.0"` to `"0.8.0"` in `src/bid_euchre/strategy/greedy.py`
- **Feature flag default:** **`cash_winners_on_lead=False`** in `GluttonStrategy.__init__`. This is critical: with the default False, merging Cash-A does not change production behavior — the operator flips the flag after AM proving. This preserves the "no auto-merge of live-behavior changes overnight" invariant even if the PR technically merges overnight (it will NOT merge overnight per auto-merge policy below, but default-False is a belt-and-suspenders safety).
- **Out-of-scope (rescoped from full Cash-A plan for overnight):**
  - **Paired H2H self-play bootstrap gate** — DEFERRED per operator "no new research" directive
  - **New experiment config YAML** — DEFERRED (would be used only for the bootstrap gate)
  - **`paired.py` / `stats.py` bootstrap CI computation** — DEFERRED
  - Cash-B follow-phase fixes (separate PR, separate wave, DEFERRED to tomorrow)
- **Validation (overnight scope):**
  - `make check-gated`
  - Targeted: `uv run python -m pytest tests/unit/test_greedy.py -x -k "cash_winners or sure_winner or draw_trump"`
  - **Local Playwright smoke** (per operator "test locally via playwright"): `make web`, play one full match against OLSa Easy with the feature flag flipped ON via a local override, capture 3 screenshots (auction, mid-hand, post-hand) in `data/local_smoke/cash_a/`, verify no crashes and hand plays through cleanly. Screenshots are ephemeral (gitignored), just the pass/fail result goes in the PR body.
- **PR body must include:**
  - `## Strategy Version` block per the new `docs/02_agent/STRATEGY_VERSIONING.md` convention (old `0.7.0`, new `0.8.0`, category MINOR)
  - Explicit note: `> **Paired H2H validation deferred** per 2026-04-06 operator "no new research" directive. Shipping behind default-False feature flag. Operator to enable flag after manual proving run. Full paired-bootstrap gate remains specified in plans/sessions/2026-04-06_ai_play_strategy_investigation.md §Validation Commands.`
  - `> **Do not auto-merge.** Track A but behavior-affecting. Waits for AM operator proving.`
- **Auto-merge:** **NO.** Despite default-False flag, operator wants to see the code + tests before merging a strategy-logic change.

**Packet W2-2 (flex-b) — Convention follow-up batch (Track C):**

- **Title:** `fix(convention): batch follow-up cleanup (#2500, #2492, #2497, #2487, #2484, #2463, #2462)`
- **Branch:** `fix/convention-batch-2026-04-06`
- **Scope (declared):** Depends on each issue body. Most are single-file, single-function edits. Expect ≤ 6 files total.
  - **#2500:** remove `check_match_limit()` + `MAX_ACTIVE_MATCHES_PER_PLAYER` from `web/middleware.py`; remove corresponding test class from `tests/unit/hosted_play/test_hardening.py`. Audit `expire_player_stale_matches` for callers; remove if dead.
  - **#2492, #2497, #2487, #2484, #2463, #2462:** open each and handle the specific convention finding. All are small auto-fixable style/naming/comment issues from the review coordinator.
- **Exclusions:** Do NOT include `fix:test` follow-ups (#2498, #2499). Tests are a different flavor of change and should be a separate PR to keep review simple.
- **Validation:** `make check-gated`. No Playwright smoke needed — no UI changes.
- **Auto-merge:** **YES** (convention-only, no rendered-UI changes, no live-strategy changes).
- **Size budget:** If the batch grows past ~8 files, split into two PRs.

**Packet W2-3 (flex-c) — Bash pattern narrowing (Track C, #2304):**

- **Title:** `fix(ops): narrow broad Bash auto-accept patterns in .claude/settings.json (#2304)`
- **Branch:** `fix/settings-narrow-bash-patterns`
- **Scope (declared):** `.claude/settings.json`
- **Change:** Replace `Bash(python *)` and `Bash(tmux *)` (if present) with the narrower patterns the issue proposes: `Bash(python -m pytest *)`, `Bash(python scripts/*)`, `Bash(python experiments/*)`, `Bash(tmux send-keys *)`, `Bash(tmux capture-pane *)`, `Bash(tmux list-*)`, `Bash(tmux display-message *)`.
- **Validation:** `make lint` (no pytest target exercises settings.json). Manual check: after the change, confirm the analyst lane can still run `uv run python -m pytest ...` without a prompt (this is the smoke).
- **Auto-merge:** **YES** (single-file config change, no runtime code touched).
- **Risk:** If the narrowed patterns break a lane mid-wave, the fleet-check skill will notice a permission stall. Recovery = revert the commit.

**Packet W2-4 (flex-d) — Test follow-ups (Track C):**

- **Title:** `test(web): add coverage for bid selector default + onboarding back button (#2499, #2498)`
- **Branch:** `test/bid-selector-onboarding-back`
- **Scope (declared):** `tests/unit/hosted_play/test_*` (precise files determined by the lane after reading each issue).
- **Validation:** `make check-gated` + targeted pytest of the new tests.
- **Auto-merge:** **YES** (tests only, no production code, no UI).

### 4.5 Wave 3 — Track B polish (parallel with Wave 2, NO auto-merge)

**These packets depend on Wave 0-A completing** (the lanes need to be off
their rescue branches before they can take new work). Orchestrator must gate.

**Packet W3-1 (brws-author-a, after W0A-1 PR is open and lane is idle) — #2521 bid form polish:**

- **Title:** `fix(web): bid form polish — single-line layout, full-width Pass, null contract default (#2521 items 2/3/4)`
- **Branch:** `fix/web-bid-form-polish`
- **Scope (declared):** `web/templates/` (auction partial), `web/static/` CSS, possibly `web/routes.py` for contract-selected validation
- **Included items (per issue body):**
  - **Item 2:** Type/Bid/Contract single-line consistent layout
  - **Item 3:** Pass button full-width to match Submit Bid
  - **Item 4:** Contract defaults to null, Submit Bid disabled until selection
- **Excluded items:**
  - **Item 1 (large text as default)** — explicitly labeled "research/feasibility task" in the issue body. DEFERRED per operator "no new research" directive.
- **Validation:**
  - `make check-gated`
  - Local Playwright smoke: `make web` + `playwright` MCP navigate to `/play/<uuid>`, reach auction, capture screenshots of the bid form. Verify: labels single-line, Pass full-width, Submit disabled with no contract selected.
- **PR body must include:** `> **Do not auto-merge.** Track B UI/UX — waits for AM operator proving.` Plus the Playwright screenshot result + note that item 1 is deferred.
- **Auto-merge:** **NO.**

**Packet W3-2 (brws-author-b, after W0A-2 PR is open and lane is idle) — #2288 items 1/2/3/5:**

- **Title:** `fix(web): UI polish round 4 — LEAD TRICK label, RB/LB legend, spade color, score labels (#2288)`
- **Branch:** `fix/web-ui-polish-round4-batch`
- **Scope (declared):** `web/templates/` + `web/static/` CSS
- **Included items (per #2288 body, remaining from 2026-04-05 triage):**
  - **Item 1:** Rename LEAD TRICK label (use "LEADER" — don't research other games' terminology; go with the obvious choice per "no new research")
  - **Item 2:** Add RB/LB tooltip/legend explaining Right Bower / Left Bower
  - **Item 3:** Contract display — ensure `♠` renders black in Contract/Trump, matching card styling
  - **Item 5:** Score labels "Your Team" / "Opponent" instead of team numbers
- **Excluded items (already done per 2026-04-05 triage):** 4, 6, 7, 8
- **Validation:**
  - `make check-gated`
  - Local Playwright smoke covering: bid screen (RB/LB badge), play screen (leader label), contract display (black spade), score bar (team labels)
- **PR body must include:** `> **Do not auto-merge.** Track B UI/UX — waits for AM operator proving.`
- **Auto-merge:** **NO.**

### 4.6 Wave 4 — Post-landing AM summary

**Packet W4-1 (analyst-a):**

- **Title:** Draft AM handoff summary
- **Scope:** `plans/sessions/2026-04-07_am_handoff.md`
- **Contents:** What shipped (Track A + C merged items), what is waiting for AM proving (Track B PRs + Cash-A), validation status, known risks, the exact `gh pr merge` sequence the operator should run after proving.
- **Auto-merge:** N/A (doc PR, can auto-merge via review coordinator).

---

## 5. Validation strategy (per wave)

| Wave | Required gate | Playwright smoke? | Notes |
|---|---|---|---|
| 0-A | `make check-gated` on existing branch | YES (rebase may change rendering) | Re-validate after rebase |
| 0-B | N/A (reset only) | NO | Just `git status` to confirm clean |
| 0-C | N/A (debris cleanup) | NO | — |
| 1 (PR-1) | `make check-gated` + targeted hosted_play pytest | NO (no UI change) | Plus manual `make web` + SQL query |
| 2 (Cash-A) | `make check-gated` + targeted `test_greedy.py` | YES (one full match) | Paired-H2H gate DEFERRED |
| 2 (Track C) | `make check-gated` | NO | Convention/config/test-only |
| 3 (Track B polish) | `make check-gated` | YES (required — visual changes) | Screenshots live in `data/local_smoke/` (gitignored) |
| 4 | — | NO | Plan doc |

**No Render deploys anywhere.** The word `render` must not appear in any
commit or CI artifact this wave other than in existing docs.

**Playwright smoke minimum for Track B:**
- Start local server via `make web` on a free port (default 8000)
- Use `mcp__playwright__browser_navigate` to load `/play/<test-uuid>`
- Exercise the affected UI region
- `mcp__playwright__browser_take_screenshot` at ≥ 2 key states
- Save screenshots to `data/local_smoke/<packet-id>/` (gitignored path)
- Attach the screenshot names (and any console errors) to the PR body

**Tier 1 vs Tier 2:** Each lane runs Tier 1 targeted pytest during implementation.
`make check-gated` (Tier 2) runs **once** before `gh pr create`, in the
foreground. See `.claude/rules/15_testing_tiers.md` and the `/start-task`
skill warning about backgrounded `make check-gated`.

---

## 6. Auto-merge policy matrix

| PR | Track | Change class | Auto-merge? | Rationale |
|---|---|---|---|---|
| W0A-1 #2505 | B | CSS color | **NO** | UI-rendered |
| W0A-2 #2508 | B | Template cleanup | **NO** | UI-rendered |
| W0A-3 #2503 | B | Pacing + template | **NO** | UI interaction |
| W0A-4 #2509 | B | Template removal | **NO** | UI-rendered |
| W1-1 PR-1 | A | Schema + wiring | **YES** | Zero behavior change; column add only |
| W2-1 Cash-A | A | Strategy logic (flag default False) | **NO** | Operator wants eyes on strategy diffs |
| W2-2 convention batch | C | Dead code + style | **YES** | No UI, no strategy |
| W2-3 Bash patterns | C | `.claude/settings.json` | **YES** | Config only |
| W2-4 test follow-ups | C | Tests only | **YES** | No production code |
| W3-1 bid form polish | B | Template + CSS + routes | **NO** | UI-rendered |
| W3-2 UI polish round 4 | B | Template + CSS | **NO** | UI-rendered |
| W4-1 AM handoff | — | Doc | **YES** | Plan doc |

**Auto-merge mechanism:** For `YES` rows, the orchestrator may run
`gh pr merge --squash --auto` once the review coordinator verdict is
`passed` and CI is green. For `NO` rows, the PR must remain open with the
review coordinator status visible and the PR body note prominent. The
orchestrator **must not** run `gh pr merge` on any `NO` PR overnight.

---

## 7. Easy wins (Track C) — numbered and assigned

| # | Source | Packet | Lane | Size | Auto-merge |
|---|---|---|---|---|---|
| 1 | #2500, #2492, #2497, #2487, #2484, #2463, #2462 | W2-2 | flex-b | M (6-8 files) | YES |
| 2 | #2304 (narrow Bash patterns) | W2-3 | flex-c | S (1 file) | YES |
| 3 | #2499, #2498 (fix:test follow-ups) | W2-4 | flex-d | S (test-only) | YES |

**Easy wins explicitly excluded from overnight:**

- **#2520** (rename `greedy.py` → `glutton.py`): The issue body itself says
  "Land it AFTER #2519 / Cash-A so it doesn't conflict with the MVP shipping
  path." It also touches `src/bid_euchre/`, `web/`, `tests/`, `experiments/`,
  `scripts/`, and notebooks — a wide-scope rename that could conflict with
  Cash-A. **Defer to tomorrow.**
- **#2471, #2441, #2442, #2440** (labeled "already fixed" in 2026-04-05 triage but still OPEN): These need a verification pass before closure — that is analyst/triage work, not implementation work. **Defer to tomorrow.** Noted in the AM checkpoint.
- **#2469, #2468** (counterfactual logging): Multi-file feature work, not "easy wins." **Defer.**

---

## 8. Cash-B — overnight or defer?

**Recommendation: DEFER to tomorrow.**

Reasons:
1. Cash-B is blocked by Cash-A merged (per the investigation plan §Cash-B "Blocked by: Cash-A merged").
2. Cash-A is blocked by PR-1 merged. Stacking Cash-B on top creates a three-deep dependency chain that cannot complete overnight given the AM-proving gate on Cash-A.
3. Cash-B's validation is the same paired-H2H bootstrap gate that is deferred per "no new research." Without that gate Cash-B has even less evidence than Cash-A has (Cash-A at least has clear unit-test surface; Cash-B depends on paired statistical analysis to prove its 2nd-hand-low fallback is a strict improvement).
4. Scope discipline: shipping Cash-A + deferring Cash-B matches the operator's go-live cadence of "one behavior bump, prove it, then ship the next."

**Tomorrow's dispatch:** once Cash-A is proven + merged, open a separate
packet for Cash-B with its own paired-H2H gate (research allowed after
overnight), using the standing Cash-A plan §Cash-B task packet skeleton.

---

## 9. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Wave 0-A rebase conflicts: the four brws branches were cut from a pre-#2519 main and may conflict with `web/` changes | MEDIUM | Each lane rebases independently in its own worktree. Conflicts are trivial (CSS/template) or abort-and-escalate per `/start-task` Phase 2b protocol. |
| R2 | Wave 0-B resets discard unique uncommitted work | LOW | Protocol requires verifying commits are duplicates of closed-issue PRs before `git branch -D`. If uncertain, STOP + escalate. |
| R3 | PR-1 migration hits a Postgres-only edge case (hosted is SQLite-only locally) | LOW | The plan §1.2 explicitly tests SQLite + Postgres syntax compatibility. `make web` local smoke validates SQLite path. Postgres path validated next AM on Render after operator redeploys. |
| R4 | Cash-A merges overnight via auto-merge misconfiguration despite the NO policy | MEDIUM | Defense in depth: (a) feature flag defaults False so behavior is unchanged even if merged; (b) PR body contains the no-auto-merge banner; (c) orchestrator runbook explicitly calls out Cash-A as do-not-merge; (d) operator AM checkpoint reviews every Track A/B PR manually. |
| R5 | Track C convention batch (W2-2) grows beyond declared scope | LOW | Size budget ≤ 8 files; lane must split if larger. |
| R6 | `.claude/settings.json` Bash-pattern narrowing (W2-3) stalls another lane | MEDIUM | The lane that ships the change should verify at least one `uv run python -m pytest ...` executes post-change in its own pane. Fleet-check skill monitors for stalls and can revert if one emerges. |
| R7 | Playwright MCP flakes mid-run (screenshot capture fails) | LOW | Screenshots are smoke-test evidence, not a gating verdict. If Playwright fails, lane records the failure in the PR body and marks the smoke as `degraded`; operator decides during AM proving. |
| R8 | Two lanes race on `src/bid_euchre/strategy/greedy.py` (PR-1 and Cash-A) | LOW | Dispatch serializes them: Cash-A cannot start until PR-1 merges. The author-a lane does both sequentially. No other lane touches this file. |
| R9 | Track B PR sits unmerged too long and the operator can't remember which screenshots belong to which PR | LOW | Each Track B PR body includes: packet ID, screenshot filenames, one-sentence "what to look for" for proving. |
| R10 | Strategy versioning plan changes underfoot while PR-1 is being implemented (analyst-b or other lane edits the plan) | LOW | The plan is stable (committed PR #2522 landed 2026-04-06). Any edits to it by other lanes trigger a conflict warning. |
| R11 | Fleet-wide `make check-gated` contention (12 lanes running Tier 2 simultaneously) | MEDIUM | `make check-gated` caps concurrency via the gated target. Fleet-check skill monitors CPU load. Stagger Wave 0-A + Wave 1 starts by ~30s each. |
| R12 | Lane dispatched to a Track B PR accidentally runs `gh pr merge` via the start-task skill muscle memory | MEDIUM | The packet instructions MUST have the no-merge note as the last line, rendered prominently. The packet validation step asks the lane to echo the note back before implementation. |
| R13 | Cash-A unit tests are insufficient to catch a regression that paired-H2H would have caught | HIGH | **ACCEPTED RISK.** This is the operator's "no new research" tradeoff made explicit. The mitigation is: (a) default-False flag, (b) operator AM proving run, (c) post-merge review hook, (d) ability to revert Cash-A independently if a regression emerges post-enable. The PR body calls this out explicitly. |

---

## 10. AM checkpoint — what the operator should find when they wake up

When the operator starts their AM session, they should see:

### Merged overnight (auto-mergeable tracks)

- **PR-1** (W1-1, strategy versioning infra) — merged ~early overnight
- **Track C PRs** (W2-2, W2-3, W2-4) — merged as they clear the review coordinator
- **Wave 4** (AM handoff doc) — merged

### Waiting for AM operator review + manual merge (NO auto-merge)

Expected count: **6 PRs**.

- **Wave 0-A rescue (4 PRs):**
  - #2505 — black suit icons (brws-author-a)
  - #2508 — duplicate auction log (brws-author-b)
  - #2503 — auction pacing (brws-author-c)
  - #2509 — remove Hand Details dropdown (brws-author-d)
- **Wave 3 UI polish (2 PRs):**
  - #2521 items 2/3/4 — bid form polish (brws-author-a)
  - #2288 items 1/2/3/5 — UI round 4 batch (brws-author-b)
- **Cash-A (1 PR)** — behavior-affecting (author-a), default-False flag, needs logic review

> **Operator's AM proving checklist (per PR):**
> 1. Read the PR body and Playwright screenshots
> 2. Pull the branch locally: `gh pr checkout <N>`
> 3. `make web` and reach the affected screen
> 4. Verify the change matches the acceptance criteria
> 5. If good: `gh pr merge <N> --squash`
> 6. If bad: comment on PR with specific repro + revert branch locally; orchestrator dispatches a fix

### Deferred to tomorrow (documented in `plans/sessions/2026-04-07_am_handoff.md`)

- **Cash-B** — blocked by Cash-A merged + operator's "no new research" deferral
- **#2520** — greedy.py → glutton.py rename (blocked by Cash-A per issue body)
- **#2521 item 1** — large text default feasibility (research task)
- **#2471, #2441, #2442, #2440** — issues marked "already fixed" in 2026-04-05 triage but still OPEN; need verification pass before closure
- **#2469, #2468** — counterfactual logging features (multi-file, non-urgent)
- **Wave 0-B stale branches** — if any lane discovered unique non-duplicate commits, the orchestrator must decide whether to rescue

### Fleet state

- All 12 author/flex lanes in a clean, idle state with `main` checked out (except author-a which may still be holding `fix/glutton-cash-winners-a` for Cash-A pending merge)
- No dangling nudges, no stuck permission prompts, no half-finished rebases
- The stale platform lane branches cleaned up per Wave 0-B

### What to look for if something is wrong

- **All 6 Track B PRs not opened** → Wave 0-A rebase conflicts cascaded; check lane panes for escalation messages
- **PR-1 not merged** → migration test failure or review coordinator stuck; check `.claude/runtime/review_loops/pr_<N>/state.json`
- **Cash-A PR open but shows merged** → auto-merge violation; revert immediately (`gh pr revert`), file a HIGH severity issue against the orchestrator runbook
- **Track C not merged** → single-file changes shouldn't block; check CI contention on fleet-check skill output

---

## 11. Deferred work register (for `plans/sessions/2026-04-07_am_handoff.md`)

| # | Item | Why deferred | Reopens when |
|---|---|---|---|
| D1 | Cash-B (sure-winner follow + 2nd-hand-low fallback) | Blocked by Cash-A merged; "no new research" disallows its paired-H2H gate overnight | Cash-A proven + merged |
| D2 | Cash-A paired-H2H bootstrap gate | "No new research" directive | Operator lifts research freeze |
| D3 | #2520 greedy.py → glutton.py rename | Issue body says "after #2519 / Cash-A"; wide-scope rename risks Cash-A conflict | Cash-A merged |
| D4 | #2521 item 1 — large text as default feasibility | Explicitly "research/feasibility task" | Operator lifts research freeze |
| D5 | #2469, #2468 — counterfactual logging | Multi-file feature work, not easy wins | Post-pilot stabilization |
| D6 | Triage verification pass for #2471, #2441, #2442, #2440 | Not overnight shipping work; analyst task | Analyst bandwidth available |
| D7 | Wave 0-B stale branches (if any had unique non-duplicate commits) | Requires operator rescue decision | Orchestrator escalation |
| D8 | Section 2 of strategy versioning plan (ablation harness, CI lint, per-decision recording, Alembic, etc.) | Operator explicitly deferred in the plan | Operator opens the research track |

---

## 12. Dispatch blockers the orchestrator must resolve before Wave 0

1. **This plan must be operator-approved.** Per operator constraint 5 ("Propose overnight run here before dispatching"), the orchestrator MUST NOT dispatch any packet until the operator signs off on this doc. The plan lives in a PR for review.
2. **Verify fleet idle state.** The `lane-status` skill should confirm all 12 author/flex lanes are idle (not mid-prompt, not mid-rebase, not stuck on permissions).
3. **Verify CI capacity.** `fleet-check` skill runs a CPU load check. If load > 70%, stagger Wave 0-A starts.
4. **Verify no open PRs.** Currently none (`gh pr list --state open --limit 30` returns empty). Any new PR opened by another agent between now and dispatch must be inspected for conflicts.
5. **Verify `make web` runs locally.** Orchestrator should smoke-test `make web` in a scratch worktree before dispatching Track B — if the hosted app is broken on main, no Playwright smoke can pass.

---

## 13. Success criteria for the overnight run

When the operator wakes up, the run is a **success** if:

- [ ] All 4 Wave 0-A PRs are open, green, and waiting for merge (4 × Track B)
- [ ] PR-1 (strategy versioning) is **merged**
- [ ] Cash-A PR is open, green, and waiting for operator logic review + merge
- [ ] At least 2 of 3 Track C PRs are merged (W2-2, W2-3, W2-4)
- [ ] Wave 3 both Track B polish PRs are open, green, and waiting for merge (2 × Track B)
- [ ] `plans/sessions/2026-04-07_am_handoff.md` exists with the proving checklist
- [ ] Zero Render deploys
- [ ] Zero auto-merged Track B PRs
- [ ] Zero regressions reported against merged Track A/C PRs via post-merge review

**Partial success** (operator-visible, not a full rollback):

- PR-1 merged but Cash-A blocked on some CI flake → operator dispatches recovery in the AM
- Wave 0-A rescues partially complete (2 of 4) → operator picks up the rest manually
- Track C only half-merged due to review coordinator contention → not a regression, just slower throughput

**Failure signals** (requires AM intervention):

- Any Track B PR auto-merged (must revert immediately)
- PR-1 reverted post-merge (blocks Cash-A and signals a methodology gap in the versioning plan)
- More than 2 lanes in a stuck state (permission stall, hung rebase, orphan cron)
- CI red on `main` caused by a merged overnight PR

---

## 14. Handoff notes for the orchestrator

- **Dispatch mechanism:** Each packet should go through `ops.py task create` with the exact `scope_declared` and `validation` from §4, then `ops.py task dispatch <id> --lane <lane>` to push the packet + nudge.
- **Task-packet template:** Each packet must reference this plan path (`plans/sessions/2026-04-06_overnight_run_plan.md`) and the applicable section (e.g., §4.3 W1-1). The receiving lane re-reads this plan + the upstream plan it cites before implementing.
- **No-auto-merge enforcement:** For every Track B / Cash-A packet, the packet body's final line must be: `> **CRITICAL: Do not run `gh pr merge`. This PR waits for AM operator proving.**`
- **AM checkpoint doc:** analyst-a (this lane) can pick up W4-1 after Wave 3 dispatches (not after they complete) to have a skeleton ready for the operator to review at AM.
- **Escalation:** Any `blocker` message from a lane pauses that wave; downstream waves continue if they don't depend on the blocked lane. The orchestrator pulls the blocked lane into recovery via the `/triaging-issues` or `/debugging-ci` skill.

---

## Outcome

*(To be filled after the orchestrator dispatches and Wave 4 completes.)*

## References

### Governing plans + prior work
- `plans/sessions/2026-04-06_strategy_versioning_plan.md` — PR-1 spec (Track A Wave 1)
- `plans/sessions/2026-04-06_ai_play_strategy_investigation.md` — Cash-A spec (Track A Wave 2)
- `plans/sessions/2026-04-05_issue_triage_go_live.md` — prior triage (source of 2026-04-05 Wave 1 items that became this plan's Wave 0-A rescue)
- `plans/sessions/2026-04-05_overnight_go_live_plan.md` — prior overnight plan

### Rules
- `.claude/rules/deferred/55_issue_closure.md` — Tier 2 verified-close (applies to Track B)
- `.claude/rules/deferred/60_review_gate.md` — review coordinator + auto-merge caveat
- `.claude/rules/deferred/40_prs.md` — PR template + hard gates
- `.claude/rules/15_testing_tiers.md` — Tier 1 / Tier 2 validation
- `.claude/rules/75_worktree_protection.md` — lane worktrees must not be removed
- `.claude/CLAUDE.md` Implementation Handoff Protocol — required execution sequence

### Issues referenced
- **Tracked for this run:** #2505, #2508, #2503, #2509, #2521, #2288, #2519, #2304, #2500, #2492, #2497, #2487, #2484, #2463, #2462, #2499, #2498
- **Deferred with documented reason:** #2520, #2469, #2468, #2521 (item 1), #2471, #2441, #2442, #2440, #1917, Cash-B

### Fleet state snapshot (captured during shaping)
- 4 brws-author lanes: unpushed 2026-04-05 Wave 1 P0 commits → Wave 0-A rescue
- 4 platform author lanes: stale branches for closed issues → Wave 0-B reset
- 1 flex-a lane: untracked screenshots → Wave 0-C cleanup
- 4 analyst lanes + 3 flex lanes: idle
- Open PRs: **0**
- Task queue: 32 packets (31 stale-dispatched to analyst-a, 1 active — this one)
