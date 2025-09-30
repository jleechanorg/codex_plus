---
name: copilot
description: "Self-contained Codex workflow for processing PR feedback and drafting responses"
argument-hint: "<comment-export.json | PR number | optional notes>"
---

# /copilot — Expanded Review Workflow (Codex Edition)

Use this command when a pull request already exists and Codex needs to process reviewer feedback end-to-end. It mirrors the Claude `/copilot-expanded` flow but stays compatible with the tooling available in this repository.

## Phase 0 – Preconditions
- Ensure `git status -sb` shows only changes relevant to the PR.
- Confirm the current branch matches the PR branch (`git branch --show-current`).
- If the argument is a PR number, verify `gh` is authenticated; otherwise prepare a local comment export or manual notes.

## Phase 1 – Workspace Setup
1. Capture a start timestamp: `START_TIME=$(date +%s)`.
2. Create a scratch directory for artifacts: `WORK_DIR=$(mktemp -d)`.
3. Define paths inside `WORK_DIR` for raw comments, triage tables, draft replies, and logs. Example:
   ```bash
   COMMENTS_JSON="$WORK_DIR/comments.json"
   TRIAGE_MD="$WORK_DIR/triage.md"
   REPLIES_MD="$WORK_DIR/replies.md"
   OPERATIONS_LOG="$WORK_DIR/operations.log"
   ```
4. Document these paths in the session output so the user can inspect them later.
5. Register a cleanup plan (`trap 'rm -rf "$WORK_DIR"' EXIT`) or explicitly remind the user to remove the directory.

## Phase 2 – Collect Review Feedback
- **GitHub CLI available:**
  ```bash
  PR_NUMBER=${ARGUMENTS:-$(gh pr view --json number --jq '.number')}
  gh pr view "$PR_NUMBER" --json comments,reviews > "$COMMENTS_JSON"
  # Need inline review threads? Capture them separately and merge:
  # gh api graphql -f query='query($pr:Int!){repository(owner:"<owner>",name:"<repo>"){pullRequest(number:$pr){reviewThreads{nodes{comments{body,path,startLine,line}}}}}}' -f pr="$PR_NUMBER" > "$WORK_DIR/review_threads.json"
  # Combine thread data into "$COMMENTS_JSON" with jq before continuing.
  ```
- **Comment export provided:** copy the file into `COMMENTS_JSON` and record the provenance (local export, pasted notes, etc.).
- **Manual input:** ask the user to supply comments via scratch file; store them in `COMMENTS_JSON` using `cat <<'EOF'`.
- Validate JSON with `jq empty "$COMMENTS_JSON"`; abort gracefully if parsing fails.

## Phase 3 – Analyse & Prioritise
1. Derive actionable entries with `jq` and write a markdown summary table to `TRIAGE_MD`. Include: `comment_id`, `author`, `file:line`, severity, and short excerpt.
2. Sort the table by severity using a cautious heuristic:
   - Mentions of "security", "failing", "bug", or similar high-risk keywords ⇒ **blocking**
   - Questions about security, correctness, or stability (e.g., "Is this safe?", "Could this leak data?", "Does this handle errors?") ⇒ **blocking**
   - Other questions (e.g., "Why did you choose this approach?", "Can this be simplified?") ⇒ **follow-up**
   - Style or minor wording items ⇒ **nit**
   - When ambiguous, err on the side of caution and categorise as **blocking** if it could impact functionality or safety. Example: "Should we validate user input here?" ⇒ **blocking**
3. Count totals (overall, actionable, already replied) and log them to `OPERATIONS_LOG` with timestamps.
4. Produce a work plan grouping comments by file or subsystem. Highlight dependencies (e.g., “update fixture before fixing tests”).

## Phase 4 – Implement Fixes
- Tackle items in priority order: blocking → follow-up → nit, noting that blocking items include security and correctness concerns.
- For each batch of related comments:
  1. Apply edits using Edit/MultiEdit.
  2. Record affected files and commands in `OPERATIONS_LOG`.
  3. Display focused diffs (`git diff -- <file>` or `git diff --stat`) so the user can verify progress.
- Use temporary branches or stashes if risky experiments are required; always return to the main PR branch before continuing.

## Phase 5 – Validation Gates
1. Run targeted checks referenced by reviewers; fall back to `pytest -k ...` or `./run_tests.sh` if uncertain.
2. Capture outputs verbatim in the session, noting pass/fail status.
3. If tests fail, loop back to Phase 4 with a concise bug report and log the failure in `OPERATIONS_LOG`.
4. Optionally check mergeability with `gh pr view "$PR_NUMBER" --json mergeable --jq '.mergeable'` when `gh` is available.
5. Re-run quick lint/type checks when they relate to the feedback (e.g., formatting feedback).

## Phase 6 – Draft Responses & Evidence
1. For each actionable comment, draft a markdown reply in `REPLIES_MD` with sections:
   - `Status` (resolved / needs input / blocked)
   - `Action Taken` (code summary, tests, commit hash if available)
   - `Reply` text prefixed with `[AI helper codex]`
2. Reference files as `path/to/file.py:123` to aid reviewers.
3. Compute response coverage with a safe default:
   ```bash
   RESPONDED=$(grep -c '^## Comment ' "$REPLIES_MD" 2>/dev/null || echo 0)
   ACTIONABLE=$(grep -c 'severity:' "$TRIAGE_MD" 2>/dev/null || echo 0)
   if [ "$ACTIONABLE" -gt 0 ]; then
     COVERAGE=$(( RESPONDED * 100 / ACTIONABLE ))
   else
     COVERAGE=100
   fi
   ```
4. Flag any comments that need escalation or reviewer clarification.

## Phase 7 – Wrap Up & Handoff
- Summarise key metrics: execution duration (`$(date +%s) - START_TIME`), files touched, tests run, response coverage.
- Provide next steps for the user (e.g., `git commit`, push, paste replies in GitHub UI).
- Remind the user to inspect and then remove `WORK_DIR` unless they wish to archive it.

## Expected Output Skeleton
```
Source: <gh api | local export | manual>

Comment Summary (stored in $WORK_DIR/triage.md)
- [blocking] src/api.py:120 (alice) – ensure auth middleware handles 401...
...

Actions
- ✅ Comment 42 – fixed in src/api.py (tests: pytest -k auth)
- 🔄 Comment 51 – needs reviewer input about staging data

Draft Replies (see $WORK_DIR/replies.md)
1. [AI helper codex] Thanks for flagging the auth bypass... (resolved)

Metrics
- Duration: 18m
- Files touched: 4
- Tests: pytest -k auth (pass)
- Coverage: 5/6 actionable (83%)

Next Steps
- Post replies in GitHub UI
- git commit -am "fix: harden auth middleware" (pending)
```

## Safety Rails
- Abort if comment collection fails; request new input before proceeding.
- Never post to GitHub automatically; all communication stays local for the user to copy.
- Clean up temporary directories and redact sensitive data from logs before finishing.
- If automation (e.g., `gh`) is unavailable, fall back to manual steps and document the limitation in the summary.
