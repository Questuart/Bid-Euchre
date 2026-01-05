# Development

## Pre-commit

### Install
```bash
pip install -e ".[dev]"
pre-commit install
```

### Run on all files
```bash
pre-commit run --all-files
```

## Notes

- Hooks run automatically on commit once installed.
- Ruff lint uses the repo Ruff settings in `pyproject.toml`.
- Some paths are excluded (e.g., `data/`, `experiments/_deprecated/`).
