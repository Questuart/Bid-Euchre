# Review Checklist — Rule Reference

Each check ID used in the `/reviewing-changes` skill is defined here with anti-patterns, correct patterns, and source rules.

---

## BLOCK Rules (must fix)

### C1 — Unseeded Randomness

**Source:** `.claude/rules/20_determinism.md`, `docs/01_core/REPRODUCIBILITY.md`

**Anti-pattern:**
```python
# Global RNG — breaks determinism
import random
random.shuffle(cards)

# Unseeded local RNG — non-reproducible
rng = random.Random()
```

**Correct:**
```python
# Seeded local RNG — deterministic
rng = random.Random(seed)
rng.shuffle(cards)
```

**Why it blocks:** Same seed + same config must produce identical results. Global or unseeded RNG breaks this invariant.

---

### C2 — Falsy Numeric Guard

**Source:** MEMORY.md "Key Patterns → Code"

**Anti-pattern:**
```python
# 0.0 is falsy — this silently replaces valid zeros with the fallback
x = x or 0.0
score = score or default_score
```

**Correct:**
```python
# Explicit None check preserves valid zero values
x = x if x is not None else 0.0
score = score if score is not None else default_score
```

**Why it blocks:** Metrics like `net_eppd` can legitimately be `0.0`. The `or` pattern silently replaces them, producing incorrect results.

---

### N1 — Missing Contract-Type Facet

**Source:** MEMORY.md "Key Rules → Contract-Type Faceting"

**Anti-pattern:**
```python
# Pooling all contract types into one chart
df.groupby('strategy')['tricks_won'].mean().plot(kind='bar')
```

**Correct:**
```python
# Faceted by contract_type
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, ct in zip(axes, ['suit', 'high', 'low']):
    subset = df[df['contract_type'] == ct]
    subset.groupby('strategy')['tricks_won'].mean().plot(kind='bar', ax=ax)
    ax.set_title(ct)
```

**Why it blocks:** Suit, high, and low contracts have fundamentally different dynamics. Pooling hides confounders.

---

### N2 — Collapsed Matchup Table

**Source:** MEMORY.md "Key Rules → Matchup Team Breakout"

**Anti-pattern:**
```python
# Single row per matchup — hides team asymmetry
matchup_summary = df.groupby('matchup')['tricks_won'].mean()
```

**Correct:**
```python
# Separate rows for team0 and team1
matchup_summary = df.groupby(['matchup', 'team'])['tricks_won'].mean()
```

**Why it blocks:** In comparator (self-play) runs, only one team bids. Collapsing teams hides this asymmetry.

---

### X3 — Merge Artifacts

**Source:** General quality

**Anti-pattern:**
```python
<<<<<<< HEAD
old_code()
=======
new_code()
>>>>>>> feature-branch

# TODO: remove before merge
debug_dump(state)

# Old approach (keeping for reference)
# def old_function():
#     ... 15 lines of commented-out code ...
```

**Correct:** Remove all merge markers, TODO-remove comments, and large commented-out blocks before merging.

**Why it blocks:** These are accidental artifacts that should never reach main.

---

## WARN Rules (recommend fixing)

### C3 — Gate Check Ordering

**Source:** MEMORY.md "Key Patterns → Gate Design"

**Anti-pattern:**
```python
# PASS before checking failure conditions — wrong order
def check(data):
    if data.is_valid:
        return GateResult.PASS
    if data.is_missing:
        return GateResult.SKIP  # Should have been checked first
    return GateResult.FAIL
```

**Correct:**
```python
# Most-restrictive first: SKIP (can't evaluate) → FAIL (violation) → PASS
def check(data):
    if data.is_missing:
        return GateResult.SKIP
    if not data.is_valid:
        return GateResult.FAIL
    return GateResult.PASS
```

**Why it warns:** SKIP means "can't evaluate" (non-blocking). FAIL means "found violation" (blocks). Returning PASS before checking for SKIP/FAIL can miss violations.

---

### C4 — Function Complexity

**Source:** General code quality

**Threshold:** Functions >50 lines or nesting depth >4 levels.

**Why it warns:** Long or deeply nested functions are harder to test, review, and maintain. Consider extracting helper functions.

---

### N3 — Claim Without Statistical Test

**Source:** `.claude/rules/05_rigor.md`

**Anti-pattern:**
```python
# "Strategy A is better" based on visual inspection only
plt.boxplot([strategy_a_data, strategy_b_data])
plt.title("Strategy A outperforms B")
```

**Correct:**
```python
# Statistical test accompanies the visual
t_stat, p_value = ttest_ind(strategy_a_data, strategy_b_data)
plt.boxplot([strategy_a_data, strategy_b_data])
plt.title(f"A vs B (t={t_stat:.2f}, p={p_value:.3f})")
```

**Why it warns:** Rigor policy requires hypothesis tests with p-values, not just visual inspection.

---

### T1 — Untested Behavior Change

**Source:** `.claude/rules/40_prs.md`

**Check:** If files in `src/bid_euchre/` have behavior changes (not just refactoring), there should be corresponding changes in `tests/`.

**Why it warns:** Behavior changes without tests can silently regress.

---

### X1 — Scope Drift

**Source:** `.claude/rules/40_prs.md` ("one concept per PR")

**Check:** Changes span 3+ unrelated modules (e.g., `core/` + `reporting/` + `notebooks/` with no clear connection).

**Why it warns:** May indicate scope drift — the PR might be doing too many things.

---

### X2 — Undocumented Contract Change

**Source:** `.claude/rules/30_data_contract.md`

**Check:** Changes to core rules, scoring, logging schema, or metrics without corresponding doc updates.

**Affected docs:**
- `docs/01_core/RULES.md` — game rules, trick resolution
- `docs/01_core/DATA_CONTRACT.md` — logging fields, schemas
- `docs/01_core/METRICS.md` — metrics, aggregation

**Why it warns:** Contract changes without doc updates cause drift between code and documentation.
