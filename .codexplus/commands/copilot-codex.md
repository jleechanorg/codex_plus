---
description: "Process and reply to PR comments"
argument-hint: "[PR number]"
model: "claude-3-5-sonnet-20241022"
---

Reply to all comments on pull request #$ARGUMENTS. Here's what you need to do:

1. First, get the repository information and fetch all review comments from PR #$ARGUMENTS
2. For each review comment you find, post a reply acknowledging it
3. Post a summary comment saying you've reviewed all feedback

Use the GitHub CLI (gh) to fetch comments and post replies. Make sure to actually post replies using `gh api` with POST method to the issues endpoint.

Start by running:
```bash
owner=$(gh repo view --json owner --jq .owner.login)
repo=$(gh repo view --json name --jq .name)
gh api repos/$owner/$repo/pulls/$ARGUMENTS/comments --paginate | jq '.[] | {id, body, user}'
```

Then for each comment, post a reply using:
```bash
gh api repos/$owner/$repo/issues/$ARGUMENTS/comments -X POST -f body="Your reply text here"
```

Make sure you actually post the replies, don't just acknowledge the comments.

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