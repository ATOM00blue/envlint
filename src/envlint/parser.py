"""A small, dependency-free ``.env`` parser that preserves line structure.

We deliberately do not use python-dotenv: linting requires knowing the *raw*
structure (line numbers, duplicate keys, quoting, whitespace) that a normal
loader throws away.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


@dataclass
class EnvEntry:
    """A single ``KEY=VALUE`` assignment line."""

    key: str
    value: str
    line: int
    raw: str
    quote: Optional[str] = None  # '"' or "'" or None
    export: bool = False

    @property
    def is_empty_value(self) -> bool:
        return self.value == ""


@dataclass
class ParsedEnv:
    """The result of parsing an env file, retaining order and structure."""

    path: str
    entries: list[EnvEntry]
    # Lines that look like assignments but are malformed (key with no '=', etc.)
    malformed: list[tuple[int, str]]

    def keys(self) -> list[str]:
        return [e.key for e in self.entries]

    def as_dict(self) -> dict[str, str]:
        """Last-value-wins mapping, matching real dotenv loader semantics."""
        out: dict[str, str] = {}
        for e in self.entries:
            out[e.key] = e.value
        return out

    def get(self, key: str) -> Optional[str]:
        return self.as_dict().get(key)


def _strip_inline_comment(value: str) -> str:
    """Strip an unquoted trailing ``# comment`` from a value.

    Only applies when the value is not wrapped in quotes (handled before call).
    A ``#`` must be preceded by whitespace (or be at the start) to count as a
    comment, so ``pass#1`` stays intact but ``pass # note`` is trimmed.
    """
    out = []
    for i, ch in enumerate(value):
        if ch == "#" and (i == 0 or value[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_line(raw_line: str, line_no: int) -> Union[EnvEntry, tuple[int, str], None]:
    """Parse a single physical line.

    Returns an :class:`EnvEntry`, a ``(line_no, raw)`` tuple for malformed
    assignment-looking lines, or ``None`` for blanks/comments.
    """
    line = raw_line.rstrip("\n").rstrip("\r")
    stripped = line.strip()

    if not stripped or stripped.startswith("#"):
        return None

    work = stripped
    export = False
    if work.startswith("export ") or work.startswith("export\t"):
        export = True
        work = work[len("export"):].strip()

    if "=" not in work:
        # Looks like a key but has no value/delimiter -> malformed.
        return (line_no, line)

    key, _, value = work.partition("=")
    key = key.strip()

    if key == "":
        return (line_no, line)

    quote: Optional[str] = None
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        quote = v[0]
        v = v[1:-1]
    else:
        # Unquoted: strip an inline comment and surrounding whitespace.
        v = _strip_inline_comment(value.strip())

    return EnvEntry(key=key, value=v, line=line_no, raw=line, quote=quote, export=export)


def parse_text(text: str, path: str = "<string>") -> ParsedEnv:
    entries: list[EnvEntry] = []
    malformed: list[tuple[int, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        result = parse_line(raw, i)
        if result is None:
            continue
        if isinstance(result, EnvEntry):
            entries.append(result)
        else:
            malformed.append(result)
    return ParsedEnv(path=path, entries=entries, malformed=malformed)


def parse_file(path: Union[str, Path]) -> ParsedEnv:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_text(text, path=str(p))
