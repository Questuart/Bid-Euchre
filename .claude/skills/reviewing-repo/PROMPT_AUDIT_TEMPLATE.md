# Prompt Audit — Sub-Agent Prompt Template

Read the template below and pass it to a `general-purpose` sub-agent. The `{REPO_ROOT}` placeholder should be replaced with the actual repo root path.

```
You are auditing `docs/02_agent/REPO_REVIEW_PROMPT.md` for staleness. Your job
is to test every verifiable claim in the protocol against the current repo state
and report what's stale.

**Working directory:** {REPO_ROOT}
**Constraint:** Read-only. Do NOT edit any files.

## Instructions

1. Read `docs/02_agent/REPO_REVIEW_PROMPT.md` in full.
2. For each testable claim below, run the verification command and compare.
3. Report ONLY items where the prompt is inaccurate. Do not report items that match.

## Audit Checklist

### A. Module Health Imports (§1.3)

For each `uv run python -c "from ..."` line in Section 1.3, run it and record
pass/fail. Report any that FAIL — these are stale import paths.

Also: run `ls -d src/bid_euchre/*/ | grep -v __pycache__` and compare against
the modules covered by §1.3 imports. Report any modules that EXIST on disk but
have NO corresponding import check in the prompt.

### B. Gold Path Commands

For each command in the GOLD PATH COMMANDS section, verify it would work:
- `make` targets: run `make -n <target> 2>&1 | head -3` to check existence
- `uv run python` commands: check the referenced scripts exist on disk
- CLI flags: check that flags mentioned in examples match the script's argparse

Report any commands that reference nonexistent targets, scripts, or flags.

### C. Current Structure Tree

Compare the directory tree in CURRENT STRUCTURE (§) against reality:
- Run `ls -d src/bid_euchre/*/` and compare to the tree's module list
- Run `ls docs/*/` and compare to the tree's docs directories
- Check that all specific files mentioned (Makefile, pyproject.toml, etc.) exist

Report structural differences (missing dirs, extra dirs, renamed items).

### D. Make Check Composition

The prompt claims `make check` includes specific sub-targets. Verify:
```bash
grep -A5 "^check:" Makefile
```
Compare the actual composition to what the prompt claims.

### E. Repo-Linter Rule Categories

The prompt lists rule categories in a table. Verify:
- Run `grep "^def check_" scripts/lint_repo.py` to get actual rules
- Check that every rule maps to one of the documented categories
- Report any rules that don't fit existing categories or categories with no rules

### F. Script and File References

Find all file paths mentioned in the prompt and verify they exist:
```bash
grep -oE '[a-z_/]+\.(py|yaml|md|json)' docs/02_agent/REPO_REVIEW_PROMPT.md | sort -u
```
For each, check if it exists on disk. Report paths that don't exist.

### G. Development Milestones

The milestones table references PR number ranges and themes. Verify:
- The latest era's PR range: check if PRs in that range exist via
  `gh pr view <last_pr_number> --json title 2>/dev/null`
- Check the "Current state" derive commands actually work

## Output Format

Return your results as structured markdown:

### Prompt Staleness Report

**Protocol version found:** <version string from the file>
**Total stale items:** <N>

### Stale Import Paths

| Line | Import | Error | Fix |
|------|--------|-------|-----|
| <approx line#> | `from bid_euchre.X import Y` | <error message> | <correct import or "remove"> |

### Missing Module Coverage

| Module | On Disk | In Prompt §1.3 |
|--------|---------|-----------------|
| <module> | yes | no — needs import check added |

### Stale Commands

| Section | Command | Issue | Fix |
|---------|---------|-------|-----|
| <section name> | `<command>` | <what's wrong> | <correct command> |

### Structure Drift

| Item | In Prompt | On Disk | Fix |
|------|-----------|---------|-----|
| <item> | <what prompt says> | <what exists> | <edit needed> |

### Stale File References

| Path in Prompt | Exists? | Fix |
|----------------|---------|-----|
| <path> | no | <remove or update to correct path> |

### Other Staleness

| Location | Issue | Fix |
|----------|-------|-----|
| <section/line> | <description> | <proposed edit> |

If no staleness is found in a category, omit that section entirely.
If the prompt is fully accurate, return:
"No staleness detected. Protocol is current."
```
