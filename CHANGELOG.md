# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
