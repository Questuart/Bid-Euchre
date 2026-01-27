# AI Assistant Quick Start

## Repository Purpose
Bid Euchre simulator + strategy framework + ML training pipeline.

## Essential Commands
```bash
make check    # Run before any PR (repo-lint + ruff + pytest)
make help     # See all available targets
```

## Do NOT Read (outdated/irrelevant)
- `docs/archive/` — Historical, may contradict current docs
- `experiments/_deprecated/` — Legacy, frozen code
- `data/runs/` — Generated outputs (gitignored)

## Read By Task Type

| Task | Start Here |
|------|-----------|
| Any code changes | [docs/02_agent/AGENTS.md](docs/02_agent/AGENTS.md) |
| Understanding game rules | [docs/01_core/RULES.md](docs/01_core/RULES.md) |
| Running experiments | [experiments/README.md](experiments/README.md) |
| Adding strategies | [src/bid_euchre/strategy/](src/bid_euchre/strategy/) |
| Training models | [docs/01_core/BIDDING_MODEL.md](docs/01_core/BIDDING_MODEL.md) |
| Known issues/gaps | [docs/03_TODO/CODEBASE_CONSISTENCY.md](docs/03_TODO/CODEBASE_CONSISTENCY.md) |

## Module Quick Reference (src/bid_euchre/)

| Module | Purpose |
|--------|---------|
| `core/` | Card primitives, rules, trick resolution (DO NOT modify without tests) |
| `sim/` | Simulation loop, deterministic deal generation |
| `strategy/` | Bot policies — bidding + play strategies |
| `features/` | Hand feature extraction for ML |
| `models/` | ML model implementations |
| `datasets/` | Dataset collectors (bidding, bidless) |
| `analysis/` | Statistical analysis utilities |
| `reporting/` | Report generation and metrics |
| `logging/` | JSONL game event logging |
| `experiments/` | Config parsing and structures |

## Config Locations

| Path | Contents |
|------|----------|
| `experiments/configs/` | Individual experiment YAML files |
| `experiments/suites/` | Batched experiment definitions |
| `experiments/configs/INDEX.md` | Config directory index |

## Key Contracts (docs/01_core/)
- **RULES.md** — Game rules, scoring, legality
- **ARCHITECTURE.md** — System design, module boundaries
- **REPRODUCIBILITY.md** — Seeding, determinism requirements
- **DATA_CONTRACT.md** — Logging schema, field definitions
