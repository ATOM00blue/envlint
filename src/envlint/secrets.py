"""Secret detection: known provider patterns + Shannon entropy heuristic."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from .parser import ParsedEnv
from .report import Finding, Severity


@dataclass(frozen=True)
class SecretPattern:
    code: str
    name: str
    regex: re.Pattern


# High-signal, low-false-positive provider patterns. Anchored where possible.
_PATTERNS: list[SecretPattern] = [
    SecretPattern("S-aws-access-key", "AWS Access Key ID",
                  re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA)[0-9A-Z]{16}\b")),
    SecretPattern("S-stripe-secret", "Stripe Secret Key",
                  re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{16,}\b")),
    SecretPattern("S-github-token", "GitHub Token",
                  re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36,}\b")),
    SecretPattern("S-github-pat", "GitHub Fine-grained PAT",
                  re.compile(r"\bgithub_pat_[0-9A-Za-z_]{22,}\b")),
    SecretPattern("S-google-api-key", "Google API Key",
                  re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    SecretPattern("S-slack-token", "Slack Token",
                  re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    SecretPattern("S-openai-key", "OpenAI API Key",
                  re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z_-]{20,}\b")),
    SecretPattern("S-slack-webhook", "Slack Webhook URL",
                  re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+")),
    SecretPattern("S-private-key", "Private Key Block",
                  re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    SecretPattern("S-jwt", "JSON Web Token",
                  re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    SecretPattern("S-twilio-sid", "Twilio Account SID",
                  re.compile(r"\bAC[0-9a-fA-F]{32}\b")),
    SecretPattern("S-sendgrid", "SendGrid API Key",
                  re.compile(r"\bSG\.[0-9A-Za-z_-]{22}\.[0-9A-Za-z_-]{43}\b")),
    SecretPattern("S-npm-token", "npm Access Token",
                  re.compile(r"\bnpm_[0-9A-Za-z]{36}\b")),
]

# Key names that strongly imply the value should be treated as a secret.
_SECRET_KEY_HINTS = re.compile(
    r"(?:^|_)(?:SECRET|PASSWORD|PASSWD|PWD|TOKEN|API[_-]?KEY|APIKEY|"
    r"PRIVATE[_-]?KEY|ACCESS[_-]?KEY|CLIENT[_-]?SECRET|AUTH|CREDENTIAL|"
    r"SIGNING[_-]?KEY|ENCRYPTION[_-]?KEY)(?:$|_)",
    re.IGNORECASE,
)

# Values that are obviously placeholders, never real secrets.
_PLACEHOLDER = re.compile(
    r"^(?:your[_-]?|my[_-]?|<.*>|\$\{.*\}|xxx+|change[_-]?me|placeholder|"
    r"example|todo|none|null|nil|test|dummy|sample|secret|password|changeme|"
    r"\*+|\.+|-+)$",
    re.IGNORECASE,
)

ENTROPY_THRESHOLD = 4.0
ENTROPY_MIN_LENGTH = 20

# Redaction defaults. We never echo a full value that might be a secret; we show
# only its length and a tiny, fixed-size prefix for debuggability.
_REDACT_PREVIEW = 4
_REDACT_SHOW_THRESHOLD = 8  # values at/under this are fully masked (a short
#                            value's prefix can be most of the secret)


def redact(value: str, *, preview: int = _REDACT_PREVIEW) -> str:
    """Return a safe, non-leaking representation of a possibly-secret value.

    Never returns more than ``preview`` leading characters of the original. The
    result is meant for human-readable diagnostics, not round-tripping.
    """
    if value == "":
        return "<empty>"
    n = len(value)
    if n <= _REDACT_SHOW_THRESHOLD:
        return f"<redacted {n}-char value>"
    return f"{value[:preview]}…<redacted {n}-char value>"


def shannon_entropy(s: str) -> float:
    """Shannon entropy of a string in bits per character."""
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _looks_like_placeholder(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    if _PLACEHOLDER.match(v):
        return True
    # Repeated single char like "aaaaaaaa" or low unique-char ratio.
    return len(set(v)) <= 2


def match_known_patterns(value: str) -> Optional[SecretPattern]:
    for pat in _PATTERNS:
        if pat.regex.search(value):
            return pat
    return None


def is_secret_key(key: str) -> bool:
    """Whether a key *name* implies a secret value."""
    return bool(_SECRET_KEY_HINTS.search(key))


def looks_high_entropy(value: str, *, threshold: float = ENTROPY_THRESHOLD) -> bool:
    """Heuristic: a long, space-free, non-placeholder, high-entropy value.

    Mirrors the entropy branch of :func:`scan` so callers (e.g. the example
    generator) can make the *same* redaction decision the scanner would.
    """
    if _looks_like_placeholder(value):
        return False
    if len(value) < ENTROPY_MIN_LENGTH or " " in value:
        return False
    return shannon_entropy(value) >= threshold


def scan(
    env: ParsedEnv,
    *,
    secret_keys: Optional[set[str]] = None,
    nonsecret_keys: Optional[set[str]] = None,
    entropy_threshold: float = ENTROPY_THRESHOLD,
) -> list[Finding]:
    """Scan parsed env entries for likely secrets.

    ``secret_keys`` are keys the schema marks ``secret = true`` (expected; a
    detected secret there is informational/at most a warning). ``nonsecret_keys``
    are keys explicitly ``secret = false`` (a detected secret there is an error).
    """
    secret_keys = secret_keys or set()
    nonsecret_keys = nonsecret_keys or set()
    findings: list[Finding] = []

    for e in env.entries:
        value = e.value
        if not value or _looks_like_placeholder(value):
            continue

        known = match_known_patterns(value)
        expected_secret = e.key in secret_keys or is_secret_key(e.key)
        declared_nonsecret = e.key in nonsecret_keys

        if known is not None:
            if declared_nonsecret:
                sev = Severity.ERROR
                hint = (
                    f"schema marks {e.key} as non-secret but the value matches "
                    f"{known.name}."
                )
            elif expected_secret:
                sev = Severity.WARNING
                hint = (
                    f"matches {known.name}. Keep this out of version control; "
                    f"add the file to .gitignore."
                )
            else:
                sev = Severity.WARNING
                hint = f"value matches {known.name} but the key name doesn't look secret."
            findings.append(
                Finding(
                    code=known.code,
                    message=f"Possible {known.name} in value of {e.key}",
                    severity=sev,
                    file=env.path,
                    line=e.line,
                    key=e.key,
                    hint=hint,
                )
            )
            continue

        # Entropy heuristic — only for non-placeholder, sufficiently long values.
        if len(value) >= ENTROPY_MIN_LENGTH and " " not in value:
            ent = shannon_entropy(value)
            if ent >= entropy_threshold:
                if declared_nonsecret:
                    sev = Severity.ERROR
                    hint = "schema marks this key as non-secret, but value looks like a secret."
                elif expected_secret:
                    # Expected to be a secret; high entropy is fine -> no finding.
                    continue
                else:
                    sev = Severity.WARNING
                    hint = (
                        f"high-entropy value ({ent:.1f} bits/char) on a key that "
                        f"doesn't look secret. Confirm it isn't a leaked credential."
                    )
                findings.append(
                    Finding(
                        code="S-entropy",
                        message=f"High-entropy value in {e.key} may be a secret",
                        severity=sev,
                        file=env.path,
                        line=e.line,
                        key=e.key,
                        hint=hint,
                    )
                )

    return findings
