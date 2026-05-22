"""Schema loading (TOML/JSON) and validation of a parsed env against it."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

from .parser import ParsedEnv
from .report import Finding, Severity
from .typo import closest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on <3.11 only
    import tomli as tomllib


VALID_TYPES = {"string", "int", "float", "bool", "url", "email", "port"}
_BOOL_TRUE = {"true", "1", "yes", "on"}
_BOOL_FALSE = {"false", "0", "no", "off"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA_FILENAMES = (".env.schema", ".env.schema.toml", ".env.schema.json")


@dataclass
class VarSpec:
    name: str
    required: bool = False
    type: str = "string"
    allowed: Optional[list[str]] = None
    pattern: Optional[str] = None
    default: Optional[str] = None
    description: str = ""
    secret: Optional[bool] = None
    example: Optional[str] = None


@dataclass
class Schema:
    vars: dict[str, VarSpec] = field(default_factory=dict)
    complete: bool = False
    path: str = ""

    @property
    def secret_keys(self) -> set[str]:
        return {n for n, s in self.vars.items() if s.secret is True}

    @property
    def nonsecret_keys(self) -> set[str]:
        return {n for n, s in self.vars.items() if s.secret is False}


def find_schema(start: Union[str, Path] = ".") -> Optional[Path]:
    """Find a schema file next to the given path or in its parent directory."""
    base = Path(start)
    search_dir = base.parent if base.is_file() else base
    for name in SCHEMA_FILENAMES:
        candidate = search_dir / name
        if candidate.is_file():
            return candidate
    return None


def _coerce_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.lower()
        if v in _BOOL_TRUE:
            return True
        if v in _BOOL_FALSE:
            return False
    return None


def load_schema(path: Union[str, Path]) -> Schema:
    """Load a schema from a TOML or JSON file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    data = json.loads(text) if p.suffix == ".json" else tomllib.loads(text)
    return _build_schema(data, path=str(p))


def _build_schema(data: dict, path: str = "") -> Schema:
    meta = data.get("meta", {}) or {}
    complete = bool(meta.get("complete", False))

    raw_vars = data.get("vars", {}) or {}
    specs: dict[str, VarSpec] = {}
    for name, raw in raw_vars.items():
        if not isinstance(raw, dict):
            raise ValueError(f"schema entry for {name!r} must be a table/object")
        vtype = str(raw.get("type", "string"))
        if vtype not in VALID_TYPES:
            raise ValueError(
                f"unknown type {vtype!r} for {name!r}; valid: {sorted(VALID_TYPES)}"
            )
        allowed = raw.get("allowed")
        if allowed is not None:
            allowed = [str(a) for a in allowed]
        specs[name] = VarSpec(
            name=name,
            required=bool(raw.get("required", False)),
            type=vtype,
            allowed=allowed,
            pattern=raw.get("pattern"),
            default=(str(raw["default"]) if "default" in raw else None),
            description=str(raw.get("description", "")),
            secret=_coerce_bool(raw["secret"]) if "secret" in raw else None,
            example=(str(raw["example"]) if "example" in raw else None),
        )
    return Schema(vars=specs, complete=complete, path=path)


def _type_error(spec: VarSpec, value: str) -> Optional[str]:
    """Return an error message if ``value`` doesn't match ``spec.type``, else None."""
    t = spec.type
    if t == "string":
        return None
    if t == "int":
        try:
            int(value)
        except ValueError:
            return f"expected an integer, got {value!r}"
        return None
    if t == "float":
        try:
            float(value)
        except ValueError:
            return f"expected a number, got {value!r}"
        return None
    if t == "bool":
        if value.lower() not in (_BOOL_TRUE | _BOOL_FALSE):
            return f"expected a boolean (true/false), got {value!r}"
        return None
    if t == "port":
        try:
            n = int(value)
        except ValueError:
            return f"expected a port number, got {value!r}"
        if not (0 <= n <= 65535):
            return f"port {n} out of range 0-65535"
        return None
    if t == "url":
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return f"expected a URL with scheme and host, got {value!r}"
        return None
    if t == "email":
        if not _EMAIL_RE.match(value):
            return f"expected an email address, got {value!r}"
        return None
    return None


def validate(env: ParsedEnv, schema: Schema) -> list[Finding]:
    """Validate a parsed env file against a schema."""
    findings: list[Finding] = []
    env_map = env.as_dict()
    # Map key -> last line number for reporting.
    line_of: dict[str, int] = {e.key: e.line for e in env.entries}

    # Required + present-value checks.
    for name, spec in schema.vars.items():
        if name not in env_map:
            if spec.required:
                findings.append(
                    Finding(
                        code="V001",
                        message=f"Required key {name!r} is missing",
                        severity=Severity.ERROR,
                        file=env.path,
                        line=0,
                        key=name,
                        hint=(spec.description or None),
                    )
                )
            continue

        value = env_map[name]
        line = line_of.get(name, 0)

        if spec.required and value == "":
            findings.append(
                Finding(
                    code="V002",
                    message=f"Required key {name!r} is present but empty",
                    severity=Severity.ERROR,
                    file=env.path,
                    line=line,
                    key=name,
                )
            )
            continue

        if value == "":
            continue  # nothing more to validate on an empty optional value

        # Type check.
        err = _type_error(spec, value)
        if err:
            findings.append(
                Finding(
                    code="V003",
                    message=f"{name}: {err}",
                    severity=Severity.ERROR,
                    file=env.path,
                    line=line,
                    key=name,
                    hint=f"declared type: {spec.type}",
                )
            )

        # Allowed values (enum).
        if spec.allowed is not None and value not in spec.allowed:
            findings.append(
                Finding(
                    code="V004",
                    message=f"{name}={value!r} is not an allowed value",
                    severity=Severity.ERROR,
                    file=env.path,
                    line=line,
                    key=name,
                    hint=f"allowed: {', '.join(spec.allowed)}",
                )
            )

        # Pattern.
        if spec.pattern is not None:
            try:
                if not re.search(spec.pattern, value):
                    findings.append(
                        Finding(
                            code="V005",
                            message=f"{name} does not match required pattern",
                            severity=Severity.ERROR,
                            file=env.path,
                            line=line,
                            key=name,
                            hint=f"pattern: {spec.pattern}",
                        )
                    )
            except re.error as exc:  # pragma: no cover - malformed schema pattern
                findings.append(
                    Finding(
                        code="V006",
                        message=f"Invalid regex pattern in schema for {name}: {exc}",
                        severity=Severity.WARNING,
                        file=schema.path,
                        line=0,
                        key=name,
                    )
                )

    # Unknown keys + typo suggestions.
    schema_keys = list(schema.vars.keys())
    for e in env.entries:
        if e.key in schema.vars:
            continue
        suggestion = closest(e.key, schema_keys, max_distance=2)
        if suggestion is not None:
            findings.append(
                Finding(
                    code="V007",
                    message=f"Unknown key {e.key!r}; did you mean {suggestion!r}?",
                    severity=Severity.WARNING,
                    file=env.path,
                    line=e.line,
                    key=e.key,
                    hint="looks like a typo of a schema key.",
                )
            )
        elif schema.complete:
            findings.append(
                Finding(
                    code="V008",
                    message=f"Unknown key {e.key!r} not declared in schema",
                    severity=Severity.WARNING,
                    file=env.path,
                    line=e.line,
                    key=e.key,
                    hint="schema is marked complete; add it or remove the key.",
                )
            )

    return findings
