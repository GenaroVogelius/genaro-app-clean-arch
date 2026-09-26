---
root: false
targets:
  - '*'
description: Always run Python commands with the project .venv activated
globs:
  - '**/*'
cursor:
  alwaysApply: true
  description: Always run Python commands with the project .venv activated
  globs:
    - '**/*'
---
# Python commands must use `.venv`

When running Python-related commands (tests, scripts, linters, tooling), **always** use the repository virtual environment.

## Preferred (bash on Windows)

```bash
source ".venv/Scripts/activate"
python -m pytest -q
```

## Safe one-liners (no activation needed)

```bash
".venv/Scripts/python" -m pytest -q
".venv/Scripts/python" -m pip install -r requirements.txt
```

If a command fails with “command not found” (e.g. `pytest`), rerun it via `python -m ...` using the `.venv` interpreter.
