# Repository Flow Diagram and Data Architecture

This document provides visual diagrams showing how modules flow together to generate data and how that data is organized, summarized, and analyzed in the Bid Euchre repository.

## Overview

The Bid Euchre repository implements a simulation framework for analyzing card game strategies. The system follows a clean separation of concerns:

- **Experiment execution** generates deterministic game data
- **Structured logging** captures game events and outcomes
- **Analysis tools** process outputs to extract insights
- **Notebooks** provide interactive exploration and visualization

All data generation is reproducible via explicit seeds, and outputs are strictly confined to `data/runs/<run_id>/` directories.

---

## Architecture Layers

```mermaid
flowchart TB
    subgraph Entry["Entry Points"]
        CLI["experiments/run_experiment.py<br/>(main CLI)"]
        Scripts["scripts/<br/>(generate_report.py, etc.)"]
    end

    subgraph Core["Core Library (src/bid_euchre/)"]
        direction TB

        subgraph Sim["sim/"]
            Deals["deals.py<br/>(deterministic deal generation)"]
            Simulation["simulation.py<br/>(game engine)"]
            Hooks["hooks.py<br/>(event system)"]
        end

        subgraph Strategy["strategy/"]
            BaseStrat["base.py<br/>(Strategy ABC)"]
            Strategies["greedy.py, glutton.py,<br/>random_strategy.py, etc."]
        end

        subgraph CoreMod["core/"]
            Cards["cards.py<br/>(Card, Suit, EUCHRE_DECK)"]
            Rules["rules.py<br/>(play_trick, legal_plays)"]
        end

        Scoring["scoring.py<br/>(standalone module)"]

        subgraph Logging["logging/"]
            GameLogger["game_logger.py<br/>(JSONL schema v5)"]
        end

        subgraph Reporting["reporting/"]
            Evaluator["evaluator.py"]
            Metrics["metrics.py"]
            Validation["validation.py"]
            Paths["paths.py"]
            Style["style.py"]
        end

        subgraph Diagnostics["diagnostics/"]
            Loaders["loaders.py"]
            HealthChecks["health_checks.py"]
            Validators["validators.py"]
            Stats["stats.py"]
            Charts["charts.py"]
            StrategyCharts["strategy_charts.py"]
        end

        subgraph Experiments["experiments/"]
            Config["config.py<br/>(YAML → dataclasses)"]
            Meta["meta.py<br/>(metadata generation)"]
            TeacherRoster["teacher_roster.py"]
        end

        subgraph Datasets["datasets/"]
            Bidding["bidding.py<br/>(auction dataset)"]
            Bidless["bidless.py<br/>(declared contract dataset)"]
        end

        subgraph Features["features/"]
            HandEval["hand_eval.py"]
            BidlessFeatures["bidless_hand_features.py"]
        end
    end

    subgraph Data["Data Storage (data/)"]
        direction TB
        Runs["runs/<run_id>/<br/>(run outputs)"]
        Fixtures["fixtures/<br/>(test data)"]
    end

    subgraph Analysis["Analysis Layer"]
        direction TB
        Notebooks["notebooks/phase0_bidless/*.ipynb<br/>(interactive exploration)"]
        Reports["Generated reports"]
    end

    CLI --> Config
    Config --> Simulation
    Deals --> Simulation
    Simulation --> Strategies
    Simulation --> CoreMod
    Simulation --> Scoring
    Simulation --> Hooks
    Hooks --> GameLogger
    GameLogger --> Runs
    CLI --> Evaluator
    Scripts --> Reporting
    Reporting --> Diagnostics
    Diagnostics --> Runs
    Notebooks --> Runs
    Notebooks --> Diagnostics
    Notebooks --> Reporting
```

---

## Experiment Execution Flow

```mermaid
flowchart TD
    Start([User runs:<br/>python experiments/run_experiment.py<br/>--config CONFIG --seed SEED])

    Start --> LoadConfig["Load YAML config<br/>(experiments/configs/*.yaml)"]
    LoadConfig --> ParseConfig["Parse & validate<br/>(config.py → StrategyConfig)"]

    ParseConfig --> CreateRunID["Generate run_id<br/>(timestamp-based)"]
    CreateRunID --> CreateRunDir["Create data/runs/&lt;run_id&gt;/"]

    CreateRunDir --> SaveEffectiveConfig["Save config_effective.yaml<br/>(resolved configuration)"]
    SaveEffectiveConfig --> SaveMeta["Save meta.json<br/>(schema v2: seed, timestamp, git_hash)"]

    SaveMeta --> InitLogger["Initialize GameLogger<br/>(JSONL schema v5)"]
    InitLogger --> InitStrategies["Instantiate strategies<br/>(GreedyStrategy, etc.)"]

    InitStrategies --> GenerateDeals["Generate deals<br/>(deals.derive_deal_from_index)"]

    GenerateDeals --> SimLoop["For each deal..."]

    subgraph Simulation["Simulation Loop (simulation.py)"]
        SimLoop --> PlayHand["play_single_hand()"]
        PlayHand --> Bidding["Bidding phase<br/>(fire BiddingDecisionEvent)"]
        Bidding --> PlayTricks["Play tricks<br/>(trick.py logic)"]
        PlayTricks --> Score["Score hand<br/>(scoring.py)"]
        Score --> LogEvents["Log events<br/>(HandEndEvent, etc.)"]
        LogEvents --> NextDeal{More deals?}
        NextDeal -->|Yes| PlayHand
    end

    NextDeal -->|No| Aggregate["Aggregate results<br/>(win rates, metrics)"]
    Aggregate --> SaveResults["Save results/&lt;strategy&gt;/*.json<br/>(suit_C.json, suit_D.json, high.json,<br/>low.json, auction.json)"]
    SaveResults --> SavePerf["Save perf.json<br/>(performance metrics)"]
    SavePerf --> SaveLogs["Save logs/*.jsonl<br/>(if --log-level != none)"]
    SaveLogs --> SaveDatasets["Save datasets/<br/>(if --emit-bidding-dataset or<br/>--emit-bidless-dataset)"]
    SaveDatasets --> End([Experiment complete<br/>Output: data/runs/&lt;run_id&gt;/])

    style Start fill:#e1f5ff
    style End fill:#e1ffe1
    style Simulation fill:#fff9e1
```

---

## Data Pipeline

```mermaid
flowchart LR
    subgraph Generation["Data Generation"]
        direction TB
        Seed["Seed (--seed N)"]
        Config["Config YAML"]
        Config --> ConfigEff["config_effective.yaml<br/>(written BEFORE simulation)"]
        ConfigEff --> Meta["meta.json<br/>(written BEFORE simulation)"]
        Seed --> Deals["Deterministic Deals<br/>(derive_deal_from_index)"]
        Meta --> Sim["Simulation Engine"]
        Deals --> Sim
        Sim --> Events["Event Stream<br/>(HandEndEvent, etc.)"]
    end

    subgraph Storage["Data Storage (data/runs/&lt;run_id&gt;/)"]
        direction TB
        Logs["logs/*.jsonl<br/>(conditional: --log-level)"]
        Results["results/&lt;strategy&gt;/*.json<br/>(suit_C, suit_D, high, low, auction)"]
        Perf["perf.json<br/>(performance metrics)"]
        Datasets["datasets/<br/>(conditional: --emit-*-dataset)"]
        Artifacts["artifacts/<br/>(model binaries)"]
        Reports["reports/<br/>(charts, figures)"]
    end

    subgraph Analysis["Analysis & Insights"]
        direction TB
        Reporting["Reporting Module<br/>(evaluator, metrics, validation)"]
        Diagnostics["Diagnostics Module<br/>(charts, stats, health)"]
        Notebooks["Jupyter Notebooks<br/>(phase0_bidless/*.ipynb)"]
    end

    Events --> Logs
    Events --> Results
    Events --> Perf
    Events --> Datasets

    Results --> Reporting
    Logs --> Diagnostics
    Results --> Diagnostics
    Datasets --> Diagnostics

    Logs --> Notebooks
    Results --> Notebooks
    Datasets --> Notebooks

    Reporting --> Reports
    Diagnostics --> Reports
    Notebooks --> Reports

    style Generation fill:#e1f5ff
    style Storage fill:#ffe1f5
    style Analysis fill:#e1ffe1
```

---

## Module Dependencies

```mermaid
flowchart TD
    subgraph External["External Entry Points"]
        RunExp["experiments/run_experiment.py"]
        GenReport["scripts/generate_report.py"]
        Notebooks["notebooks/*.ipynb"]
    end

    subgraph Core["Core Modules (src/bid_euchre/)"]
        direction TB

        ExpConfig["experiments/config.py"]

        SimDeals["sim/deals.py"]
        SimEngine["sim/simulation.py"]
        SimHooks["sim/hooks.py"]

        CoreCards["core/cards.py"]
        CoreRules["core/rules.py"]
        Scoring["scoring.py"]

        StratBase["strategy/base.py"]
        StratImpl["strategy/greedy.py<br/>strategy/glutton.py<br/>etc."]

        Logger["logging/game_logger.py"]

        RepEvaluator["reporting/evaluator.py"]
        RepMetrics["reporting/metrics.py"]
        RepValidation["reporting/validation.py"]

        DiagLoaders["diagnostics/loaders.py"]
        DiagCharts["diagnostics/charts.py"]
        DiagStats["diagnostics/stats.py"]
        DiagHealth["diagnostics/health_checks.py"]
        DiagValidators["diagnostics/validators.py"]
    end

    RunExp --> ExpConfig
    RunExp --> SimEngine
    RunExp --> Logger
    RunExp --> RepEvaluator

    ExpConfig --> StratImpl

    SimEngine --> SimDeals
    SimEngine --> SimHooks
    SimEngine --> StratBase
    SimEngine --> CoreRules
    SimEngine --> Scoring

    CoreRules --> CoreCards
    Scoring --> CoreCards

    StratImpl --> StratBase
    StratImpl --> CoreCards

    SimHooks --> Logger

    GenReport --> RepEvaluator
    GenReport --> RepMetrics

    RepEvaluator --> DiagHealth
    RepMetrics --> DiagStats

    Notebooks --> DiagCharts
    Notebooks --> DiagStats
    Notebooks --> DiagHealth
    Notebooks --> DiagLoaders

    DiagCharts --> DiagStats
    DiagHealth --> DiagValidators
    DiagValidators --> DiagStats

    style External fill:#e1f5ff
    style Core fill:#fff9e1
```

---

## Analysis Workflow

```mermaid
flowchart TD
    Start([Experiment completed<br/>data/runs/&lt;run_id&gt;/])

    Start --> LoadData["Load run outputs"]

    subgraph DataSources["Data Sources"]
        Meta["meta.json<br/>(seed, config, timestamp)"]
        Logs["logs/*.jsonl<br/>(structured events, conditional)"]
        Datasets["datasets/*<br/>(bidding, bidless, conditional)"]
        Results["results/&lt;strategy&gt;/*.json<br/>(aggregated metrics)"]
        Perf["perf.json<br/>(performance metrics)"]
    end

    LoadData --> Meta
    LoadData --> Logs
    LoadData --> Datasets
    LoadData --> Results
    LoadData --> Perf

    subgraph Analysis["Analysis Tools"]
        direction TB

        HealthChecks["Health Checks<br/>(diagnostics/health_checks.py)"]
        Stats["Statistical Analysis<br/>(diagnostics/stats.py)"]
        Charts["Visualization<br/>(diagnostics/charts.py)"]
    end

    Meta --> HealthChecks
    Datasets --> HealthChecks

    HealthChecks --> Validate{Data quality OK?}
    Validate -->|No| Alert["⚠️ Validation failed<br/>(sample size, bias, schema)"]
    Validate -->|Yes| Stats

    Datasets --> Stats
    Results --> Stats

    Stats --> Charts

    subgraph Notebooks["Interactive Notebooks"]
        direction TB
        Health["00_health_checks.ipynb<br/>(balance, distributions)"]
        Explore["01-04_charts.ipynb<br/>(feature analysis)"]
        Model["05+_model_dev.ipynb<br/>(ML experiments)"]
    end

    Charts --> Health
    Charts --> Explore
    Stats --> Health
    Stats --> Explore

    Datasets --> Model

    subgraph Outputs["Analysis Outputs"]
        direction TB
        ReportsOut["reports/<br/>(saved charts)"]
        Insights["Documented insights<br/>(README, docs)"]
    end

    Health --> ReportsOut
    Explore --> ReportsOut
    Model --> ReportsOut

    Health --> Insights
    Explore --> Insights
    Model --> Insights

    style Start fill:#e1f5ff
    style Alert fill:#ffe1e1
    style Outputs fill:#e1ffe1
```

---

## Data Organization Detail

```mermaid
flowchart TD
    subgraph DataRoot["data/"]
        direction TB

        subgraph Runs["runs/"]
            direction TB
            RunID["&lt;run_id&gt;/<br/>(e.g., 20260131_123456_abc123)"]

            subgraph RunContents["Run Contents"]
                MetaFile["📄 meta.json<br/>(written BEFORE simulation)"]
                ConfigFile["📄 config_effective.yaml<br/>(written BEFORE simulation)"]
                PerfFile["📄 perf.json<br/>(performance metrics)"]

                LogsDir["📁 logs/<br/>*.jsonl (conditional)<br/>(requires --log-level)"]

                ResultsDir["📁 results/<br/>&lt;strategy&gt;/*.json<br/>(suit_C, suit_D, high, low, auction)"]

                DatasetsDir["📁 datasets/<br/>bidding.* / bidless.* (conditional)<br/>(requires --emit-*-dataset)"]

                ReportsDir["📁 reports/<br/>*.png, *.html<br/>(generated charts)"]

                ArtifactsDir["📁 artifacts/<br/>*.pkl, *.joblib<br/>(model binaries)"]

                SplitsDir["📁 splits/<br/>train.parquet<br/>test.parquet<br/>val.parquet"]
            end

            RunID --> MetaFile
            RunID --> ConfigFile
            RunID --> PerfFile
            RunID --> LogsDir
            RunID --> ResultsDir
            RunID --> DatasetsDir
            RunID --> ReportsDir
            RunID --> ArtifactsDir
            RunID --> SplitsDir
        end

        Fixtures["📁 fixtures/<br/>(tiny test data, version-controlled)"]
    end

    Note1["✅ Committed: fixtures/ only"]
    Note2["❌ Not committed: runs/, reports/, models/, training/"]

    style Runs fill:#ffe1f5
    style Fixtures fill:#e1ffe1
    style Note1 fill:#e1ffe1
    style Note2 fill:#ffe1e1
```

---

## Run Invariants vs Optional Artifacts

Every run directory has a guaranteed structure and conditional outputs based on CLI flags.

### Always Present (Guaranteed)

These files are created for every experiment run:

- **meta.json** - Run metadata (seed, timestamp, git_hash), written BEFORE simulation starts
- **config_effective.yaml** - Resolved configuration with all defaults applied, written BEFORE simulation
- **perf.json** - Performance metrics (execution time, deals processed), written AFTER simulation completes
- **results/** - Per-strategy metric rollups, organized by execution mode:
  - `self_play`: `results/<strategy>/*.json`
  - `head_to_head`: `results/<team0>_vs_<team1>/*.json`
  - `head_to_head_matrix`: `results/<strat_a>_vs_<strat_b>/*.json`
- **logs/** - Directory always created (contents conditional on --log-level)
- **reports/** - Directory for generated visualizations
- **splits/** - Reserved directory for train/test/val splits
- **artifacts/** - Reserved directory for model binaries

### Conditional Artifacts (Flag-Dependent)

These files are only created when specific flags are provided:

| Artifact | CLI Flag | When Generated | Notes |
|----------|----------|----------------|-------|
| `logs/*.jsonl` | `--log-level hand` or `--log-level trick` | During simulation | JSONL schema v5 event stream |
| `datasets/bidding.*` | `--emit-bidding-dataset` | After simulation | Only in auction mode (contract_type: null) |
| `datasets/bidless.*` | `--emit-bidless-dataset` | After simulation | Only in declared contract mode |

### Checking for Conditional Artifacts

When analyzing runs programmatically, always check for existence:

```python
from pathlib import Path

run_dir = Path("data/runs/<run_id>")

# Always present
assert (run_dir / "meta.json").exists()
assert (run_dir / "perf.json").exists()
assert (run_dir / "config_effective.yaml").exists()

# Conditional - check before loading
logs_file = run_dir / "logs" / "game_events.jsonl"
if logs_file.exists():
    # Process logs
    pass

bidding_dataset = run_dir / "datasets" / "bidding.parquet"
if bidding_dataset.exists():
    # Analyze bidding decisions
    pass
```

---

## Modes and Scenario Types

### Execution Modes

The experiment runner supports three execution modes that determine how strategies compete:

**self_play** (default):
- All 4 seats use the same strategy
- Results organized in: `results/<strategy>/`
- One run per strategy listed in config
- Example: Testing how well GreedyStrategy performs against itself

**head_to_head**:
- Team 0 (seats 0 & 2) vs Team 1 (seats 1 & 3)
- Results organized in: `results/<team0>_vs_<team1>/`
- Requires `--team1-strategy` CLI flag
- Example: `--strategy greedy --team1-strategy random` → `results/greedy_vs_random/`

**head_to_head_matrix**:
- All-vs-all matchups from config
- Results organized in: `results/<strat_a>_vs_<strat_b>/` for each matchup
- Requires `matchups:` list in YAML config
- Example config:
  ```yaml
  matchups:
    - [greedy, random]
    - [greedy, glutton]
    - [random, glutton]
  ```

### Contract Modes

Scenarios can operate in two fundamentally different contract modes:

**Declared Contract** (contract_type specified):
- No bidding phase - contract and trump are predetermined
- Contract type and trump suit come from scenario configuration
- Enables `--emit-bidless-dataset` collection
- Result filenames by contract type:
  - `suit_C.json` (Club contract)
  - `suit_D.json` (Diamond contract)
  - `suit_H.json` (Heart contract)
  - `suit_S.json` (Spade contract)
  - `high.json` (High no-trump contract)
  - `low.json` (Low no-trump contract)

**Auction Mode** (contract_type: null):
- Bidding phase where strategies compete to set contract
- Winner of auction chooses trump suit and contract type
- Enables `--emit-bidding-dataset` collection
- Result filename: `auction.json`

### Example Directory Structure by Mode

```
# Self-play mode
data/runs/<run_id>/results/
├── greedy/
│   ├── suit_C.json
│   ├── suit_D.json
│   └── auction.json
└── random/
    ├── suit_C.json
    └── high.json

# Head-to-head mode
data/runs/<run_id>/results/
└── greedy_vs_random/
    ├── suit_C.json
    └── auction.json

# Head-to-head matrix mode
data/runs/<run_id>/results/
├── greedy_vs_random/
│   └── auction.json
├── greedy_vs_glutton/
│   └── auction.json
└── random_vs_glutton/
    └── auction.json
```

---

## Deterministic Deal Generation

```mermaid
flowchart LR
    Seed["Scenario Seed<br/>(base_seed + scenario_index)"]
    DealIndex["Deal Index<br/>(0, 1, 2, ...)"]
    Config["Scenario Config<br/>(contract_type, trump_suit)"]

    Seed --> DeriveFn["derive_deal_from_index()<br/>(deals.py)"]
    DealIndex --> DeriveFn

    DeriveFn --> RNG["Per-deal RNG<br/>seed = scenario_seed × 1_000_003 + deal_id<br/>Random(seed)"]

    RNG --> Shuffle["Shuffle 40-card Euchre deck<br/>(2× T,J,Q,K,A × 4 suits)"]
    Shuffle --> Deal["40-card Deal<br/>(10 cards × 4 seats)"]

    Deal --> Leader["Random leader<br/>(rng.randrange(4))"]
    Config --> ContractTrump["Contract & Trump<br/>(from scenario config)"]

    Leader --> Output["(Deal, Leader, Contract, Trump)<br/>Fully reproducible"]
    ContractTrump --> Output

    Note["Deterministic: shuffle + leader from RNG<br/>Config-driven: contract + trump from scenario"]

    style Seed fill:#e1f5ff
    style Config fill:#fff9e1
    style Output fill:#e1ffe1
    style Note fill:#fffacd
```

---

## Event System (Hooks)

```mermaid
flowchart TD
    subgraph Simulation["Simulation Engine"]
        PlayHand["play_single_hand()"]
    end

    subgraph Events["Event Types (sim/hooks.py)"]
        BiddingEvent["BiddingDecisionEvent<br/>(seat, hand, available_contracts)"]
        HandEndEvent["HandEndEvent<br/>(deal, trump, contract, tricks_won, scores)"]
        OtherEvents["TrickEndEvent, etc.<br/>(future extensions)"]
    end

    subgraph Listeners["Event Listeners"]
        GameLogger["GameLogger<br/>(logging/game_logger.py)"]
        Collectors["Data Collectors<br/>(bidding, bidless datasets)"]
        Custom["Custom Hooks<br/>(user-defined)"]
    end

    PlayHand -->|fire event| BiddingEvent
    PlayHand -->|fire event| HandEndEvent
    PlayHand -->|fire event| OtherEvents

    BiddingEvent --> GameLogger
    BiddingEvent --> Collectors

    HandEndEvent --> GameLogger
    HandEndEvent --> Collectors

    OtherEvents --> Custom

    GameLogger --> JSONL["logs/game_events.jsonl<br/>(schema v5)"]
    Collectors --> Parquet["datasets/*.parquet"]

    style Simulation fill:#e1f5ff
    style Events fill:#fff9e1
    style Listeners fill:#ffe1f5
```

---

## Key Principles

### Reproducibility

#### Deterministic Execution
- All experiments require `--seed <int>` for deterministic execution
- Same seed + same config → identical results every time
- Deal generation uses `derive_deal_from_index(seed, index)` for per-deal reproducibility

#### Deck Specification
- **40-card Euchre deck**: 2 copies of each (Ten, Jack, Queen, King, Ace) × 4 suits
- **Hand size**: 10 cards per player (entire deck is dealt, no cards left over)
- Total: 4 suits × 5 ranks × 2 copies = 40 cards

#### RNG Formula
Each deal gets a unique, deterministic random seed:

```python
# Scenario seed combines base seed with scenario index
scenario_seed = base_seed + scenario_index

# Deal seed uses large prime to avoid collisions
rng_seed = scenario_seed * 1_000_003 + deal_id
rng = random.Random(rng_seed)
```

This ensures:
- Different scenarios never share deals (scenario_index offset)
- Different deals within a scenario are independent (deal_id offset)
- Same base seed reproduces entire experiment exactly

#### What's Deterministic vs Config-Driven

**Deterministic (from RNG)**:
- ✅ Card shuffle - `rng.shuffle(deck)`
- ✅ Leader selection - `rng.randrange(4)`
- ✅ Dealer selection in auction mode - `rng.randrange(4)`

**Config-Driven (from scenario)**:
- ❌ Contract type - specified in scenario YAML (`contract_type: suit`, `high`, `low`, or `null` for auction)
- ❌ Trump suit - specified in scenario YAML (`trump_suit: C/D/H/S`) or chosen by auction winner

This separation ensures reproducibility while allowing exploration of different contract scenarios.

### Data Contract
- **Outputs confined to**: `data/runs/<run_id>/` only
- **Version control**: `data/fixtures/` only (tiny test data)
- **Never commit**: `data/runs/`, `data/reports/`, `data/models/`, `data/training/`

### Validation Gates
- Health checks enforce sample size minimums (≥2,000 deals for bias detection)
- Statistical tests required for inference claims (ANOVA, t-tests, effect sizes)
- Schema validation ensures compatibility across pipeline stages

### Canonical Entry Points
- **Experiment execution**: `experiments/run_experiment.py` (only runner)
- **Configuration**: YAML files in `experiments/configs/`
- **Reporting**: `scripts/generate_report.py`
- **Interactive analysis**: `notebooks/phase0_bidless/*.ipynb`

---

## Quick Reference

### Run an experiment
```bash
python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42
```

### Validate before PR
```bash
make check  # repo-lint + ruff + pytest
```

### Generate analysis
```bash
# Interactive exploration
jupyter notebook notebooks/phase0_bidless/00_health_checks.ipynb

# Automated reporting
python scripts/generate_report.py --run-id <run_id>
```

---

## References

- **Architecture**: `docs/01_core/ARCHITECTURE.md`
- **Data Contract**: `docs/01_core/DATA_CONTRACT.md`
- **Reproducibility**: `docs/01_core/REPRODUCIBILITY.md`
- **Metrics**: `docs/01_core/METRICS.md`
- **Experiment Design**: `docs/01_core/EXPERIMENTS.md`
