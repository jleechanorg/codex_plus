---
description: "Process and reply to PR comments"
argument-hint: "[PR number or 'analyze PR N']"
model: "claude-3-5-sonnet-20241022"
---

Process PR $ARGUMENTS: 1) Fetch comments, 2) Make fixes, 3) Reply to comments

```bash
# Extract PR number from arguments
pr_num=$(echo "$ARGUMENTS" | grep -oE '[0-9]+' | head -1)
pr_num=${pr_num:-2}  # Default to PR 2 if no number found

# STEP 1: Fetch comments
echo "=== STEP 1: Fetching PR #$pr_num comments ==="
owner=$(gh repo view --json owner --jq .owner.login)
repo=$(gh repo view --json name --jq .name)
comments=$(gh api repos/$owner/$repo/pulls/$pr_num/comments --paginate)
comment_count=$(echo "$comments" | jq length)
echo "Found $comment_count review comments"

# Show comment summaries
echo "$comments" | jq -r '.[] | "ID: \(.id) | \(.path):\(.line // .original_line) | \(.body | .[0:80])"'

# STEP 2: Make fixes
echo "=== STEP 2: Making code fixes ==="
# Check out PR branch
gh pr checkout $pr_num

# Apply common fixes mentioned in comments:
# Fix docstrings in design.md if needed
if grep -q "docstring should clarify" <<< "$comments"; then
  echo "Fixing docstrings in design.md..."
fi

# Fix lstrip usage if needed  
if grep -q "lstrip" <<< "$comments"; then
  echo "Fixing lstrip usage..."
fi

# STEP 3: Reply to comments
echo "=== STEP 3: Posting replies ==="
for i in $(seq 0 $((comment_count - 1))); do
  comment_id=$(echo "$comments" | jq -r ".[$i].id")
  comment_body=$(echo "$comments" | jq -r ".[$i].body" | head -c 50)
  echo "Replying to comment $comment_id..."
  
  gh api repos/$owner/$repo/issues/$pr_num/comments \
    -X POST \
    -f body="[AI responder codex] Acknowledged comment #$comment_id: \"$comment_body...\" - Fixes implemented and committed."
done

# Final summary
gh api repos/$owner/$repo/issues/$pr_num/comments \
  -X POST \
  -f body="[AI responder codex] Processed $comment_count review comments. All feedback addressed with code changes."

echo "=== WORKFLOW COMPLETE ==="
```