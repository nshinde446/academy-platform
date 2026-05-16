# Event Definitions

The Academic Event Bus is the heart of the platform. Every major action generates an event that drives analytics, notifications, and plugin integration.

---

## Event Structure

Every event follows this standard structure:

```json
{
  "event_id": "uuid",
  "event_type": "LECTURE_STARTED",
  "timestamp": "2026-01-15T10:30:00Z",
  "branch_id": "uuid",
  "academic_year_id": "uuid",
  "student_id": "uuid | null",
  "teacher_id": "uuid | null",
  "batch_id": "uuid | null",
  "subject_id": "uuid | null",
  "topic_id": "uuid | null",
  "lecture_id": "uuid | null",
  "test_id": "uuid | null",
  "actor_id": "uuid",
  "metadata": {}
}
```

### Field Descriptions

| Field             | Type        | Required | Description                               |
|-------------------|-------------|----------|-------------------------------------------|
| event_id          | UUID        | Yes      | Unique identifier for this event          |
| event_type        | string      | Yes      | Event type enum (see below)               |
| timestamp         | datetime    | Yes      | When the event occurred                   |
| branch_id         | UUID        | Yes      | Branch where the event occurred           |
| academic_year_id  | UUID        | Yes      | Academic year context                     |
| student_id        | UUID | null | No       | Related student (if applicable)           |
| teacher_id        | UUID | null | No       | Related teacher (if applicable)           |
| batch_id          | UUID | null | No       | Related batch (if applicable)             |
| subject_id        | UUID | null | No       | Related subject (if applicable)           |
| topic_id          | UUID | null | No       | Related topic (if applicable)             |
| lecture_id        | UUID | null | No       | Related lecture (if applicable)           |
| test_id           | UUID | null | No       | Related test (if applicable)              |
| actor_id          | UUID        | Yes      | User who triggered the event              |
| metadata          | JSONB       | No       | Additional event-specific data            |

---

## Event Types

### Lecture Events

| Event Type            | Trigger                          | Key Fields                          |
|-----------------------|----------------------------------|-------------------------------------|
| LECTURE_SCHEDULED     | New lecture created in schedule   | lecture_id, teacher_id, batch_id    |
| LECTURE_STARTED       | Teacher starts a lecture         | lecture_id, teacher_id, actual_start|
| LECTURE_PAUSED        | Lecture paused mid-session       | lecture_id                          |
| LECTURE_RESUMED       | Paused lecture resumed           | lecture_id                          |
| LECTURE_COMPLETED     | Lecture marked as completed      | lecture_id, topics covered          |
| LECTURE_CANCELLED     | Lecture cancelled                | lecture_id, reason                  |
| LECTURE_RESCHEDULED   | Lecture moved to new time/date   | lecture_id, old/new schedule        |

### Attendance Events

| Event Type             | Trigger                          | Key Fields                        |
|------------------------|----------------------------------|-----------------------------------|
| ATTENDANCE_MARKED      | Student attendance recorded      | student_id, lecture_id, status    |
| ATTENDANCE_OVERRIDE    | Manual correction by admin       | student_id, old/new status        |
| PUNCH_LOG_SYNCED       | Biometric device data synced     | device_id, record count           |
| ATTENDANCE_PROCESSED   | Raw punches processed into records| batch processing metadata        |

### Test Events

| Event Type            | Trigger                          | Key Fields                         |
|-----------------------|----------------------------------|------------------------------------|
| TEST_CREATED          | New test defined                 | test_id, subject_id, topics        |
| TEST_UPLOADED         | Test paper uploaded              | test_id, question count            |
| MARKS_UPLOADED        | Student marks entered            | test_id, student count             |
| MARKS_UPDATED         | Individual marks corrected       | test_id, student_id, old/new marks |

### Academic Events

| Event Type            | Trigger                          | Key Fields                         |
|-----------------------|----------------------------------|------------------------------------|
| TOPIC_COMPLETED       | Topic marked as fully covered    | topic_id, subject_id, batch_id     |
| CHAPTER_COMPLETED     | All topics in chapter completed  | chapter_id, subject_id             |
| SYLLABUS_UPDATED      | Syllabus coverage changed        | subject_id, coverage percentage    |

### Student Events

| Event Type            | Trigger                          | Key Fields                         |
|-----------------------|----------------------------------|------------------------------------|
| STUDENT_ENROLLED      | Student added to a batch         | student_id, batch_id               |
| STUDENT_TRANSFERRED   | Student moved between batches    | student_id, old/new batch_id       |
| STUDENT_DEACTIVATED   | Student marked inactive          | student_id, reason                 |

### System Events

| Event Type            | Trigger                          | Key Fields                         |
|-----------------------|----------------------------------|------------------------------------|
| IMPORT_COMPLETED      | Bulk import finished             | entity_type, success/failure count |
| REPORT_GENERATED      | Report created and ready         | report_type, file_url              |

---

## Event Storage

Events are stored in two tables:

- `academic_events` — all raw events.
- `processed_events` — events that have been consumed by analytics/notifications.

---

## Event Processing Rules

- **Idempotency**: Processing the same event twice must produce the same result.
- **Retries**: Failed event processing must be retried with exponential backoff.
- **Deduplication**: Duplicate events (same event_id) must be detected and skipped.
- **Ordering**: Events are ordered by timestamp within a branch context.

---

## Event Consumers

| Consumer       | Purpose                                        |
|----------------|------------------------------------------------|
| Analytics      | Aggregates events into metrics and dashboards  |
| Notifications  | Triggers alerts based on event rules           |
| Plugins        | External systems subscribe to relevant events  |
| Audit          | Records events for compliance and traceability |

---

## Generating Events

Every feature must generate events (Governance Rule 5).

Events are emitted from the **service layer** after successful operations:

```
Service completes business logic
      ↓
Event emitted to Academic Event Bus
      ↓
Consumers process asynchronously
```
