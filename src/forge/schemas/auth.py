"""Authentication-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from forge.core.security import validate_password
from forge.models.user import UserRole
from forge.schemas.base import BaseSchema


class UserInviteRequest(BaseSchema):
    """Request schema for inviting a single user."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    roles: list[UserRole] = Field(..., min_length=1)
    cohort_id: UUID | None = None


class BulkInviteUserEntry(BaseSchema):
    """Single user entry for bulk invite."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    roles: list[UserRole] = Field(..., min_length=1)


class BulkInviteRequest(BaseSchema):
    """Request schema for bulk user invitations."""

    users: list[BulkInviteUserEntry] = Field(..., min_length=1)
    cohort_id: UUID | None = None


class BulkInviteResultEntry(BaseSchema):
    """Result for a single user in bulk invite."""

    email: str
    success: bool
    message: str | None = None


class BulkInviteResponse(BaseSchema):
    """Response schema for bulk invite operation."""

    total: int
    successful: int
    failed: int
    results: list[BulkInviteResultEntry]


class AccountActivationRequest(BaseSchema):
    """Request schema for activating an account."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets requirements."""
        result = validate_password(v)
        if not result.is_valid:
            raise ValueError("; ".join(result.errors))
        return v


class LoginRequest(BaseSchema):
    """Request schema for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseSchema):
    """Response schema for authentication tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiration


class TokenRefreshRequest(BaseSchema):
    """Request schema for refreshing tokens."""

    refresh_token: str


class PasswordResetRequest(BaseSchema):
    """Request schema for initiating password reset."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseSchema):
    """Request schema for completing password reset."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets requirements."""
        result = validate_password(v)
        if not result.is_valid:
            raise ValueError("; ".join(result.errors))
        return v


class InvitationResponse(BaseSchema):
    """Response schema for invitation details."""

    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    expires_at: datetime
    created_at: datetime
    used_at: datetime | None
    intended_roles: list[str] | None
