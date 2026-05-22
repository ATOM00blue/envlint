from envlint.parser import EnvEntry, parse_file, parse_line, parse_text


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
