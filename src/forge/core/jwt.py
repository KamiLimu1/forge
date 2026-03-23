"""JWT token generation and validation utilities."""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from jose import JWTError, jwt

from forge.core.config import settings


class TokenType(str, Enum):
    """Types of JWT tokens."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Exception raised for token-related errors."""

    pass


def create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Create a JWT token.

    Args:
        subject: The subject of the token (usually user_id).
        token_type: Type of token (access or refresh).
        expires_delta: Optional custom expiration time.
        additional_claims: Optional additional claims to include.

    Returns:
        Tuple of (token, jti, expiration_datetime).
    """
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        if token_type == TokenType.ACCESS:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        else:
            expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    expire = now + expires_delta
    jti = str(uuid.uuid4())

    to_encode: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": expire,
        "jti": jti,
    }

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt, jti, expire


def create_access_token(
    user_id: uuid.UUID,
    additional_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Create an access token for a user.

    Args:
        user_id: The user's UUID.
        additional_claims: Optional additional claims.

    Returns:
        Tuple of (token, jti, expiration_datetime).
    """
    return create_token(
        subject=str(user_id),
        token_type=TokenType.ACCESS,
        additional_claims=additional_claims,
    )


def create_refresh_token(
    user_id: uuid.UUID,
    additional_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Create a refresh token for a user.

    Args:
        user_id: The user's UUID.
        additional_claims: Optional additional claims.

    Returns:
        Tuple of (token, jti, expiration_datetime).
    """
    return create_token(
        subject=str(user_id),
        token_type=TokenType.REFRESH,
        additional_claims=additional_claims,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string.

    Returns:
        The decoded token payload.

    Raises:
        TokenError: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise TokenError(f"Invalid token: {e}") from e


def get_token_payload(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decode a token and verify its type.

    Args:
        token: The JWT token string.
        expected_type: The expected token type.

    Returns:
        The decoded token payload.

    Raises:
        TokenError: If token is invalid, expired, or wrong type.
    """
    payload = decode_token(token)

    token_type = payload.get("type")
    if token_type != expected_type.value:
        raise TokenError(f"Invalid token type: expected {expected_type.value}, got {token_type}")

    return payload


def get_token_subject(token: str, expected_type: TokenType) -> str:
    """Extract the subject (user_id) from a token.

    Args:
        token: The JWT token string.
        expected_type: The expected token type.

    Returns:
        The subject claim (user_id as string).

    Raises:
        TokenError: If token is invalid or subject is missing.
    """
    payload = get_token_payload(token, expected_type)
    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token missing subject claim")
    return subject


def get_token_jti(token: str) -> str:
    """Extract the JTI (JWT ID) from a token.

    Args:
        token: The JWT token string.

    Returns:
        The JTI claim.

    Raises:
        TokenError: If token is invalid or JTI is missing.
    """
    payload = decode_token(token)
    jti = payload.get("jti")
    if not jti:
        raise TokenError("Token missing JTI claim")
    return jti


def get_token_expiration(token: str) -> datetime:
    """Extract the expiration datetime from a token.

    Args:
        token: The JWT token string.

    Returns:
        The expiration datetime.

    Raises:
        TokenError: If token is invalid or expiration is missing.
    """
    payload = decode_token(token)
    exp = payload.get("exp")
    if not exp:
        raise TokenError("Token missing expiration claim")
    return datetime.fromtimestamp(exp, tz=timezone.utc)
