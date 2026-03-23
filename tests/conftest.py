"""Pytest configuration and fixtures for Forge tests."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from forge.core.config import settings
from forge.core.jwt import create_access_token, create_refresh_token
from forge.core.security import hash_password
from forge.db.base import Base
from forge.db.session import get_db
from forge.main import app
from forge.models import AccountState, Invitation, User, UserRole, UserRoleAssignment


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a test database engine using SQLite in-memory."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        password_hash=hash_password("AdminPass123"),
        first_name="Admin",
        last_name="User",
        account_state=AccountState.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRoleAssignment(
        user_id=user.id,
        role=UserRole.ADMIN,
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a regular active user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="user@test.com",
        password_hash=hash_password("UserPass123"),
        first_name="Regular",
        last_name="User",
        account_state=AccountState.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRoleAssignment(
        user_id=user.id,
        role=UserRole.MENTEE,
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def pending_user(db_session: AsyncSession) -> User:
    """Create a pending user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="pending@test.com",
        password_hash=None,
        first_name="Pending",
        last_name="User",
        account_state=AccountState.PENDING,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def suspended_user(db_session: AsyncSession) -> User:
    """Create a suspended user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="suspended@test.com",
        password_hash=hash_password("SuspendedPass123"),
        first_name="Suspended",
        last_name="User",
        account_state=AccountState.SUSPENDED,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def valid_invitation(db_session: AsyncSession, admin_user: User) -> Invitation:
    """Create a valid invitation for testing."""
    invitation = Invitation(
        email="newuser@test.com",
        token="valid-invitation-token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        invited_by=admin_user.id,
        first_name="New",
        last_name="User",
        intended_roles=[UserRole.MENTEE.value],
    )
    db_session.add(invitation)
    await db_session.commit()
    await db_session.refresh(invitation)

    return invitation


@pytest_asyncio.fixture
async def expired_invitation(db_session: AsyncSession, admin_user: User) -> Invitation:
    """Create an expired invitation for testing."""
    invitation = Invitation(
        email="expired@test.com",
        token="expired-invitation-token",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        invited_by=admin_user.id,
    )
    db_session.add(invitation)
    await db_session.commit()
    await db_session.refresh(invitation)

    return invitation


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Generate an access token for the admin user."""
    token, _, _ = create_access_token(admin_user.id)
    return token


@pytest.fixture
def user_token(regular_user: User) -> str:
    """Generate an access token for the regular user."""
    token, _, _ = create_access_token(regular_user.id)
    return token


def auth_header(token: str) -> dict[str, str]:
    """Create authorization header with bearer token."""
    return {"Authorization": f"Bearer {token}"}
