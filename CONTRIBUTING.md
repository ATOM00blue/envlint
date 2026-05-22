# Contributing to envlint

Thanks for your interest in improving envlint! This project aims to be a small,
focused, dependable tool, so contributions that keep it lean and well-tested
are very welcome.

## Development setup

```bash
git clone https://github.com/ATOM00blue/envlint
cd envlint

python -m venv .venv
# macOS / Linux:
. .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

## Running the test suite

```bash
pytest                 # run all tests
pytest --cov=envlint   # with coverage
```

All new behavior should come with tests. We keep fixtures of good and bad
`.env` files under `tests/fixtures/`.

## Linting & formatting

We use [ruff](https://github.com/astral-sh/ruff):

```bash
ruff check .
ruff format .
```

CI runs the test suite and ruff on Python 3.9–3.13 across Linux and Windows.
Please make sure both pass before opening a PR.

## Adding a new check

1. Decide which module it belongs to:
   - structural/syntax → `src/envlint/lint.py`
   - schema validation → `src/envlint/schema.py`
   - secret detection → `src/envlint/secrets.py`
2. Emit a `Finding` with a **stable, unique `code`** and an appropriate
   `Severity`. Add a `hint` that tells the user how to fix it.
3. Add it to the rule reference table in `README.md`.
4. Add tests, including a fixture if useful.

## Adding a secret pattern

Add a `SecretPattern` to `_PATTERNS` in `secrets.py`. Prefer **anchored,
high-signal** regexes to keep the false-positive rate low, and add a test with
a realistic (fake) example value.

## Commit & PR guidelines

- Keep PRs focused; one logical change per PR.
- Write a clear description of *why*, not just *what*.
- Reference any related issue.

## Code of conduct

Be respectful and constructive. We want envlint to be a welcoming project.
