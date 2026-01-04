# Code Changes for RULES.md Consistency

**Created:** 2026-01-04  
**Source:** RULES.md consistency review  
**Status:** Not yet implemented

This document tracks code changes needed to align the codebase with RULES.md specifications. These were identified during consistency review but deferred for future implementation.

---

## 🔴 Priority 1: CRITICAL

### 1.1 Implement Scoring System (Section 6)

**Issue:** RULES.md Section 6 describes a comprehensive per-hand points scoring system, but code only tracks tricks.

**Current state:**
- `simulation.py` only returns `(t0, t1)` trick counts
- No points calculation
- No "make-bid" determination
- No concept of "declaring team" vs "defending team" beyond partnership

**Required implementation:**
```python
# Add to simulation.py after tricks are counted
def calculate_points(
    tricks_declaring: int,
    tricks_defending: int,
    bid_tricks: int,
    declarer_team: int
) -> Tuple[int, int]:
    """Calculate points per RULES.md Section 6.3"""
    points_defending = tricks_defending
    
    if tricks_declaring >= bid_tricks:  # Make
        points_declaring = tricks_declaring
    else:  # Set
        points_declaring = -bid_tricks
    
    # Map to team0/team1
    if declarer_team == 0:
        return points_declaring, points_defending
    else:
        return points_defending, points_declaring
```

**Files to modify:**
- `src/bid_euchre/sim/simulation.py` - Add scoring logic
- `src/bid_euchre/logging/game_logger.py` - Log points fields
- Tests - Add scoring validation tests

**Effort:** 2-3 hours  
**Impact:** HIGH - Required for proper strategy evaluation

**Blockers:** None - can be implemented independently

---

### 1.2 Add Auction Transcript Logging (Section 8.2)

**Issue:** RULES.md Section 8.2 requires logging all 4 bids/passes, but current code only logs final result.

**Current state:**
- Only `winning_bid` and `bidder_position` logged
- No per-player bid actions
- No `redeal_flag` field
- Cannot replay or audit bidding decisions

**Required implementation:**

Create new log record type:
```python
@dataclass
class BidActionRecord:
    """Record for a single bid action in the auction."""
    schema_version: int
    event: str = "bid_action"
    run_id: str
    deal_id: int
    seat: int
    action: str  # "PASS" or "BID"
    tricks_bid: Optional[int]  # null if PASS
    contract_type: Optional[str]  # null if PASS
    trump: Optional[str]  # null if PASS or non-suit
    current_high_tricks: int  # After this action
    timestamp: str
```

Modify `simulation.py` to log each bid action during the auction loop.

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Add `BidActionRecord`, `log_bid_action()`
- `src/bid_euchre/sim/simulation.py` - Call logger in bidding loop
- Increase `SCHEMA_VERSION` to 6

**Effort:** 1-2 hours  
**Impact:** HIGH - Essential for debugging bidding strategies

**Blockers:** None

---

## 🟡 Priority 2: HIGH

### 2.1 Implement Card Instance IDs (Section 8.3)

**Issue:** RULES.md requires `card_instance_id` to distinguish duplicate cards, but this isn't implemented.

**Current state:**
- `Card` is just `(suit, rank)` - no instance ID
- Duplicate cards indistinguishable in logs
- "Earlier play wins" tie-break cannot be audited

**Required implementation:**

1. Modify `Card` dataclass:
```python
@dataclass(frozen=True)
class Card:
    suit: str  # "C", "D", "H", "S"
    rank: str  # "T", "J", "Q", "K", "A"
    instance_id: int = 0  # Unique within a hand
```

2. Assign IDs when dealing:
```python
def deal_hands_with_ids(deck: List[Card], ...) -> List[List[Card]]:
    # Assign instance_id 0-39 to cards based on deal order
    for i, card in enumerate(deck):
        deck[i] = Card(card.suit, card.rank, instance_id=i)
    # ... deal as normal
```

3. Update logger to include instance_id in all card references

**Files to modify:**
- `src/bid_euchre/core/cards.py` - Add `instance_id` field
- `src/bid_euchre/core/cards.py` - Update `deal_hands()`
- `src/bid_euchre/logging/game_logger.py` - Log instance IDs
- `src/bid_euchre/sim/simulation.py` - Pass through instance IDs
- ALL test files - Update Card construction

**Effort:** 2-3 hours (plus test updates)  
**Impact:** HIGH - Required for deterministic replay

**Blockers:** This will break existing Card construction everywhere. Consider making `instance_id` optional with default=0 for backward compatibility.

---

### 2.2 Add `redeal_flag` to Logger (Section 8.2)

**Issue:** RULES.md requires explicit `redeal_flag` field in hand logs.

**Current state:**
- Misdeals logged but no explicit flag
- Implicit: `leader=-1` or `winning_bid=0` indicates misdeal
- Not clear from log schema

**Required implementation:**

Add field to `HandEndRecord`:
```python
@dataclass
class HandEndRecord:
    # ... existing fields
    redeal_flag: bool = False  # True if all-pass misdeal
```

Update `simulation.py` misdeal handling to set `redeal_flag=True`.

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Add field to `HandEndRecord`
- `src/bid_euchre/sim/simulation.py` - Pass `redeal_flag=True` for misdeals
- Increase `SCHEMA_VERSION` to 6 (or 7 if 1.2 is done first)

**Effort:** 15-30 minutes  
**Impact:** MEDIUM - Improves log clarity

**Blockers:** None

---

## 🟢 Priority 3: MEDIUM

### 3.1 Standardize Terminology: bidder → declarer

**Issue:** Mixed terminology - docs use "declarer", code uses "bidder".

**Current state:**
- `bidder_position` in code
- `declarer_seat` in RULES.md
- Inconsistent but functionally equivalent

**Recommendation:** Rename for consistency with standard trick-taking game terminology.

**Files to modify (estimate 10+ occurrences each):**
- `src/bid_euchre/sim/simulation.py` - `bidder_position` → `declarer_seat`
- `src/bid_euchre/logging/game_logger.py` - `bidder_position` → `declarer_seat`
- All experiment scripts that reference this field
- All test files

**Effort:** 30-60 minutes (careful find/replace)  
**Impact:** MEDIUM - Improves clarity and consistency

**Blockers:** Will break any analysis scripts that read logs with `bidder_position`

---

### 3.2 Standardize Terminology: dealer_index → dealer_seat

**Issue:** Mixed terminology - docs use "dealer_seat", code uses "dealer_index" and "dealer_position".

**Current state:**
- `dealer_index` in `simulation.py`
- `dealer_position` in `game_logger.py`
- `dealer_seat` in RULES.md

**Recommendation:** Unify on `dealer_seat`.

**Files to modify:**
- `src/bid_euchre/sim/simulation.py` - `dealer_index` → `dealer_seat`
- `src/bid_euchre/logging/game_logger.py` - `dealer_position` → `dealer_seat`

**Effort:** 15-30 minutes  
**Impact:** LOW-MEDIUM - Improves consistency

**Blockers:** Same as 3.1

---

### 3.3 Standardize Terminology: bid terminology

**Issue:** Multiple terms for the same bidding concepts.

**Current state:**
- `bid`, `bid_amount`, `tricks_bid` all used for the same thing
- `trump`, `trump_suit` used interchangeably

**Recommendation:** Standardize on RULES.md terms:
- Use `tricks_bid` for the number (not `bid_amount`)
- Use `trump` consistently (not `trump_suit`)

**Files to modify:**
- `src/bid_euchre/strategy/base.py` - Docstring says `bid_amount`
- Various strategy files
- Logger docstrings

**Effort:** 15-30 minutes  
**Impact:** LOW - Mostly comments/docstrings

**Blockers:** None (mostly documentation)

---

## 🔵 Priority 4: LOW

### 4.1 Rename `contract` → `contract_type` in Logger

**Issue:** Logger parameter is named `contract` but actually holds `contract_type` value.

**Current state:**
```python
def log_hand_end(
    self,
    # ...
    contract: str,  # Actually contract_type ("suit", "high", "low")
    trump: Optional[str],
```

**Recommendation:** Rename for clarity:
```python
def log_hand_end(
    self,
    # ...
    contract_type: str,  # "suit", "high", "low"
    trump: Optional[str],
```

**Files to modify:**
- `src/bid_euchre/logging/game_logger.py` - Rename parameter
- `src/bid_euchre/sim/simulation.py` - Update call sites
- All experiment scripts that use the logger

**Effort:** 10-15 minutes  
**Impact:** LOW - Improves clarity

**Blockers:** None

---

### 4.2 Log Computed Scoring Fields (Section 8.5)

**Issue:** Once scoring is implemented (1.1), should log derived fields.

**Required after 1.1:**
- `tricks_declaring`, `tricks_defending`
- `points_declaring_team`, `points_defending_team`

**Effort:** 5-10 minutes (after 1.1 is done)  
**Impact:** LOW - Nice to have, but derivable

**Blockers:** Depends on 1.1

---

## 📋 Implementation Priority Order

### **Suggested Order:**

1. **Quick win (30 min):** 2.2 - Add `redeal_flag`
2. **High value (2 hrs):** 1.2 - Auction transcript logging
3. **Foundation (3 hrs):** 1.1 - Implement scoring system
4. **Big effort (3 hrs):** 2.1 - Card instance IDs (when needed for replay)
5. **Cleanup (1 hr):** 3.1-3.3 - Terminology standardization

### **Or defer all for now** if current system is working for your analysis.

---

## 🔍 Impact Summary

| Change | Files | Effort | User Impact |
|--------|-------|--------|-------------|
| 1.1 Scoring | 3-5 | 2-3 hrs | HIGH - Can properly evaluate strategies |
| 1.2 Auction logging | 2 | 1-2 hrs | HIGH - Can debug bidding |
| 2.1 Card instance IDs | 10+ | 2-3 hrs | MEDIUM - Needed for perfect replay |
| 2.2 Redeal flag | 2 | 15 min | LOW - Improves log clarity |
| 3.1-3.3 Terminology | 10+ | 1-1.5 hrs | LOW - Improves consistency |
| 4.1-4.2 Minor renames | 3-5 | 30 min | LOW - Polishing |

**Total estimated effort:** 8-12 hours for all changes

---

## ✅ Completion Checklist

When implementing any of these:

- [ ] Update RULES.md if needed
- [ ] Update this TODO file (mark as completed or move to archive)
- [ ] Write or update tests
- [ ] Update schema version if changing logs
- [ ] Update relevant documentation
- [ ] Run full test suite
- [ ] Consider backward compatibility

---

**Questions or blockers?** Add notes here and discuss before implementing.
