# Reproducibility

## Run metadata contract

Every experiment run writes `data/runs/<run_id>/meta.json` containing:
- Git SHA of the codebase
- Config file path and SHA256 hash
- UTC timestamp
- Seed and run parameters

This ensures runs can be traced and reproduced.

**Schema documentation:** See `docs/01_core/schemas/meta_json.md`.
