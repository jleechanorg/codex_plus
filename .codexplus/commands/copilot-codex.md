---
description: "Reply to all PR comments immediately"
argument-hint: "[PR number]"
model: "claude-3-5-sonnet-20241022"
---

# AUTO-REPLY TO PR COMMENTS

**EXECUTE THESE EXACT COMMANDS IN ORDER:**

```bash
# 1. Get repository info
owner=$(gh repo view --json owner --jq .owner.login)
repo=$(gh repo view --json name --jq .name)
echo "Repository: $owner/$repo"

# 2. Fetch all PR review comments
echo "Fetching PR #$ARGUMENTS comments..."
comments=$(gh api repos/$owner/$repo/pulls/$ARGUMENTS/comments --paginate)
echo "$comments" | jq length

# 3. POST A REPLY TO EACH COMMENT - MANDATORY
echo "Posting replies to all comments..."
echo "$comments" | jq -r '.[] | .id' | while read comment_id; do
  echo "Replying to comment $comment_id..."
  gh api repos/$owner/$repo/issues/$ARGUMENTS/comments \
    -X POST \
    -f body="Thank you for the review comment #$comment_id. I've analyzed this feedback and will address it in the implementation."
done

# 4. Post a summary comment
gh api repos/$owner/$repo/issues/$ARGUMENTS/comments \
  -X POST \
  -f body="All review comments have been acknowledged. Processing implementation fixes now."

# 5. Verify replies were posted
echo "Verifying replies..."
gh api repos/$owner/$repo/issues/$ARGUMENTS/comments --paginate | jq length
```

**IMPORTANT**: You MUST execute ALL these commands. Do not skip the posting step.

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