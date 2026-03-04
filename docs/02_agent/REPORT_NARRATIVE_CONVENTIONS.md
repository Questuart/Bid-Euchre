# Report Narrative Conventions

Codifies the narrative patterns established during R0 report writing.
These conventions apply to all auto-generated and hand-crafted reports
in the Bid Euchre framework.

**Exemplar references:** All conventions below are demonstrated in the R0
reports at `docs/04_reports/r0/`. When in doubt, match the R0 style.

---

## 1. Executive Summary: Five-Question Structure

Every report's executive summary answers five questions in order:

1. **What is this?** — One sentence identifying the report's purpose and scope
   (e.g., "R0 baseline establishment for Arc D's OLSa-Hybrid bidder")
2. **What did we do?** — Brief campaign inventory: deal counts, configurations,
   key parameters (e.g., "Six campaigns, ~580k deals, seed=42")
3. **What did we find?** — Key results with numbers. Include a compact metrics
   table when comparing arms or bidders
4. **What are the caveats?** — Known limitations, sample size warnings,
   surprising findings that need context
5. **What's the decision?** — Bold the verdict (e.g., **PROMOTED**, **HALT**,
   **RETAIN**). Include 1-sentence rationale

### Key Metrics Table

After the five questions, include a compact side-by-side table when the report
compares two or more entities (arms, bidders, configurations):

```markdown
| Metric | OLSa (constrained) | OLSa_Full (promotional) |
|--------|---------------------|-------------------------|
| net_eppd | +1.627 | +1.484 |
| make_rate | 87.3% | 83.3% |
```

---

## 2. Section Commentary Convention

Every data section (tables, charts, statistics) should be followed by
**2-4 sentences of interpretation**:

1. **What the data shows** — summarize the key pattern
2. **What it means** — interpret in context of the rung/experiment goals
3. **Caveats** (if any) — flag sample sizes, missing data, known confounds
4. **Cross-reference** (if relevant) — point to companion reports for depth

**Example:**
> Both arms show positive net_eppd, with OLSa slightly outperforming OLSa_Full
> (+0.14 gap). This negative attribution gap is unexpected — the constrained
> arm's hand-picked features appear more robust at R0 model quality. See
> [01_01_r0_promotion_report.md](01_r0_promotion_report.md) for multi-seed stability
> analysis.

**Anti-pattern:** Tables without any interpretation. Every table needs at
minimum a one-sentence summary of the key takeaway.

---

## 3. Summarize-and-Link Convention

When a topic is covered in depth by a companion report, the main report
carries a **compact summary + cross-link**, not a full duplicate:

### Pattern

1. **Compact table** — 5-7 rows max, key metric + CI
2. **2-3 sentences** — headline finding + methodology note
3. **Cross-link** — "See [report_name.md](report_name.md) for full analysis"

### Table Sizing Guidance

| Context | Max Rows | Columns |
|---------|----------|---------|
| Rankings summary | 7 (all bidders) | bidder, net_eppd, CI |
| H2H key matchups | 4-5 | matchup, delta, CI, verdict |
| Gate checks | All checks | check, result |
| Feature list | 10 (top features) | feature, coefficient |

### When to Summarize vs Full Duplicate

- **Summarize-and-link:** The companion report exists and is authoritative
- **Full content:** The information appears only in this report
- **Never:** Duplicate large tables across reports (stale data risk)

---

## 4. Rigor Annotations

Flag rigor concerns inline where they arise, not just in a limitations
section at the end.

### Sample Size Flags

Flag when sample size falls below thresholds from `.claude/rules/05_rigor.md`:

```markdown
- **Sample size warning:** HIGH contracts have only 261 deals, below the
  2,000-deal minimum for reliable bias detection.
```

### Missing CIs

When reporting point estimates without confidence intervals:

```markdown
- Note: R² values are point estimates from a single eval seed; bootstrap
  CIs from multi-seed runs are in [01_r0_promotion_report.md].
```

### Statistical Test Notes

When a comparison lacks formal testing:

```markdown
- The +0.21 attribution gap is from a single H2H run. See
  [05_c33_ablation_report.md] for the ablation with bootstrap CIs.
```

---

## 5. Cross-Linking Convention

### Internal Links

Use relative Markdown links within the same report directory:

```markdown
See [03_comparator_rankings.md](03_comparator_rankings.md) for full analysis.
```

### Companion Reports Section

Every rung report should end with a companion reports table:

```markdown
### Companion Reports

| Report | Focus |
|--------|-------|
| [01_01_r0_promotion_report.md](01_r0_promotion_report.md) | Gate results, multi-seed |
| [03_comparator_rankings.md](03_comparator_rankings.md) | Absolute benchmarking |
```

### Cross-Rung Links

When referencing a previous rung's report:

```markdown
Compared to R0 ([02_model_arc_r0.md](../r0/02_model_arc_r0.md)), R1 shows...
```

---

## 6. Report Versioning

### Stable Filenames

Reports use stable filenames without dates (e.g., `02_model_arc_r0.md`, not
`model_arc_r0_20260224.md`). The generation timestamp lives in the report
header.

### Archive Convention

When a report is substantially revised, archive the previous version:

```
docs/04_reports/r0/archive/model_arc_r0_v1_20260224.md
```

Format: `{name}_v{N}_{original_date}.md`

---

## 7. Contract-Type Faceting Requirement

Every chart, table, or statistical summary **MUST** be faceted by
contract_type (suit, high, low) or explicitly justify pooling.
This is a repo-wide convention — see `MEMORY.md` key rules.

### Pooled Metrics

When showing aggregate metrics across contract types, include both:
- The aggregate value
- A note about contract-type breakdown availability

```markdown
Overall R² = 0.27 (suit: 0.29, high: 0.24, low: 0.19)
```

---

## 8. Matchup Team Breakout Requirement

Matchup summary tables **MUST** show team0 and team1 separately, not
collapsed into a single matchup row. This makes the bidding asymmetry
visible (in comparator runs, only one team bids).

---

## 9. Reproduction Commands

Every report should include a reproduction section with:

1. **Exact commands** with seeds and config paths (no placeholders)
2. **Pipeline stages** — which stages to re-run to regenerate
3. **Dependencies** — what artifacts must exist first

```markdown
## Reproduction Commands

### Chart Generation
uv run python scripts/internal/generate_rung_charts.py \
  --rung r0 \
  --eval-dir data/runs/arc_d_eval_r0_42_20260303_201729 \
  --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
  --output-dir data/reports/arc_d/r0/charts/

### Report Generation
uv run python -c "
from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
df = build_eval_dataset('data/runs/.../logs/*.jsonl')
generate_arc_d_rung_report('data/artifacts/.../rung_bundle_r0.json',
    eval_df=df, chart_dir='data/reports/.../charts/',
    output_path='docs/04_reports/r0/02_model_arc_r0.md')
"
```
