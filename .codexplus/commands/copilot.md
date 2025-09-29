---
name: copilot
description: "Process review feedback, apply fixes, and draft replies using only Codex CLI tools"
argument-hint: "<comment-export.json | PR number | optional notes>"
---

# /copilot — Review Feedback Helper (Codex Edition)

Use this command when a pull request already exists and you need Codex to work through reviewer feedback. It mirrors the intent of the Claude `/copilot` workflow but stays within tools that ship in this repository.

## Inputs & Context
- If `$ARGUMENTS` points to a local JSON/NDJSON export (from `gh api` or the GitHub UI), load it with `jq`.
- If the argument looks like a PR number and the GitHub CLI (`gh`) is available, gather comments with
  `gh pr view $pr --json reviewComments,comments`.
- If neither is available, ask the user to paste the feedback or point to a scratch file inside the repo.
- Always record which source was used in the final summary.

## Phase 1 – Snapshot & Prioritise
1. Confirm current branch and diff with `git status -sb` and `git diff --stat`.
2. Build a comment table capturing: `id`, `author`, `type (blocking/nit/question)`, `file:line`, and a short excerpt.
3. Sort the table by severity using a simple heuristic:
   - Mentions of "security", "failing", "bug" ⇒ **blocking**
   - Questions ⇒ **follow-up**
   - Style/minor wording ⇒ **nit**

## Phase 2 – Triage & Plan
- Group comments by file so fixes can be batched efficiently.
- Generate a short action plan that maps each comment group to files/tests.
- Identify any comments that require clarification and flag them early.

## Phase 3 – Implement Fixes
- Apply changes with Edit/MultiEdit; keep commits small and reference the comment ids in inline notes when helpful.
- After each batch, show the relevant portion of `git diff` so the user can verify.
- Prioritise blocking issues first, then questions, then nits.

## Phase 4 – Validate
- Run targeted tests mentioned in the comments; fall back to `pytest -q` or `./run_tests.sh` when unsure.
- Capture command outputs. If tests cannot run, explain why and suggest next steps.
- Re-run quick lint/type checks when they relate to the feedback (e.g., formatting complaints).

## Phase 5 – Draft Replies & Evidence
- For every comment, prepare a structured reply with:
  - `Status`: resolved / needs input / needs escalation
  - `Action taken`: code or test summary referencing commit hashes or diff snippets
  - `Reply text`: ready-to-paste Markdown (prefix with `[AI helper codex]` for traceability)
- Do **not** attempt to post via API; just surface the replies in the response body.
- Include links to relevant lines using repository-relative paths when possible (`src/module/file.py:123`).

## Phase 6 – Wrap Up
- Summarise overall progress: number of comments resolved vs outstanding, tests run, remaining blockers.
- If follow-up is required from the reviewer, list concrete questions.
- Recommend next manual steps (e.g., run `git commit`, push branch, post replies in GitHub UI).

## Safety Rails
- Stop immediately if fetching comments fails and let the user decide how to proceed.
- Never delete reviewer comments or rewrite history without explicit approval.
- Keep temporary artefacts in `/tmp` and clean them up before finishing.

## Expected Output Skeleton
```
Source: <comment export | gh PR | manual input>

Comment Table
- [blocking] file.py:42 (author) – summary
...

Actions
- ✅ Comment 123 – fixed with ... (tests: ...)
- 🔄 Comment 127 – needs clarification: ...

Draft Replies
1. [AI helper codex] ...

Tests
- pytest -k foo  (pass)

Next Steps
- [1] Post replies in GitHub UI
- [2] git commit -am "..." (pending)
```

The goal is to leave the user with reviewed code, passing tests, and high quality draft responses they can copy into the PR.
