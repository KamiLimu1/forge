"""Pydantic schemas for request/response validation."""

from forge.schemas.auth import (
    AccountActivationRequest,
    BulkInviteRequest,
    BulkInviteResponse,
    BulkInviteResultEntry,
    BulkInviteUserEntry,
    InvitationResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserInviteRequest,
)
from forge.schemas.base import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
    SuccessResponse,
    TimestampSchema,
)
from forge.schemas.user import (
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserUpdateRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserResponse,
    UserRoleResponse,
)

__all__ = [
    # Base
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationParams",
    "SuccessResponse",
    "TimestampSchema",
    # Auth
    "AccountActivationRequest",
    "BulkInviteRequest",
    "BulkInviteResponse",
    "BulkInviteResultEntry",
    "BulkInviteUserEntry",
    "InvitationResponse",
    "LoginRequest",
    "PasswordResetConfirmRequest",
    "PasswordResetRequest",
    "TokenRefreshRequest",
    "TokenResponse",
    "UserInviteRequest",
    # User
    "AdminUserDetailResponse",
    "AdminUserListResponse",
    "AdminUserUpdateRequest",
    "UserProfileResponse",
    "UserProfileUpdateRequest",
    "UserResponse",
    "UserRoleResponse",
]
