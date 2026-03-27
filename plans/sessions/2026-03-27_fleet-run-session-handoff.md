# Session Handoff -- 2026-03-27 Fleet Run

**Author:** analyst-a
**Session span:** 06:57 - 21:44 UTC (14h 47m wall clock; ~7h active fleet run from 15:22)
**PRs merged:** 32 (3 pre-fleet analyst/dashboard + 29 fleet run)
**Issues closed:** 29 (15 created today + 14 pre-existing)
**Issues created:** 29 (14 remain open)
**Open issues at session end:** 19

---

## Milestone Status

### Platform-9a (Idle-Attention Alerts)

**Status: IN_PROGRESS** (checkpoints.md Step 4, Phase 4 `4_remote_channel`)

**Shipped this session (4 PRs):**
- PR #1944 -- wire `run_push_cycle()` into monitor module
- PR #1956 -- e2e smoke test for alert-push-ack loop
- PR #1959 -- wire inbound ack parsing into monitor module
- PR #1961 -- report save failures as ack failures in `process_inbound_ack`

**Still open (exit criteria not met):**
- **E3:** MCP `reply` call for actual Telegram delivery -- `run_push_cycle()` evaluates alerts and prepares payloads but does not call the Telegram plugin's `reply` tool
- **E4/E7:** Live inbound ack consumer for `execute_remote_ack()` -- ack parser shipped but not wired to a real inbound message stream
- **E9:** Real remote round-trip proving -- no end-to-end alert-push-ack cycle demonstrated on live Telegram

**Issues #1824 and #1826 remain OPEN on GitHub.**

Supporting PRs for Telegram instance competition:
- PR #1945 -- add Telegram lane routing filter (#1824)
- PR #1946 -- restrict Telegram plugin to orchestrator lane only

These mitigate the instance competition bug but do not fully close #1824 -- the issue remains open because a live fleet-run verification has not been performed.

### Tmux 5-Window Layout

**Status: Shipped and running; formal proving deferred to next session.**

The previous handoff marked layout proving as DEFERRED. This session visually confirmed the layout was running correctly (analyst pool panes active, flex-d added via PR #1927), but the formal proving protocol from the handoff checklist was not executed.

### Platform-10 (Core Ops Extraction)

**Status: IN_PROGRESS** -- 5 PRs shipped across sessions.

Shipped this session:
- PR #1950 -- ServiceProvider for core adapter wiring (PR5)
- PR #1954 -- core adapter contract and integration tests (PR4)

Remaining: additional adapter integration, migration docs, and deployment validation.

### Browser Game Expansion

**Status: Active** -- significant bug fix and test coverage wave completed.

All PR-4b through PR-5c gap items from the roadmap are now closed. The open
roadmap items are: PR-9 (GBT evaluation), PR-AC1 (leaderboard), PR-AC2 (forum).

---

## PRs Merged (32)

### Pre-Fleet -- Analyst Work (3 PRs)

| # | Time | Title |
|---|------|-------|
| #1902 | 06:57 | chore: update PR analytics dashboard |
| #1907 | 13:39 | docs: gap analysis of 18 recently closed issues vs codebase state |
| #1921 | 14:25 | docs: glutton strategy revamp experiment design (#1917) |

### Wave 0 -- Clear the Decks (4 PRs, 15:22-15:37)

| # | Time | Title | Closes |
|---|------|-------|--------|
| #1929 | 15:22 | fix(test): disable age-based pruning in per-worktree-cap snapshot test | -- |
| #1923 | 15:36 | fix(web): trick winner card display + moon exchange interstitial | #1915 |
| #1922 | 15:37 | fix(web): seat crowding CSS + scoring test matrix | #1895 |
| #1927 | 15:37 | ops: add flex-d lane and widen auto-accept permissions | #1919, #1920 |

### Wave 1 -- Quick Fixes (7 PRs, 16:33-17:39)

| # | Time | Title | Closes |
|---|------|-------|--------|
| #1924 | 16:33 | fix(web): score bug (#1913) + lead indicator (#1914) | #1913, #1914 |
| #1934 | 16:40 | fix(test): add public exchange wrappers and unit tests (#1906) | #1906 |
| #1935 | 16:48 | refactor(test): deduplicate _advance_pending_reveals into shared conftest (#1905) | #1905 |
| #1936 | 16:50 | fix(web): seed browser test AI decisions for determinism (#1909) | #1909 |
| #1939 | 17:03 | fix(web): coerce bidder_seat to int in hand result template (#1928) | #1928 |
| #1925 | 17:13 | feat(web): sort hand by suit/bower rank + add trick history toggle | #1892, #1911 |
| #1933 | 17:39 | feat(ops): add squash merge verification tool (#1908) | #1908 |

### Wave 2 -- Platform + Tests (2 PRs, 19:38)

| # | Time | Title | Closes |
|---|------|-------|--------|
| #1942 | 19:38 | fix(ops): add paste-bracket delay for tmux send-keys (#1834) | #1834 |
| #1943 | 19:38 | test(web): add exhaustive bid/outcome test scaffold (#1918) | #1918 |

### Wave 3 -- Platform-9a + Browser Polish + Platform-10 (16 PRs, 20:16-21:44)

| # | Time | Title | Closes |
|---|------|-------|--------|
| #1941 | 20:16 | feat(test): data capture pipeline validation scaffold (#1926) | #1926 |
| #1944 | 20:23 | feat(ops): wire run_push_cycle into monitor module (#1826 part 1) | -- |
| #1948 | 20:30 | docs(ops): update Platform-9a checkpoints (#1826 part 4) | -- |
| #1945 | 20:33 | fix(ops): add Telegram lane routing filter (#1824) | -- |
| #1946 | 20:34 | fix(ops): restrict Telegram plugin to orchestrator lane only | -- |
| #1949 | 20:47 | feat(web): make moon exchange interactive (#1893) | #1893 |
| #1952 | 20:49 | chore: update PR analytics dashboard with fleet run data | -- |
| #1953 | 20:52 | docs: reconcile all governing plan checkpoints (session 2026-03-27) | -- |
| #1950 | 20:52 | feat(ops): add ServiceProvider for core adapter wiring (Platform-10 PR5) | -- |
| #1957 | 21:00 | feat(web): template/CSS cleanup -- extract inline styles, fix button hover | -- |
| #1954 | 21:00 | test(ops): add core adapter contract and integration tests (Platform-10 PR4) | -- |
| #1955 | 21:03 | fix(test): harden flaky tests against timing and filesystem assumptions | -- |
| #1956 | 21:05 | test(ops): e2e smoke test for alert-push-ack loop (#1826 part 3) | -- |
| #1958 | 21:05 | test(web): expand hosted-play E2E test coverage | -- |
| #1959 | 21:32 | feat(ops): wire inbound ack parsing into monitor module (#1826) | -- |
| #1961 | 21:44 | fix(ops): report save failures as ack failures in process_inbound_ack | -- |

**PR count verification:** 3 + 4 + 7 + 2 + 16 = **32 PRs** (matches `gh pr list --state merged --search 'merged:2026-03-27'`)

---

## Issues Closed (29)

### Pre-Existing Issues Closed by This Session (14)

| # | Title | Closed By |
|---|-------|-----------|
| #1749 | ops: activate steward-analyst lane | Session proving (visual) |
| #1788 | follow-up for PR #1778 | Convention fix (pre-session) |
| #1819 | follow-up for PR #1818 | Convention fix (pre-session) |
| #1825 | follow-up for PR #1823 | Convention fix (pre-session) |
| #1829 | ops: Telegram elapsed time | Docs fix (pre-session) |
| #1831 | ops: VS Code workspace audit | Docs fix (pre-session) |
| #1834 | ops: tmux paste bracketing | PR #1942 |
| #1889 | fix(web): help drawer rules copy | Pre-session merge |
| #1890 | fix(web): remove browser fallback | Pre-session merge |
| #1891 | fix(web): replace pace controls with Next flow | Pre-session merge |
| #1892 | feat(web): cards-played history toggle | PR #1925 |
| #1893 | fix(web): moon exchange interactive | PR #1949 |
| #1894 | fix(web): randomize opening dealer | Pre-session merge |
| #1895 | fix(web): seat crowding CSS | PR #1922 |

### Issues Created and Closed Today (15)

| # | Title | Closed By |
|---|-------|-----------|
| #1903 | scope drift: PR #1880 | PR merged (pre-fleet) |
| #1904 | scope drift: PR #1870 | PR merged (pre-fleet) |
| #1905 | deduplicate test helper | PR #1935 |
| #1906 | exchange wrapper unit tests | PR #1934 |
| #1908 | squash merge verification | PR #1933 |
| #1909 | browser test root causes | PR #1936 |
| #1911 | sort hand by suit/bower | PR #1925 |
| #1913 | score bug: wrong team set | PR #1924 |
| #1914 | trick leader indicator | PR #1924 |
| #1915 | show winning card | PR #1923 |
| #1918 | exhaustive bid/outcome testing | PR #1943 (scaffold) |
| #1919 | add flex-d lane | PR #1927 |
| #1920 | auto-accept permissions | PR #1927 |
| #1926 | data capture pipeline | PR #1941 (scaffold) |
| #1928 | seat labels "Seat N" | PR #1939 |

**Issue count verification:** 14 + 15 = **29 issues closed** (matches `gh issue list --search 'closed:2026-03-27' --limit 100 --state closed`)

---

## Issues Created (29)

| # | Title | Status |
|---|-------|--------|
| #1903 | scope drift: PR #1880 | CLOSED |
| #1904 | scope drift: PR #1870 | CLOSED |
| #1905 | deduplicate test helper | CLOSED |
| #1906 | exchange wrapper unit tests | CLOSED |
| #1908 | squash merge verification | CLOSED |
| #1909 | browser test root causes | CLOSED |
| #1910 | end-to-end browser proving | OPEN |
| #1911 | sort hand by suit/bower | CLOSED |
| #1912 | analyst dispatch proving | OPEN |
| #1913 | score bug: wrong team set | CLOSED |
| #1914 | trick leader indicator | CLOSED |
| #1915 | show winning card | CLOSED |
| #1916 | comments and leaderboard tabs | OPEN |
| #1917 | glutton strategy revamp | OPEN |
| #1918 | exhaustive bid/outcome testing | CLOSED |
| #1919 | add flex-d lane | CLOSED |
| #1920 | auto-accept permissions | CLOSED |
| #1926 | data capture pipeline | CLOSED |
| #1928 | seat labels "Seat N" | CLOSED |
| #1930 | moon exchange reveal test | OPEN |
| #1931 | document permission pattern | OPEN |
| #1932 | review lane permission stalls | OPEN |
| #1937 | follow-up for PR #1935 | OPEN |
| #1938 | follow-up for PR #1936 | OPEN |
| #1940 | follow-up for PR #1925 | OPEN |
| #1947 | model economy rate-limit handling | OPEN |
| #1951 | orphaned pytest/make processes | OPEN |
| #1960 | follow-up for PR #1955 | OPEN |
| #1962 | follow-up for PR #1961 | OPEN |

**Created count verification:** 15 closed + 14 open = **29 issues** (matches `gh issue list --search 'created:2026-03-27' --limit 100 --state all`)

---

## Open Issues at Session End (19)

### Pre-Existing (5)

| # | Category | Title | Notes |
|---|----------|-------|-------|
| #1288 | platform | Codex comment ingestion bridge | Dormant, Phase 5+ scope |
| #1824 | platform | Telegram instance competition | PRs #1945/#1946 shipped mitigations; live fleet verification needed |
| #1826 | platform | Platform-9a remote alert/ack | 4 PRs shipped (parts 1-4); E3/E4/E7/E9 exit criteria remain |
| #1852 | platform | Playwright MCP | Needs architectural decision |
| #1887 | platform | Telegram elapsed-time proving | Requires live fleet run |

### Created Today, Still Open (14)

| # | Category | Title | Priority |
|---|----------|-------|----------|
| #1910 | browser | End-to-end browser proving | HIGH (requires human) |
| #1912 | platform | Analyst dispatch proving | MEDIUM (self-validates during fleet runs) |
| #1916 | browser | Comments and leaderboard tabs | LOW (needs user design input) |
| #1917 | research | Glutton strategy revamp | LOW (experiment design doc shipped) |
| #1930 | browser | Moon exchange reveal test | MEDIUM (review follow-up) |
| #1931 | platform | Document permission pattern | LOW (review follow-up) |
| #1932 | platform | Review lane permission stalls | MEDIUM (blocks autonomous review) |
| #1937 | process | Follow-up for PR #1935 | LOW (convention) |
| #1938 | process | Follow-up for PR #1936 | LOW (convention) |
| #1940 | process | Follow-up for PR #1925 | LOW (convention) |
| #1947 | platform | Model economy rate-limit handling | HIGH (blocks large fleet runs) |
| #1951 | platform | Orphaned pytest/make processes | HIGH (resource leak) |
| #1960 | process | Follow-up for PR #1955 | LOW (convention) |
| #1962 | process | Follow-up for PR #1961 | LOW (convention) |

---

## Operational Learnings

### 1. API Rate Limits (#1947)

At the ~5h mark with 11 parallel lanes, API rate limits were hit. With each
lane making concurrent API calls, aggregate volume exceeded single-subscription
capacity.

**Impact:** Lanes slowed; some tasks took longer than expected.
**Mitigation needed:** Lane-level backoff + jitter, and/or subscription failover.

### 2. Orphaned Process Leak (#1951)

Lanes spawn background `pytest` and `make check` processes. When a lane
completes or moves to a new task, these processes continue running. During a
5-hour run, 33 orphaned pytest processes were observed consuming 100MB+ each.

**Impact:** System memory pressure during late waves.
**Mitigation needed:** Process cleanup on task completion or lane reset.

### 3. Review Lane Permission Stalls (#1932)

The review lane repeatedly hit permission/auth prompts requiring manual
approval, stalling the autonomous review loop.

**Impact:** Reviews backed up, some PRs merged with advisory-only review.
**Mitigation needed:** Widen auto-accept patterns for review-specific tools.

### 4. Browser PR Serial Merge Bottleneck

The 4 browser PRs in Wave 0 shared 6 hotspot files and required serial merge
with rebases between each. This consumed ~55 minutes and was the session's
critical path bottleneck.

**Learning:** Future fleet runs should avoid dispatching overlapping-scope PRs
to different lanes. Group related template/CSS changes into a single lane or
use the analyst lane to pre-merge overlapping work.

### 5. Fleet Run Plan Accuracy

The fleet run plan (dispatched to analyst-a) estimated 46 PRs across 6 waves.
Actual: 29 fleet-run PRs across 4 waves. The plan was optimistic on later
waves because:
- Wave 2 was smaller than planned (2 vs 9 PRs)
- Wave 3 was larger but combined elements of planned waves 3-5
- Waves 4-5 were absorbed into the expanded Wave 3

**Learning:** Plan for 30-35 PRs in a single-session fleet run. 40+ requires
a ~8-10 hour active window with no bottlenecks.

---

## Next Session Startup Sequence

### 1. Recover Context

```bash
# Read memory and recent session handoff
cat MEMORY.md
cat plans/sessions/2026-03-27_fleet-run-session-handoff.md
```

### 2. Verify Main is Green

```bash
git fetch origin main && git log --oneline -5 origin/main
gh pr list --state open  # Check for any stuck PRs
```

### 3. Priority Work (User-Dependent)

| Priority | Item | Reason |
|----------|------|--------|
| P0 | #1910 -- browser proving run | Many features shipped but not end-to-end verified |
| P0 | #1947 -- rate-limit handling | Blocks next fleet run at scale |
| P0 | #1951 -- orphaned process cleanup | Blocks long fleet runs |
| P1 | #1824/#1826 -- Platform-9a completion | 4 PRs shipped; exit criteria E3/E4/E7/E9 remain |
| P1 | #1932 -- review lane permissions | Blocks autonomous review loop |
| P2 | Convention follow-ups (#1937, #1938, #1940, #1960, #1962) | Mechanical; can batch-dispatch |

### 4. Autonomous Backlog (No User Input Needed)

- Convention follow-ups: 5 issues (#1937, #1938, #1940, #1960, #1962)
- Review follow-ups: #1930, #1931
- Platform-9a wiring: E3 (MCP reply call), E4/E7 (live ack consumer)
- Platform-10: Additional adapter integration work

### 5. User-Dependent Work

- #1910 -- End-to-end browser proving (requires human browser interaction)
- #1916 -- Leaderboard/comments design (requires user vision input)
- #1887 -- Telegram elapsed-time proving (requires live fleet observation)
- Production deployment authorization

---

## Restart Notes

- **Main branch HEAD:** `921ece28` (`fix(ops): report save failures as ack failures`)
- **Open PRs:** 0 (all 6 from session start merged; no new ones open)
- **Checkpoints:** Reconciled via PR #1953
- **MEMORY.md:** Needs refresh for this session (not yet updated)
- **Fleet run plan:** `plans/sessions/2026-03-27_fleet-run-plan.md` (committed to PR #1921 branch; should be merged or filed separately if the analyst branch is stale)
