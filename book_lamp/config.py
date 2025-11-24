"""Application configuration with hashed allowed user email."""
import hashlib
import os

# SHA-256 hash of the single allowed user's email address
# To generate: echo -n "your.email@example.com" | sha256sum
ALLOWED_USER_EMAIL_HASH = os.environ.get(
    "ALLOWED_USER_EMAIL_HASH",
    "fd911bd8cac2e603a80efafca2210b7a917c97410f0c29d9f2bfb99867e5a589"  # user@example.com
)


def verify_email(email: str) -> bool:
    """Verify if the provided email matches the allowed user hash."""
    email_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    return email_hash == ALLOWED_USER_EMAIL_HASH
