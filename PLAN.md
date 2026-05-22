# envlint — Plan & Spec

> Lint, validate, and document your `.env` files — catch missing vars, leaked secrets, and typos before they bite.

## Why

`.env` files are everywhere and almost never checked. Mistakes are silent until runtime:
missing required keys, duplicate keys (last wins, surprising), a secret accidentally committed,
or a typo (`DATBASE_URL`) that an app reads as "unset". `envlint` brings linting + schema
validation + secret detection + documentation generation to `.env` files, with a CI mode.

## Competitive landscape (research)

- **dotenv-linter (Rust)**: fast, syntax-focused (duplicate keys, ordering, blank lines, quotes).
  Strong on *style*, weak on *schema validation* and *secret detection*.
- **detect-secrets / gitleaks / trufflehog**: great secret scanners, but general-purpose and
  not `.env`-aware; no schema/required-key concept; heavy.
- **Gap envlint fills**: one focused tool that does **schema validation** (required keys, types,
  allowed values, patterns), **secret leak detection** (regex + entropy), **typo suggestions**
  against the schema, **`.env.example` generation**, and **diff** — all `.env`-native, pip/pipx
  installable, with a first-class CI mode.

## Scope (MVP + standout)

### Commands
- `envlint check [PATHS...]` — lint + validate. Core command.
  - `--schema PATH` (auto-detects `.env.schema`)
  - `--strict` (treat warnings as errors)
  - `--no-secrets` / `--no-schema` toggles
  - `--format text|json` (json for CI/tooling)
  - `--quiet`
  - Exit code 0 = clean, 1 = problems found, 2 = usage error.
- `envlint example [ENV] [-o .env.example]` — generate redacted example file.
- `envlint diff A B` — show keys only in A, only in B, and value-differing keys.
- `envlint schema [ENV] [-o .env.schema]` — scaffold a schema from an existing `.env`.

### Lint checks (syntax / structure)
- Duplicate keys
- Empty keys / keys with no `=`
- Leading/trailing whitespace around keys or values (unquoted)
- Lowercase keys (convention warning)
- Spaces around `=` (unquoted)
- Keys not starting with a letter/underscore (invalid POSIX env name)

### Schema validation
- Required keys present & non-empty
- Unknown keys (when schema marks itself complete) -> warning
- Type checks: `string|int|float|bool|url|email|port`
- `allowed = [...]` enum values
- `pattern = "regex"`
- Typo suggestions: a present key close (Levenshtein) to a schema key it doesn't match.

### Secret detection
- Known provider patterns (AWS, Stripe, GitHub, Google, Slack, OpenAI, JWT, private keys, ...).
- Shannon entropy heuristic for high-entropy values on secret-ish key names
  (KEY/SECRET/TOKEN/PASSWORD/...), with allowlist via schema (`secret = true/false`).
- Reported as warnings by default (a `.env` legitimately holds secrets), errors in `--strict`
  or when key is *not* expected to be secret.

## Schema format (`.env.schema`, TOML)

```toml
# .env.schema
[meta]
complete = true            # if true, unknown keys are flagged

[vars.DATABASE_URL]
required = true
type = "url"
description = "Postgres connection string"
secret = false

[vars.PORT]
type = "port"
default = "8000"

[vars.LOG_LEVEL]
allowed = ["debug", "info", "warn", "error"]
default = "info"

[vars.API_KEY]
required = true
secret = true
```

JSON schema (`.env.schema.json`) accepted too with the same structure.

## File layout

```
envlint/
  pyproject.toml
  README.md  LICENSE  CONTRIBUTING.md  CHANGELOG.md  PLAN.md  .gitignore
  src/envlint/
    __init__.py        # version
    cli.py             # typer app, output, exit codes
    parser.py          # .env parser (line model, dup detection)
    schema.py          # schema load (toml/json), types, validation
    lint.py            # structural lint rules
    secrets.py         # regex patterns + entropy
    diff.py            # diff two env files
    generate.py        # example + schema scaffolding
    report.py          # Finding model, severities, rich/json rendering
    typo.py            # levenshtein suggestions
  tests/
    test_parser.py test_schema.py test_lint.py test_secrets.py
    test_diff.py test_generate.py test_cli.py
    fixtures/ (good/bad .env + schema)
  .github/workflows/ci.yml
```

## Tech

- Python 3.9+ (use `tomllib` on 3.11+, fall back to `tomli` on <3.11).
- `typer` (CLI) + `rich` (output). Zero other runtime deps.
- `pytest` for tests. Ruff for lint (dev). GitHub Actions matrix (3.9–3.12, Win+Linux).

## Quality bar

- Cross-platform (Windows-first verified). Clean exit codes. JSON output stable.
- >90% of core logic covered by tests. Real fixtures. CLI smoke tested.
