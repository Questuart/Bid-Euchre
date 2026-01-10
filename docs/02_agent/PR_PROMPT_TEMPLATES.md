# PR Prompt Templates (Robust, Parallel-Safe)

These templates are designed for **cheap agents** operating in a repo with strict determinism + reproducibility requirements.

## When to use which template

- Use the **SHORT** template for:
  - 1–3 files
  - docs-only changes
  - small bugfixes with obvious chokepoints

- Use the **LONG** template for:
  - multi-file changes
  - changes that require coordinating tests/fixtures/contracts
  - anything where scope creep is likely

## Multi-agent / parallel PR guardrails (important)

If you are running multiple agents in parallel:
- Treat scope as a hard lock. Do not "helpfully" touch shared files outside scope.
- Avoid central index files unless explicitly scoped (e.g., top-level README, docs/README.md, AGENTS.md).
- Always prove you started from `main`.
- Always produce scope proof even if `git fetch` is blocked.

---

# REPO PR AGENT PROMPT TEMPLATE (ROBUST SHORT TEMPLATE FOR CHEAPER AGENTS — UPDATED)

ROLE
You are a patch-focused maintainer. Implement ONLY what this PR asks. No refactors, no drive-by cleanups.

STYLE
- Minimal diff, surgical edits.
- Determinism-first: do not introduce nondeterminism.
- Prefer precise fixes over cleanup.

ABSOLUTE RULES
- Do NOT claim a PR exists until you have a PR URL (from gh or UI-created).
- Do NOT stop after "Step 0" unless a STOP CONDITION applies.
- If GitHub access fails, you must still finish: push branch + provide manual UI steps + FULL PR body text.
- FINAL RESPONSE must include validation proof + PR body header validation + clean workspace proof.
- Paste terminal outputs **verbatim** when asked (do not summarize).

PARALLEL-SAFE RULES (if running alongside other PRs)
- Do not touch shared/central files unless explicitly scoped.
- If you discover required changes outside scope that touch shared files: STOP and report.

GIT HYGIENE (required)
- Never work or commit on main.
- Branch before edits.
- Stage explicitly (no `git add .`).
- Single commit per PR.
- Return workspace to clean main at the end.

PERMISSIONS / GH ACCESS (critical)
- Run gh checks early (Step 0.2).
- If gh fails due to auth/TLS/permissions/locks:
  - Do ONE retry in full-permissions mode (Cursor: required_permissions: ["all"]).
  - If still failing: proceed without gh and provide manual PR steps + FULL PR body.

PR Title
<one line>

Goal
<end state>

Non-goals
- <bullet>
- <bullet>

Hard Scope (Allowed files only)
- <file1>
- <file2>
- <new_file3>
If any other file is needed: smallest necessary change + list under "Scope exceptions" in final response.

Hard Gates / Acceptance
- make check passes (or state exactly what is missing locally; rely on CI)
- determinism preserved
- no generated artifacts committed
- baseline/invariant tests pass unless explicitly listed
- PR body MUST include EVERY "##" section header from .github/pull_request_template.md
- Final response MUST include proof snippets (see below)

DOC COMMAND VALIDATION (required for docs changes that add/modify commands)
For every command you add or change, include proof for at least one of:
- `PYTHONPATH=src python <script> --help` (paste relevant flag lines), OR
- `ls <referenced path>` (for referenced configs/suites/scripts)

STOP CONDITIONS (only)
- Required files/configs/tests can't be found after searching (rg/grep).
- You cannot run any validations at all (missing python tooling) AND cannot rely on CI.
If STOP: say exactly what you searched and what's missing.

────────────────────────────────────────
Step -1 — Git setup (MUST; no code)
Run + paste outputs verbatim:
- git status
- git branch --show-current
- git fetch origin (or "fetch blocked")

Then:
- You MUST be on main before branching:
  - git checkout main
  - git status -sb

Create branch:
- git checkout -b <branch-name>

BASE PROOF (required)
- git merge-base --is-ancestor main HEAD && echo "based on main ✅" || echo "NOT based on main ❌"
If NOT based on main ❌: STOP and restart from main.

────────────────────────────────────────
Step 0 — Confirm anchors (MUST; no code)
Run + paste minimal proof (rg/grep output snippets) that you found:
- the chokepoint(s) you will edit
- the config/test anchors you will use
Then state: "I will edit only <scoped file list>."
IMPORTANT: Continue to implementation unless STOP CONDITIONS apply.

────────────────────────────────────────
Step 0.2 — GitHub capability check (MUST early)
Run + paste outputs verbatim:
- gh --version (or "gh missing")
- gh auth status (or failure)
- git remote -v
If gh auth/status fails due to permissions/TLS/locks:
- ONE retry in full permissions (Cursor: required_permissions: ["all"])
- If still failing: continue anyway; you'll do manual PR steps later.

────────────────────────────────────────
Implementation (do the work)
1) Make minimal changes to achieve Goal.
2) Add minimal tests needed for Goal.
3) Keep outputs deterministic (sort keys / avoid nondeterministic iteration).

────────────────────────────────────────
Validation (MUST try)
Run:
- make check
If deps missing:
- run what you can (e.g., make repo-lint / make lint / pytest -q) and state exactly what failed.

HARD RULE:
- If any existing test fails due to your change: STOP, do not commit, report failure.

PROOF REQUIRED:
- Paste the last ~10 lines of output from make check (or fallback command).

────────────────────────────────────────
Diff hygiene (MUST)
Run + paste outputs verbatim:

Preferred (if fetch worked):
- git diff --name-only origin/main...HEAD

Fallback (if fetch blocked OR origin/main unavailable):
- git diff --name-only main...HEAD

And always:
- git show --name-status --oneline -1

Must match Hard Scope.

────────────────────────────────────────
Commit + push (MUST)
- git add <file1> <file2> <new_file3>
- git diff --cached --name-only (paste; must match scope)
- git commit -m "<PR Title>"
- git push -u origin HEAD

Single-commit proof (required):
- git log --oneline --decorate -3
- git show --stat -1

────────────────────────────────────────
PR body (MUST fill template completely)
- (printf "Summary\n- <b1>\n- <b2>\n- <b3>\n\n"; cat .github/pull_request_template.md) > pr_body_raw.md
- Fill ALL sections in pr_body_raw.md and save as pr_body.md

HARD GATE (header match):
- rg -n "^## " .github/pull_request_template.md (or grep)
- rg -n "^## " pr_body.md
These header lists MUST match (same headers, no omissions).

PROOF REQUIRED:
"PR body validation passed ✅ (all template headers present)"

────────────────────────────────────────
Create PR (gh preferred; fallback required)
Try:
- gh pr create --base main --head <branch-name> --title "<PR Title>" --body-file pr_body.md
If fails:
- ONE remediation attempt (auth login OR full permissions: required_permissions: ["all"])
- Retry once
If still fails:
- Provide manual UI steps + paste FULL pr_body.md contents in final response

If PR is created successfully:
- gh pr diff --name-only (must match scope)
- gh pr checks --watch (or state "checks unavailable/pending")

PR ID PROOF (required if PR created):
- gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'

Cleanup always:
- rm -f pr_body.md pr_body_raw.md

────────────────────────────────────────
Return to main (MUST)
- git checkout main
- git pull --ff-only origin main (or "pull blocked")
- git status -sb (clean)

PROOF REQUIRED:
- Paste the final git status -sb output showing clean workspace.

────────────────────────────────────────
FINAL RESPONSE (MUST)
Return exactly:
1) Branch name + commit SHA
2) PR URL + number (OR "PR not created" + manual UI steps)
3) Files cha
