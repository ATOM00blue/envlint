import json

import pytest

from envlint.parser import parse_file, parse_text
from envlint.schema import (
    _build_schema,
    find_schema,
    load_schema,
    validate,
)


def codes(findings):
    return {f.code for f in findings}


def test_load_schema_toml(schema_file):
    schema = load_schema(schema_file)
    assert "DATABASE_URL" in schema.vars
    assert schema.vars["DATABASE_URL"].required is True
    assert schema.vars["DATABASE_URL"].type == "url"
    assert schema.complete is True


def test_secret_key_sets(schema_file):
    schema = load_schema(schema_file)
    assert "API_KEY" in schema.secret_keys


def test_find_schema(fixtures):
    found = find_schema(fixtures / "schema.env")
    assert found is not None
    assert found.name == ".env.schema"


def test_find_schema_none(tmp_path):
    assert find_schema(tmp_path) is None


def test_missing_required_key():
    schema = _build_schema({"vars": {"NEEDED": {"required": True}}})
    findings = validate(parse_text("OTHER=1"), schema)
    assert "V001" in codes(findings)


def test_required_present_but_empty():
    schema = _build_schema({"vars": {"NEEDED": {"required": True}}})
    findings = validate(parse_text("NEEDED="), schema)
    assert "V002" in codes(findings)


@pytest.mark.parametrize(
    "vtype,value,ok",
    [
        ("int", "42", True),
        ("int", "4.2", False),
        ("float", "4.2", True),
        ("float", "abc", False),
        ("bool", "true", True),
        ("bool", "maybe", False),
        ("port", "8080", True),
        ("port", "99999", False),
        ("url", "https://x.com", True),
        ("url", "not a url", False),
        ("email", "a@b.com", True),
        ("email", "nope", False),
    ],
)
def test_type_validation(vtype, value, ok):
    schema = _build_schema({"vars": {"K": {"type": vtype}}})
    findings = validate(parse_text(f"K={value}"), schema)
    has_type_error = "V003" in codes(findings)
    assert has_type_error != ok


def test_allowed_values():
    schema = _build_schema({"vars": {"LVL": {"allowed": ["a", "b"]}}})
    bad = validate(parse_text("LVL=c"), schema)
    good = validate(parse_text("LVL=a"), schema)
    assert "V004" in codes(bad)
    assert "V004" not in codes(good)


def test_pattern():
    schema = _build_schema({"vars": {"DSN": {"pattern": "^https://"}}})
    bad = validate(parse_text("DSN=http://x"), schema)
    good = validate(parse_text("DSN=https://x"), schema)
    assert "V005" in codes(bad)
    assert "V005" not in codes(good)


def test_typo_suggestion():
    schema = _build_schema({"vars": {"PORT": {"type": "port"}}})
    findings = validate(parse_text("PORRT=8080"), schema)
    assert "V007" in codes(findings)
    msg = next(f for f in findings if f.code == "V007").message
    assert "PORT" in msg


def test_unknown_key_when_complete():
    schema = _build_schema({"meta": {"complete": True}, "vars": {"KNOWN": {}}})
    findings = validate(parse_text("KNOWN=1\nTOTALLYUNRELATED=2"), schema)
    assert "V008" in codes(findings)


def test_unknown_key_when_not_complete_is_silent():
    schema = _build_schema({"vars": {"KNOWN": {}}})
    findings = validate(parse_text("KNOWN=1\nSOMETHINGELSE=2"), schema)
    assert "V008" not in codes(findings)


def test_invalid_type_in_schema_raises():
    with pytest.raises(ValueError):
        _build_schema({"vars": {"K": {"type": "banana"}}})


def test_non_dict_var_raises():
    with pytest.raises(ValueError):
        _build_schema({"vars": {"K": "notatable"}})


def test_load_json_schema(tmp_path):
    p = tmp_path / ".env.schema.json"
    p.write_text(json.dumps({"vars": {"K": {"required": True, "type": "int"}}}))
    schema = load_schema(p)
    assert schema.vars["K"].type == "int"


def test_validate_against_fixture(schema_env, schema_file):
    findings = validate(parse_file(schema_env), load_schema(schema_file))
    found = codes(findings)
    assert "V001" in found  # API_KEY missing & required
    assert "V003" in found  # PORT out of range / ADMIN_EMAIL invalid
    assert "V004" in found  # LOG_LEVEL=verbose not allowed
    assert "V008" in found  # EXTRA_KEY unknown (schema complete)


def test_secret_false_helper():
    schema = _build_schema({"vars": {"K": {"secret": False}}})
    assert "K" in schema.nonsecret_keys
