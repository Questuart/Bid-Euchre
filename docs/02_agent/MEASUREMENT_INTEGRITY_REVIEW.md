# Measurement Integrity Review Template

> Fill-in template for rung-completion methodology reviews.
> File to: `docs/04_reports/<rung>/measurement_integrity_<rung>.md`

## Header

| Field | Value |
|-------|-------|
| **Arc** | |
| **Rung** | |
| **Date** | |
| **Reviewer** | |
| **gate_status** | *(copy from promotion decision, e.g., PROMOTED)* |

> **Lint note:** The `gate_status` field above satisfies the existing
> `registry-requires-gate-reference` lint rule, which checks all `.md` files
> under `docs/04_reports/` for at least one gate-evidence token. Include it
> in every review.

## Evaluation Batteries

List all evaluation batteries used to inform the promotion decision.

| Battery | Purpose | Script Path | Deal Count | Seed |
|---------|---------|-------------|------------|------|
| | | | | |

## Known Methodological Limitations

Classify each limitation into one of three categories:

| ID | Description | Category | Notes |
|----|-------------|----------|-------|
| | | | |

### Category Definitions

- **(a) Inherent/accepted** — Fundamental to the evaluation design. Understood
  and accepted as a trade-off. No action needed.
- **(b) Fixable, deferred** — A known fix exists but is deferred to a later
  rung or PR. **Requires a deferral cost description in Section 4.**
- **(c) Must fix before advancement** — Blocks both PROMOTED and ADVANCED
  outcomes. Must be resolved before the rung gate can pass.

### Rigor Firewall

Blockers identified by `.claude/rules/deferred/05_rigor.md` are **always category (c)**:

- Inadequate sample size (below documented thresholds)
- Missing confidence intervals on key metrics
- Missing statistical tests (visual-only validation)
- Uncontrolled confounders affecting promotion decision inputs

These cannot be deferred regardless of cost analysis.

## Deferral Cost Descriptions

For each **(b)** item, provide a qualitative cost assessment:

### B-{id}: {limitation title}

- **Fix-now impact:** What would it cost (PRs, experiment reruns, delay) to
  fix before advancing?
- **Fix-later impact:** What additional costs accrue if deferred? Does the
  fix compound (e.g., require crosswalk tables between rungs)?
- **Never-fix consequence:** If this is never fixed, what is the long-term
  impact on metric validity, decision quality, or scientific claims?

## Blockers

Unresolved **(c)** items. All must be cleared before the rung gate can pass.

- [ ] *(list (c) items here, or write "None" if no (c) items)*

## Sign-off

- [ ] All evaluation batteries listed
- [ ] All known limitations classified (a/b/c)
- [ ] All (b) items have deferral cost descriptions
- [ ] No (c) items remain unresolved
- [ ] Rigor firewall applied (05_rigor.md blockers are category (c))

---

## Light-Review Mode

If the evaluation methodology is **unchanged from the prior rung**, a light
review is acceptable:

1. Reference the prior review: `Prior review: measurement_integrity_<prev_rung>.md`
2. Document only **deltas** — new batteries, resolved limitations, new limitations
3. Re-certify: confirm prior (a)/(b) classifications still hold
4. Update the gate_status field for the current rung
