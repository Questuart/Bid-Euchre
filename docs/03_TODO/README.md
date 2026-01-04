# TODO Directory

**Purpose:** Track future work and technical debt

This directory contains documents tracking work that needs to be done but isn't urgent enough to block current development.

---

## 📋 Current TODOs

### Active
- **CODEBASE_CONSISTENCY.md** - Code changes needed to align with RULES.md specifications (8-12 hours estimated)

### Completed
_(None yet - move completed items here with completion date)_

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
1. Move file to `_completed/` subdirectory
2. Add completion date and commit hash
3. Update this README

### Prioritization
- 🔴 **Critical:** Blocks production use
- 🟡 **High:** Important for correctness
- 🟢 **Medium:** Improves consistency
- 🔵 **Low:** Nice to have

---

## 🎯 Current Focus

The primary TODO is **CODEBASE_CONSISTENCY.md** which tracks alignment between RULES.md and implementation:

**Quick wins (< 1 hour):**
- Add `redeal_flag` to logger (15 min)
- Rename `contract` → `contract_type` (15 min)

**High value (2-3 hours each):**
- Auction transcript logging
- Scoring system implementation

**Can defer:**
- Card instance IDs (complex, needed for perfect replay)
- Terminology standardization (polish)

---

**See individual TODO files for details.**
