# Contributing to ComradBot

Thank you for helping improve ComradBot. Read `AGENTS.md` before changing the project; it defines the
architecture, safety constraints, coding conventions, and definition of done for both human and AI
contributors.

## Development setup

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Use only test credentials in local development. Never commit `.env`, Discord tokens, OpenAI keys,
signed stream URLs, or authentication headers.

## Making a change

1. Inspect the related implementation, tests, documentation, and open roadmap items.
2. Keep Discord Cogs thin and put business rules in services or domain modules.
3. Preserve the shared guild audio player and existing provider/repository abstractions.
4. Add deterministic tests for important success and failure behavior.
5. Update `README.md` and `TODO.md` when behavior or project status changes.
6. Keep documentation and commit messages in English.

The default test suite must not call Discord, OpenAI, or media platforms.

## Required checks

Run all checks before proposing a change:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

Report any command that could not be run and explain why. Do not claim skipped checks passed.

## Pull requests

Keep pull requests focused and describe:

- what changed and why;
- architectural or security decisions;
- tests added or updated;
- commands executed and their results;
- remaining limitations or manual setup.

Do not bundle unrelated refactors with a feature or bug fix.
