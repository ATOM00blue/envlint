from envlint.lint import lint
from envlint.parser import parse_file, parse_text


def codes(findings):
    return {f.code for f in findings}


def test_clean_file_has_no_lint_errors(good_env):
    findings = lint(parse_file(good_env))
    error_codes = {f.code for f in findings if f.severity.value == "error"}
    assert error_codes == set()


def test_duplicate_key_detected():
    findings = lint(parse_text("A=1\nA=2"))
    assert "E002" in codes(findings)


def test_malformed_line_detected():
    findings = lint(parse_text("NODELIM"))
    assert "E001" in codes(findings)


def test_invalid_key_name_detected():
    findings = lint(parse_text("1BAD=x"))
    assert "E003" in codes(findings)


def test_lowercase_key_warning():
    findings = lint(parse_text("lower=x"))
    assert "W001" in codes(findings)


def test_whitespace_before_eq():
    findings = lint(parse_text("KEY =value"))
    assert "W002" in codes(findings)


def test_whitespace_after_eq():
    findings = lint(parse_text("KEY= value"))
    assert "W003" in codes(findings)


def test_trailing_whitespace_in_value():
    findings = lint(parse_text("KEY=value   "))
    assert "W004" in codes(findings)


def test_quoted_value_with_spaces_is_clean():
    findings = lint(parse_text('KEY="a b c"'))
    assert codes(findings) == set()


def test_bad_fixture_has_many_problems(bad_env):
    findings = lint(parse_file(bad_env))
    found = codes(findings)
    assert "E002" in found  # duplicate API_KEY
    assert "E001" in found  # NO_DELIMITER_LINE
    assert "E003" in found  # 1INVALID
    assert "W001" in found  # lowercase_key


def test_malformed_line_hint_redacts_value():
    """E001 must not echo the full raw line, which may contain a secret."""
    secret = "ghp_0123456789abcdefABCDEF0123456789abcd0000"
    findings = lint(parse_text(f"export {secret}"))
    e001 = [f for f in findings if f.code == "E001"]
    assert e001
    for f in e001:
        assert secret not in (f.hint or "")
