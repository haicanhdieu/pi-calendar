"""Small shared provisioning constants.

This module intentionally has no crypto or device imports so validation and
settings boot checks do not pull the PBKDF2 implementation into memory.
"""

ADMIN_VERIFIER_VERSION = "pbkdf2-sha256-v2"
LEGACY_ADMIN_VERIFIER_VERSION = "pbkdf2-sha256-v1"
PBKDF2_ITERATIONS = 500
LEGACY_PBKDF2_ITERATIONS = 20_000
SALT_LEN = 16
DIGEST_LEN = 32
