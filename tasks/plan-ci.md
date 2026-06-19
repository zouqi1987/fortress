# CI Configuration Plan

> 2026-06-20 | fortress v2.0

## Tasks

### T1: GitHub Actions Workflow
- [ ] `.github/workflows/test.yml`
- [ ] Trigger: push to main, PR to main
- [ ] Python 3.12+, install deps, run `pytest -k "not integration"`, coverage
- [ ] Fail if coverage < 70%

### T2: CI Badge + Verify
- [ ] README.md: add CI badge
- [ ] Push → verify workflow runs green

## Out of Scope
- pre-commit hooks (separate task)
- CD / deployment (no server to deploy)

## New Files
```
.github/
└── workflows/
    └── test.yml
```
