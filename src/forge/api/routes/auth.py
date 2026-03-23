"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from forge.api.deps import AdminUser, CurrentUser, DbSession
from forge.core.config import settings
from forge.models import Invitation, User
from forge.schemas import (
    AccountActivationRequest,
    BulkInviteRequest,
    BulkInviteResponse,
    BulkInviteResultEntry,
    ErrorResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    SuccessResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserInviteRequest,
)
from forge.services.auth import (
    AccountNotActiveError,
    AccountSuspendedError,
    InvitationError,
    InvalidCredentialsError,
    TokenServiceError,
    activate_account,
    authenticate_user,
    create_invitation,
    create_password_reset_token,
    logout_user,
    refresh_tokens,
    reset_password,
)
from forge.services.email import send_invitation_email, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "/invite",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new user",
    responses={
        201: {
            "description": "Invitation sent successfully",
            "content": {
                "application/json": {
                    "example": {"success": True, "message": "Invitation sent successfully"}
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "User already exists or pending invitation exists",
        },
        403: {"model": ErrorResponse, "description": "Not authorized (requires admin role)"},
    },
)
async def invite_user(
    request_data: UserInviteRequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser,
    db: DbSession,
) -> SuccessResponse:
    """Invite a new user to the system.

    **Requires admin role.**

    Creates an invitation record and sends an email with an activation link.
    The invitation token expires after 7 days.

    The invited user will receive an email with a link to activate their account
    and set their password.

    **Request body:**
    - `email`: Valid email address for the new user
    - `first_name`: User's first name
    - `last_name`: User's last name
    - `roles`: List of roles to assign (e.g., ["mentee"], ["peer_mentor_1:1"])
    - `cohort_id`: (Optional) UUID of the cohort to assign the user to
    """
    # Check if user already exists
    existing = await db.scalar(
        select(User).where(User.email == request_data.email.lower())
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # Check if there's a pending invitation
    existing_invitation = await db.scalar(
        select(Invitation).where(
            Invitation.email == request_data.email.lower(),
            Invitation.used_at.is_(None),
        )
    )
    if existing_invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invitation already exists for this email",
        )

    invitation = await create_invitation(
        db=db,
        email=request_data.email,
        invited_by_id=current_user.id,
        first_name=request_data.first_name,
        last_name=request_data.last_name,
        intended_roles=request_data.roles,
        intended_cohort_id=request_data.cohort_id,
    )

    # Send email in background
    background_tasks.add_task(
        send_invitation_email,
        to=invitation.email,
        first_name=invitation.first_name or "User",
        invitation_token=invitation.token,
    )

    return SuccessResponse(message="Invitation sent successfully")


@router.post(
    "/bulk-invite",
    response_model=BulkInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk invite multiple users",
    responses={
        201: {"description": "Bulk invitation processed"},
        403: {"model": ErrorResponse, "description": "Not authorized (requires admin role)"},
    },
)
async def bulk_invite_users(
    request_data: BulkInviteRequest,
    background_tasks: BackgroundTasks,
    current_user: AdminUser,
    db: DbSession,
) -> BulkInviteResponse:
    """Bulk invite multiple users to the system.

    **Requires admin role.**

    Processes a list of users and creates invitations for each.
    Returns a detailed report of successes and failures.

    This is useful for onboarding an entire cohort at once.

    **Request body:**
    - `users`: Array of user objects with email, first_name, last_name, and roles
    - `cohort_id`: (Optional) UUID of the cohort to assign all users to

    **Response includes:**
    - `total`: Total number of users in request
    - `successful`: Number of invitations sent
    - `failed`: Number of failures
    - `results`: Per-user breakdown of success/failure
    """
    results: list[BulkInviteResultEntry] = []
    successful = 0
    failed = 0

    for user_entry in request_data.users:
        try:
            # Check if user already exists
            existing = await db.scalar(
                select(User).where(User.email == user_entry.email.lower())
            )
            if existing:
                results.append(
                    BulkInviteResultEntry(
                        email=user_entry.email,
                        success=False,
                        message="User already exists",
                    )
                )
                failed += 1
                continue

            invitation = await create_invitation(
                db=db,
                email=user_entry.email,
                invited_by_id=current_user.id,
                first_name=user_entry.first_name,
                last_name=user_entry.last_name,
                intended_roles=user_entry.roles,
                intended_cohort_id=request_data.cohort_id,
            )

            background_tasks.add_task(
                send_invitation_email,
                to=invitation.email,
                first_name=invitation.first_name or "User",
                invitation_token=invitation.token,
            )

            results.append(
                BulkInviteResultEntry(
                    email=user_entry.email,
                    success=True,
                    message="Invitation sent",
                )
            )
            successful += 1

        except Exception as e:
            results.append(
                BulkInviteResultEntry(
                    email=user_entry.email,
                    success=False,
                    message=str(e),
                )
            )
            failed += 1

    return BulkInviteResponse(
        total=len(request_data.users),
        successful=successful,
        failed=failed,
        results=results,
    )


@router.post(
    "/activate",
    response_model=TokenResponse,
    summary="Activate account with invitation token",
    responses={
        200: {"description": "Account activated successfully, tokens returned"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid, expired, or already-used invitation token",
        },
        422: {"description": "Password does not meet requirements"},
    },
)
async def activate_user_account(
    request_data: AccountActivationRequest,
    db: DbSession,
) -> TokenResponse:
    """Activate a user account using an invitation token.

    This endpoint is called when a user clicks the activation link in their
    invitation email. It sets their password and returns authentication tokens.

    **Password requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit

    **Request body:**
    - `token`: The invitation token from the email link
    - `password`: The password to set for the account

    **Returns:**
    - `access_token`: JWT token for API authentication (expires in 1 hour)
    - `refresh_token`: Token to obtain new access tokens (expires in 7 days)
    - `expires_in`: Seconds until access token expiration
    """
    try:
        user, access_token, refresh_token = await activate_account(
            db=db,
            token=request_data.token,
            password=request_data.password,
        )
    except InvitationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    responses={
        200: {"description": "Login successful, tokens returned"},
        401: {"model": ErrorResponse, "description": "Invalid email or password"},
        403: {
            "model": ErrorResponse,
            "description": "Account is suspended or not activated",
        },
    },
)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: DbSession,
) -> TokenResponse:
    """Authenticate a user with email and password.

    Returns JWT tokens for accessing protected endpoints.

    **Request body:**
    - `email`: User's email address
    - `password`: User's password

    **Returns:**
    - `access_token`: JWT token for API authentication (expires in 1 hour)
    - `refresh_token`: Token to obtain new access tokens (expires in 7 days)
    - `token_type`: Always "bearer"
    - `expires_in`: Seconds until access token expiration

    **Usage:**
    Include the access token in the Authorization header:
    ```
    Authorization: Bearer <access_token>
    ```
    """
    ip_address = get_client_ip(request)

    try:
        user, access_token, refresh_token = await authenticate_user(
            db=db,
            email=request_data.email,
            password=request_data.password,
            ip_address=ip_address,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except AccountSuspendedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except AccountNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={
        200: {"description": "Tokens refreshed successfully"},
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    request_data: TokenRefreshRequest,
    db: DbSession,
) -> TokenResponse:
    """Refresh authentication tokens using a refresh token.

    Use this endpoint when the access token has expired.
    The refresh token is rotated (old one invalidated, new one issued).

    **Request body:**
    - `refresh_token`: The refresh token from login or previous refresh

    **Returns:**
    - `access_token`: New JWT access token
    - `refresh_token`: New refresh token (old one is invalidated)
    - `expires_in`: Seconds until access token expiration
    """
    try:
        access_token, refresh_token = await refresh_tokens(
            db=db,
            refresh_token=request_data.refresh_token,
        )
    except TokenServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="Logout current user",
    responses={
        200: {"description": "Logged out successfully"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def logout(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    current_user: CurrentUser,
    db: DbSession,
    refresh_token: str | None = None,
) -> SuccessResponse:
    """Logout the current user by invalidating tokens.

    **Requires authentication.**

    Adds the access token (and optionally refresh token) to a blacklist,
    preventing their future use.

    **Query parameters:**
    - `refresh_token`: (Optional) Also invalidate this refresh token
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    ip_address = get_client_ip(request)

    await logout_user(
        db=db,
        access_token=credentials.credentials,
        refresh_token=refresh_token,
        user_id=current_user.id,
        ip_address=ip_address,
    )

    return SuccessResponse(message="Successfully logged out")


@router.post(
    "/request-reset",
    response_model=SuccessResponse,
    summary="Request password reset email",
    responses={
        200: {"description": "Request processed (always returns success)"},
    },
)
async def request_password_reset(
    request_data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> SuccessResponse:
    """Request a password reset email.

    Sends an email with a password reset link if the account exists.

    **Security note:** This endpoint always returns success to prevent
    email enumeration attacks. The response does not indicate whether
    an account exists with the given email.

    **Request body:**
    - `email`: Email address of the account to reset

    The reset link expires after 24 hours.
    """
    reset_token = await create_password_reset_token(
        db=db,
        email=request_data.email,
    )

    if reset_token:
        # Get user for name
        user = await db.scalar(
            select(User).where(User.email == request_data.email.lower())
        )
        if user:
            background_tasks.add_task(
                send_password_reset_email,
                to=user.email,
                first_name=user.first_name or "User",
                reset_token=reset_token.token,
            )

    return SuccessResponse(
        message="If an account exists with this email, a password reset link has been sent"
    )


@router.post(
    "/reset-password",
    response_model=SuccessResponse,
    summary="Complete password reset",
    responses={
        200: {"description": "Password reset successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid, expired, or already-used reset token",
        },
        422: {"description": "Password does not meet requirements"},
    },
)
async def complete_password_reset(
    request_data: PasswordResetConfirmRequest,
    db: DbSession,
) -> SuccessResponse:
    """Complete a password reset using the reset token.

    This endpoint is called when a user clicks the reset link in their email.

    **Password requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit

    **Request body:**
    - `token`: The reset token from the email link
    - `new_password`: The new password to set
    """
    try:
        await reset_password(
            db=db,
            token=request_data.token,
            new_password=request_data.new_password,
        )
    except TokenServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return SuccessResponse(message="Password has been reset successfully")
