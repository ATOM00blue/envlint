# envlint

> Lint, validate, and document your `.env` files — catch missing vars, leaked secrets, and typos before they bite.

[![CI](https://github.com/ATOM00blue/envlint/actions/workflows/ci.yml/badge.svg)](https://github.com/ATOM00blue/envlint/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/badge/pypi-envlint-blue)](https://pypi.org/project/envlint/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

`.env` files are everywhere and almost never checked. A missing key, a duplicate
that silently wins, a real secret about to be committed, or a typo like
`DATBASE_URL` — all of these fail *silently* until your app blows up in
production. **envlint** is a fast, focused linter that catches them first.

```text
$ envlint check .env
Location      Level  Rule  Message
.env:3        error  E002  Duplicate key 'API_KEY' (previously defined on line 1)
.env:7        error  V001  Required key 'DATABASE_URL' is missing
.env:9        warn   S-aws-access-key  Possible AWS Access Key ID in value of AWS_KEY
.env:12       warn   V007  Unknown key 'PORRT'; did you mean 'PORT'?

1 error(s), 2 warning(s), 0 info
```

---

## Features

- **Schema validation** — declare required keys, types (`int`, `bool`, `url`,
  `email`, `port`, …), allowed values, and regex patterns in a simple
  `.env.schema`. Get an error when something is missing, empty, or the wrong type.
- **Secret leak detection** — known provider patterns (AWS, Stripe, GitHub,
  Google, Slack, OpenAI, Twilio, SendGrid, JWTs, private keys, …) **plus** a
  Shannon-entropy heuristic for custom tokens. Placeholder-aware to keep
  false positives low.
- **Typo suggestions** — present a key that's one or two edits away from a
  schema key and envlint says *"did you mean `PORT`?"*.
- **Structural lint** — duplicate keys, malformed lines, invalid variable
  names, non-uppercase keys, stray whitespace around `=` and values.
- **`.env.example` generator** — produce a redacted, commit-safe example file
  in one command.
- **Diff** — see which keys differ between two env files (e.g. `.env` vs
  `.env.production`).
- **First-class CI mode** — `--format json`, `--strict`, and clean exit codes
  (`0` clean, `1` problems, `2` usage error).
- **Zero config to start, no heavy deps** — pure Python, only `typer` + `rich`.

## Install

```bash
# Recommended: isolated install with pipx
pipx install envlint

# Or with uv
uv tool install envlint

# Or plain pip
pip install envlint
```

Then run:

```bash
envlint --help
```

## Quick start

```bash
# Lint the .env in the current directory
envlint check

# Lint a specific file (auto-detects a sibling .env.schema)
envlint check config/.env

# Generate a commit-safe example file
envlint example .env -o .env.example

# Scaffold a schema from an existing .env, then edit it
envlint schema .env -o .env.schema

# Diff two environments
envlint diff .env .env.production
```

## Commands

| Command            | What it does                                                        |
| ------------------ | ------------------------------------------------------------------- |
| `envlint check`    | Lint + validate + secret-scan one or more `.env` files.             |
| `envlint example`  | Generate a redacted `.env.example`.                                 |
| `envlint schema`   | Scaffold a `.env.schema` (TOML) from an existing `.env`.            |
| `envlint diff`     | Compare two `.env` files (keys-only-in-A/B, differing values).      |

### `check` options

| Option              | Description                                              |
| ------------------- | ------------------------------------------------------- |
| `-s, --schema PATH` | Schema file (auto-detected next to the env if omitted). |
| `--strict`          | Treat warnings as errors (non-zero exit on any).        |
| `-f, --format`      | `text` (default) or `json`.                             |
| `--no-secrets`      | Skip secret detection.                                  |
| `--no-schema`       | Skip schema validation.                                 |
| `--no-lint`         | Skip structural lint rules.                             |
| `-q, --quiet`       | Only print problems.                                    |

## Schema format

Drop a `.env.schema` (TOML) next to your `.env` and `envlint check` finds it
automatically. JSON (`.env.schema.json`) is also supported.

```toml
# .env.schema
[meta]
complete = true            # if true, keys not declared here are flagged

[vars.DATABASE_URL]
required = true
type = "url"
description = "Postgres connection string"
secret = false             # a secret here is reported as an ERROR

[vars.PORT]
type = "port"              # validates 0–65535
default = "8000"

[vars.LOG_LEVEL]
allowed = ["debug", "info", "warn", "error"]
default = "info"

[vars.SENTRY_DSN]
type = "url"
pattern = "^https://"      # custom regex constraint
required = false

[vars.API_KEY]
required = true
secret = true              # entropy/known-secret here is expected (not flagged)
example = "your-api-key"   # used by `envlint example`
```

### Supported types

`string` (default), `int`, `float`, `bool` (`true/false/yes/no/on/off`),
`port` (int 0–65535), `url` (scheme + host), `email`.

### Per-key fields

| Field         | Meaning                                                        |
| ------------- | ------------------------------------------------------------- |
| `required`    | Must be present and non-empty.                                |
| `type`        | One of the supported types above.                            |
| `allowed`     | Enum of permitted string values.                             |
| `pattern`     | Regex the value must match.                                  |
| `default`     | Shown in generated examples.                                 |
| `description` | Documentation; emitted as a comment in `envlint example`.    |
| `secret`      | `true` = expected secret (don't flag); `false` = must *not* be a secret (flag as error). |
| `example`     | Placeholder used by `envlint example`.                       |

## CI usage

`envlint check` exits non-zero when problems are found, so it drops straight
into any pipeline.

### GitHub Actions

```yaml
name: env
on: [push, pull_request]
jobs:
  envlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install envlint
      - run: envlint check .env.example --strict
```

### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: envlint
        name: envlint
        entry: envlint check .env.example --strict
        language: system
        files: \.env.*
        pass_filenames: false
```

### JSON output

```bash
envlint check .env --format json
```

```json
{
  "exit_code": 1,
  "summary": { "errors": 1, "warnings": 1, "infos": 0, "total": 2 },
  "findings": [
    {
      "code": "V001",
      "message": "Required key 'DATABASE_URL' is missing",
      "severity": "error",
      "file": ".env",
      "line": 0,
      "key": "DATABASE_URL",
      "hint": "Postgres connection string"
    }
  ]
}
```

## Rule reference

| Code  | Level | Meaning                                          |
| ----- | ----- | ------------------------------------------------ |
| E001  | error | Line is not a valid `KEY=VALUE` assignment.      |
| E002  | error | Duplicate key (last assignment silently wins).   |
| E003  | error | Invalid environment variable name.               |
| W001  | warn  | Key is not `UPPER_CASE`.                          |
| W002  | warn  | Whitespace before `=`.                            |
| W003  | warn  | Whitespace after `=` (unquoted).                  |
| W004  | warn  | Trailing whitespace in an unquoted value.         |
| V001  | error | Required key missing.                             |
| V002  | error | Required key present but empty.                   |
| V003  | error | Value fails its declared type.                    |
| V004  | error | Value not in `allowed` list.                      |
| V005  | error | Value does not match `pattern`.                   |
| V007  | warn  | Unknown key that looks like a typo of a schema key. |
| V008  | warn  | Unknown key (schema is `complete`).              |
| S-\*  | warn/error | Likely secret (known pattern or high entropy). |

## FAQ

**Does envlint read or upload my secrets anywhere?**
No. envlint runs fully locally and never makes network calls. It only reads
the files you point it at.

**Won't it flag every secret in my `.env`?**
Secrets in a `.env` are expected, so detected secrets are **warnings** by
default. Mark a key `secret = true` in the schema to silence it, or
`secret = false` to turn a detected secret into an **error** (useful for keys
that should never hold credentials). Obvious placeholders are ignored.

**How is this different from dotenv-linter?**
dotenv-linter is an excellent *style/syntax* linter. envlint adds **schema
validation**, **secret detection**, and **typo suggestions**, and ships a
Python-native install and JSON/CI output.

**Does it support `export FOO=bar` and inline comments?**
Yes. `export` prefixes are recognized, and unquoted inline `# comments` are
stripped from values.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

```bash
git clone https://github.com/ATOM00blue/envlint
cd envlint
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

## License

[MIT](LICENSE) © 2026 ATOM00blue
