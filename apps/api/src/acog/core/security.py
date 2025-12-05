"""
Security utilities for authentication and authorization.

This module provides JWT token creation and verification,
password hashing, and other security-related functions.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from acog.core.config import get_settings
from acog.core.exceptions import AuthenticationError

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token.
              Should include 'sub' (subject) at minimum.
        expires_delta: Optional custom expiration time.
                      Defaults to settings.access_token_expire_minutes.

    Returns:
        Encoded JWT token string

    Example:
        ```python
        token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        ```
    """
    settings = get_settings()

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})

    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def verify_token(token: str) -> dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: The JWT token string to verify

    Returns:
        Dictionary of decoded token claims

    Raises:
        AuthenticationError: If the token is invalid, expired,
                           or cannot be decoded

    Example:
        ```python
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")
        except AuthenticationError:
            # Handle invalid token
            pass
        ```
    """
    settings = get_settings()

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(
            message="Invalid or expired token",
            details={"error": str(e)},
        ) from e


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Example:
        ```python
        hashed = hash_password("user_password")
        # Store hashed in database
        ```
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise

    Example:
        ```python
        if verify_password(input_password, user.hashed_password):
            # Password is correct
            pass
        ```
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_token_subject(token: str) -> str:
    """
    Extract the subject (user ID) from a token.

    Args:
        token: JWT token string

    Returns:
        The subject claim from the token

    Raises:
        AuthenticationError: If token is invalid or has no subject
    """
    payload = verify_token(token)
    subject = payload.get("sub")

    if subject is None:
        raise AuthenticationError(
            message="Token has no subject",
            details={"error": "Missing 'sub' claim"},
        )

    return str(subject)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token with longer expiration.

    Refresh tokens have a longer lifespan and are used to
    obtain new access tokens without re-authentication.

    Args:
        data: Dictionary of claims to encode
        expires_delta: Optional custom expiration (default: 30 days)

    Returns:
        Encoded JWT refresh token string
    """
    settings = get_settings()

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        # Default: 30 days for refresh tokens
        expire = datetime.now(UTC) + timedelta(days=30)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    })

    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def verify_refresh_token(token: str) -> dict[str, Any]:
    """
    Verify a refresh token.

    Args:
        token: The refresh token string to verify

    Returns:
        Dictionary of decoded token claims

    Raises:
        AuthenticationError: If token is invalid or not a refresh token
    """
    payload = verify_token(token)

    if payload.get("type") != "refresh":
        raise AuthenticationError(
            message="Invalid token type",
            details={"error": "Expected refresh token"},
        )

    return payload
