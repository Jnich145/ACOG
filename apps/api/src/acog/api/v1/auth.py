"""
Authentication endpoints.

Provides login, logout, token refresh, and user info endpoints.
Note: Full implementation pending User model in Phase 2.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from acog.core.security import create_access_token, create_refresh_token

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=1, description="User password")


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration in seconds")


class TokenRefreshRequest(BaseModel):
    """Token refresh request schema."""

    refresh_token: str = Field(description="Refresh token")


class UserInfo(BaseModel):
    """User information schema."""

    id: str = Field(description="User ID")
    email: str = Field(description="User email")
    name: str | None = Field(description="User display name")
    role: str = Field(description="User role")


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login",
    description="Authenticate user and return access tokens.",
)
async def login(request: LoginRequest) -> LoginResponse:
    """
    Authenticate user with email and password.

    Note: This is a stub implementation. Full authentication
    will be implemented with the User model in Phase 2.

    For now, accepts a demo user for development:
    - email: admin@acog.io
    - password: admin123

    Args:
        request: Login credentials

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Stub implementation - accept demo credentials
    if request.email == "admin@acog.io" and request.password == "admin123":
        # Create tokens for demo user
        token_data = {
            "sub": "demo-user-id",
            "email": request.email,
            "role": "admin",
        }

        access_token = create_access_token(data=token_data)
        refresh_token = create_refresh_token(data=token_data)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=60 * 60 * 24 * 7,  # 1 week
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post(
    "/refresh",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Token",
    description="Get new access token using refresh token.",
)
async def refresh_token(request: TokenRefreshRequest) -> LoginResponse:
    """
    Refresh access token using a valid refresh token.

    Args:
        request: Refresh token

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    from acog.core.security import verify_refresh_token

    try:
        payload = verify_refresh_token(request.refresh_token)

        # Create new tokens
        token_data = {
            "sub": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
        }

        access_token = create_access_token(data=token_data)
        new_refresh_token = create_refresh_token(data=token_data)

        return LoginResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=60 * 60 * 24 * 7,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Logout current user (invalidate tokens).",
)
async def logout() -> dict[str, str]:
    """
    Logout current user.

    Note: JWT tokens are stateless, so logout is handled client-side
    by discarding the tokens. In Phase 2, we may implement token
    blacklisting for enhanced security.

    Returns:
        Logout confirmation message
    """
    return {"message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=UserInfo,
    status_code=status.HTTP_200_OK,
    summary="Get Current User",
    description="Get information about the currently authenticated user.",
)
async def get_current_user(
    # Note: In production, this would use get_current_user_id dependency
    # user_id: str = Depends(get_current_user_id),
) -> UserInfo:
    """
    Get current user information.

    Note: This is a stub implementation returning demo user info.
    Full implementation will be added with User model in Phase 2.

    Returns:
        Current user information
    """
    # Stub implementation - return demo user
    return UserInfo(
        id="demo-user-id",
        email="admin@acog.io",
        name="Demo Admin",
        role="admin",
    )


@router.post(
    "/register",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Register User",
    description="Register a new user account.",
)
async def register() -> dict[str, Any]:
    """
    Register a new user account.

    Note: User registration is not implemented in Phase 1.
    This endpoint will be implemented with the User model in Phase 2.

    Raises:
        HTTPException: Always returns 501 Not Implemented
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User registration not implemented in Phase 1",
    )
