---
description: "Reply to PR comments with AI responder tag"
argument-hint: "[PR number]"
---

Run these commands now:

pr_num=$(echo "$ARGUMENTS" | grep -oE '[0-9]+' | head -1 || echo "2")
owner=$(gh repo view --json owner --jq .owner.login)
repo=$(gh repo view --json name --jq .name)
comments=$(gh api repos/$owner/$repo/pulls/$pr_num/comments --paginate)
comment_count=$(echo "$comments" | jq length)

for i in $(seq 0 $((comment_count - 1))); do
  comment_id=$(echo "$comments" | jq -r ".[$i].id")
  gh api repos/$owner/$repo/issues/$pr_num/comments -X POST -f body="[AI responder codex] Acknowledged comment #$comment_id - implementing fixes now."
done

gh api repos/$owner/$repo/issues/$pr_num/comments -X POST -f body="[AI responder codex] Posted replies to $comment_count review comments. Implementing fixes next."