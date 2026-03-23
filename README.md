# Forge - KamiLimu Learning System

Forge is the backend API for the KamiLimu mentorship programme management system. It provides a comprehensive REST API for managing mentees, sessions, attendance, and programme operations.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Creating the System Administrator](#creating-the-system-administrator)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [User Management](#user-management)
- [Development](#development)
- [Testing](#testing)

## Features

- **Invitation-based Registration**: Secure user onboarding through email invitations
- **JWT Authentication**: Token-based authentication with access and refresh tokens
- **Role-based Access Control**: Fine-grained permissions based on user roles
- **Audit Logging**: Track all significant actions for accountability
- **Email Notifications**: Automated emails for invitations and password resets

## Requirements

- Python 3.11+
- PostgreSQL 14+ (or Supabase)
- (Optional) Resend account for email delivery

## Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd forge
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   # Install production dependencies
   pip install -e .

   # Install development dependencies (for testing and linting)
   pip install -e ".[dev]"
   ```

## Configuration

1. **Copy the example environment file**

   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your settings**

   ```bash
   # Required settings to configure:

   # Database connection (PostgreSQL)
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/forge

   # IMPORTANT: Generate a secure secret key for production
   # Use: openssl rand -hex 32
   SECRET_KEY=your-secure-secret-key-here

   # Frontend URL for email links
   FRONTEND_URL=https://your-frontend-domain.com

   # Email service (optional but recommended for production)
   RESEND_API_KEY=re_your_api_key_here
   EMAIL_FROM_ADDRESS=noreply@yourdomain.com
   ```

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT signing key (use `openssl rand -hex 32`) | Required for production |
| `FRONTEND_URL` | Base URL for email links | `http://localhost:3000` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | `http://localhost:3000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `INVITATION_TOKEN_EXPIRE_DAYS` | Invitation link validity | `7` |
| `RESEND_API_KEY` | Resend API key for emails | Optional |
| `EMAIL_FROM_ADDRESS` | Sender email address | `noreply@kamilimu.org` |

## Database Setup

1. **Create the database**

   ```bash
   # Using psql
   createdb forge

   # Or connect to PostgreSQL and run:
   # CREATE DATABASE forge;
   ```

2. **Run database migrations**

   ```bash
   alembic upgrade head
   ```

   This creates all required tables:
   - `users` - User accounts
   - `user_roles` - Role assignments
   - `invitations` - User invitations
   - `token_blacklist` - Revoked JWT tokens
   - `password_reset_tokens` - Password reset requests
   - `audit_logs` - Action audit trail
   - `cohorts` - Programme cohorts (Phase 2)

## Creating the System Administrator

The first admin user must be created using the CLI tool. This admin can then invite other users through the API.

### Using the CLI

```bash
# Interactive mode (recommended - prompts for password)
forge-cli create-admin \
  --email admin@kamilimu.org \
  --first-name Admin \
  --last-name User

# Non-interactive mode (for scripting)
forge-cli create-admin \
  --email admin@kamilimu.org \
  --first-name Admin \
  --last-name User \
  --password "YourSecurePassword123"
```

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

### Alternative: Direct Database Insert

For automated deployments, you can also create the admin via SQL:

```sql
-- Generate password hash using Python first:
-- python -c "from forge.core.security import hash_password; print(hash_password('YourPassword123'))"

INSERT INTO users (id, email, password_hash, first_name, last_name, account_state, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'admin@kamilimu.org',
  '$2b$12$...hashed_password_here...',
  'Admin',
  'User',
  'active',
  NOW(),
  NOW()
);

-- Get the user ID and assign admin role
INSERT INTO user_roles (id, user_id, role, assigned_at)
SELECT gen_random_uuid(), id, 'admin', NOW()
FROM users WHERE email = 'admin@kamilimu.org';
```

## Running the Application

### Development

```bash
# Start the development server with auto-reload
uvicorn forge.main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Using uvicorn directly
uvicorn forge.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or with gunicorn
gunicorn forge.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Docker

```dockerfile
# Example Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["uvicorn", "forge.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## API Documentation

Once the application is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

## User Management

### How Users are Created

Forge uses an **invitation-based system**. Users cannot self-register.

1. **Admin invites a user** via `POST /api/v1/auth/invite`
2. **User receives email** with an activation link
3. **User activates account** by setting their password at `POST /api/v1/auth/activate`
4. **User can now log in** via `POST /api/v1/auth/login`

### Inviting Users (Admin Only)

```bash
# Single user invitation
curl -X POST http://localhost:8000/api/v1/auth/invite \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mentee@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "roles": ["mentee"],
    "cohort_id": "optional-cohort-uuid"
  }'

# Bulk invitation (for onboarding a cohort)
curl -X POST http://localhost:8000/api/v1/auth/bulk-invite \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "users": [
      {"email": "user1@example.com", "first_name": "User", "last_name": "One", "roles": ["mentee"]},
      {"email": "user2@example.com", "first_name": "User", "last_name": "Two", "roles": ["mentee"]}
    ],
    "cohort_id": "optional-cohort-uuid"
  }'
```

### User Roles

| Role | Description |
|------|-------------|
| `admin` | Full system access, can manage all users and settings |
| `committee` | Programme management and oversight |
| `mentee` | Programme participant |
| `peer_mentor_1:1` | One-on-one peer mentor (KamiLimu alumni) |
| `peer_mentor_ict` | ICT track peer mentor |
| `professional_mentor` | Session facilitator |
| `partner` | Programme partner/sponsor |
| `alumni` | Graduated mentee |

### Authentication Flow

```
1. Login
   POST /api/v1/auth/login
   Body: {"email": "user@example.com", "password": "password"}
   Response: {"access_token": "...", "refresh_token": "...", "expires_in": 3600}

2. Use access token in requests
   Authorization: Bearer <access_token>

3. When access token expires, refresh it
   POST /api/v1/auth/refresh
   Body: {"refresh_token": "..."}
   Response: {"access_token": "...", "refresh_token": "...", "expires_in": 3600}

4. Logout (invalidates tokens)
   POST /api/v1/auth/logout
   Authorization: Bearer <access_token>
```

## Development

### Project Structure

```
forge/
   alembic/                 # Database migrations
      versions/            # Migration files
   src/forge/
      api/
         deps.py          # Dependency injection
         routes/          # API endpoints
      core/
         config.py        # Settings
         jwt.py           # Token utilities
         security.py      # Password hashing
      db/
         base.py          # SQLAlchemy base
         session.py       # Database session
      models/              # SQLAlchemy models
      schemas/             # Pydantic schemas
      services/            # Business logic
      cli.py               # CLI commands
      main.py              # Application entry
   tests/
      unit/                # Unit tests
      integration/         # Integration tests
   .env.example             # Environment template
   alembic.ini              # Alembic config
   pyproject.toml           # Project config
```

### Code Quality

```bash
# Run linter
ruff check src tests

# Run formatter
ruff format src tests

# Run type checker
mypy src
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=forge --cov-report=html

# Run specific test file
pytest tests/unit/test_security.py

# Run specific test
pytest tests/integration/test_auth_endpoints.py::TestLogin::test_login_success
```

### Test Database

Tests use an in-memory SQLite database by default. For integration tests against PostgreSQL:

```bash
# Set test database URL
export TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/forge_test

# Run tests
pytest
```

## License

Proprietary - KamiLimu

## Support

For issues and questions, contact support@kamilimu.org
