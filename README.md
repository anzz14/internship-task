# Finance Tracker API

A RESTful backend for managing personal financial records — income, expenses, categories, and analytics — built with FastAPI, PostgreSQL, and JWT-based authentication.

**Stack:** FastAPI · PostgreSQL · SQLAlchemy (ORM) · Alembic · JWT · pytest

---

## What it does

- **Auth** — register, login, and refresh JWT access tokens.
- **Transactions** — full CRUD with pagination, date/category/type filters, and role-scoped visibility.
- **Categories** — shared category management (admin-only mutations).
- **Analytics** — summary totals, category breakdown, monthly trends, and recent activity.
- **Users** — admin-only user management with role assignment.
- **RBAC** — three roles (viewer / analyst / admin) with clearly enforced permissions at every endpoint.

---

## Project structure

```
finance_app/
├── main.py                    # FastAPI app, global exception handlers, router registration
├── config.py                  # pydantic-settings config (reads .env or env vars)
├── seed.py                    # Optional: populate DB with sample users, categories, transactions
├── requirements.txt
├── .env.example
├── alembic/                   # Alembic migration scripts
│   └── versions/
└── app/
    ├── database.py            # SQLAlchemy engine + session factory (lru_cache singletons)
    ├── dependencies.py        # Shared FastAPI deps: get_db, get_current_user, require_role
    ├── models/
    │   ├── user.py            # User model + UserRole enum
    │   ├── transaction.py     # Transaction model
    │   └── category.py        # Category model
    ├── schemas/
    │   ├── user.py            # Register / login / response schemas
    │   ├── transaction.py     # Create / update / list / response schemas
    │   ├── analytics.py       # Summary / breakdown / monthly / recent schemas
    │   └── category.py        # Category create / update / response schemas
    ├── routers/
    │   ├── auth.py
    │   ├── transactions.py
    │   ├── categories.py
    │   ├── analytics.py
    │   └── users.py
    ├── services/
    │   ├── auth_service.py
    │   ├── transaction_service.py
    │   ├── analytics_service.py
    │   ├── category_service.py
    │   └── user_service.py
    └── utils/
        ├── hashing.py         # bcrypt helpers (reduced rounds in test env)
        ├── jwt.py             # Token creation and verification
        ├── pagination.py      # Offset + total-pages helpers
        └── sentinel.py        # UNSET sentinel for partial update fields
└── tests/
    ├── conftest.py            # Fixtures: test DB session (rollback pattern), HTTP client, seed helpers
    ├── test_auth.py
    ├── test_transactions.py
    ├── test_analytics.py
    ├── test_users.py
    ├── test_categories.py
    └── test_health.py
```

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd <repo-root>
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r finance_app/requirements.txt
```

### 3. Configure environment

```bash
cp finance_app/.env.example finance_app/.env
# Edit finance_app/.env with your database credentials and secret key
```

### 4. Run migrations

```bash
alembic -c finance_app/alembic.ini upgrade head
```

### 5. Seed sample data (recommended)

```bash
python -m finance_app.seed --password secret123 --show-password
```

This creates three ready-to-use accounts, five categories, and seven sample transactions spread across several months:

| Email | Role | Password |
|---|---|---|
| `viewer@example.com` | viewer | `secret123` |
| `analyst@example.com` | analyst | `secret123` |
| `admin@example.com` | admin | `secret123` |

**Categories created:**

| Name | Type |
|---|---|
| `Salary` | income |
| `Freelance` | income |
| `Food` | expense |
| `Rent` | expense |
| `Utilities` | expense |

**Sample transactions** are spread across January–April 2026 for all three users, so analytics endpoints like `/api/analytics/monthly` and `/api/analytics/by-category` return meaningful data immediately after seeding.

The seed script is idempotent — safe to run multiple times without duplicating data.

### 6. Start the server

```bash
uvicorn finance_app.main:app --reload
```

API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes* | — | Full PostgreSQL connection URL |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | yes* | — | Alternative to DATABASE_URL |
| `DB_HOST` | no | `localhost` | DB host |
| `DB_PORT` | no | `5432` | DB port |
| `SECRET_KEY` | yes | — | JWT signing secret |
| `ALGORITHM` | no | `HS256` | JWT algorithm (HS256 / HS384 / HS512) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `60` | Token lifetime |
| `POOL_SIZE` | no | `5` | SQLAlchemy connection pool size |
| `MAX_OVERFLOW` | no | `10` | Max connections above pool size |

*Provide either `DATABASE_URL` or the three `DB_*` component variables.

---

## Roles & permissions

| Action | Viewer | Analyst | Admin |
|---|---|---|---|
| View own transactions | ✓ | ✓ | ✓ |
| Apply filters (type / category / date) | ✗ (403) | ✓ | ✓ |
| View analytics | ✗ (403) | ✓ (own data) | ✓ (all data) |
| Create / update transactions | ✗ | ✓ (own) | ✓ (any user) |
| Delete transactions | ✗ | ✗ (403) | ✓ |
| Manage categories | ✗ | ✗ | ✓ |
| Manage users | ✗ | ✗ | ✓ |

---

## API endpoints

### Auth
```
POST  /api/auth/register     Register a new account (returns viewer role by default)
POST  /api/auth/login        Obtain a JWT access token
POST  /api/auth/refresh      Refresh token using current token (no body needed)
```

### Transactions
```
GET    /api/transactions              List (paginated; filters blocked for viewer role)
POST   /api/transactions              Create transaction (admin can set target_user_id)
GET    /api/transactions/{id}         Get single transaction (ownership enforced)
PUT    /api/transactions/{id}         Update transaction
DELETE /api/transactions/{id}         Delete transaction [admin only]
```

Query parameters for `GET /api/transactions`:

| Param | Type | Description |
|---|---|---|
| `type` | `income` \| `expense` | Filter by transaction type |
| `category_id` | UUID | Filter by category |
| `date_from` | date (YYYY-MM-DD) | Lower bound on transaction date |
| `date_to` | date (YYYY-MM-DD) | Upper bound on transaction date |
| `page` | int (≥1) | Page number (default: 1) |
| `page_size` | int (1–100) | Results per page (default: 20) |

Viewers who supply any filter parameter receive `403 Forbidden`.

### Analytics (analyst and admin only)
```
GET  /api/analytics/summary       Total income, expenses, balance
GET  /api/analytics/by-category   Spending/income breakdown per category
GET  /api/analytics/monthly       Month-by-month income, expenses, balance
GET  /api/analytics/recent        Last N transactions (query param: limit, default 5, max 100)
```

Admin sees all users' data; analyst sees only their own.

### Categories (read: any authenticated user; write: admin only)
```
GET    /api/categories              List all categories (filter by ?type=income|expense)
GET    /api/categories/{id}         Get a single category
POST   /api/categories              Create category [admin]
PUT    /api/categories/{id}         Update category [admin]
DELETE /api/categories/{id}         Delete category [admin] — blocked if referenced by transactions
```

### Users (admin only)
```
GET    /api/users              List all users
GET    /api/users/{id}         Get user by ID
PUT    /api/users/{id}/role    Update role (viewer / analyst / admin)
DELETE /api/users/{id}         Delete user (cascades their transactions)
```

### Health
```
GET  /health      Application health check
GET  /health/db   Database connectivity check
```

---

## Example requests

### Register
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123", "full_name": "Alice"}'
```
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "alice@example.com",
  "full_name": "Alice",
  "role": "viewer",
  "created_at": "2026-04-04T10:00:00"
}
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}'
```
```json
{ "access_token": "eyJhbGci...", "token_type": "bearer" }
```

### Create a transaction (admin)
```bash
curl -X POST http://localhost:8000/api/transactions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5000,
    "type": "income",
    "category_id": "<uuid>",
    "date": "2026-04-01",
    "notes": "Freelance payment"
  }'
```

### Get analytics summary (analyst or admin)
```bash
curl http://localhost:8000/api/analytics/summary \
  -H "Authorization: Bearer <token>"
```
```json
{
  "total_income": 85000.00,
  "total_expenses": 42300.50,
  "balance": 42699.50,
  "period": "all-time"
}
```

---

## Error responses

| Status | When |
|---|---|
| `401 Unauthorized` | Missing or invalid JWT token |
| `403 Forbidden` | Authenticated but insufficient role |
| `404 Not Found` | Resource does not exist (or is not visible to the caller) |
| `409 Conflict` | Duplicate email on register; duplicate category name+type; deleting a category in use |
| `422 Unprocessable Entity` | Validation failure (negative amount, category type mismatch, etc.) |
| `503 Service Unavailable` | Database unreachable |

All errors return a JSON body with a `detail` field:
```json
{ "detail": "Viewer cannot apply filters to transactions" }
```

---

## Testing the API manually

The fastest way to explore all endpoints is through the Swagger UI at `http://localhost:8000/docs` after starting the server.

1. Run the seed script to create all three role accounts (see step 5 above)
2. Call `POST /api/auth/login` with any seeded email and password to get a token
3. Click **Authorize** at the top of the Swagger UI and paste the token
4. All endpoints are now available to test interactively

To test role restrictions, log in with different accounts — viewer, analyst, and admin each have different access levels clearly enforced at every endpoint.

---

## Running tests

Tests run against the primary database from `finance_app/.env` using a rollback-per-test pattern — no data is left behind after each run.

```bash
# From the repo root
cd finance_app
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing

# Specific file
pytest tests/test_transactions.py -v
```

The test suite covers auth flows, full transaction CRUD, role enforcement (viewer filter blocking, analyst delete blocking), analytics scoping, category conflicts, user management, and health checks.

---

## Design decisions and assumptions

- **Categories are shared across users.** There is no per-user category concept. Admins manage categories via the API.
- **Amount is always stored as a positive `NUMERIC(12,2)`.** The `type` field (`income` / `expense`) determines the sign for analytics calculations.
- **Soft delete is not implemented.** `DELETE` is permanent. User deletion cascades to their transactions.
- **Pagination defaults** to page 1, page_size 20 (max 100).
- **Viewers** have read-only access to their own transactions but cannot apply any filters or access analytics.
- **Analysts** can filter and access analytics (scoped to their own data) but cannot delete transactions.
- **Admins** have full CRUD on all transactions across all users, can create transactions on behalf of any user via `target_user_id`, and see all data in analytics.
- **Authentication** uses JWT Bearer tokens only, no session cookies.
- **bcrypt rounds** are reduced to 4 in the test environment (`APP_ENV=test`) to keep the test suite fast.
- **Database URL** accepts either a single `DATABASE_URL` or component variables (`DB_USER`, `DB_PASSWORD`, `DB_NAME`, etc.) for Docker-compose compatibility. `postgresql://` is automatically normalized to `postgresql+psycopg://` for the psycopg v3 driver.
