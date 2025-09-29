---
name: pr
description: "End-to-end PR workflow tailored for Codex CLI"
argument-hint: "<task summary or ticket id>"
---

# /pr — Codex-Friendly Pull Request Flow

Run this command when you want Codex to take a change from idea to a ready-to-ship PR without relying on Claude-only automation. The assistant should execute each phase sequentially and surface checkpoints so the user can intervene at any time.

## Phase 0 – Setup & Guardrails
- Confirm repo state with `git status -sb`; stop if unrelated dirty files exist unless the user opts in.
- Record current branch, target branch, and task summary from arguments or prompt the user if missing.
- Establish a scratch plan file (e.g. note in conversation) instead of writing to protected docs.

## Phase 1 – Deep Understanding & Plan
- Analyse the request, existing code, and relevant tests. Use `rg`, `ls`, or targeted file reads only as needed.
- Produce a concise plan (3–6 steps) that maps work items to files/test suites. Ask for confirmation when scope is ambiguous.

## Phase 2 – Implementation
- Execute the plan step by step using the Codex edit tools (Edit/MultiEdit).
- Keep diffs tight and well commented; avoid touching files flagged in `CLAUDE.md` as protected.
- After each major edit, show `git diff --stat` (or relevant snippet) so progress stays visible.

## Phase 3 – Validation
- Prefer `./run_tests.sh` when runtime is reasonable; otherwise run the smallest meaningful subset (e.g. `pytest -k <pattern>` or module-level scripts).
- Capture command output in the response. If tests are skipped, explain why and list follow-up steps.
- Optionally run lightweight lint or type checks that ship in this repo.

## Phase 4 – Commit Preparation
- Summarize changes and confirm there are no leftover debug artifacts.
- Stage files with `git add` only after verifying the diff (show snippets for critical logic).
- Craft a Conventional Commit-style message that matches repo guidance (`fix(middleware): …`, etc.). Ask the user before running `git commit`; if approved, execute `git commit` and show the summary.

## Phase 5 – PR Package
- Gather the information needed for the PR template: Goal, Modifications, Necessity, Integration Proof, Tests/Logs.
- If `gh` is available, optionally run `gh pr view --json` to gather metadata; otherwise rely on local context.
- Produce a final report containing:
  - ✅ Status of each plan step
  - 🧪 Test commands + results
  - 📝 Draft commit message (or confirmation it was committed)
  - 📄 Ready-to-paste PR description following repository guidelines
  - 🔜 Next steps (e.g. open PR, request review)

## Completion Rules
- Do not skip phases even if the task seems trivial.
- Stop immediately and surface blockers if dependencies are missing or tests fail.
- Always leave the workspace in a clean state or clearly call out remaining work.
