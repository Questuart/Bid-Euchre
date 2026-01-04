# Reporting & Visualization Framework

## Overview

The reporting system generates comprehensive visualizations and summaries for simulation runs, organized into three main categories:

1. **Health Dashboard** - Data quality and sanity checks
2. **Trick Strategy Analysis** - Strategy performance comparisons  
3. **Bidding Strategy Analysis** - Hand evaluation and bidding (future)

## Report Structure

All reports are stored under `data/runs/<run_id>/reports/`:

```
<run_id>/
├── raw/                          # Raw simulation data (future)
│   ├── logs/                     # JSONL hand-by-hand logs
│   └── results/                  # JSON aggregated results
├── logs/                         # Legacy: JSONL logs
├── results/                      # Legacy: JSON results
└── reports/
    ├── health/                   # Data quality checks
    │   ├── health_dashboard.png
    │   ├── summary.md
    │   └── _history/<timestamp>/
    ├── trick_strategy/           # Strategy performance (future)
    │   ├── paired/
    │   └── head_to_head/
    ├── bidding_strategy/         # Hand evaluation (future)
    ├── dashboards/<strategy>/    # Legacy: per-strategy dashboards
    ├── paired/                   # Legacy: paired comparisons
    ├── head_to_head/             # Legacy: H2H matrices
    ├── summary.md                # Overall run summary
    └── manifest.json             # Report generation log
```

## Health Dashboard

**Purpose**: Validate simulation mechanics and data quality before trusting strategy comparisons.

**Generated for**: All run types (self-play, head-to-head, head-to-head matrix)

**Plots**:
1. **Trick Count Distribution (PMF)** - Validates game mechanics
   - Shows probability mass function of tricks won (0-10)
   - Color-coded: red (<5), orange (=5), green (>5)
   - Displays mean, std dev, and sample size
   
2. **Score by Trick Count (Violin)** - Shows score variance and outliers
   - Violin plot of hand scores by tricks won
   - Uses exact scores from JSONL logs when available
   - Helps identify scoring anomalies
   
3. **Suit Symmetry** - Ensures no suit bias in dealing
   - Mean tricks by suit with 95% confidence intervals
   - Kruskal-Wallis test for statistical significance
   - Effect size (Cohen's d) for practical significance
   
4. **Tricks by Contract Type (Violin)** - Validates High/Low/Suit behavior
   - Distribution of tricks by contract type
   - Ensures contract types behave as expected
   - Statistical test across contract types

**Data Quality Checks**:
- ✅ Mean tricks near 5.0 (balanced game)
- ✅ Suit symmetry (Kruskal-Wallis p > 0.05)
- ✅ Adequate sample size (N > 1000)
- ✅ Contract type differences are expected

**Usage**:
```bash
PYTHONPATH=src python experiments/generate_health_dashboard.py \
    --run-dir data/runs/<run_id>
```

## Strategy Dashboards (Legacy)

**Purpose**: Per-strategy performance analysis

**Generated for**: self-play and head-to-head modes (with logs)

**Plots**:
- Trick distribution
- Score by tricks
- Feature vs tricks
- Win rates by contract
- Feature correlations
- Trump/bowers heatmap

**Usage**:
```bash
PYTHONPATH=src python experiments/generate_dashboard.py \
    --run-dir data/runs/<run_id> \
    --strategy <strategy_name>
```

## Paired Comparison (Legacy)

**Purpose**: Statistical comparison of strategies on common deals

**Generated for**: head-to-head mode with common_deals=True

**Plots**:
- Delta score distributions  
- Win/push/loss rates with confidence intervals
- Effect sizes (Cohen's d)

**Usage**:
```bash
PYTHONPATH=src python experiments/generate_paired_comparison.py \
    --run-dir data/runs/<run_id> \
    --baseline random_legal
```

## Head-to-Head Matrix (Legacy)

**Purpose**: Pairwise matchup analysis

**Generated for**: head_to_head_matrix mode

**Plots**:
- Comparison matrix heatmap (win rates)
- Per-matchup detail plots (distributions)

**Usage**:
```bash
PYTHONPATH=src python experiments/generate_head_to_head_report.py \
    --run-dir data/runs/<run_id>
```

## Generate All Reports

**Recommended**: Use the unified report generator to create all applicable reports:

```bash
PYTHONPATH=src python experiments/generate_all_reports.py \
    --run-dir data/runs/<run_id> \
    --baseline random_legal
```

This automatically:
1. ✅ Generates health dashboard (all modes)
2. ✅ Generates hand evaluation dashboard (if logs available)
3. Generates strategy dashboards (if logs available)
4. Generates paired comparison (if applicable)
5. Generates head-to-head matrix (if applicable)
6. ✅ Generates trick strategy dashboard (head_to_head_matrix mode)
7. Creates overall summary markdown
8. Writes manifest.json

**Reports by Mode**:

| Report Type | self_play | head_to_head | head_to_head_matrix |
|-------------|-----------|--------------|---------------------|
| Health Dashboard | ✅ | ✅ | ✅ |
| Hand Evaluation Dashboard | ✅ (with logs) | ✅ (with logs) | ✅ (with logs) |
| Strategy Dashboards | ✅ (with logs) | ✅ (with logs) | ❌ |
| Paired Comparison | ❌ | ✅ (with common_deals) | ❌ |
| Head-to-Head Matrix | ❌ | ❌ | ✅ (legacy) |
| Trick Strategy Dashboard | ❌ | ❌ | ✅ |

## Archive + Latest Pattern

All reports use an **archive + latest** pattern:
- **Archive**: Timestamped versions in `_history/<timestamp>/`
- **Latest**: Most recent version in main directory
- **latest.txt**: Points to archive location for provenance

This allows:
- Version history of report generations
- Easy access to most recent version
- Comparison of reports over time
- Reproducibility tracking

## Plotting Style

All plots use consistent styling from `bid_euchre.reporting.style`:
- Modern color palette (flatui-inspired)
- High DPI (150) for readability
- Consistent fonts and sizing
- Color-coded outcomes:
  - Red (#e74c3c): Loss
  - Green (#2ecc71): Win
  - Orange (#f39c12): Push/neutral
  - Blue (#3498db): General data
- Statistical annotations (p-values, effect sizes)

## Data Sources

Reports use two data sources:

1. **JSON Results** (`results/*.json`):
   - Aggregated statistics per scenario
   - Distribution buckets
   - Feature summaries
   - Fast to load and process

2. **JSONL Logs** (`logs/*.jsonl`):
   - Hand-by-hand records
   - Exact scores and features per player
   - Required for paired comparisons
   - Required for exact violin plots

## Backward Compatibility

The framework maintains backward compatibility:
- Checks for both `raw/logs` and `logs` directories
- Supports both `raw/results` and `results` directories
- Legacy report locations (`dashboards/`, `paired/`, `head_to_head/`) still work
- New reports go to categorized folders (`health/`, `trick_strategy/`, `bidding_strategy/`)

## Trick Strategy Dashboard

**Status**: ✅ Implemented

**Purpose**: Consolidated strategy performance analysis combining multiple visualizations

**Generated for**: head_to_head_matrix mode

**Plots** (2x2 grid):
1. **Win Rate Matrix** - Heatmap showing head-to-head win rates
   - Rows: Team 0 (player), Columns: Team 1 (opponent)
   - Color-coded: Green (>50%), Red (<50%), gradient for intermediate
   - Shows all pairwise matchups at a glance

2. **Strategy vs Baseline (Violin)** - Outcome distributions by strategy
   - Violin plots of tricks won for each strategy vs baseline
   - Color-coded: Green (better), Red (worse), Orange (similar)
   - Δ tricks shown above each violin
   - Sorted by performance (best to worst)

3. **Win Rate Bars** - Win rates with confidence intervals
   - Bar chart of win rates vs baseline
   - 95% confidence intervals
   - Color-coded by significance (CI excludes 50%)
   - Sorted by win rate (highest to lowest)

4. **Summary Statistics Table** - Key metrics at a glance
   - Strategy, Δ tricks, win rate, 95% CI, status
   - Color-coded rows by performance
   - Includes significance indicators (✅ Better, ❌ Worse, ➖ Similar)

**Usage**:
```bash
PYTHONPATH=src python experiments/generate_trick_strategy_dashboard.py \
    --run-dir data/runs/<run_id> \
    --baseline random_legal
```

**Auto-generated by**: `generate_all_reports.py` in head_to_head_matrix mode

**Insights Provided**:
- Which strategies dominate overall
- Pairwise strategy matchups
- Performance consistency (violin width)
- Statistical significance of differences
- Ranking of top performers

## Hand Evaluation Dashboard (Bidding Strategy)

**Status**: ✅ Implemented

**Purpose**: Analyze hand evaluation features and their relationship to trick-taking performance

**Generated for**: All modes with JSONL logs available

**Plots** (2x2 grid):
1. **Feature Importance** - Bar chart of top 15 features by correlation with tricks
   - Color-coded: Green (positive), Red (negative)
   - Shows Pearson correlation coefficients
   - Sorted by absolute correlation strength

2. **Hand Score Calibration** - Density heatmap of hand score vs actual tricks
   - Shows how well hand scoring predicts performance
   - Includes linear regression line
   - Correlation coefficient displayed

3. **Feature Distribution** (Top Feature) - Violin plot by contract type
   - Shows distribution of most important feature
   - Grouped by High/Low/Suit contracts
   - Includes mean and sample size

4. **Feature Distribution or Interaction** (Second Feature) - Context-dependent
   - Either violin plot of second-most important feature
   - OR 2D heatmap showing interaction between top 2 features
   - Helps identify feature combinations

**Usage**:
```bash
PYTHONPATH=src python experiments/generate_hand_eval_dashboard.py \
    --run-dir data/runs/<run_id>
```

**Auto-generated by**: `generate_all_reports.py` for all modes with logs

**Current Features Analyzed** (5 legacy features):
- `bowers` - Number of bowers (right + left)
- `trump_count` - Total trump cards
- `offsuit_aces` - Number of offsuit aces
- `high_offsuit` - High offsuit cards (K, Q, J, T)
- `rank_sum` - Sum of card ranks

**Note**: The dashboard is designed to handle 40+ features from `hand_eval.py`. Currently, only 5 legacy features are logged in JSONL files. When logging is updated to include all features, the dashboard will automatically display them.

**Future Enhancements** (when bidding is implemented):
- Bid decision patterns (bid level by features)
- Bid accuracy (predicted vs actual tricks)
- Expected value by bid level
- Optimal bidding thresholds

## Quick View Commands

```bash
# View health dashboard (all modes)
open data/runs/<run_id>/reports/health/health_dashboard.png

# View hand evaluation dashboard (all modes with logs)
open data/runs/<run_id>/reports/bidding_strategy/hand_eval_dashboard.png

# View trick strategy dashboard (head_to_head_matrix mode)
open data/runs/<run_id>/reports/trick_strategy/comprehensive_dashboard.png

# View strategy dashboards (self-play, head_to_head modes)
open data/runs/<run_id>/reports/dashboards/*/dashboard.png

# View paired comparison (head_to_head mode)
open data/runs/<run_id>/reports/paired/paired_comparison.png

# View head-to-head matrix (head_to_head_matrix mode - legacy)
open data/runs/<run_id>/reports/head_to_head/comparison_matrix.png

# View all latest reports (macOS)
open data/runs/<run_id>/reports/health/*.png
open data/runs/<run_id>/reports/bidding_strategy/*.png
open data/runs/<run_id>/reports/trick_strategy/*.png
```

## Reporting Module Structure

The reporting framework is located in `src/bid_euchre/reporting/`:

- **`paths.py`**: Path management with backward compatibility
- **`style.py`**: Consistent plot styling and colors
- **`metrics.py`**: Statistical functions and formatters
- **`__init__.py`**: Public API exports

Report generators are in `experiments/`:

- `generate_health_dashboard.py` - Health checks
- `generate_dashboard.py` - Strategy dashboards
- `generate_paired_comparison.py` - Paired analysis
- `generate_head_to_head_report.py` - H2H matrices
- `generate_all_reports.py` - Orchestrates all reports

## Best Practices

1. **Always generate health dashboard first** to validate data quality
2. **Use generate_all_reports.py** for comprehensive analysis
3. **Check summary.md** for high-level overview before diving into plots
4. **Compare archived versions** to track performance changes over time
5. **Document anomalies** in health dashboard (e.g., suit imbalances)

## Troubleshooting

**Issue**: Suit symmetry test fails (p < 0.05)
- **Cause**: Imbalanced dealing or specific matchup patterns
- **Action**: Check if pattern is consistent across runs; may be expected in H2H mode

**Issue**: Missing plots in dashboard
- **Cause**: Insufficient data for violin plots (n < 10 per bin)
- **Action**: Increase sample size (n_per parameter)

**Issue**: Matplotlib warnings about tight_layout
- **Cause**: Complex subplot arrangements
- **Action**: Can be ignored; outputs are still correct

**Issue**: Reports generate slowly
- **Cause**: Loading large JSONL files
- **Action**: Reduce log_level or use aggregate JSON results only
