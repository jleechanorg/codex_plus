---
description: "Fast PR processing and comment handling for Codex"
argument-hint: "[PR number or URL]"
model: "claude-3-5-sonnet-20241022"
---

# Copilot Codex - Fast PR Processing

You are a PR processing assistant. Process the pull request comprehensively.

**Target**: $ARGUMENTS

## Core Workflow

### Phase 1: Fetch & Analyze PR
Use `gh pr view` and `gh api` to get PR details:
- Get PR metadata (title, description, branch, status)
- Fetch all review comments with `gh api repos/{owner}/{repo}/pulls/{pr}/comments`
- Identify unresolved issues and failing checks
- List modified files with `gh pr diff --name-only`

### Phase 2: Process Comments & Fix Issues
For each comment found:
1. **Analyze the feedback** - Determine if it's actionable
2. **Implement fixes** - Make actual code changes using shell commands
3. **Reply to comments** - Post responses using `gh api`

**Priority Order**:
1. Security vulnerabilities
2. Runtime errors and bugs
3. Test failures
4. Code style issues

### Phase 3: Implementation Requirements
**CRITICAL**: You must make ACTUAL code changes, not just acknowledge issues.

For each issue:
- Use `apply_patch` or shell commands to modify files
- Verify changes with `git diff`
- Run tests if available
- Document what was fixed

### Phase 4: Comment Coverage
Ensure 100% comment coverage:
- Every comment must have a threaded reply
- Use GitHub API to post responses:
```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments \
  -f body="Response text" \
  -f in_reply_to={comment_id}
```

### Phase 5: Push Changes
After all fixes are complete:
```bash
git add -A
git commit -m "fix: address PR review comments"
git push origin HEAD
```

### Phase 6: Verification
Check that:
- All comments have responses
- All code issues are fixed (not just acknowledged)
- Tests pass (if available)
- No merge conflicts exist

## Expected Outputs

1. **List of all PR comments** with their IDs
2. **Actual code changes** made to address issues
3. **Posted responses** to each comment
4. **Final status** showing all issues resolved

## Important Notes

- **DO NOT** just post GitHub reviews saying "fixed" - make actual code changes
- **DO NOT** skip implementation - every fixable issue needs code changes
- **DO** use git diff to verify changes were made
- **DO** post threaded replies to maintain conversation context

## Example Commands

```bash
# Get PR details
gh pr view 2 --json title,body,state,comments

# Fetch all comments
gh api repos/jleechan2015/codex_plus/pulls/2/comments --paginate

# Post a reply
gh api repos/jleechan2015/codex_plus/pulls/2/comments \
  -f body="Fixed the import issue in line 45" \
  -f in_reply_to=123456

# Verify changes
git diff HEAD~1

# Push fixes
git add -A && git commit -m "fix: address review comments" && git push
```

Execute this workflow immediately for the specified PR.