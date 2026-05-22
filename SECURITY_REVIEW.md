# Security & Quality Review — envlint

Date: 2026-05-22
Reviewer: autonomous application-security review
Scope: `src/envlint/**`, CLI behavior, secret handling, regex safety, dependencies, tests, docs.
Method: source audit + dynamic probes (ReDoS timing, leak tracing, encoding) + `pip-audit`, `bandit -r src`, `ruff`, `pytest`.

Severity legend: Critical / High / Medium / Low / Info.

---

## Summary

envlint is a small, well-structured, dependency-light tool. Bandit reports **no issues**, the
secret-detection regexes are **ReDoS-safe** (no nested/overlapping quantifiers; all scale linearly),
and the architecture cleanly separates stdout (results) from stderr (diagnostics).

The audit found, however, that the tool — whose entire purpose is *not leaking secrets* — leaks
detected/secret-looking **values verbatim into its own output** along several paths, including the
generated `.env.example` (the file users are most likely to commit). These are the highest-priority
fixes. A handful of robustness bugs (UTF-8 crash, no input-size limit) and minor quality items round
out the list.

| # | Severity | Area | Title |
|---|----------|------|-------|
| 1 | High | Secret handling | `.env.example` generator leaks short high-entropy values verbatim |
| 2 | High | Secret handling | Schema type errors (V003) print the full value, leaking secrets |
| 3 | High | Secret handling | Schema enum errors (V004) print the full value, leaking secrets |
| 4 | Medium | Robustness / DoS | No size limit when reading env/schema files (memory/CPU exhaustion) |
| 5 | Medium | Robustness | Non-UTF-8 `.env` crashes with an unhandled `UnicodeDecodeError` |
| 6 | Medium | Secret handling | Malformed-line lint (E001) echoes the raw line, which may contain a secret |
| 7 | Low | Supply chain | `pip-audit` flags venv-bundled `setuptools` (not an envlint runtime dep) |
| 8 | Low | Quality | No regression tests for ReDoS timing or redaction guarantees |
| 9 | Info | Correctness | `diff --values` intentionally prints values (documented, flag-gated) — acceptable |

ReDoS: **No catastrophic backtracking found.** All 13 provider patterns plus the placeholder and
key-hint regexes scale linearly even on 100k–200k-char adversarial inputs (worst observed < 30 ms).
The patterns use bounded/single-pass character classes anchored with `\b`; there is no
quantifier-over-quantifier construct. The residual concern is unbounded *input size* (see #4), which
is addressed defensively.

---

## Findings

### 1. High — `.env.example` generator leaks short high-entropy values
File: `src/envlint/generate.py:10-24` (`_placeholder_for`)

Impact: `_placeholder_for` only redacts a value when the key *name* looks secret, the value matches a
*known* provider pattern, or the value is longer than 24 chars. A high-entropy opaque token of <= 24
chars on a key whose name does not look secret (e.g. `CONFIG_BLOB`, `SESSION_TOKEN_FRAGMENT`,
`HASH=...`) is copied **verbatim** into the generated `.env.example`. Because `.env.example` is
specifically meant to be committed, this is the most dangerous leak path in the tool.

Proof:
```
CONFIG_BLOB=Zx9KqL2mNpW8vR4tY7uH3sD   (24 chars, entropy ~4.4 bits/char, no known pattern)
-> generated example keeps:  CONFIG_BLOB=Zx9KqL2mNpW8vR4tY7uH3sD
```

Fix: apply the same Shannon-entropy heuristic used by the scanner when deciding to redact, so any
high-entropy value (regardless of length or key name) is replaced with a placeholder. Lower the
"keep as hint" path to short, clearly low-entropy values. **Fixed.**

### 2. High — Schema type errors (V003) print the full value
File: `src/envlint/schema.py:121-159` (`_type_error`), surfaced at `schema.py:206-218`

Impact: every `_type_error` branch interpolates `value!r` into the finding message
(`expected an integer, got '<value>'`, etc.). If a secret-typed/looking value fails a type check
(common: an API key declared `type = "int"` by mistake, or any value on a `url`/`email`/`port`
field), the **entire secret** is printed to stdout and into `--format json`. This directly
contradicts the README's "never leaks secrets" guarantee.

Proof:
```
API_KEY (type=int) = ghp_…  ->  V003 "API_KEY: expected an integer, got 'ghp_0123…0000'"
```

Fix: redact the offending value in all type-error messages — show a redacted/length-bounded preview
(`<redacted 40-char value>` style) rather than the raw value. **Fixed.**

### 3. High — Schema enum errors (V004) print the full value
File: `src/envlint/schema.py:220-232`

Impact: `f"{name}={value!r} is not an allowed value"` prints the full value. A secret on an
`allowed`-constrained key leaks the same way as #2.

Fix: report only the key name and the allowed set; redact the actual value. **Fixed.**

### 4. Medium — No size limit when reading files
File: `src/envlint/parser.py:123-126` (`parse_file`), `src/envlint/schema.py:82-87` (`load_schema`)

Impact: both readers call `read_text()` with no bound. A maliciously large or accidentally huge file
(e.g. a binary mistaken for a `.env`, a multi-GB log) is read fully into memory and then scanned by
13 regexes plus an O(n) entropy pass per value — a memory/CPU denial-of-service. The regexes are
linear, so this is bounded-but-large rather than exponential, but there is still no guardrail.

Fix: enforce a generous default size cap (configurable) when reading env and schema files; refuse
files above the cap with a clean usage error instead of OOM. **Fixed.**

### 5. Medium — Non-UTF-8 `.env` crashes with an unhandled exception
File: `src/envlint/parser.py:125`, CLI guard at `src/envlint/cli.py:140-148`

Impact: `read_text(encoding="utf-8")` raises `UnicodeDecodeError` on legacy-encoded files (e.g.
Latin-1 `café`). `_parse_or_exit` only catches `OSError`, so the CLI dies with a Python traceback and
a non-deterministic exit code instead of the documented clean `2` usage error. Cross-platform
robustness is an advertised feature.

Proof:
```
KEY=café (latin-1)  ->  UnicodeDecodeError, CLI exits 1 via traceback (no clean message)
```

Fix: decode with `errors="replace"` (the file is only being inspected, never executed/round-tripped)
and broaden the CLI's exception handling to cover decode errors with a clean usage error. **Fixed.**

### 6. Medium — Malformed-line lint (E001) echoes the raw line
File: `src/envlint/lint.py:19-29`

Impact: the E001 hint is `f"got: {raw.strip()!r}"`, echoing the raw text of any line that looks like
an assignment but is malformed. If such a line contains a secret (e.g. a key/value pasted without an
`=`), the secret is printed. Lower likelihood than #1–#3 but the same class of leak; a secret tool
should never echo raw file content unbounded.

Fix: truncate/redact the echoed raw line to a short, length-bounded preview. **Fixed.**

### 7. Low — `pip-audit` flags venv-bundled `setuptools`
Impact: `pip-audit` reported 5 advisories — all in `setuptools 65.5.0` (PYSEC-2022-43012,
PYSEC-2025-49, CVE-2024-6345). `setuptools` is **not** a declared or transitive runtime dependency of
envlint (runtime deps: `typer`, `rich`, `tomli` on <3.11). It was the build-time setuptools that
shipped in the development virtualenv.

Fix: upgraded setuptools to `82.0.1` in the dev venv; `pip-audit` is then clean. No change to
shipped package metadata is required because envlint does not depend on setuptools. **Resolved.**

### 8. Low — Missing ReDoS/redaction regression tests
Impact: the redaction guarantee and the ReDoS-safety property were unverified by the suite, so a
future pattern change could silently reintroduce a leak or catastrophic-backtracking pattern.

Fix: added regression tests — a timing bound for every detector pattern against adversarial input,
and redaction assertions for the example generator, V003/V004 messages, E001, and the size cap.
**Fixed.**

### 9. Info — `diff --values` prints values by design
File: `src/envlint/cli.py:283-310`

`diff` hides values by default and only prints them behind the explicit `--values` flag, whose help
text already warns "may reveal secrets". This is intended, opt-in behavior and is left as-is.

---

## Verification (post-fix)

- `ruff check .` — clean.
- `pytest` — all tests green (including new regression tests).
- `bandit -r src` — no issues.
- `pip-audit` — clean after the setuptools upgrade in the dev venv.
- End-to-end smoke on fixtures: `check` (text + json), `example`, `schema`, `diff` — secrets redacted
  in every output path; exit codes correct (0 clean / 1 problems / 2 usage).

## Intentionally not changed

- `diff --values` value display (finding #9) — documented, opt-in, flag-gated.
- The set of provider patterns and the entropy threshold (4.0 bits/char, min length 20) — current
  false-positive/negative balance is reasonable and changing it is out of scope for a security fix.
