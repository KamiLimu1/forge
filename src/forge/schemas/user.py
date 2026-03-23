"""User-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from forge.models.user import AccountState, UserRole
from forge.schemas.base import BaseSchema, TimestampSchema


class UserRoleResponse(BaseSchema):
    """Response schema for a user's role assignment."""

    id: UUID
    role: UserRole
    cohort_id: UUID | None
    assigned_at: datetime


class UserResponse(BaseSchema):
    """Response schema for user details."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    account_state: AccountState
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    roles: list[UserRoleResponse] = []


class UserProfileResponse(BaseSchema):
    """Response schema for current user's profile."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    account_state: AccountState
    last_login_at: datetime | None
    created_at: datetime
    roles: list[UserRoleResponse] = []


class UserProfileUpdateRequest(BaseSchema):
    """Request schema for updating user profile."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)


class AdminUserUpdateRequest(BaseSchema):
    """Request schema for admin updating a user."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None


class AdminUserListResponse(BaseSchema):
    """Response schema for admin user list."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    account_state: AccountState
    last_login_at: datetime | None
    created_at: datetime


class AdminUserDetailResponse(UserResponse):
    """Detailed response schema for admin viewing a user."""

    pass
