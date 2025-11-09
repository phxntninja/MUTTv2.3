# Development Standards (Phase 1)

This document summarizes the Phase 1 code hygiene and clarity standards adopted for MUTT v2.5 modernization.

## Tools

- Formatting: `black` (line length 100)
- Imports: `isort` (Black profile)
- Linting: `ruff` (pycodestyle/pyflakes/imports/pyupgrade)
- Type checking: `mypy` (incremental rollout)

A shared configuration lives in `pyproject.toml`.

## Local Commands

```bash
pip install black isort ruff mypy

black .
isort .
ruff check services/ tests/
mypy services/ tests/
```

## CI

The CI Lint job runs all four. Ruff and MyPy are initially non-blocking to preserve stability during incremental adoption.

## Rollout Plan

- Add type hints to service boundaries and utility functions first.
- Improve/standardize docstrings for public functions and modules.
- Address Ruff warnings in small batches; then make Ruff blocking.
- Once types are in place for critical paths, make MyPy blocking.

## Notes

- Do not change runtime behavior during hygiene-only changes.
- Prefer small, reviewable PRs focused on one subsystem at a time.
