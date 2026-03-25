# Sub-Plan Registry -- Browser Game Expansion and Pilot Readiness

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-25 by analyst (reconcile SP-2-01/SP-2-02 to partial after user proving)

---

## Registry

| ID | Title | Parent Section | Status | Owner | File | Created | Completed |
|----|-------|----------------|--------|-------|------|---------|-----------|
| SP-0-01 | Proving Contract and Browser Testing Foundation | Phase 0 -- Execution Foundation | completed | brws-author-a | `0_execution_foundation/sub/2026-03-24_proving-contract-and-browser-testing.md` | 2026-03-24 | 2026-03-25 |
| SP-1-01 | OLSa Roster Migration | Phase 1 -- Model and Rules Core | completed | brws-author-a | `1_model_and_rules_core/sub/2026-03-24_olsa-roster-migration.md` | 2026-03-24 | 2026-03-25 (PR #1798) |
| SP-1-02 | Moon/Loner Hosted-Play Plumbing | Phase 1 -- Model and Rules Core | completed | brws-author-a | `1_model_and_rules_core/sub/2026-03-24_moon-loner-hosted-play.md` | 2026-03-24 | 2026-03-25 (PR #1804) |
| SP-2-01 | Gameplay Readability and Hand Pacing | Phase 2 -- Product Experience | **partial** | brws-author-a | `2_product_experience/sub/2026-03-24_gameplay-readability-and-pacing.md` | 2026-03-24 | — (PR #1809 shipped Step 1 only; Steps 2-3 NOT implemented. See #1842, #1844, #1845, #1846) |
| SP-2-02 | Mobile, Accessibility, and Help Pass | Phase 2 -- Product Experience | **partial** | brws-author-a | `2_product_experience/sub/2026-03-24_mobile-accessibility-help.md` | 2026-03-24 | — (PR #1818 shipped responsive layout + ARIA; tap-select #1847, pace controls #1848, help drawer #1849 NOT shipped) |
| SP-3-01 | Invite Codes and Nickname Flow | Phase 3 -- Pilot Access Control | completed | brws-author-b | `3_pilot_access_control/sub/2026-03-24_invite-codes-and-nickname-flow.md` | 2026-03-24 | 2026-03-25 (PR #1800) |
| SP-4-01 | Browser Automation, Smoke, and Pilot Proving | Phase 4 -- Validation and Launch | in_progress | brws-author-c/d | `4_validation_and_launch/sub/2026-03-24_browser-automation-smoke-and-proving.md` | 2026-03-24 | — (PRs #1821, #1822 shipped; 2 of 7 Playwright tests failing — see #1827; user proving Steps 4-5 pending) |
| SP-5-01 | GBT Evaluation and Optional Promotion | Phase 5 -- Optional GBT Evaluation | proposed | -- | `5_optional_gbt_evaluation/sub/2026-03-24_gbt-evaluation-and-promotion.md` | 2026-03-24 | -- |
| SP-AC-01 | Leaderboard and Analytics | Phase AC -- Analytics and Community | proposed | -- | `4_analytics_and_community/sub/2026-03-25_leaderboard-and-analytics.md` | 2026-03-25 | -- |
| SP-AC-02 | Feedback Forum and Claude User Constraints | Phase AC -- Analytics and Community | proposed | -- | `4_analytics_and_community/sub/2026-03-25_feedback-forum-and-claude-user.md` | 2026-03-25 | -- |

## Status Summary

| Status | Count |
|--------|-------|
| proposed | 3 |
| in_progress | 1 |
| partial | 2 |
| blocked | 0 |
| completed | 4 |
| abandoned | 0 |
| superseded | 0 |

## Conventions

- **ID format:** `SP-<phase>-<seq>` where `<phase>` is the phase number and
  `<seq>` is a zero-padded sequence within that phase.
- **Lifecycle:** proposed -> in_progress -> completed | abandoned | superseded.
  A sub-plan may transition to `blocked` from `in_progress` and back.
  A sub-plan is `partial` when its PR merged but user proving reveals
  significant unshipped scope.
- **File location:** `plans/browser_game_expansion/<phase>/sub/YYYY-MM-DD_<slug>.md`
- **Updates:** Update this registry whenever a sub-plan changes status.
