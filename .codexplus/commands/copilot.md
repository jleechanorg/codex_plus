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
2. Create a namespaced scratch root under `/tmp` so artifacts stay grouped by repo and branch:
   ```bash
   REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
   CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   SCRATCH_ROOT="/tmp/${REPO_NAME}__${CURRENT_BRANCH}"
   mkdir -p "$SCRATCH_ROOT"
   WORK_DIR=$(mktemp -d "$SCRATCH_ROOT/copilot.XXXXXX")
   ```
3. Define paths inside `WORK_DIR` for raw comments, triage tables, draft replies, and logs. Example:
   ```bash
   COMMENTS_JSON="$WORK_DIR/comments.json"
   TRIAGE_MD="$WORK_DIR/triage.md"
   REPLIES_MD="$WORK_DIR/replies.md"
   RESPONSES_JSON="$WORK_DIR/responses.json"
   OPERATIONS_LOG="$WORK_DIR/operations.log"
   ```
4. Document `SCRATCH_ROOT` and these artifact paths in the session output so the user can inspect them later.
5. Register a cleanup plan (`trap 'rm -rf "$WORK_DIR"' EXIT`) or explicitly remind the user to remove the directory (and the parent `SCRATCH_ROOT` when empty).

## Phase 2 – Collect Review Feedback
- **GitHub CLI available:**
  ```bash
  if [ -n "${ARGUMENTS:-}" ]; then
    read -r PR_NUMBER _ <<<"$ARGUMENTS"
  fi
  if [ -z "${PR_NUMBER:-}" ]; then
    PR_NUMBER=$(gh pr view --json number --jq '.number')
  fi
  gh pr view "$PR_NUMBER" --json comments,reviews > "$COMMENTS_JSON"
  # Need inline review threads? Capture them separately and merge:
  # gh api graphql -f query='query($pr:Int!){repository(owner:"<owner>",name:"<repo>"){pullRequest(number:$pr){reviewThreads{nodes{comments{body,path,startLine,line}}}}}}' -f pr="$PR_NUMBER" > "$WORK_DIR/review_threads.json"
  # Combine thread data into "$COMMENTS_JSON" with jq before continuing.
  ```
- **Comment export provided:** copy the file into `COMMENTS_JSON` and record the provenance (local export, pasted notes, etc.).
- **Manual input:** ask the user to supply comments via scratch file; store them in `COMMENTS_JSON` using `cat <<'EOF'`.
- Validate JSON with `jq empty "$COMMENTS_JSON"`; abort gracefully if parsing fails.

## Phase 3 – Analyse & Prioritise
1. Derive actionable entries with `jq` and write them to `TRIAGE_MD` as a markdown bullet list, one per comment, e.g. `- [blocking] path/to/file.py:120 (alice) – ensure auth middleware handles 401`. Include the `comment_id` and linkable context where helpful.
2. Sort the list by severity using a cautious heuristic:
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
1. For each actionable comment, capture the REST `comment_id` (e.g., `gh api ... --jq '.id'`) and draft a numbered reply block in `REPLIES_MD`:
   ```markdown
   1. [AI responder] Thanks for flagging the auth bypass—added an explicit check.
      - Status: resolved
      - Action Taken: Updated middleware guard and added regression test.
      - Evidence: pytest -k auth_guard (pass)
   ```
   Keep `[AI responder]` at the start of the numbered line to satisfy auto-posting requirements.
2. Reference files as `path/to/file.py:123` inside the reply body to aid reviewers.
3. Compute response coverage with a safe default that matches the documented formats:
   ```bash
   RESPONDED=$(grep -c '^[0-9]\+\. \[AI responder\]' "$REPLIES_MD" 2>/dev/null || echo 0)
   ACTIONABLE=$(grep -c '^- \[[^]]\+\]' "$TRIAGE_MD" 2>/dev/null || echo 0)
   if [ "$ACTIONABLE" -gt 0 ]; then
     COVERAGE=$(( RESPONDED * 100 / ACTIONABLE ))
   else
     COVERAGE=100
   fi
   ```
4. Materialise API-ready responses for auto-posting (use numeric `comment_id` values from `gh api`):
   ```bash
   cat <<'EOF' > "$RESPONSES_JSON"
   {
     "responses": [
       {
         "comment_id": 1234567890,
         "reply_text": "[AI responder] DONE – replace with your actual reply text"
       }
     ]
   }
   EOF
   ```
   Add or edit entries per comment before posting.
5. Optionally auto-post replies when Codex-compatible tooling is available:
   - **Repo script available:**
     ```bash
     if [ -f scripts/commentreply.py ]; then
       OWNER=$(gh repo view --json owner --jq '.owner.login')
       REPO=$(gh repo view --json name --jq '.name')
       PR_NUMBER=${PR_NUMBER:-$(gh pr view --json number --jq '.number')}
       python scripts/commentreply.py --owner "$OWNER" --repo "$REPO" --pr "$PR_NUMBER" --input "$RESPONSES_JSON"
     fi
     ```
   - **No automation:** fall back to manual posting via `gh api` (document the limitation in `OPERATIONS_LOG` and in the final summary).
   Review any tool output for success indicators and capture URLs in `OPERATIONS_LOG`.
6. Flag any comments that need escalation or reviewer clarification.

## Phase 7 – Wrap Up & Handoff
- Summarise key metrics: execution duration (`$(date +%s) - START_TIME`), files touched, tests run, response coverage.
- Provide next steps for the user (e.g., `git commit`, push, paste replies in GitHub UI).
- Remind the user to inspect and then remove `WORK_DIR` (and clean up `/tmp/${REPO_NAME}__${CURRENT_BRANCH}` if empty) unless they wish to archive it.

## Expected Output Skeleton
```text
Source: <gh api | local export | manual>

Comment Summary (stored in $WORK_DIR/triage.md within /tmp/${REPO_NAME}__${CURRENT_BRANCH})
- [blocking] path/to/file.py:120 (alice) – ensure auth middleware handles 401...
- [follow-up] docs/update.md:45 (reviewer) – clarify CLI flag behaviour

Actions
- ✅ Added language hint to Expected Output Skeleton (.codexplus/commands/copilot.md:92)
- ✅ Posted replies via scripts/commentreply.py (see OPERATIONS_LOG URLs)
- ✅ pytest -q (pass)

Draft Replies (see $WORK_DIR/replies.md within /tmp/${REPO_NAME}__${CURRENT_BRANCH})
1. [AI responder] Thanks for flagging the auth bypass—added an explicit check.
   - Status: resolved
   - Action Taken: Updated middleware guard and added regression test.
   - Evidence: pytest -k auth_guard (pass)
2. [AI responder] Confirmed CLI flag behaviour remains unchanged.
   - Status: resolved
   - Action Taken: Clarified docs and added assertion.
   - Evidence: pytest -k cli_flags (pass)

Metrics
- Duration: 18m
- Files touched: 4
- Tests: pytest -q (pass)
- Coverage: 5/6 actionable (83%)
- Auto-post: scripts/commentreply.py ✅

Next Steps
- sanity-check posted replies on GitHub
- git commit -am "fix: harden auth middleware" (pending)
```

## Safety Rails
- Abort if comment collection fails; request new input before proceeding.
- Clean up temporary directories and redact sensitive data from logs before finishing.
- If automation (e.g., `gh`) is unavailable, fall back to manual steps and document the limitation in the summary.
