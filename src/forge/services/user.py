"""User service with business logic."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forge.models import AccountState, AuditLog, User, UserRoleAssignment


class UserNotFoundError(Exception):
    """Raised when a user is not found."""

    pass


async def get_user_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
    load_roles: bool = True,
) -> User:
    """Get a user by their ID.

    Args:
        db: Database session.
        user_id: The user's UUID.
        load_roles: Whether to eagerly load roles.

    Returns:
        The User object.

    Raises:
        UserNotFoundError: If user not found.
    """
    query = select(User).where(User.id == user_id)
    if load_roles:
        query = query.options(selectinload(User.roles))

    user = await db.scalar(query)
    if not user:
        raise UserNotFoundError(f"User with id {user_id} not found")

    return user


async def update_user_profile(
    db: AsyncSession,
    user: User,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """Update a user's own profile.

    Args:
        db: Database session.
        user: The user to update.
        first_name: Optional new first name.
        last_name: Optional new last name.

    Returns:
        The updated User object.
    """
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name

    await db.commit()
    await db.refresh(user)

    return user


async def admin_update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> User:
    """Admin update of user details.

    Args:
        db: Database session.
        user_id: ID of user to update.
        admin_user_id: ID of admin making the change.
        first_name: Optional new first name.
        last_name: Optional new last name.
        email: Optional new email.

    Returns:
        The updated User object.

    Raises:
        UserNotFoundError: If user not found.
    """
    user = await get_user_by_id(db, user_id)

    changes = {}
    if first_name is not None and first_name != user.first_name:
        changes["first_name"] = {"old": user.first_name, "new": first_name}
        user.first_name = first_name
    if last_name is not None and last_name != user.last_name:
        changes["last_name"] = {"old": user.last_name, "new": last_name}
        user.last_name = last_name
    if email is not None and email.lower() != user.email:
        changes["email"] = {"old": user.email, "new": email.lower()}
        user.email = email.lower()

    if changes:
        audit_log = AuditLog(
            user_id=admin_user_id,
            action="admin_update_user",
            resource_type="user",
            resource_id=user_id,
            meta_data={"changes": changes},
        )
        db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    return user


async def suspend_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> User:
    """Suspend a user account.

    Args:
        db: Database session.
        user_id: ID of user to suspend.
        admin_user_id: ID of admin performing the action.
        ip_address: Optional IP address for audit.

    Returns:
        The updated User object.

    Raises:
        UserNotFoundError: If user not found.
    """
    user = await get_user_by_id(db, user_id, load_roles=False)

    old_state = user.account_state
    user.account_state = AccountState.SUSPENDED

    audit_log = AuditLog(
        user_id=admin_user_id,
        action="suspend_user",
        resource_type="user",
        resource_id=user_id,
        meta_data={"old_state": old_state.value},
        ip_address=ip_address,
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    return user


async def activate_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    ip_address: str | None = None,
) -> User:
    """Reactivate a suspended user account.

    Args:
        db: Database session.
        user_id: ID of user to activate.
        admin_user_id: ID of admin performing the action.
        ip_address: Optional IP address for audit.

    Returns:
        The updated User object.

    Raises:
        UserNotFoundError: If user not found.
    """
    user = await get_user_by_id(db, user_id, load_roles=False)

    old_state = user.account_state
    user.account_state = AccountState.ACTIVE

    audit_log = AuditLog(
        user_id=admin_user_id,
        action="reactivate_user",
        resource_type="user",
        resource_id=user_id,
        meta_data={"old_state": old_state.value},
        ip_address=ip_address,
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(user)

    return user


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    account_state: AccountState | None = None,
) -> tuple[list[User], int]:
    """List users with pagination.

    Args:
        db: Database session.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        account_state: Optional filter by account state.

    Returns:
        Tuple of (users, total_count).
    """
    query = select(User).options(selectinload(User.roles))

    if account_state:
        query = query.where(User.account_state == account_state)

    # Get total count
    count_query = select(func.count()).select_from(User)
    if account_state:
        count_query = count_query.where(User.account_state == account_state)
    total = await db.scalar(count_query) or 0

    # Get paginated results
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    users = list(result.scalars().all())

    return users, total
