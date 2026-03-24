"""Security utilities for password hashing and validation."""

import re
import secrets
from typing import NamedTuple

from passlib.context import CryptContext

from forge.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordValidationResult(NamedTuple):
    """Result of password validation."""

    is_valid: bool
    errors: list[str]


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password(password: str) -> PasswordValidationResult:
    """Validate password against configured requirements.

    Returns a NamedTuple with is_valid bool and list of error messages.
    """
    errors: list[str] = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
        )

    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")

    return PasswordValidationResult(is_valid=len(errors) == 0, errors=errors)


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(nbytes)
