# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Redact possibly-secret values everywhere they were previously echoed. Schema
  type errors (`V003`) and disallowed-enum errors (`V004`) now show a redacted,
  length-bounded preview instead of the raw value; the malformed-line lint hint
  (`E001`) is likewise redacted. Output (text and JSON) no longer leaks secrets.
- `envlint example` now redacts short, high-entropy values too (previously any
  value ≤ 24 chars on a key whose name didn't look secret was copied verbatim
  into the generated `.env.example`). The generator now uses the same entropy
  heuristic as the scanner.
- Cap the size of env/schema files read into memory (default 8 MiB) to prevent a
  memory/CPU denial-of-service from an accidental or hostile huge file.

### Fixed
- Non-UTF-8 (e.g. Latin-1) `.env` files no longer crash with an unhandled
  `UnicodeDecodeError`; they are decoded leniently and inspected safely. Size /
  read errors now produce a clean usage exit code (`2`) instead of a traceback.
- Schema files whose root is not a table/object are rejected with a clear error.

### Added
- `redact()` and `looks_high_entropy()` helpers in `envlint.secrets`, and
  `read_text_capped()` / `MAX_FILE_BYTES` / `EnvFileTooLargeError` in
  `envlint.parser`.
- Regression tests: per-detector ReDoS timing bounds, redaction guarantees for
  every output path, non-UTF-8 handling, and the file-size cap.

## [0.1.0] - 2026-05-22

### Added
- Initial release.
- `envlint check`: structural lint, schema validation, and secret detection for
  `.env` files, with `text`/`json` output, `--strict`, and `--no-*` toggles.
- Schema format (`.env.schema` TOML or `.env.schema.json`): `required`, `type`
  (`string`/`int`/`float`/`bool`/`url`/`email`/`port`), `allowed`, `pattern`,
  `default`, `description`, `secret`, and `example`.
- Secret detection via known provider patterns (AWS, Stripe, GitHub, Google,
  Slack, OpenAI, Twilio, SendGrid, npm, JWT, private keys) plus a Shannon-entropy
  heuristic, with placeholder awareness.
- Typo suggestions for unknown keys close to declared schema keys.
- `envlint example`: generate a redacted, commit-safe `.env.example`.
- `envlint schema`: scaffold a `.env.schema` from an existing `.env`.
- `envlint diff`: compare two `.env` files.
- Clean exit codes for CI: `0` clean, `1` problems found, `2` usage error.
- GitHub Actions CI across Python 3.9–3.13 on Linux and Windows.

[Unreleased]: https://github.com/ATOM00blue/envlint/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ATOM00blue/envlint/releases/tag/v0.1.0
