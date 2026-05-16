# Database Conventions

Standards for all database design in the platform.

---

## Naming Convention

All database identifiers use `snake_case`:

- Table names: `student`, `lecture`, `attendance_log`, `student_batch_mapping`
- Column names: `created_at`, `branch_id`, `is_deleted`
- Index names: `ix_{table}_{column}`
- Foreign key names: `fk_{table}_{column}`
- Constraint names: `ck_{table}_{constraint}`

---

## Base Fields

Every table MUST include the following fields:

```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
created_by  UUID REFERENCES users(id)
updated_by  UUID REFERENCES users(id)
status      VARCHAR NOT NULL DEFAULT 'active'
is_deleted  BOOLEAN NOT NULL DEFAULT false
```

- `id`: UUID v4, auto-generated.
- `created_at` / `updated_at`: timestamps with timezone, auto-managed.
- `created_by` / `updated_by`: user references for audit trail.
- `status`: domain-specific status (e.g., `active`, `inactive`, `archived`).
- `is_deleted`: soft delete flag.

---

## Branch Isolation

Every core academic table MUST include:

```sql
branch_id        UUID NOT NULL REFERENCES branch(id)
academic_year_id UUID NOT NULL REFERENCES academic_year(id)
```

- All queries must scope data to the user's authorized branch.
- Backend middleware/service layer enforces branch isolation.
- Super Admin may query across branches.

---

## Soft Delete

Hard deletes are **never allowed** (Governance Rule 7).

- Set `is_deleted = true` instead of `DELETE FROM`.
- All default queries must include `WHERE is_deleted = false`.
- Repository layer applies this filter automatically.
- Soft-deleted records are retained for audit trails, analytics, and potential recovery.

---

## Primary Keys

- All tables use UUID primary keys.
- UUIDs are generated server-side using `gen_random_uuid()`.
- No auto-incrementing integer IDs.

---

## Foreign Keys

- All relationships use explicit foreign key constraints.
- Foreign key columns follow the pattern `{referenced_table}_id`.
- Cascading deletes are NOT used (soft delete only).

---

## Indexes

Required indexes:

- Primary key (automatic).
- All foreign key columns.
- `branch_id` on every branch-scoped table.
- `is_deleted` where frequently filtered.
- `created_at` for time-based queries.
- Composite indexes for common query patterns (e.g., `branch_id + status`).

---

## Migrations

All schema changes require Alembic migrations (Governance Rule 6).

- One migration per logical change.
- Migrations must be reversible (include `downgrade()`).
- Migration files are stored in `backend/migrations/`.
- Never modify a migration that has been applied to a shared environment.

---

## Data Types

| Use Case           | Type                        |
|--------------------|-----------------------------|
| Identifiers        | UUID                        |
| Short text         | VARCHAR(n)                  |
| Long text          | TEXT                        |
| Booleans           | BOOLEAN                     |
| Timestamps         | TIMESTAMP WITH TIME ZONE    |
| Monetary values    | NUMERIC(precision, scale)   |
| JSON/metadata      | JSONB                       |
| Enums              | VARCHAR with CHECK constraint|

---

## Academic Hierarchy Tables

```
institute
 └── branch
      └── academic_year
           └── course
                └── subject
                     └── chapter
                          └── topic
                               └── subtopic
```

Each level references its parent via foreign key, and all include `branch_id` for isolation.

---

## Status Values

Standard status patterns:

- Entities: `active`, `inactive`, `archived`
- Lectures: `scheduled`, `started`, `paused`, `completed`, `cancelled`, `rescheduled`
- Attendance: `present`, `absent`, `late`, `partial`, `excused`, `manual_override`
