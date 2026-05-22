import pytest

from envlint.parser import (
    MAX_FILE_BYTES,
    EnvEntry,
    EnvFileTooLargeError,
    parse_file,
    parse_line,
    parse_text,
    read_text_capped,
)


def test_parse_basic_assignment():
    env = parse_text("FOO=bar")
    assert env.entries[0].key == "FOO"
    assert env.entries[0].value == "bar"
    assert env.entries[0].line == 1
    assert env.entries[0].quote is None


def test_blank_and_comment_lines_ignored():
    env = parse_text("# comment\n\n   \nFOO=bar\n")
    assert len(env.entries) == 1
    assert env.entries[0].line == 4


def test_export_prefix():
    env = parse_text("export FOO=bar")
    assert env.entries[0].key == "FOO"
    assert env.entries[0].export is True


def test_double_quoted_value_preserves_inner_spaces():
    env = parse_text('GREETING="hello world"')
    assert env.entries[0].value == "hello world"
    assert env.entries[0].quote == '"'


def test_single_quoted_value():
    env = parse_text("GREETING='hi there'")
    assert env.entries[0].value == "hi there"
    assert env.entries[0].quote == "'"


def test_inline_comment_stripped_when_unquoted():
    env = parse_text("FOO=bar # trailing note")
    assert env.entries[0].value == "bar"


def test_hash_without_space_kept():
    env = parse_text("PASSWORD=p#ss")
    assert env.entries[0].value == "p#ss"


def test_inline_comment_not_stripped_when_quoted():
    env = parse_text('FOO="bar # not a comment"')
    assert env.entries[0].value == "bar # not a comment"


def test_malformed_line_no_delimiter():
    env = parse_text("JUSTAKEY")
    assert env.entries == []
    assert env.malformed == [(1, "JUSTAKEY")]


def test_empty_key_is_malformed():
    env = parse_text("=value")
    assert env.malformed == [(1, "=value")]


def test_as_dict_last_value_wins():
    env = parse_text("A=1\nA=2\nB=3")
    assert env.as_dict() == {"A": "2", "B": "3"}


def test_keys_order_preserved_with_duplicates():
    env = parse_text("A=1\nB=2\nA=3")
    assert env.keys() == ["A", "B", "A"]


def test_get_helper():
    env = parse_text("A=1")
    assert env.get("A") == "1"
    assert env.get("MISSING") is None


def test_parse_file(good_env):
    env = parse_file(good_env)
    assert "DATABASE_URL" in env.as_dict()
    assert env.path == str(good_env)


def test_parse_line_returns_entry_for_valid():
    result = parse_line("FOO=bar", 1)
    assert isinstance(result, EnvEntry)


def test_empty_value():
    env = parse_text("EMPTY=")
    assert env.entries[0].is_empty_value is True


def test_non_utf8_file_does_not_crash(tmp_path):
    """A legacy-encoded (Latin-1) .env must be parsed, not crash."""
    p = tmp_path / "latin1.env"
    p.write_bytes(b"KEY=caf\xe9_value\n")
    env = parse_file(p)  # would raise UnicodeDecodeError before the fix
    assert env.entries[0].key == "KEY"
    # The undecodable byte is replaced, not lost; the line still parses.
    assert env.entries[0].value.startswith("caf")


def test_file_over_size_limit_rejected(tmp_path):
    p = tmp_path / "big.env"
    with open(p, "wb") as fh:
        fh.write(b"A=1\n")
        fh.seek(MAX_FILE_BYTES + 1024)
        fh.write(b"B=2\n")
    with pytest.raises(EnvFileTooLargeError):
        parse_file(p)


def test_read_text_capped_respects_custom_limit(tmp_path):
    p = tmp_path / "small.env"
    p.write_text("KEY=value\n", encoding="utf-8")
    with pytest.raises(EnvFileTooLargeError):
        read_text_capped(p, max_bytes=3)
    # Under the default limit it reads fine.
    assert "KEY=value" in read_text_capped(p)
