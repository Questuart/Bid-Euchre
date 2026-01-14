# Teacher Baseline Roster Manifest (v1)

## Purpose

The teacher baseline roster is a machine-readable manifest that defines canonical bidding baselines for comparative evaluation. It serves as the single source of truth for baseline definitions, ensuring consistent configuration across experiments like `bid_eval_tiny`.

The roster enables:
- **Deterministic ordering**: Baselines are sorted by ID for reproducible comparisons
- **Validation**: Import paths and artifact existence are verified at load time
- **Versioning**: Schema changes are versioned to prevent silent breaks
- **Experiment consumption**: Configs reference baselines by ID rather than duplicating implementation details

## Schema v1

The manifest uses YAML format with the following top-level structure:

```yaml
roster_version: "1"              # Must be "1"
created: "2026-01-13"           # ISO date string
description: "..."              # Human-readable description
baselines:                      # Array of baseline definitions
  - id: "unique_id"
    display_name: "Human Readable Name"
    kind: "policy" | "artifact_policy"
    import_path: "module.path.ClassName"
    params: {}                  # Optional parameters dict
    notes: "..."                # Optional documentation
```

### Field Requirements

#### Required Fields
- `roster_version`: Must be exactly `"1"`
- `created`: ISO date string (YYYY-MM-DD format)
- `description`: Brief description of the roster's purpose
- `baselines`: Non-empty array of baseline definitions

#### Per-Baseline Required Fields
- `id`: Unique identifier (lowercase, underscores allowed)
- `display_name`: Human-readable name for reports
- `kind`: Either `"policy"` (for heuristic bidders) or `"artifact_policy"` (for model-based bidders)
- `import_path`: Python import path to the bidder class

#### Optional Fields
- `params`: Dictionary of constructor parameters
- `notes`: Free-form documentation string

### Validation Rules

1. **No duplicate IDs**: All baseline IDs must be unique within the roster
2. **Import validation**: All `import_path` values must resolve to callable classes
3. **Artifact validation**: `artifact_policy` baselines must have `params.artifact_path` pointing to an existing file
4. **Version locking**: Only `roster_version: "1"` is supported

## Deterministic Ordering Rules

Baselines are sorted by `id` field for consistent experiment ordering:

```python
# Baselines are sorted lexicographically by ID
sorted_baselines = sorted(roster['baselines'], key=lambda b: b['id'])
```

This ensures reproducible comparisons across runs and environments.

## Adding New Baselines Safely

### Do's
- Use descriptive, unique IDs (e.g., `strict_raiser`, `artifact_bidder`)
- Test import paths manually before adding
- Include meaningful `notes` for future maintainers
- Use `params` dict for configuration instead of hardcoding
- Validate with `scripts/validate_teacher_roster_manifest.py` before committing

### Don'ts
- Don't change existing IDs (breaks experiment reproducibility)
- Don't remove baselines without updating dependent configs
- Don't add untested import paths
- Don't modify `roster_version` without schema changes
- Don't use non-deterministic ordering in configs

## How bid_eval_tiny Consumes the Roster

### Configuration
The experiment config references the roster and selects specific baselines:

```yaml
experiment_name: bid_eval_tiny
strategy_roster_path: experiments/baselines/teacher_roster_v1.yaml
include_baselines:
  - strict_raiser
  - heuristics
  - artifact_bidder
```

### Runtime Loading
The config loader (`src/bid_euchre/experiments/config.py`) performs these steps:

1. **Load roster**: Uses `load_teacher_roster()` to validate and load the YAML
2. **Validate selection**: Ensures all `include_baselines` IDs exist in the roster
3. **Convert to configs**: Transforms roster entries into `BiddingPolicyConfig` objects:
   - `policy` kind → Direct class instantiation
   - `artifact_policy` kind → `ArtifactBidder` with `artifact_path` parameter
4. **Sort ordering**: Applies deterministic ID-based sorting

### Commands

Run the baseline comparison suite:

```bash
# Full suite with roster-driven baseline selection
PYTHONPATH=src python scripts/run_suite.py --suite experiments/suites/bid_eval_tiny.yaml
```

Validate roster integrity:

```bash
# Check schema, imports, and artifact paths
PYTHONPATH=src python scripts/validate_teacher_roster_manifest.py experiments/baselines/teacher_roster_v1.yaml
```

View available baselines:

```bash
# Roster file location
cat experiments/baselines/teacher_roster_v1.yaml
```

## Current Baselines

As of v1, the roster defines these baselines:

- **`always_pass`**: Always passes in auctions (negative control)
- **`strict_raiser`**: Bids 3S initially, raises by 1 each time
- **`heuristics`**: Rule-based bidding using hand evaluation
- **`fixed_bidder`**: Fixed-bid baseline for controlled experiments
- **`artifact_bidder`**: Linear regression model with greedy play

## Schema Evolution

When adding new schema versions:
1. Increment `roster_version` (e.g., `"2"`)
2. Update validation code in `teacher_roster.py`
3. Maintain backward compatibility where possible
4. Update this documentation

The v1 schema is locked and will only accept compatible changes that don't break existing configs.
