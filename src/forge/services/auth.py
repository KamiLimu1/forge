"""Authentication service with business logic."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forge.core.config import settings
from forge.core.jwt import (
    TokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    get_token_expiration,
    get_token_jti,
    get_token_subject,
)
from forge.core.security import generate_secure_token, hash_password, verify_password
from forge.models import (
    AccountState,
    AuditLog,
    Invitation,
    PasswordResetToken,
    TokenBlacklist,
    User,
    UserRole,
    UserRoleAssignment,
)


class AuthenticationError(Exception):
    """Base exception for authentication errors."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    pass


class AccountSuspendedError(AuthenticationError):
    """Raised when account is suspended."""

    pass


class AccountNotActiveError(AuthenticationError):
    """Raised when account is not active."""

    pass


class InvitationError(Exception):
    """Base exception for invitation errors."""

    pass


class InvitationExpiredError(InvitationError):
    """Raised when invitation has expired."""

    pass


class InvitationAlreadyUsedError(InvitationError):
    """Raised when invitation was already used."""

    pass


class InvitationNotFoundError(InvitationError):
    """Raised when invitation is not found."""

    pass


class TokenServiceError(Exception):
    """Base exception for token service errors."""

    pass


async def create_invitation(
    db: AsyncSession,
    email: str,
    invited_by_id: uuid.UUID,
    first_name: str | None = None,
    last_name: str | None = None,
    intended_roles: list[UserRole] | None = None,
    intended_cohort_id: uuid.UUID | None = None,
) -> Invitation:
    """Create a new user invitation.

    Args:
        db: Database session.
        email: Email address to invite.
        invited_by_id: UUID of the user sending the invitation.
        first_name: Optional first name for the invited user.
        last_name: Optional last name for the invited user.
        intended_roles: Optional list of roles to assign on activation.
        intended_cohort_id: Optional cohort ID for role assignment.

    Returns:
        The created Invitation object.
    """
    token = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.INVITATION_TOKEN_EXPIRE_DAYS
    )

    invitation = Invitation(
        email=email.lower(),
        token=token,
        expires_at=expires_at,
        invited_by=invited_by_id,
        first_name=first_name,
        last_name=last_name,
        intended_roles=[r.value for r in intended_roles] if intended_roles else None,
        intended_cohort_id=intended_cohort_id,
    )

    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    return invitation


async def get_invitation_by_token(
    db: AsyncSession,
    token: str,
) -> Invitation:
    """Get an invitation by its token.

    Args:
        db: Database session.
        token: The invitation token.

    Returns:
        The Invitation object.

    Raises:
        InvitationNotFoundError: If invitation not found.
        InvitationExpiredError: If invitation has expired.
        InvitationAlreadyUsedError: If invitation was already used.
    """
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token == token)
    )

    if not invitation:
        raise InvitationNotFoundError("Invalid invitation token")

    if invitation.used_at is not None:
        raise InvitationAlreadyUsedError("Invitation has already been used")

    if invitation.expires_at < datetime.now(timezone.utc):
        raise InvitationExpiredError("Invitation has expired")

    return invitation


async def activate_account(
    db: AsyncSession,
    token: str,
    password: str,
) -> tuple[User, str, str]:
    """Activate a user account from an invitation.

    Args:
        db: Database session.
        token: The invitation token.
        password: The password to set for the account.

    Returns:
        Tuple of (User, access_token, refresh_token).

    Raises:
        InvitationError subclass: If invitation is invalid.
    """
    invitation = await get_invitation_by_token(db, token)

    # Check if user already exists (shouldn't happen, but handle it)
    existing_user = await db.scalar(
        select(User).where(User.email == invitation.email.lower())
    )

    if existing_user:
        # If user exists and is pending, activate them
        if existing_user.account_state == AccountState.PENDING:
            existing_user.password_hash = hash_password(password)
            existing_user.account_state = AccountState.ACTIVE
            existing_user.last_login_at = datetime.now(timezone.utc)
            user = existing_user
        else:
            raise InvitationAlreadyUsedError(
                "An account with this email already exists"
            )
    else:
        # Create new user
        user = User(
            email=invitation.email.lower(),
            password_hash=hash_password(password),
            first_name=invitation.first_name or "",
            last_name=invitation.last_name or "",
            account_state=AccountState.ACTIVE,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)

    # Mark invitation as used
    invitation.used_at = datetime.now(timezone.utc)

    await db.flush()

    # Assign intended roles if specified
    if invitation.intended_roles:
        for role_value in invitation.intended_roles:
            role = UserRole(role_value)
            role_assignment = UserRoleAssignment(
                user_id=user.id,
                role=role,
                cohort_id=invitation.intended_cohort_id,
                assigned_by=invitation.invited_by,
            )
            db.add(role_assignment)

    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action="account_activated",
        resource_type="user",
        resource_id=user.id,
        meta_data={"invitation_id": str(invitation.id)},
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token, _, _ = create_access_token(user.id)
    refresh_token, _, _ = create_refresh_token(user.id)

    return user, access_token, refresh_token


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    ip_address: str | None = None,
) -> tuple[User, str, str]:
    """Authenticate a user with email and password.

    Args:
        db: Database session.
        email: User's email address.
        password: User's password.
        ip_address: Optional IP address for audit logging.

    Returns:
        Tuple of (User, access_token, refresh_token).

    Raises:
        InvalidCredentialsError: If credentials are invalid.
        AccountSuspendedError: If account is suspended.
        AccountNotActiveError: If account is not active.
    """
    user = await db.scalar(
        select(User)
        .options(selectinload(User.roles))
        .where(User.email == email.lower())
    )

    if not user or not user.password_hash:
        raise InvalidCredentialsError("Invalid email or password")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if user.account_state == AccountState.SUSPENDED:
        raise AccountSuspendedError(
            "Account is suspended. Please contact the administrator."
        )

    if user.account_state == AccountState.PENDING:
        raise AccountNotActiveError(
            "Account is not activated. Please check your email for activation link."
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token, _, _ = create_access_token(user.id)
    refresh_token, _, _ = create_refresh_token(user.id)

    return user, access_token, refresh_token


async def refresh_tokens(
    db: AsyncSession,
    refresh_token: str,
) -> tuple[str, str]:
    """Refresh access and refresh tokens.

    Args:
        db: Database session.
        refresh_token: The refresh token.

    Returns:
        Tuple of (new_access_token, new_refresh_token).

    Raises:
        TokenServiceError: If token is invalid or blacklisted.
    """
    try:
        user_id_str = get_token_subject(refresh_token, TokenType.REFRESH)
        jti = get_token_jti(refresh_token)
    except TokenError as e:
        raise TokenServiceError(str(e)) from e

    # Check if refresh token is blacklisted
    blacklisted = await db.scalar(
        select(TokenBlacklist).where(TokenBlacklist.token_jti == jti)
    )
    if blacklisted:
        raise TokenServiceError("Token has been revoked")

    # Verify user exists and is active
    user_id = uuid.UUID(user_id_str)
    user = await db.scalar(select(User).where(User.id == user_id))

    if not user:
        raise TokenServiceError("User not found")

    if user.account_state == AccountState.SUSPENDED:
        raise TokenServiceError("Account is suspended")

    # Blacklist old refresh token (rotate tokens)
    try:
        exp = get_token_expiration(refresh_token)
        blacklist_entry = TokenBlacklist(
            token_jti=jti,
            expires_at=exp,
        )
        db.add(blacklist_entry)
        await db.commit()
    except TokenError:
        pass  # Token might be expired, which is fine

    # Generate new tokens
    new_access_token, _, _ = create_access_token(user.id)
    new_refresh_token, _, _ = create_refresh_token(user.id)

    return new_access_token, new_refresh_token


async def logout_user(
    db: AsyncSession,
    access_token: str,
    refresh_token: str | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> None:
    """Logout a user by blacklisting their tokens.

    Args:
        db: Database session.
        access_token: The access token to blacklist.
        refresh_token: Optional refresh token to blacklist.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP address for audit logging.
    """
    try:
        access_jti = get_token_jti(access_token)
        access_exp = get_token_expiration(access_token)
        db.add(TokenBlacklist(token_jti=access_jti, expires_at=access_exp))
    except TokenError:
        pass  # Token might be invalid/expired

    if refresh_token:
        try:
            refresh_jti = get_token_jti(refresh_token)
            refresh_exp = get_token_expiration(refresh_token)
            db.add(TokenBlacklist(token_jti=refresh_jti, expires_at=refresh_exp))
        except TokenError:
            pass

    if user_id:
        audit_log = AuditLog(
            user_id=user_id,
            action="logout",
            resource_type="user",
            resource_id=user_id,
            ip_address=ip_address,
        )
        db.add(audit_log)

    await db.commit()


async def create_password_reset_token(
    db: AsyncSession,
    email: str,
) -> PasswordResetToken | None:
    """Create a password reset token for a user.

    Args:
        db: Database session.
        email: User's email address.

    Returns:
        PasswordResetToken if user exists, None otherwise.
        (We return None to prevent email enumeration)
    """
    user = await db.scalar(select(User).where(User.email == email.lower()))

    if not user:
        return None

    if user.account_state == AccountState.SUSPENDED:
        return None

    token = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )

    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )

    db.add(reset_token)
    await db.commit()
    await db.refresh(reset_token)

    return reset_token


async def reset_password(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> User:
    """Reset a user's password using a reset token.

    Args:
        db: Database session.
        token: The password reset token.
        new_password: The new password.

    Returns:
        The updated User object.

    Raises:
        TokenServiceError: If token is invalid, expired, or already used.
    """
    reset_token = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )

    if not reset_token:
        raise TokenServiceError("Invalid reset token")

    if reset_token.used_at is not None:
        raise TokenServiceError("Reset token has already been used")

    if reset_token.expires_at < datetime.now(timezone.utc):
        raise TokenServiceError("Reset token has expired")

    user = await db.scalar(
        select(User).where(User.id == reset_token.user_id)
    )

    if not user:
        raise TokenServiceError("User not found")

    # Update password
    user.password_hash = hash_password(new_password)
    reset_token.used_at = datetime.now(timezone.utc)

    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action="password_reset",
        resource_type="user",
        resource_id=user.id,
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    return user
