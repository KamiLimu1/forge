"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from forge.api.routes import auth, users
from forge.core.config import settings
from forge.db.session import engine

DESCRIPTION = """
## Forge - KamiLimu Learning System API

Forge is the backend API for the KamiLimu mentorship programme management system.
It provides endpoints for authentication, user management, and programme operations.

### Key Features

* **Invitation-based Registration**: Users are invited by administrators and activate
  their accounts via email links
* **JWT Authentication**: Secure token-based authentication with access and refresh tokens
* **Role-based Access Control**: Fine-grained permissions based on user roles
* **Audit Logging**: All significant actions are logged for accountability

### Authentication Flow

1. Admin invites user via `/auth/invite` endpoint
2. User receives email with activation link
3. User activates account at `/auth/activate` with password
4. User logs in at `/auth/login` to receive tokens
5. Access token is used in `Authorization: Bearer <token>` header
6. Refresh token is used at `/auth/refresh` when access token expires

### User Roles

- **admin**: Full system access
- **committee**: Programme management and oversight
- **mentee**: Programme participant
- **peer_mentor_1:1**: One-on-one peer mentor
- **peer_mentor_ict**: ICT track peer mentor
- **professional_mentor**: Session facilitator
- **partner**: Programme partner/sponsor
- **alumni**: Graduated mentee
"""

TAGS_METADATA = [
    {
        "name": "Authentication",
        "description": "User authentication operations including login, logout, "
        "token refresh, password reset, and account activation.",
    },
    {
        "name": "Users",
        "description": "User profile and management operations. Regular users can "
        "view and update their own profiles. Admins can manage all users.",
    },
    {
        "name": "Health",
        "description": "Health check endpoints for monitoring.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle application startup and shutdown events."""
    yield
    await engine.dispose()


def custom_openapi(app: FastAPI) -> dict:
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description=DESCRIPTION,
        routes=app.routes,
        tags=TAGS_METADATA,
    )

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT access token",
        }
    }

    # Add contact and license info
    openapi_schema["info"]["contact"] = {
        "name": "KamiLimu Support",
        "email": "support@kamilimu.org",
    }
    openapi_schema["info"]["license"] = {
        "name": "Proprietary",
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=DESCRIPTION,
        version="0.1.0",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
        openapi_tags=TAGS_METADATA,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(users.router, prefix=settings.API_V1_PREFIX)

    # Use custom OpenAPI schema
    app.openapi = lambda: custom_openapi(app)

    return app


app = create_application()


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Check if the API is running and healthy.

    Returns a simple status message indicating the API is operational.
    This endpoint does not require authentication.
    """
    return {"status": "healthy"}


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint providing basic API information.

    Returns a welcome message and the API version. This endpoint is public and does not require authentication.
    """
    return {"message": "Welcome to the KamiLimu Learning System API. Check the documentation for more information at api/v1/docs.", "version": "0.1.0"}
