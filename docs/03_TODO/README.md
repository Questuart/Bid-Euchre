# TODO Directory

**Purpose:** Track future work and technical debt

This directory contains documents tracking work that needs to be done but isn't urgent enough to block current development.

---

## 📋 Current TODOs

### Active
- **CODEBASE_CONSISTENCY.md** — Remaining "Later" items: dual outcome tracking, card instance IDs, separate strategy IDs, team-randomized comparator, strategy-centric metrics, terminology standardization
- REPO_REVIEW_2026-02-26.md — Latest review (from PR #449)

### Completed
- **CODEBASE_CONSISTENCY items 1-3** (2026-02-18): auction_transcript (schema v7), redeal_flag (schema v6), made_bid (schema v6) — all wired in PRs #361/#362

---

## 📝 How to Use This Directory

### Adding New TODOs
1. Create a descriptive markdown file: `FEATURE_NAME.md`
2. Include:
   - Problem description
   - Required changes
   - Estimated effort
   - Priority level
   - Blockers/dependencies
3. List it in this README under "Active"

### Completing TODOs
1. Move historical reviews to `docs/archive/reviews/`. Move completed plans to `plans/archive/`.
2. Add completion date and commit hash
3. Update this README

### Prioritization
- 🔴 **Critical:** Blocks production use
- 🟡 **High:** Important for correctness
- 🟢 **Medium:** Improves consistency
- 🔵 **Low:** Nice to have

---

## 🎯 Current Focus

The quick-wins and high-value items from CODEBASE_CONSISTENCY.md are resolved (auction transcript, redeal_flag, made_bid, scoring system). Remaining open items are in the "Later" section of CODEBASE_CONSISTENCY.md:

**Can defer:**
- Card instance IDs (complex, needed for perfect replay)
- Dual outcome tracking (trick_win vs points_win)
- Separate strategy IDs in logs
- Team-randomized comparator protocol
- Terminology standardization (polish)

---

**See individual TODO files for details.**
