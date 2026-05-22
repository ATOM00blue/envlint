"""Structural / syntax lint rules for .env files."""

from __future__ import annotations

import re

from .parser import ParsedEnv
from .report import Finding, Severity
from .secrets import redact

# Valid POSIX-ish env var name.
_VALID_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def lint(env: ParsedEnv) -> list[Finding]:
    """Run all structural lint rules over a parsed env file."""
    findings: list[Finding] = []

    # E001: malformed lines (look like assignments but have no '=' / empty key).
    # The raw line may contain a secret, so it is redacted before being echoed.
    for line_no, raw in env.malformed:
        findings.append(
            Finding(
                code="E001",
                message="Line is not a valid KEY=VALUE assignment",
                severity=Severity.ERROR,
                file=env.path,
                line=line_no,
                hint=f"got: {redact(raw.strip())}",
            )
        )

    seen: dict[str, int] = {}
    for e in env.entries:
        key = e.key

        # E002: duplicate keys (last value silently wins at load time).
        if key in seen:
            findings.append(
                Finding(
                    code="E002",
                    message=f"Duplicate key {key!r} (previously defined on line {seen[key]})",
                    severity=Severity.ERROR,
                    file=env.path,
                    line=e.line,
                    key=key,
                    hint="the last assignment wins; remove the earlier one.",
                )
            )
        else:
            seen[key] = e.line

        # E003: invalid key name (won't be a usable environment variable).
        if not _VALID_KEY.match(key):
            findings.append(
                Finding(
                    code="E003",
                    message=f"Invalid environment variable name {key!r}",
                    severity=Severity.ERROR,
                    file=env.path,
                    line=e.line,
                    key=key,
                    hint="names must match [A-Za-z_][A-Za-z0-9_]*.",
                )
            )

        # W001: lowercase key (convention is UPPER_SNAKE_CASE).
        elif key != key.upper():
            findings.append(
                Finding(
                    code="W001",
                    message=f"Key {key!r} is not UPPER_CASE",
                    severity=Severity.WARNING,
                    file=env.path,
                    line=e.line,
                    key=key,
                    hint="environment variable names are conventionally uppercase.",
                )
            )

        # W002: spaces around '=' on an unquoted value introduce surprises.
        if e.quote is None:
            # Look at the raw text around the first '='.
            raw = e.raw
            if "=" in raw:
                before, _, after = raw.partition("=")
                if before.endswith(" ") or before.endswith("\t"):
                    findings.append(
                        Finding(
                            code="W002",
                            message=f"Whitespace before '=' for key {key!r}",
                            severity=Severity.WARNING,
                            file=env.path,
                            line=e.line,
                            key=key,
                            hint="some loaders include it in the key name.",
                        )
                    )
                if after[:1] in (" ", "\t") and e.value != "":
                    findings.append(
                        Finding(
                            code="W003",
                            message=f"Whitespace after '=' for key {key!r}",
                            severity=Severity.WARNING,
                            file=env.path,
                            line=e.line,
                            key=key,
                            hint="leading space may become part of the value; quote it instead.",
                        )
                    )

            # W004: trailing whitespace after an unquoted value on the raw line.
            # The parser normalizes ``e.value``, so inspect the raw text: the
            # portion after the first '=' that ends in whitespace and has a
            # non-empty value is a likely accidental trailing space.
            raw_after = e.raw.partition("=")[2] if "=" in e.raw else ""
            if e.value != "" and raw_after != raw_after.rstrip() and "#" not in raw_after:
                findings.append(
                    Finding(
                        code="W004",
                        message=f"Trailing whitespace in value of {key!r}",
                        severity=Severity.WARNING,
                        file=env.path,
                        line=e.line,
                        key=key,
                        hint="quote the value if the whitespace is intentional.",
                    )
                )

    return findings
