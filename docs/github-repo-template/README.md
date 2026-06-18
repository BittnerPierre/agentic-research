# GitHub Repo Governance Template

This directory packages the current repository standards into a small copy-ready starter for a new GitHub repo.

Contents:

- `ci.yml`: GitHub Actions workflow with the same CI checks used here
- `pyproject.toml`: minimal Python project config for `uv`, `pytest`, and `ruff`
- `github-branch-protection-checklist.md`: branch protection settings to reproduce on `main`

Target baseline:

- Python 3.12
- `uv` for dependency install and command execution
- `ruff check .`
- `ruff format --check .`
- `pytest tests/ -v --tb=short`

Recommended rollout for a new repo:

1. Copy `ci.yml` to `.github/workflows/ci.yml`
2. Merge the `pyproject.toml` sections into the target repo
3. Apply the branch protection checklist to `main`
4. Mark required status checks with the exact job names:
   - `Lint & Format Check`
   - `Test (Python 3.12)`

Notes:

- This starter goes one step further than the current remote config of this repo by explicitly requiring pull requests and reviews on `main`.
- Keep the job names unchanged if you want the branch protection checklist to match without adaptation.
