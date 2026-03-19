# Commit Analytics Dashboard — GitHub Actions Auto-Update
**Date:** 2026-03-18
**Goal:** Deploy an auto-updating churn-corrected Bollinger Band chart to the repo, generated daily by GitHub Actions and embedded in the README.

## Context
Interactive exploration session produced a commit analytics pipeline that:
- Computes daily commit counts (working days only)
- Calculates line-level churn ratio (gross vs net line changes)
- Derives effective commits = raw × (1 − churn ratio)
- Renders 10-working-day Bollinger Bands with %B and bandwidth panels

## Plan

### Step 1: Create `scripts/generate_dashboard.py`
- Clean up the `/tmp/commit_timeseries.py` prototype into a production script
- Must work headless in CI (matplotlib Agg backend)
- Accept `--output` flag for the output PNG path (default: `assets/dashboard/commit_bollinger.png`)
- Accept `--repo` flag for git repo path (default: `.`)
- Remove hardcoded "today" — derive from latest commit date
- Add `if __name__ == "__main__"` guard with argparse

### Step 2: Create `assets/dashboard/` directory
- Add `.gitkeep` or the initial generated PNG
- This directory holds auto-generated dashboard images

### Step 3: Create `.github/workflows/dashboard.yml`
- **Triggers:**
  - `push` to `main` (update after merges)
  - `schedule: cron '0 6 * * *'` (daily at 6am UTC)
  - `workflow_dispatch` (manual trigger)
- **Job:**
  - Checkout with `fetch-depth: 0` (needs full history for git log)
  - Setup Python 3.12 + uv
  - Install deps (`uv sync --frozen`)
  - Run `uv run python scripts/generate_dashboard.py --output assets/dashboard/commit_bollinger.png`
  - Commit and push if the image changed (use `stefanzweifel/git-auto-commit-action@v5`)
- **Permissions:** `contents: write` (to push the updated image)
- **Concurrency:** `dashboard` group, cancel-in-progress

### Step 4: Add image embed to README.md
- Add a `## Dashboard` section near the top of the README
- Embed: `![Commit Analytics](assets/dashboard/commit_bollinger.png)`
- Brief description of what the chart shows

### Step 5: Validate locally
- Run the script against the repo
- Verify the PNG generates correctly
- Run `make check-quiet` to ensure no regressions

## Files
- `scripts/generate_dashboard.py` — new: chart generation script
- `assets/dashboard/commit_bollinger.png` — new: generated chart (auto-committed)
- `.github/workflows/dashboard.yml` — new: GitHub Actions workflow
- `README.md` — edit: add dashboard embed section

## Dependencies
- `matplotlib` — already in `pyproject.toml`
- `numpy` — already in `pyproject.toml`
- Full git history — workflow uses `fetch-depth: 0`
- `stefanzweifel/git-auto-commit-action@v5` — trusted, widely-used action for auto-commits

## Risks
- **Auto-commit loop:** The dashboard workflow commits a PNG, which triggers `push` to `main`, which triggers the dashboard workflow again. Mitigate with: `paths-ignore: ['assets/dashboard/**']` on the push trigger, or check if the image actually changed before committing.
- **Large binary in git:** PNG at 150 DPI is ~200-400KB. Acceptable for a single file. Could add to `.gitattributes` as LFS if it grows.

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
