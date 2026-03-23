"""FastAPI dependencies for authentication and authorization."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forge.core.jwt import TokenError, TokenType, get_token_payload
from forge.db.session import get_db
from forge.models import AccountState, TokenBlacklist, User, UserRole, UserRoleAssignment

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user from the JWT token.

    Raises:
        HTTPException: If token is invalid, blacklisted, or user not found.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = get_token_payload(credentials.credentials, TokenType.ACCESS)
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti:
        blacklisted = await db.scalar(
            select(TokenBlacklist).where(TokenBlacklist.token_jti == jti)
        )
        if blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Get user
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.scalar(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == UUID(user_id))
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.account_state == AccountState.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact the administrator.",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user, ensuring they are active."""
    if current_user.account_state != AccountState.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )
    return current_user


def has_role(required_roles: list[UserRole]):
    """Dependency factory to check if user has any of the required roles.

    Args:
        required_roles: List of roles that grant access.

    Returns:
        Dependency function that validates user has required role.
    """
    async def check_role(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        user_roles = {role.role for role in current_user.roles}

        # Admin always has access
        if UserRole.ADMIN in user_roles:
            return current_user

        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return check_role


def require_admin():
    """Dependency to require admin role."""
    return has_role([UserRole.ADMIN])


def require_committee_or_admin():
    """Dependency to require committee or admin role."""
    return has_role([UserRole.COMMITTEE, UserRole.ADMIN])


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(has_role([UserRole.ADMIN]))]
CommitteeUser = Annotated[User, Depends(has_role([UserRole.COMMITTEE, UserRole.ADMIN]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]
