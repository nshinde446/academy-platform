# Testing Rules

Standards for all testing in the platform.

---

## Testing Pyramid

All modules must follow the testing pyramid:

```
        ╱ E2E Tests ╲         ← Few, high-value user flows
       ╱─────────────╲
      ╱ Integration    ╲      ← API + DB + repository tests
     ╱─────────────────╲
    ╱   Unit Tests       ╲    ← Services, validators, business rules
   ╱─────────────────────╲
```

- **Unit tests** form the base: fast, isolated, numerous.
- **Integration tests** in the middle: verify components work together.
- **E2E tests** at the top: validate complete user workflows.

---

## Unit Tests

**What to test:**

- Service layer business logic
- Validators and custom validation rules
- Business rule enforcement
- Utility functions
- Event generation logic

**Characteristics:**

- No database or external service calls.
- Use mocks/stubs for dependencies.
- Fast execution (milliseconds per test).
- Every service method has at least one test.

---

## Integration Tests

**What to test:**

- API endpoints (request/response contracts)
- Repository layer (actual database queries)
- Database interactions (CRUD operations, constraints)
- Authentication and authorization flows
- Branch isolation enforcement

**Characteristics:**

- Use a real test database (PostgreSQL).
- Test against actual API routes via `httpx` async client.
- Verify correct HTTP status codes and response schemas.
- Test error cases (validation errors, 404s, permission denials).

---

## E2E Tests

**What to test:**

- Complete user workflows across frontend and backend.
- Critical paths: login, student creation, lecture scheduling, attendance marking.
- Cross-module flows: lecture → attendance → analytics.

**Characteristics:**

- Run against a fully deployed stack (frontend + backend + database).
- Use Playwright for browser automation.
- Focus on golden-path scenarios and critical edge cases.

---

## Tools

| Layer       | Tool       | Purpose                          |
|-------------|------------|----------------------------------|
| Backend     | pytest     | Unit and integration test runner |
| API Testing | httpx      | Async HTTP client for API tests  |
| Frontend    | Vitest     | Component and logic tests        |
| E2E         | Playwright | Browser-based end-to-end tests   |

---

## Backend Test Structure

Tests live within each module and in the top-level `tests/` directory:

```
backend/
├── app/
│   └── modules/
│       └── students/
│           └── tests/          ← Module-specific tests
│               ├── test_services.py
│               ├── test_repositories.py
│               └── test_api.py
└── tests/                      ← Cross-module and integration tests
    ├── conftest.py
    ├── integration/
    └── e2e/
```

---

## Test Requirements

- Every module must have automated tests (Governance Rule 6 from architecture).
- Tests must pass before code is merged (enforced via CI/CD).
- New features require tests covering both success and error paths.
- Bug fixes require a regression test that reproduces the bug.

---

## Test Database

- Integration tests use a separate PostgreSQL database.
- Database is created fresh for each test session.
- Migrations are applied before tests run.
- Each test runs in a transaction that is rolled back after completion.

---

## CI/CD Integration

Tests run automatically in the pipeline:

```
Code Push
   ↓
Lint
   ↓
Security Scan
   ↓
Unit Tests
   ↓
Integration Tests
   ↓
Build
   ↓
Deploy
```

All test stages must pass for deployment to proceed.
