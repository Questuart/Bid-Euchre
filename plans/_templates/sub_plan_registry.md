# Sub-Plan Registry — <Initiative Name>

**Governing plan:** `plans/<initiative>/governing_plan.md`
**Last updated:** YYYY-MM-DD

---

## Registry

| ID | Title | Parent Section | Status | Owner | File | Created | Completed |
|----|-------|----------------|--------|-------|------|---------|-----------|
| SP-0-01 | Example sub-plan | Phase 0, item 3 | proposed | -- | `<phase>/sub/YYYY-MM-DD_slug.md` | YYYY-MM-DD | -- |

## Status Summary

| Status | Count |
|--------|-------|
| proposed | 0 |
| in_progress | 0 |
| blocked | 0 |
| completed | 0 |
| abandoned | 0 |
| superseded | 0 |

## Conventions

- **ID format:** `SP-<phase>-<seq>` where `<phase>` is the phase/rung number
  and `<seq>` is a zero-padded sequence within that phase (e.g., `SP-0-01`).
- **Lifecycle:** proposed -> in_progress -> completed | abandoned | superseded.
  A sub-plan may transition to `blocked` from `in_progress` and back.
- **File location:** Sub-plan documents live in
  `plans/<initiative>/<phase>/sub/YYYY-MM-DD_<slug>.md`.
- **Updates:** Update this registry whenever a sub-plan changes status.
  The registry is the index; the sub-plan file is the detail.
