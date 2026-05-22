from envlint.generate import generate_example, generate_schema
from envlint.parser import parse_file, parse_text
from envlint.schema import load_schema
from fake_secrets import FAKE_GITHUB


def test_example_redacts_secrets():
    env = parse_text(f"API_KEY={FAKE_GITHUB}")
    out = generate_example(env)
    assert "ghp_" not in out
    assert "your-api-key-here" in out


def test_example_keeps_short_nonsecret():
    env = parse_text("PORT=8000")
    out = generate_example(env)
    assert "PORT=8000" in out


def test_example_dedupes_keeps_last():
    env = parse_text("A=1\nA=2")
    out = generate_example(env)
    # Only one A line, with the last value.
    assert out.count("A=") == 1
    assert "A=2" in out


def test_example_uses_schema_description_and_example(schema_file):
    schema = load_schema(schema_file)
    env = parse_text(f"DATABASE_URL=postgres://localhost/db\nAPI_KEY={FAKE_GITHUB}")
    out = generate_example(env, schema=schema)
    assert "# Postgres connection string" in out
    assert FAKE_GITHUB not in out


def test_example_adds_schema_only_keys(schema_file):
    schema = load_schema(schema_file)
    env = parse_text("DATABASE_URL=postgres://localhost/db")
    out = generate_example(env, schema=schema)
    # PORT is in schema but not env -> should appear with its default.
    assert "PORT=" in out


def test_generate_schema_marks_secret():
    env = parse_text(f"API_KEY={FAKE_GITHUB}")
    out = generate_schema(env)
    assert "[vars.API_KEY]" in out
    assert "secret = true" in out


def test_generate_schema_guesses_types():
    env = parse_text("PORT=8000\nRATIO=1.5\nDEBUG=true\nHOME=https://x.com\nNAME=bob")
    out = generate_schema(env)
    assert 'type = "port"' in out
    assert 'type = "float"' in out
    assert 'type = "bool"' in out
    assert 'type = "url"' in out
    assert 'type = "string"' in out


def test_generate_schema_valid_toml(good_env):
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    out = generate_schema(parse_file(good_env))
    parsed = tomllib.loads(out)
    assert "vars" in parsed
    assert parsed["meta"]["complete"] is True


def test_example_ends_with_newline():
    out = generate_example(parse_text("A=1"))
    assert out.endswith("\n")
