# Plugin Guidelines

Standards for how plugins interact with the core platform.

---

## Core Principle

Plugins NEVER directly modify the core database (Governance Rule 8).

Plugins interact with the platform exclusively through:

- **APIs** — consuming core platform REST endpoints.
- **Events** — subscribing to the Academic Event Bus.

---

## Plugin Architecture

```
Plugin
 ├── Event Subscriber     ← Listens to academic events
 ├── API Consumer         ← Calls core platform APIs
 ├── Config Layer         ← Plugin-specific configuration
 └── Optional UI          ← Frontend components (if needed)
```

---

## Plugin Registration

Plugins are registered in the plugin system tables:

### Tables

```
plugins               — Plugin registry
plugin_config         — Plugin-specific settings
plugin_events         — Events the plugin subscribes to
plugin_dependencies   — Dependencies between plugins
```

### Plugin Config Fields

| Field          | Type    | Description                          |
|----------------|---------|--------------------------------------|
| plugin_name    | string  | Unique identifier for the plugin     |
| version        | string  | Semantic version (e.g., 1.0.0)       |
| enabled        | boolean | Whether the plugin is active         |
| dependencies   | JSONB   | List of required plugins/services    |
| configuration  | JSONB   | Plugin-specific settings             |

---

## How Plugins Consume APIs

Plugins call core platform REST endpoints just like any other client:

1. Plugin authenticates via service account or API key.
2. Plugin makes standard HTTP requests to `/api/v1/{resource}`.
3. Plugin receives standard JSON responses.
4. Plugin must handle errors, rate limits, and pagination.

Plugins do NOT:

- Import core models or repositories.
- Execute raw SQL against the core database.
- Bypass authentication or authorization.

---

## How Plugins Consume Events

Plugins subscribe to specific event types from the Academic Event Bus:

1. Plugin registers its event subscriptions in `plugin_events`.
2. When a matching event is emitted, the plugin receives it.
3. Plugin processes the event asynchronously.
4. Plugin must handle idempotency and retries.

Example: A WhatsApp notification plugin subscribes to `ATTENDANCE_MARKED` events and sends alerts to parents when a student is absent.

---

## Plugin Isolation

Each plugin:

- Has its own database schema (if it needs storage) — separate from core tables.
- Cannot read or write core tables directly.
- Can be enabled/disabled without affecting core functionality.
- Can be added or removed without schema migrations on core tables.

---

## Future Plugin Examples

| Plugin           | API Dependencies         | Event Subscriptions                    |
|------------------|--------------------------|----------------------------------------|
| Live Classes     | Lecture APIs             | LECTURE_SCHEDULED, LECTURE_STARTED      |
| AI Question Bank | Test Engine APIs         | TEST_CREATED                           |
| Parent App       | Student APIs, Analytics  | ATTENDANCE_MARKED, MARKS_UPDATED       |
| WhatsApp Engine  | Notification APIs        | All notification-triggering events     |
| AI Tutor         | Student APIs, Analytics  | MARKS_UPDATED, TOPIC_COMPLETED         |
| Fee Management   | Student APIs             | STUDENT_ENROLLED, STUDENT_DEACTIVATED  |
| DPP Generator    | Test Engine, Topic APIs  | TOPIC_COMPLETED, LECTURE_COMPLETED     |
| Adaptive Testing | Test Engine, Analytics   | MARKS_UPDATED, TEST_CREATED            |

---

## Plugin Development Rules

1. Follow all 9 governance rules.
2. Use only public APIs — no internal service imports.
3. Subscribe to events — do not poll the database.
4. Handle failures gracefully — plugins must not crash the core system.
5. Version your plugin — follow semantic versioning.
6. Document API and event dependencies.
7. Include tests for your plugin.

---

## Live Class Plugin Example

Demonstrates how a future plugin integrates without modifying the core:

```
Lecture Scheduled (core event)
      ↓
Live Class Plugin receives LECTURE_SCHEDULED event
      ↓
Plugin checks delivery_mode via Lecture API
      ↓
If online/hybrid → Plugin generates meeting link
      ↓
Plugin stores link in its own schema
      ↓
Plugin exposes link via its own API
      ↓
Attendance synced back via core Attendance API
      ↓
Recording stored in plugin's own storage
```

The core Lecture Engine never knows about meeting links or recordings — it just schedules lectures and emits events.
