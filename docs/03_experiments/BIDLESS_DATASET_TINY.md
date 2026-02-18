# Bidless Dataset Tiny Suite

The `bidless_dataset_tiny` suite provides quick collection of hand-level data without bidding decisions for training dataset generation.

## Purpose

Generate small, deterministic JSONL datasets containing hand features for:
- Quick iteration on training scripts
- Debugging dataset collection pipelines
- Baseline dataset generation for future ML training

## Usage

Run a small bidless dataset experiment using the canonical runner:

```bash
uv run python experiments/run_experiment.py \
    --config experiments/configs/bidless_dataset_tiny.yaml \
    --seed 42
```

This generates a JSONL file containing hand-level data records under `data/runs/`.

## Output Structure

Each JSONL line contains a hand record with:
- `hand_id`: Unique identifier for the hand
- `cards`: List of card representations
- `features`: Computed hand features (trump strength, offsuit control, etc.)
- `seed`: Random seed used for generation
- `run_id`: Unique run identifier

## Dependencies

- Requires PR 140 (bidless dataset collector types/paths)
- Uses hand evaluation features from `src/bid_euchre/features/hand_eval.py`
- Output format is JSONL for easy streaming and training consumption

## Performance

- Suite runs in under ~2 minutes locally with n_per=10
- Deterministic output for same seed
- Small dataset size suitable for quick iteration
