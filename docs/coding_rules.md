# Development Governance Rules

These rules are **MANDATORY** for all development on the Coaching Institute Academic Intelligence Platform.

---

## Rule 1 — Frontend Never Owns Authentication

Frontend NEVER owns authentication logic.

- All authentication is handled by the backend Auth Engine.
- Frontend only sends credentials and receives tokens.
- Login, logout, token refresh — all server-side operations.

---

## Rule 2 — Frontend Never Validates Permissions

Frontend NEVER validates permissions.

Backend ALWAYS validates:

- **Authentication** — is the user who they claim to be?
- **Authorization** — is the user allowed to perform this action?
- **RBAC** — does the user's role grant access to this resource?

Frontend may hide UI elements for UX purposes, but the backend is the single source of truth for access control.

---

## Rule 3 — No Direct DB Access from API Routes

API routes must NEVER directly access the database.

Correct flow:

```
Route (API layer)
 ↓
Service (business logic)
 ↓
Repository (data access)
 ↓
Database
```

- **Route**: receives HTTP request, validates input schema, delegates to service.
- **Service**: contains business logic, orchestrates repositories, emits events.
- **Repository**: executes database queries via SQLAlchemy, returns model objects.

---

## Rule 4 — Mandatory Module Structure

Every module must contain the following layers:

| Layer          | Purpose                              |
|----------------|--------------------------------------|
| `api/`         | FastAPI route definitions            |
| `services/`    | Business logic                       |
| `repositories/`| Data access (SQLAlchemy queries)     |
| `models/`      | SQLAlchemy ORM models                |
| `schemas/`     | Pydantic request/response schemas    |
| `validators/`  | Custom validation logic              |
| `permissions/` | Role/permission checks for this module|
| `tests/`       | Unit and integration tests           |

No module may skip any of these layers.

---

## Rule 5 — All Features Must Generate Events

Every feature MUST generate academic events.

- Lectures generate `LECTURE_STARTED`, `LECTURE_COMPLETED`, etc.
- Attendance generates `ATTENDANCE_MARKED`.
- Tests generate `TEST_UPLOADED`, `MARKS_UPDATED`.
- Topic tracking generates `TOPIC_COMPLETED`.

Events are the foundation for analytics, notifications, and plugin integration.

---

## Rule 6 — All DB Changes Require Migrations

All database schema changes require Alembic migrations.

- No manual SQL execution against the database.
- Every table creation, column addition, index change, or constraint modification must be an Alembic migration.
- Migrations must be reviewed and tested before deployment.

---

## Rule 7 — No Hard Deletes

No hard deletes are allowed anywhere in the system.

Use soft delete:

```python
is_deleted = True
```

- All queries must filter out soft-deleted records by default.
- Soft-deleted records remain available for audit trails and analytics.
- Only authorized maintenance operations may permanently purge data.

---

## Rule 8 — Plugin Isolation

Plugins NEVER directly access the core database.

Plugins interact with the platform ONLY via:

- **APIs** — consuming core platform REST endpoints.
- **Events** — subscribing to the Academic Event Bus.

This ensures:

- Core schema can evolve without breaking plugins.
- Plugins cannot corrupt core data.
- Plugins can be added or removed without affecting the core system.

---

## Rule 9 — Predefined Standards Only

Claude Code implements predefined standards ONLY.

Claude NEVER invents:

- **Architecture** — follow the monorepo structure and module layout defined in the blueprint.
- **Naming conventions** — use `snake_case` for database, follow existing patterns for code.
- **DB patterns** — use the standard base fields, soft delete, and branch isolation defined in the blueprint.
- **Auth flow** — use JWT + HTTP-only cookies as specified, no alternative auth mechanisms.

All implementation decisions must trace back to the architecture blueprint or execution blueprint.
