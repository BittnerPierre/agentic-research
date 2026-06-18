# Branch Protection Checklist for `main`

Apply this in GitHub: Settings > Branches > Add branch protection rule

Branch name pattern:

- `main`

Enable these settings:

- Require a pull request before merging
- Require approvals: `1` minimum
- Dismiss stale pull request approvals when new commits are pushed
- Require review from code owners: only if the target repo has a `CODEOWNERS` file
- Require conversation resolution before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Include administrators

Required status checks to select:

- `Lint & Format Check`
- `Test (Python 3.12)`

Enable these restrictions:

- Allow force pushes: disabled
- Allow deletions: disabled

Optional, depending on your merge policy:

- Require linear history: enable if you want merge commits forbidden
- Require signed commits: enable only if the team already signs commits
- Lock branch: keep disabled for normal development

Result:

- direct pushes to `main` are blocked because merges must go through a pull request
- at least one review is required before merge
- CI must be green before merge
- admins are also subject to the same rule set
