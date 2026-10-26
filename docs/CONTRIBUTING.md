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

Testing

Run the test suite from the repository root:

```powershell
pytest
```

On some Windows systems, pytest may fail before tests run because the default
temporary directory is not writable. If you see Windows temp directory
permission errors, run pytest with a workspace-local temp directory:

```powershell
pytest --basetemp .\test-tmp
```

Submitting a PR

- Ensure tests pass locally.
- Provide a clear description and screenshots where applicable.
- Link any related issues.
