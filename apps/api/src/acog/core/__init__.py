"""
ACOG Core Module.

This module contains the foundational components of the ACOG application:
- Configuration management
- Database connections and session handling
- Security utilities (JWT, password hashing)
- Custom exceptions
- Dependency injection helpers
"""

from acog.core.config import Settings, get_settings
from acog.core.database import Base, get_db
from acog.core.exceptions import (
    ACOGException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "Settings",
    "get_settings",
    "Base",
    "get_db",
    "ACOGException",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
]
