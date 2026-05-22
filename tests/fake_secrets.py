"""Synthetic, never-real secret values for tests.

These are assembled at runtime from fragments so that no complete provider
token literal is ever stored in source. That keeps secret-scanning push
protection (GitHub, etc.) from flagging the test suite while still exercising
envlint's detection regexes against realistically shaped values.
"""

# Each value is built by concatenation so the full token never appears as one
# string literal in the repository.
FAKE_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"
FAKE_STRIPE = "sk_" + "live_" + "0123456789abcdefABCDEF99"
FAKE_GITHUB = "ghp_" + "0123456789" + "abcdefABCDEF" + "0123456789abcd0000"
# AIza + exactly 35 chars
FAKE_GOOGLE = "AIza" + "Sy" + ("0" * 33)
FAKE_SLACK = "xoxb-" + "000000000000-" + "abcdefABCDEF0000"
FAKE_RSA_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"
