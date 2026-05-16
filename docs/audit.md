# Audit Engine

The audit engine provides a centralized, low-impact logging system for tracking all data mutations across the platform.

## Table: `audit_logs`

| Column      | Type                     | Notes                              |
|-------------|--------------------------|------------------------------------|
| id          | UUID (PK)                | Auto-generated                     |
| user_id     | UUID (FK → users.id)     | Nullable for system/automated actions |
| action      | VARCHAR(50)              | CREATE, UPDATE, DELETE, IMPORT, OVERRIDE |
| table_name  | VARCHAR(100)             | Target table name                  |
| record_id   | UUID                     | ID of the affected record          |
| old_values  | TEXT (JSON-encoded)      | Previous state (nullable)          |
| new_values  | TEXT (JSON-encoded)      | New state (nullable)               |
| timestamp   | TIMESTAMP WITH TIME ZONE | Auto-set to current time           |
| ip_address  | VARCHAR(45)              | Client IP (nullable)               |
| branch_id   | UUID (FK → branch.id)    | For branch-level filtering (nullable) |

## Usage

### From any service layer

```python
from app.modules.audit.services import audit_service

await audit_service.log_action(
    session,
    user_id=current_user["user_id"],
    action="CREATE",
    table_name="students",
    record_id=student.id,
    new_values={"name": student.name, "email": student.email},
    ip_address=request_ip,
    branch_id=current_user.get("branch_id"),
)
```

### Parameters

- `user_id`: UUID of the acting user, or `None` for system events (e.g., automated imports, cron jobs).
- `action`: One of `CREATE`, `UPDATE`, `DELETE`, `IMPORT`, `OVERRIDE`.
- `table_name`: The database table being modified.
- `record_id`: The UUID of the record being modified.
- `old_values`: Dict of previous field values (for UPDATE/DELETE). Pass `None` for CREATE.
- `new_values`: Dict of new field values (for CREATE/UPDATE). Pass `None` for DELETE.
- `ip_address`: Client IP address from the request.
- `branch_id`: Branch context for branch-level audit filtering.

## API Endpoint

**GET** `/api/v1/audit/logs` — requires `super_admin` role.

Query parameters: `table_name`, `record_id`, `user_id`, `action`, `branch_id`, `offset`, `limit`.

## Design Decisions

- **Separate from BaseModel**: The audit_logs table does NOT inherit BaseModel's soft-delete fields. Audit logs are immutable append-only records.
- **JSON as Text**: Values are stored as JSON-encoded text for SQLite test compatibility. In production (PostgreSQL), consider switching to JSONB columns for query performance.
- **Low-impact**: Audit logging uses `session.flush()` within the same transaction — no extra DB connections or async tasks needed.
- **Manual invocation**: Services call `audit_service.log_action(...)` explicitly. This keeps audit logging visible and intentional rather than hidden behind magic interceptors.
