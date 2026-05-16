# API Conventions

Standards for all RESTful API endpoints in the platform.

---

## URL Structure

All API endpoints follow this pattern:

```
/api/v{version}/{module}/{resource}
```

Examples:

```
GET    /api/v1/students
GET    /api/v1/students/{id}
POST   /api/v1/students
PUT    /api/v1/students/{id}
DELETE /api/v1/students/{id}
```

---

## Versioning

- All APIs are versioned with a `v1`, `v2`, etc. prefix.
- Version is part of the URL path, not a header.
- Breaking changes require a new version. Non-breaking additions (new optional fields, new endpoints) do not.
- Deprecated versions must be maintained until all consumers migrate.

---

## HTTP Methods

| Method | Purpose                  | Idempotent |
|--------|--------------------------|------------|
| GET    | Retrieve resource(s)     | Yes        |
| POST   | Create a new resource    | No         |
| PUT    | Full update of a resource| Yes        |
| PATCH  | Partial update           | Yes        |
| DELETE | Soft delete a resource   | Yes        |

---

## Request Format

- Content-Type: `application/json`
- All request bodies use Pydantic schemas for validation.
- Path parameters for resource identification (`{id}`).
- Query parameters for filtering, pagination, and sorting.

### Pagination

```
GET /api/v1/students?page=1&page_size=20&sort_by=created_at&sort_order=desc
```

Standard query parameters:

| Parameter   | Type   | Default | Description              |
|-------------|--------|---------|--------------------------|
| page        | int    | 1       | Page number              |
| page_size   | int    | 20      | Items per page (max 100) |
| sort_by     | string | created_at | Sort field            |
| sort_order  | string | desc    | `asc` or `desc`          |

### Filtering

Use query parameters matching field names:

```
GET /api/v1/students?branch_id=uuid&status=active
```

---

## Response Format

### Success — Single Resource

```json
{
  "data": {
    "id": "uuid",
    "name": "John Doe",
    "status": "active",
    "created_at": "2026-01-15T10:30:00Z"
  }
}
```

### Success — Collection

```json
{
  "data": [
    { "id": "uuid", "name": "John Doe" }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8
  }
}
```

### Success — Create

- HTTP 201 Created
- Returns the created resource in `data`.

### Success — Delete (Soft)

- HTTP 200 OK
- Returns confirmation message.

---

## Error Responses

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

### Standard Error Codes

| HTTP Status | Error Code            | When                                  |
|-------------|-----------------------|---------------------------------------|
| 400         | VALIDATION_ERROR      | Request body/params fail validation   |
| 401         | UNAUTHORIZED          | Missing or expired token              |
| 403         | FORBIDDEN             | Valid token but insufficient permissions |
| 404         | NOT_FOUND             | Resource does not exist or is soft-deleted |
| 409         | CONFLICT              | Duplicate entry or state conflict     |
| 422         | UNPROCESSABLE_ENTITY  | Valid syntax but semantic errors      |
| 429         | RATE_LIMITED          | Too many requests                     |
| 500         | INTERNAL_ERROR        | Unexpected server error               |

---

## Authentication

- All endpoints (except login/register) require a valid JWT access token.
- Token is sent via HTTP-only secure cookie (set by backend on login).
- Backend validates the token and extracts user context on every request.
- Expired tokens return 401; frontend must call the refresh endpoint.

---

## Branch Isolation

- Most endpoints require `branch_id` context.
- Backend enforces that users can only access data within their authorized branches.
- Super Admin can access all branches.

---

## Naming Conventions

- URL paths: `snake_case` (e.g., `/api/v1/student_marks`)
- JSON fields: `snake_case` (e.g., `created_at`, `branch_id`)
- Consistent with database column naming.

---

## Development Flow

1. Define the API contract (endpoint, request schema, response schema, error cases).
2. Create Pydantic schemas.
3. Implement the route in the `api/` layer.
4. Route delegates to the `services/` layer for business logic.
5. Service delegates to the `repositories/` layer for data access.
6. Write tests covering success and error scenarios.
