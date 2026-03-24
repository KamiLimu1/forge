"""User management API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from forge.api.deps import ActiveUser, AdminUser, DbSession
from forge.models import AccountState
from forge.schemas import (
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserUpdateRequest,
    ErrorResponse,
    PaginatedResponse,
    SuccessResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserRoleResponse,
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

router = APIRouter(tags=["Users"])


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get(
    "/users/me",
    response_model=UserProfileResponse,
)
async def get_current_user_profile(
    current_user: ActiveUser,
) -> UserProfileResponse:
    """Get the current user's profile."""
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        account_state=current_user.account_state,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
        roles=[
            UserRoleResponse(
                id=role.id,
                role=role.role,
                cohort_id=role.cohort_id,
                assigned_at=role.assigned_at,
            )
            for role in current_user.roles
        ],
    )


@router.patch(
    "/users/me",
    response_model=UserProfileResponse,
)
async def update_current_user_profile(
    request_data: UserProfileUpdateRequest,
    current_user: ActiveUser,
    db: DbSession,
) -> UserProfileResponse:
    """Update the current user's profile."""
    updated_user = await update_user_profile(
        db=db,
        user=current_user,
        first_name=request_data.first_name,
        last_name=request_data.last_name,
    )

    return UserProfileResponse(
        id=updated_user.id,
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        account_state=updated_user.account_state,
        last_login_at=updated_user.last_login_at,
        created_at=updated_user.created_at,
        roles=[
            UserRoleResponse(
                id=role.id,
                role=role.role,
                cohort_id=role.cohort_id,
                assigned_at=role.assigned_at,
            )
            for role in updated_user.roles
        ],
    )


@router.get(
    "/admin/users",
    response_model=PaginatedResponse[AdminUserListResponse],
    responses={403: {"model": ErrorResponse}},
)
async def list_all_users(
    current_user: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_state: AccountState | None = None,
) -> PaginatedResponse[AdminUserListResponse]:
    """List all users (Admin only)."""
    users, total = await list_users(
        db=db,
        page=page,
        page_size=page_size,
        account_state=account_state,
    )

    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=[
            AdminUserListResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                account_state=user.account_state,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
            )
            for user in users
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/admin/users/{user_id}",
    response_model=AdminUserDetailResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_user_details(
    user_id: UUID,
    current_user: AdminUser,
    db: DbSession,
) -> AdminUserDetailResponse:
    """Get detailed user information (Admin only)."""
    try:
        user = await get_user_by_id(db, user_id)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        account_state=user.account_state,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[
            UserRoleResponse(
                id=role.id,
                role=role.role,
                cohort_id=role.cohort_id,
                assigned_at=role.assigned_at,
            )
            for role in user.roles
        ],
    )


@router.patch(
    "/admin/users/{user_id}",
    response_model=AdminUserDetailResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def admin_update_user_details(
    user_id: UUID,
    request_data: AdminUserUpdateRequest,
    current_user: AdminUser,
    db: DbSession,
) -> AdminUserDetailResponse:
    """Update a user's details (Admin only)."""
    try:
        user = await admin_update_user(
            db=db,
            user_id=user_id,
            admin_user_id=current_user.id,
            first_name=request_data.first_name,
            last_name=request_data.last_name,
            email=request_data.email,
        )
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    # Reload to get roles
    user = await get_user_by_id(db, user_id)

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        account_state=user.account_state,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[
            UserRoleResponse(
                id=role.id,
                role=role.role,
                cohort_id=role.cohort_id,
                assigned_at=role.assigned_at,
            )
            for role in user.roles
        ],
    )


@router.post(
    "/admin/users/{user_id}/suspend",
    response_model=SuccessResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def suspend_user_account(
    user_id: UUID,
    request: Request,
    current_user: AdminUser,
    db: DbSession,
) -> SuccessResponse:
    """Suspend a user account (Admin only)."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own account",
        )

    ip_address = get_client_ip(request)

    try:
        await suspend_user(
            db=db,
            user_id=user_id,
            admin_user_id=current_user.id,
            ip_address=ip_address,
        )
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return SuccessResponse(message="User account has been suspended")


@router.post(
    "/admin/users/{user_id}/activate",
    response_model=SuccessResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def reactivate_user_account(
    user_id: UUID,
    request: Request,
    current_user: AdminUser,
    db: DbSession,
) -> SuccessResponse:
    """Reactivate a suspended user account (Admin only)."""
    ip_address = get_client_ip(request)

    try:
        await activate_user(
            db=db,
            user_id=user_id,
            admin_user_id=current_user.id,
            ip_address=ip_address,
        )
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return SuccessResponse(message="User account has been reactivated")
