# Proving Matrix -- Browser Game Expansion and Pilot Readiness

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-24

---

## Validation Layers

| Layer | Owner | Automation | Purpose |
|-------|-------|------------|---------|
| Unit | Claude | Full | Protect core rules, schema helpers, model loading, and route helpers. |
| Integration | Claude | Full | Prove DB wiring, migration path, export/replay, and seeded end-to-end flows. |
| Browser E2E | Claude | Full | Prove real browser flows through the FastAPI app, including moon/loner, access codes, and mobile viewport behavior. |
| Smoke | Claude | Full | Prove app startup, Docker/Postgres/local server wiring, and critical route health. |
| Human proving | User | Minimal | Cover only real-device and authorization-sensitive gaps. |

## Old Features That Must Still Work

- Landing page and match creation
- Nickname/session resume semantics until replaced by invite-code gating
- Regular bidding and regular trick play
- All-pass redeal
- Match scoring to `+52 / -52`
- Decision logging and export/replay
- Refresh/resume at any point
- Deployment health/readiness checks

## New Features That Must Be Proven

- `OLSa` default browser model wiring
- Moon bidding legality
- Loner bidding legality
- Moon exchange
- Loner sit-out flow
- Moon/loner scoring and match accounting
- Last-trick visibility
- Action rail and turn/dealer/declarer markers
- Hand-end pause and explicit next-deal action
- Pace controls and reduced motion
- Mobile touch-safe play
- Invite-code access control and code generator workflow
- Claude-direct browser testing capability

## Automated Validation Commands (Target State)

```bash
# Fast regression
uv run python -m pytest tests/unit/hosted_play -q

# DB + integration
uv run python -m pytest tests/integration/hosted_play -q

# Browser E2E
uv run python -m pytest tests/e2e/hosted_play -q

# Docker/local smoke
bash scripts/internal/smoke_hosted.sh

# Full hosted-play sweep before launch
uv run python -m pytest \
  tests/unit/hosted_play \
  tests/integration/hosted_play \
  tests/e2e/hosted_play -q
```

## Required User Proving Runs

| Run | Why It Requires a Human | Exit Condition |
|-----|--------------------------|----------------|
| Real iPhone Safari smoke | Device/browser fidelity cannot be fully reduced to desktop automation | User can complete one regular hand and one moon/loner hand or scripted smoke path on phone |
| Production deployment authorization | Requires hosting credentials and user approval | User explicitly approves release and confirms deploy target |
| First live invite redemption | Confirms real-world code distribution and phone session behavior if automation is insufficient | One real invite code is redeemed successfully on the deployed build |

## Explicitly Not User-Proving By Default

These should be automated unless a failure forces escalation:

- Regular browser match flow
- Redeal behavior
- Decision logging correctness
- Moon exchange correctness
- Loner trick-order correctness
- Mobile narrow-layout regression
- Access-code happy path
- Postgres/local Docker smoke
