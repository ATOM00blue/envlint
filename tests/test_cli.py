import json

from typer.testing import CliRunner

from envlint.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "envlint" in result.stdout


def test_check_clean_file_exit_zero(good_env):
    result = runner.invoke(app, ["check", str(good_env), "--no-schema"])
    assert result.exit_code == 0
    assert "passed" in result.stdout.lower()


def test_check_bad_file_exit_one(bad_env):
    result = runner.invoke(app, ["check", str(bad_env), "--no-schema"])
    assert result.exit_code == 1
    assert "error" in result.stdout.lower()


def test_check_missing_file_exit_two():
    result = runner.invoke(app, ["check", "does-not-exist.env"])
    assert result.exit_code == 2


def test_check_json_output(bad_env):
    result = runner.invoke(app, ["check", str(bad_env), "--no-schema", "--format", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 1
    assert payload["summary"]["errors"] >= 1
    assert isinstance(payload["findings"], list)


def test_check_strict_promotes_warnings(good_env, tmp_path):
    # good.env has lowercase? No. Use a file with only a warning.
    f = tmp_path / ".env"
    f.write_text("lowercase=value\n")
    normal = runner.invoke(app, ["check", str(f), "--no-schema"])
    strict = runner.invoke(app, ["check", str(f), "--no-schema", "--strict"])
    assert normal.exit_code == 0
    assert strict.exit_code == 1


def test_check_with_schema_autodetect(schema_env):
    result = runner.invoke(app, ["check", str(schema_env)])
    # schema.env has validation errors against the sibling .env.schema
    assert result.exit_code == 1
    assert "V001" in result.stdout or "missing" in result.stdout.lower()


def test_check_explicit_schema(schema_env, schema_file):
    result = runner.invoke(app, ["check", str(schema_env), "--schema", str(schema_file)])
    assert result.exit_code == 1


def test_check_no_secrets_flag(secrets_env):
    with_secrets = runner.invoke(app, ["check", str(secrets_env), "--no-schema"])
    without = runner.invoke(app, ["check", str(secrets_env), "--no-schema", "--no-secrets"])
    # secrets cause warnings (exit 0 by default), but findings differ
    assert "S-aws-access-key" in with_secrets.stdout
    assert "S-aws-access-key" not in without.stdout


def test_example_to_stdout(secrets_env):
    result = runner.invoke(app, ["example", str(secrets_env)])
    assert result.exit_code == 0
    assert "AKIA" not in result.stdout  # redacted


def test_example_to_file(good_env, tmp_path):
    out = tmp_path / ".env.example"
    result = runner.invoke(app, ["example", str(good_env), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "PORT" in out.read_text()


def test_example_no_overwrite_without_force(good_env, tmp_path):
    out = tmp_path / ".env.example"
    out.write_text("existing")
    result = runner.invoke(app, ["example", str(good_env), "-o", str(out)])
    assert result.exit_code == 2
    assert out.read_text() == "existing"


def test_example_force_overwrite(good_env, tmp_path):
    out = tmp_path / ".env.example"
    out.write_text("existing")
    result = runner.invoke(app, ["example", str(good_env), "-o", str(out), "--force"])
    assert result.exit_code == 0
    assert "existing" not in out.read_text()


def test_schema_command(good_env):
    result = runner.invoke(app, ["schema", str(good_env)])
    assert result.exit_code == 0
    assert "[meta]" in result.stdout
    assert "[vars.DATABASE_URL]" in result.stdout


def test_diff_command(good_env, bad_env):
    result = runner.invoke(app, ["diff", str(good_env), str(bad_env)])
    assert result.exit_code == 0
    assert "Only in" in result.stdout


def test_diff_identical(good_env):
    result = runner.invoke(app, ["diff", str(good_env), str(good_env)])
    assert result.exit_code == 0
    assert "No differences" in result.stdout


def test_diff_with_values(tmp_path):
    a = tmp_path / "a.env"
    b = tmp_path / "b.env"
    a.write_text("SHARED=one\n")
    b.write_text("SHARED=two\n")
    result = runner.invoke(app, ["diff", str(a), str(b), "--values"])
    assert result.exit_code == 0
    assert "one" in result.stdout
    assert "two" in result.stdout


def test_check_quiet_clean(good_env):
    result = runner.invoke(app, ["check", str(good_env), "--no-schema", "--quiet"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_check_invalid_schema_path(good_env):
    result = runner.invoke(app, ["check", str(good_env), "--schema", "nope.toml"])
    assert result.exit_code == 2


def test_schema_to_file(good_env, tmp_path):
    out_file = tmp_path / ".env.schema"
    result = runner.invoke(app, ["schema", str(good_env), "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    assert "[meta]" in out_file.read_text()


def test_check_multiple_files(good_env, bad_env):
    result = runner.invoke(app, ["check", str(good_env), str(bad_env), "--no-schema"])
    # bad_env has errors -> overall exit 1
    assert result.exit_code == 1


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # no_args_is_help -> exit code 0 or 2 depending on typer, help text present
    assert "Usage" in result.stdout or "Commands" in result.stdout


def test_check_json_output_never_leaks_secret(tmp_path):
    """End-to-end: a secret on a type-mismatched key must not appear in output."""
    secret = "ghp_0123456789abcdefABCDEF0123456789abcd0000"
    env = tmp_path / ".env"
    env.write_text(f"API_KEY={secret}\n")
    schema = tmp_path / ".env.schema"
    schema.write_text('[vars.API_KEY]\ntype = "int"\nsecret = true\n')
    result = runner.invoke(app, ["check", str(env), "--format", "json"])
    assert secret not in result.stdout


def test_check_non_utf8_file_clean_exit(tmp_path):
    p = tmp_path / "legacy.env"
    p.write_bytes(b"KEY=caf\xe9\n")
    result = runner.invoke(app, ["check", str(p), "--no-schema"])
    # Parses cleanly (no traceback); KEY is valid -> exit 0.
    assert result.exception is None
    assert result.exit_code == 0


def test_check_oversized_file_usage_error(tmp_path):
    from envlint.parser import MAX_FILE_BYTES

    p = tmp_path / "huge.env"
    with open(p, "wb") as fh:
        fh.write(b"A=1\n")
        fh.seek(MAX_FILE_BYTES + 1024)
        fh.write(b"B=2\n")
    result = runner.invoke(app, ["check", str(p), "--no-schema"])
    assert result.exit_code == 2
