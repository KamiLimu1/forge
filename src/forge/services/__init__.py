"""Business logic services."""

from forge.services.auth import (
    AccountNotActiveError,
    AccountSuspendedError,
    AuthenticationError,
    InvitationAlreadyUsedError,
    InvitationError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvalidCredentialsError,
    TokenServiceError,
    activate_account,
    authenticate_user,
    create_invitation,
    create_password_reset_token,
    get_invitation_by_token,
    logout_user,
    refresh_tokens,
    reset_password,
)
from forge.services.email import (
    send_email,
    send_invitation_email,
    send_password_reset_email,
)
from forge.services.user import (
    UserNotFoundError,
    activate_user,
    admin_update_user,
    get_user_by_id,
    list_users,
    suspend_user,
    update_user_profile,
)

__all__ = [
    # Auth
    "AccountNotActiveError",
    "AccountSuspendedError",
    "AuthenticationError",
    "InvitationAlreadyUsedError",
    "InvitationError",
    "InvitationExpiredError",
    "InvitationNotFoundError",
    "InvalidCredentialsError",
    "TokenServiceError",
    "activate_account",
    "authenticate_user",
    "create_invitation",
    "create_password_reset_token",
    "get_invitation_by_token",
    "logout_user",
    "refresh_tokens",
    "reset_password",
    # Email
    "send_email",
    "send_invitation_email",
    "send_password_reset_email",
    # User
    "UserNotFoundError",
    "activate_user",
    "admin_update_user",
    "get_user_by_id",
    "list_users",
    "suspend_user",
    "update_user_profile",
]
