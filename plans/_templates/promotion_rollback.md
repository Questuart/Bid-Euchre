# <Promotion / Rollback Plan Title>

**Date:** YYYY-MM-DD
**Artifact:** `<path/being/promoted_or_rolled_back>`
**Direction:** promote | rollback
**Owner:** <agent session ID or operator>

## Trigger

What event authorized this promotion or rollback? Example: "Draft 8 final
review recommended PROMOTE-AFTER-FIXES; 12 fixes landed in PR #NNNN; all 8
validation commands passed."

## Preconditions

Observable gates that must be true *before* the rename or revert runs.
Every gate must be checkable from the repo or a named command.

- [ ] Working tree clean (`git status --short` empty)
- [ ] All open fix tasks completed (`TaskList` shows no open items in scope)
- [ ] Validation suite passed (link to PR or artifact)
- [ ] Lineage destination exists (`ls -d <archive_dir>`)

## Rename / revert sequence

List as an atomic burst so the diff reads as a single logical change. Use
`git mv` for lineage-preserving renames.

```bash
git mv <src> <dst-archive>
git mv <draft_n> <canonical_name>
# update cross-references via sed/Edit — never leave dangling refs
```

Include a note to prepend (for promotion) or restore (for rollback) at the
top of the canonical file: "Promoted from draft N on YYYY-MM-DD. Lineage:
`<archive_dir>/...`."

## Cross-reference update

- `grep -rE '<old_ref>' <scope>/` — should return only lineage-history
  mentions; update any live references.
- Any skills, ADRs, or plans that point at the old path must be updated or
  explicitly left as lineage mentions.

## Rollback plan (for promotions)

If the promotion is later reverted, describe the shape of the reverse
rename. A promotion template is only complete if a symmetric rollback is
writable. Example: "Revert via `git mv <canonical>.md → <archive>/<canonical>.draft<N>.md` then
`git mv <archive>/<canonical>.draft<N>.md → <canonical>.draft<N>.md` at repo root (restores the pre-promotion draft path)."

## Outcome

(Filled after the rename/revert lands.) Link to PR, record any deviations
from the sequence above, and note residual work (e.g., downstream skill
edits filed as follow-ups).
