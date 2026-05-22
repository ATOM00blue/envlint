from pathlib import Path

import pytest

from fake_secrets import (
    FAKE_AWS,
    FAKE_GITHUB,
    FAKE_GOOGLE,
    FAKE_STRIPE,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def good_env() -> Path:
    return FIXTURES / "good.env"


@pytest.fixture
def bad_env() -> Path:
    return FIXTURES / "bad.env"


@pytest.fixture
def secrets_env(tmp_path) -> Path:
    """A .env containing realistically shaped (but fake) secret values.

    Generated at runtime from assembled fragments so no full provider token is
    ever committed to the repository (avoids secret-scanning push protection).
    """
    content = "\n".join(
        [
            "# Contains values that look like real secrets",
            f"AWS_ACCESS_KEY_ID={FAKE_AWS}",
            f"STRIPE_SECRET={FAKE_STRIPE}",
            f"GITHUB_TOKEN={FAKE_GITHUB}",
            f"GOOGLE_API_KEY={FAKE_GOOGLE}",
            "RANDOM_BLOB=Zx9KqL2mNpW8vR4tY7uH3sD6fG1jB5cA0eXwQ",
            "PLACEHOLDER_KEY=your-api-key-here",
            "NORMAL_VALUE=hello",
            "",
        ]
    )
    p = tmp_path / "secrets.env"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def schema_env() -> Path:
    return FIXTURES / "schema.env"


@pytest.fixture
def schema_file() -> Path:
    return FIXTURES / ".env.schema"
