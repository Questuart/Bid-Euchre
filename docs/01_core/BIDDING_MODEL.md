# Bidding Model Artifact Schema (v1)

## Overview

Bidding model artifacts define a deterministic, JSON-serializable format for storing trained bidding models. This schema enables stable model persistence and interchange across different training runs and environments.

## Schema Definition

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Must be `"1"` (current schema version) |
| `model_type` | string | Model type identifier (e.g., `"linear_regression"`, `"random_forest"`) |
| `contract` | string | Target contract: `"C"`, `"D"`, `"H"`, `"S"`, `"HIGH"`, `"LOW"` |
| `model_params` | object | JSON-serializable model parameters |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | object | JSON-serializable metadata (creation time, description, etc.) |

## Contract Types

Contracts are represented as single strings matching the bidding protocol:

- `"C"`, `"D"`, `"H"`, `"S"`: Suit contracts (Clubs, Diamonds, Hearts, Spades)
- `"HIGH"`, `"LOW"`: Special contracts (no trump suit)

## JSON Requirements

All fields must be JSON-serializable:
- No Python objects, sets, or custom classes
- No `numpy` arrays (convert to lists)
- No `datetime` objects (use ISO strings)

## Example Artifact

```json
{
  "schema_version": "1",
  "model_type": "linear_regression",
  "contract": "H",
  "model_params": {
    "coefficients": [0.1, 0.2, -0.05],
    "features": ["trump_count", "high_card_points", "suit_length"],
    "intercept": 0.5
  },
  "metadata": {
    "created_at": "2024-01-01T00:00:00Z",
    "description": "Example bidding model for hearts contract",
    "training_data_size": 10000
  }
}
```

## API Reference

### `validate_artifact(obj: Dict[str, Any]) -> None`

Validates an artifact dictionary against the schema.

**Raises**: `ValueError` with descriptive message on validation failure.

### `load_artifact(path: str) -> Dict[str, Any]`

Loads and validates an artifact from a JSON file.

**Returns**: Validated artifact dictionary

**Raises**:
- `FileNotFoundError`: File doesn't exist
- `ValueError`: Invalid JSON or schema validation failure

### `dump_artifact(obj: Dict[str, Any], path: str) -> None`

Saves an artifact to a JSON file with stable formatting.

- Validates artifact before writing
- Uses `sort_keys=True, indent=2` for deterministic output
- Creates parent directories as needed

**Raises**:
- `ValueError`: Invalid artifact
- `OSError`: File system errors

## Validation Rules

1. **Required fields**: All fields in "Required Fields" must be present
2. **Schema version**: Must exactly equal `"1"`
3. **Model type**: Non-empty string
4. **Contract**: Must be one of the valid contract strings
5. **JSON serializable**: `model_params` and `metadata` must pass `json.dumps()`

## File Format

Artifacts are stored as UTF-8 encoded JSON files with:
- Sorted keys for deterministic output
- 2-space indentation
- Trailing newline
- ASCII-compatible encoding (`ensure_ascii=False`)

## Usage in Training Pipeline

```python
from bid_euchre.models.bidding_artifact import dump_artifact, load_artifact

# After training
artifact = {
    "schema_version": "1",
    "model_type": "linear_regression",
    "contract": "H",
    "model_params": trained_model_params,
    "metadata": {"accuracy": 0.85, "created_at": "2024-01-01T00:00:00Z"}
}

dump_artifact(artifact, "models/hearts_v1.json")

# Later, in inference
model_artifact = load_artifact("models/hearts_v1.json")
# Use model_artifact["model_params"] for inference
```

## Teacher Baseline Roster

The canonical "teacher baseline" roster consists of three deterministic bidding strategies that serve as training targets for imitation learning. These baselines establish a foundation for bidding model development and evaluation.

### Baseline Teachers

| Teacher | Description | Strategy |
|---------|-------------|----------|
| `strict_raiser` | StrictRaiserBidder | Simple raising strategy - bids if hand strength meets minimum threshold |
| `heuristics` | HeuristicsBidder | Rule-based heuristics (v1 baseline) - considers position, cards, and opponents |
| `fiveheadfred` | FiveHeadFred | Aggressive bidder - always bids 5 if legal, otherwise passes |

### Training Commands

Train each baseline teacher into a bidding artifact using `scripts/train_bidder.py`:

```bash
# Train strict_raiser teacher (default)
PYTHONPATH=src python scripts/train_bidder.py \
  --teacher strict_raiser \
  --contract S \
  --output data/artifacts/bidding_strict_raiser_S.json \
  --seed 42

# Train heuristics teacher
PYTHONPATH=src python scripts/train_bidder.py \
  --teacher heuristics \
  --contract S \
  --output data/artifacts/bidding_heuristics_S.json \
  --seed 42

# Train fiveheadfred teacher
PYTHONPATH=src python scripts/train_bidder.py \
  --teacher fiveheadfred \
  --contract S \
  --output data/artifacts/bidding_fiveheadfred_S.json \
  --seed 42
```

**Output Convention**: Artifacts follow `data/artifacts/bidding_<teacher>_<contract>.json` naming.

### Evaluation with `bid_eval_tiny`

Evaluate trained artifacts using the `bid_eval_tiny` suite:

```bash
# Run evaluation on a single artifact
PYTHONPATH=src python scripts/run_suite.py \
  --suite experiments/suites/bid_eval_tiny.yaml \
  --seed 42 \
  --n-per 20
```

**Suite Configuration**: The suite uses `experiments/configs/bid_eval_tiny.yaml` with auction mode (`contract_type: null`) and hand-level logging for risk metrics.

**Comparing Baselines**: Run `bid_eval_tiny` on each trained artifact to establish comparative performance. The suite generates structured logs enabling computation of risk-aware metrics (CVaR, downside variance).

### Pause Point: Regression Loops Deferred

**Regression/value modeling loops are intentionally paused after these baselines settle.**

Further bidding model development (neural networks, advanced regression, reinforcement learning) should wait until:
- Baseline teacher performance is well-characterized
- `bid_eval_tiny` evaluation metrics stabilize
- Comparative analysis between teachers is complete

This ensures new modeling approaches build on a solid foundation rather than introducing confounding variables during baseline establishment.

## Migration Notes

- **v1 is initial schema**: No migration path from earlier versions
- **Stability guarantee**: v1 artifacts will remain loadable in future versions
- **Extension strategy**: New fields may be added as optional in future versions
