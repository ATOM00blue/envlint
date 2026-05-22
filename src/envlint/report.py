"""Findings model, severities, and rendering (text/JSON)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    """Severity of a finding. Order matters for sorting/exit-code logic."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 0, "warning": 1, "info": 2}[self.value]


@dataclass
class Finding:
    """A single issue discovered in an env file."""

    code: str
    """Stable machine-readable rule id, e.g. ``E001`` or ``S-aws-access-key``."""
    message: str
    severity: Severity
    file: str = ""
    line: int = 0
    key: Optional[str] = None
    hint: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class Report:
    """A collection of findings, possibly across multiple files."""

    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.INFO]

    def has_problems(self, *, strict: bool = False) -> bool:
        """True if there are errors (or warnings when ``strict``)."""
        if self.errors:
            return True
        return bool(strict and self.warnings)

    def sorted(self) -> list[Finding]:
        """Findings ordered by file, line, then severity."""
        return sorted(
            self.findings,
            key=lambda f: (f.file, f.line, f.severity.rank, f.code),
        )

    def to_json(self, *, exit_code: int = 0) -> str:
        payload = {
            "exit_code": exit_code,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "infos": len(self.infos),
                "total": len(self.findings),
            },
            "findings": [f.to_dict() for f in self.sorted()],
        }
        return json.dumps(payload, indent=2)
