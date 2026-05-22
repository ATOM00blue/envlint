import time

import pytest

from envlint.parser import parse_file, parse_text
from envlint.secrets import (
    _PATTERNS,
    _PLACEHOLDER,
    _SECRET_KEY_HINTS,
    is_secret_key,
    looks_high_entropy,
    match_known_patterns,
    redact,
    scan,
    shannon_entropy,
)
from fake_secrets import (
    FAKE_AWS,
    FAKE_GITHUB,
    FAKE_GOOGLE,
    FAKE_RSA_HEADER,
    FAKE_SLACK,
    FAKE_STRIPE,
)


def codes(findings):
    return {f.code for f in findings}


def test_shannon_entropy_zero_for_repeated_char():
    assert shannon_entropy("aaaaaa") == 0.0


def test_shannon_entropy_empty():
    assert shannon_entropy("") == 0.0


def test_shannon_entropy_higher_for_random():
    assert shannon_entropy("aB3$xZ9!qW2#") > shannon_entropy("aaaabbbb")


@pytest.mark.parametrize(
    "value,code",
    [
        (FAKE_AWS, "S-aws-access-key"),
        (FAKE_STRIPE, "S-stripe-secret"),
        (FAKE_GITHUB, "S-github-token"),
        (FAKE_GOOGLE, "S-google-api-key"),
        (FAKE_RSA_HEADER, "S-private-key"),
        (FAKE_SLACK, "S-slack-token"),
    ],
)
def test_known_patterns_match(value, code):
    pat = match_known_patterns(value)
    assert pat is not None
    assert pat.code == code


def test_normal_value_no_pattern():
    assert match_known_patterns("hello") is None


def test_is_secret_key():
    assert is_secret_key("API_KEY")
    assert is_secret_key("DB_PASSWORD")
    assert is_secret_key("CLIENT_SECRET")
    assert not is_secret_key("PORT")
    assert not is_secret_key("LOG_LEVEL")


def test_scan_detects_aws_key():
    env = parse_text(f"AWS_ACCESS_KEY_ID={FAKE_AWS}")
    findings = scan(env)
    assert "S-aws-access-key" in codes(findings)


def test_scan_ignores_placeholders():
    env = parse_text("API_KEY=your-api-key-here\nTOKEN=changeme\nPW=xxxxxx")
    findings = scan(env)
    assert findings == []


def test_entropy_flag_on_nonsecret_key():
    env = parse_text("RANDOM_BLOB=Zx9KqL2mNpW8vR4tY7uH3sD6fG1jB5cA0eXwQ")
    findings = scan(env)
    assert "S-entropy" in codes(findings)


def test_high_entropy_on_expected_secret_not_flagged():
    env = parse_text("API_KEY=Zx9KqL2mNpW8vR4tY7uH3sD6fG1jB5cA0eXwQ")
    findings = scan(env)
    # Key looks secret, value is just high entropy (no known pattern) -> no finding
    assert codes(findings) == set()


def test_declared_nonsecret_with_secret_is_error():
    env = parse_text(f"PUBLIC_ID={FAKE_AWS}")
    findings = scan(env, nonsecret_keys={"PUBLIC_ID"})
    assert any(f.severity.value == "error" for f in findings)


def test_secret_key_with_known_pattern_is_warning():
    env = parse_text(f"API_KEY={FAKE_GITHUB}")
    findings = scan(env, secret_keys={"API_KEY"})
    assert findings
    assert all(f.severity.value == "warning" for f in findings)


def test_secrets_fixture(secrets_env):
    findings = scan(parse_file(secrets_env))
    found = codes(findings)
    assert "S-aws-access-key" in found
    assert "S-stripe-secret" in found
    assert "S-github-token" in found
    # Placeholder and short normal value not flagged
    flagged_keys = {f.key for f in findings}
    assert "PLACEHOLDER_KEY" not in flagged_keys
    assert "NORMAL_VALUE" not in flagged_keys


# --- redaction ---------------------------------------------------------------


def test_redact_never_returns_full_value():
    secret = FAKE_GITHUB
    out = redact(secret)
    assert secret not in out
    # At most a tiny prefix is exposed.
    assert out.count(secret[:4]) <= 1
    assert "redacted" in out


def test_redact_short_value_fully_masked():
    out = redact("abc123")
    assert "abc123" not in out
    assert out == "<redacted 6-char value>"


def test_redact_empty():
    assert redact("") == "<empty>"


def test_scan_findings_never_contain_raw_secret():
    """No finding emitted by scan() should ever embed the raw value."""
    env = parse_text(
        f"AWS={FAKE_AWS}\nTOK={FAKE_STRIPE}\nGH={FAKE_GITHUB}\n"
        "BLOB=Zx9KqL2mNpW8vR4tY7uH3sD6fG1jB5cA0eXwQ"
    )
    for f in scan(env):
        blob = " ".join(filter(None, [f.message, f.hint or ""]))
        assert FAKE_AWS not in blob
        assert FAKE_STRIPE not in blob
        assert FAKE_GITHUB not in blob
        assert "Zx9KqL2mNpW8vR4tY7uH3sD6fG1jB5cA0eXwQ" not in blob


def test_looks_high_entropy():
    assert looks_high_entropy("Zx9KqL2mNpW8vR4tY7uH3sD6fG1jB5cA0eXwQ")
    assert not looks_high_entropy("short")
    assert not looks_high_entropy("your-api-key-here")
    assert not looks_high_entropy("a value with spaces in it that is long")


# --- ReDoS / catastrophic backtracking ---------------------------------------


@pytest.mark.parametrize("pat", _PATTERNS, ids=[p.code for p in _PATTERNS])
def test_detector_patterns_have_no_catastrophic_backtracking(pat):
    """Every detector must stay linear on adversarial input.

    A pattern with catastrophic backtracking would blow up super-linearly as
    the input grows. We feed large adversarial strings (long runs of in-class
    characters, matching prefixes with no terminator) and require each search
    to complete well under a generous bound.
    """
    adversarial = [
        "A" * 50000,
        "0" * 50000,
        "a0A_-" * 10000,
        "sk_live_" + "a" * 50000 + " ",
        "eyJ" + "A" * 50000,
        "AKIA" + "0" * 50000,
        "-----BEGIN " + "A" * 50000,
    ]
    for s in adversarial:
        start = time.perf_counter()
        pat.regex.search(s)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"{pat.code} took {elapsed:.3f}s on len {len(s)}"


@pytest.mark.parametrize("rx", [_PLACEHOLDER, _SECRET_KEY_HINTS])
def test_helper_regexes_are_redos_safe(rx):
    for s in ("<" + "a" * 100000, "your_" + "a" * 100000, "API_" * 25000):
        start = time.perf_counter()
        rx.search(s) if rx is _SECRET_KEY_HINTS else rx.match(s)
        assert (time.perf_counter() - start) < 0.5
