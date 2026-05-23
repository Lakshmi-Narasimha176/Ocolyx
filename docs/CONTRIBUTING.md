# Contributing to Ocolyx

Thanks for your interest in contributing to Ocolyx. This document describes how to set up a local development environment and the project's contribution workflow.

- Create a feature branch from `main`.
- Keep changes small and focused.
- Run tests and linters before submitting a PR.

Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Coding standards

- Follow PEP8 and use type hints where practical.
- Keep UI logic separated from business logic.
- Write tests for new features when possible.

Submitting a PR

- Ensure tests pass locally.
- Provide a clear description and screenshots where applicable.
- Link any related issues.
