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

        subgraph Game["game/"]
            Bidding["bidding.py"]
            Scoring["scoring.py"]
            Trick["trick.py"]
        end

        subgraph Logging["logging/"]
            GameLogger["game_logger.py<br/>(JSONL schema v5)"]
        end

        subgraph Diagnostics["diagnostics/"]
            Charts["charts.py"]
            Stats["stats.py"]
            Health["health_checks.py"]
        end

        subgraph Experiments["experiments/"]
            Config["config.py<br/>(YAML → dataclasses)"]
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
    Simulation --> Game
    Simulation --> Hooks
    Hooks --> GameLogger
    GameLogger --> Runs
    Scripts --> Diagnostics
    Diagnostics --> Runs
    Notebooks --> Runs
    Notebooks --> Diagnostics
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

    CreateRunDir --> SaveMeta["Save meta.json<br/>(schema v2: seed, timestamp, config)"]
    SaveMeta --> SaveEffectiveConfig["Save config_effective.yaml<br/>(resolved configuration)"]

    SaveEffectiveConfig --> InitLogger["Initialize GameLogger<br/>(JSONL schema v5)"]
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
    Aggregate --> SaveResults["Save results/<br/>(performance_summary.json)"]
    SaveResults --> SaveLogs["Save logs/<br/>(game_events.jsonl)"]
    SaveLogs --> SaveDatasets["Save datasets/<br/>(bidding.parquet, etc.)"]
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
        Seed --> Deals["Deterministic Deals<br/>(derive_deal_from_index)"]
        Config --> Sim["Simulation Engine"]
        Deals --> Sim
        Sim --> Events["Event Stream<br/>(HandEndEvent, etc.)"]
    end

    subgraph Storage["Data Storage (data/runs/&lt;run_id&gt;/)"]
        direction TB
        Meta["meta.json<br/>(run metadata)"]
        ConfigEff["config_effective.yaml"]
        Logs["logs/<br/>game_events.jsonl"]
        Results["results/<br/>performance_summary.json"]
        Datasets["datasets/<br/>bidding.parquet<br/>bidless.parquet"]
        Artifacts["artifacts/<br/>(model binaries)"]
        Reports["reports/<br/>(charts, figures)"]
    end

    subgraph Analysis["Analysis & Insights"]
        direction TB
        Diagnostics["Diagnostics Module<br/>(charts, stats, health)"]
        Notebooks["Jupyter Notebooks<br/>(phase0_bidless/*.ipynb)"]
        ReportGen["Report Generator<br/>(scripts/generate_report.py)"]
    end

    Events --> Meta
    Events --> Logs
    Events --> Results
    Events --> Datasets

    Logs --> Diagnostics
    Results --> Diagnostics
    Datasets --> Diagnostics

    Logs --> Notebooks
    Results --> Notebooks
    Datasets --> Notebooks

    Diagnostics --> Reports
    Diagnostics --> ReportGen
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

        GameBidding["game/bidding.py"]
        GameTrick["game/trick.py"]
        GameScoring["game/scoring.py"]
        GameDeck["game/deck.py"]

        StratBase["strategy/base.py"]
        StratImpl["strategy/greedy.py<br/>strategy/glutton.py<br/>etc."]

        Logger["logging/game_logger.py"]

        DiagCharts["diagnostics/charts.py"]
        DiagStats["diagnostics/stats.py"]
        DiagHealth["diagnostics/health_checks.py"]
    end

    RunExp --> ExpConfig
    RunExp --> SimEngine
    RunExp --> Logger

    ExpConfig --> StratImpl

    SimEngine --> SimDeals
    SimEngine --> SimHooks
    SimEngine --> StratBase
    SimEngine --> GameBidding
    SimEngine --> GameTrick
    SimEngine --> GameScoring

    GameBidding --> GameDeck
    GameTrick --> GameDeck
    GameScoring --> GameBidding

    StratImpl --> StratBase
    StratImpl --> GameBidding

    SimHooks --> Logger

    GenReport --> DiagCharts
    GenReport --> DiagStats

    Notebooks --> DiagCharts
    Notebooks --> DiagStats
    Notebooks --> DiagHealth

    DiagCharts --> DiagStats
    DiagHealth --> DiagStats

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
        Logs["logs/game_events.jsonl<br/>(structured events)"]
        Datasets["datasets/*.parquet<br/>(bidding, bidless)"]
        Results["results/*.json<br/>(aggregated metrics)"]
    end

    LoadData --> Meta
    LoadData --> Logs
    LoadData --> Datasets
    LoadData --> Results

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
                MetaFile["📄 meta.json<br/>(schema v2: seed, timestamp, git_hash)"]
                ConfigFile["📄 config_effective.yaml<br/>(resolved configuration)"]

                LogsDir["📁 logs/<br/>game_events.jsonl<br/>(schema v5: JSONL events)"]

                ResultsDir["📁 results/<br/>performance_summary.json<br/>(win rates, metrics)"]

                DatasetsDir["📁 datasets/<br/>bidding.parquet<br/>bidless.parquet<br/>(structured datasets)"]

                ReportsDir["📁 reports/<br/>*.png, *.html<br/>(generated charts)"]

                ArtifactsDir["📁 artifacts/<br/>*.pkl, *.joblib<br/>(model binaries)"]

                SplitsDir["📁 splits/<br/>train.parquet<br/>test.parquet<br/>val.parquet"]
            end

            RunID --> MetaFile
            RunID --> ConfigFile
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

## Deterministic Deal Generation

```mermaid
flowchart LR
    Seed["Seed<br/>(--seed N)"]
    DealIndex["Deal Index<br/>(0, 1, 2, ...)"]

    Seed --> DeriveFn["derive_deal_from_index()<br/>(deals.py)"]
    DealIndex --> DeriveFn

    DeriveFn --> RNG["Per-deal RNG<br/>(Random(seed + index))"]

    RNG --> Shuffle["Shuffle deck<br/>(deterministic)"]
    Shuffle --> Deal["52-card Deal<br/>(13 cards × 4 seats)"]

    Deal --> Trump["Random trump<br/>(H/D/C/S)"]
    Deal --> Contract["Random contract<br/>(Suit/NT)"]

    Trump --> Output["(Deal, Trump, Contract)<br/>Fully reproducible"]
    Contract --> Output

    Note["Same seed + same index<br/>→ Identical deal every time"]

    style Seed fill:#e1f5ff
    style Output fill:#e1ffe1
    style Note fill:#fff9e1
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
- All experiments require `--seed <int>` for deterministic execution
- Same seed + same config → identical results every time
- Deal generation uses `derive_deal_from_index(seed, index)` for per-deal reproducibility

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
python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42
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
