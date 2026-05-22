import pytest

from envlint.parser import parse_file, parse_text
from envlint.secrets import (
    is_secret_key,
    match_known_patterns,
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
