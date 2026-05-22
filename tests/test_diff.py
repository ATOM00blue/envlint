from envlint.diff import diff_envs
from envlint.parser import parse_text


def test_no_differences():
    a = parse_text("A=1\nB=2")
    b = parse_text("A=1\nB=2")
    result = diff_envs(a, b)
    assert not result.has_differences
    assert set(result.common) == {"A", "B"}


def test_only_in_a():
    a = parse_text("A=1\nB=2")
    b = parse_text("A=1")
    result = diff_envs(a, b)
    assert result.only_in_a == ["B"]
    assert result.only_in_b == []
    assert result.has_differences


def test_only_in_b():
    a = parse_text("A=1")
    b = parse_text("A=1\nC=3")
    result = diff_envs(a, b)
    assert result.only_in_b == ["C"]


def test_changed_values():
    a = parse_text("A=1")
    b = parse_text("A=2")
    result = diff_envs(a, b)
    assert result.changed == {"A": ("1", "2")}
    assert result.has_differences


def test_diff_sorted_output():
    a = parse_text("Z=1\nA=1")
    b = parse_text("M=1")
    result = diff_envs(a, b)
    assert result.only_in_a == ["A", "Z"]
