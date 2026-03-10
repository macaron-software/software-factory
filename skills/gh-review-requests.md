---
name: gh-review-requests
version: 1.0.0
description: Fetch unread GitHub notifications for open PRs where review is requested
  from a specified team or opened by a team member. Use when asked to "find PRs I
  need to review", "show my review requests", ...
metadata:
  category: development
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - asked to "find prs i need to review", "show my review requests",
  - '`"review requested from: <team name>"` — the team is a requested reviewer'
eval_cases:
- id: gh-review-requests-approach
  prompt: How should I approach gh review requests for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on gh review requests
  tags:
  - gh
- id: gh-review-requests-best-practices
  prompt: What are the key best practices and pitfalls for gh review requests?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for gh review requests
  tags:
  - gh
  - best-practices
- id: gh-review-requests-antipatterns
  prompt: What are the most common mistakes to avoid with gh review requests?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - gh
  - antipatterns
---
# gh-review-requests

# GitHub Review Requests

Fetch unread `review_requested` notifications for open (unmerged) PRs, filtered by a GitHub team.

**Requires**: GitHub CLI (`gh`) authenticated.

## Step 1: Identify the Team

If the user has not specified a team, ask:

> Which GitHub team should I filter by? (e.g. `streaming-platform`)

Accept either a team slug (`streaming-platform`) or a display name ("Streaming Platform") — convert to lowercase-hyphenated slug before passing to the script.

## Step 2: Run the Script

```bash
uv run ${CLAUDE_SKILL_ROOT}/scripts/fetch_review_requests.py --org getsentry --teams <team-slug>
```

To filter by multiple teams, pass a comma-separated list:

```bash
uv run ${CLAUDE_SKILL_ROOT}/scripts/fetch_review_requests.py --org getsentry --teams <team slugs>
```

### Script output

```json
{
  "total": 3,
  "prs": [
    {
      "notification_id": "12345",
      "title": "feat(kafka): add workflow to restart a broker",
      "url": "https://github.com/getsentry/ops/pull/19144",
      "repo": "getsentry/ops",
      "pr_number": 19144,
      "author": "bmckerry",
      "reasons": ["opened by: bmckerry"]
    }
  ]
}
```

`reasons` will contain one or both of:
- `"review requested from: <Team Name>"` — the team is a requested reviewer
- `"opened by: <login>"` — the PR author is a team member

## Step 3: Present Results

Display results as a markdown table with full URLs:

| # | Title | URL | Reason |
|---|-------|-----|--------|
| 1 | feat(kafka): add workflow to restart a broker | https://github.com/getsentry/ops/pull/19144 | opened by: evanh |

If `total` is 0, say: "No unread review requests found for that team."

## Fallback

If the script fails, run manually:

```bash
gh api notifications --paginate
```

Then for each `review_requested` notification, check:
- `gh api repos/{repo}/pulls/{number}` — skip if `state == "closed"` or `merged_at` is set
- `gh api repos/{repo}/pulls/{number}/requested_reviewers` — check `teams[].name`
- `gh api orgs/{org}/teams/{slug}/members` — check if author is a member
