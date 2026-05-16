# Coaching Institute Academic Intelligence Platform

## Master Architecture Document

---

## 1. Project Objective

The platform is designed as a **"Modular Academic Operating System"**.

The system must:

- Manage academic operations
- Manage attendance
- Manage lectures
- Manage tests and evaluations
- Analyze academic performance
- Monitor teacher productivity
- Support multi-branch institutes
- Support future AI systems
- Support future plugins
- Scale without architectural rewrites

Future features (without changing core architecture):

- AI Question Bank Hosting
- Live Classes
- Parent Portal
- WhatsApp Notifications
- AI Recommendation Engine
- DPP Generator
- Adaptive Learning
- Mobile Apps
- Fee Management
- AI Tutor

---

## 2. Core Development Principle

### Build Stable Core + Extensible Plugin Layer

The system must NOT be:

- Screen-driven
- Tightly coupled
- Dashboard-first
- Feature-first

Everything revolves around:

```
Student
 ↕
Lecture
 ↕
Topic
 ↕
Attendance
 ↕
Tests
 ↕
Performance
 ↕
Teacher
```

This makes the system: analytics-ready, AI-ready, plugin-ready, and scalable.

---

## 3. Technology Stack

### Backend

- Python FastAPI
- SQLAlchemy 2.0
- AsyncPG
- Alembic

### Frontend

- Next.js (React)
- Tailwind CSS
- shadcn/ui
- React Query
- Zustand

### Database

- PostgreSQL

### Cache & Queues

- Redis (sessions, caching, queues, event buffering)

### Async Jobs

- Celery + Redis

### File Storage

- S3-compatible object storage

### DevOps

- Docker / Docker Compose
- Nginx
- GitHub Actions
- Kubernetes (future)

### Monitoring

- Prometheus
- Grafana
- Flower

### Security

- bandit
- npm audit
- OWASP ZAP / Snyk

---

## 4. System Architecture

```
Frontend Layer
   ├── Admin Portal
   ├── Teacher Portal
   ├── Student Portal
   └── Parent Portal (future)

            ↓

API Gateway Layer

            ↓

Core Backend Platform
   ├── Auth Engine
   ├── Academic Core
   ├── Lecture Engine
   ├── Attendance Engine
   ├── Test Engine
   ├── Analytics Engine
   ├── Reporting Engine
   ├── Notification Engine
   └── Audit Engine

            ↓

Academic Event Bus

            ↓

Plugin Layer
   ├── AI Question Bank
   ├── Live Classes
   ├── DPP Generator
   ├── AI Tutor
   ├── WhatsApp Notifications
   ├── Parent App
   ├── Fee Management
   └── Recommendation Engine

            ↓

Data Layer
   ├── PostgreSQL
   ├── Redis
   ├── File Storage
   └── Analytics Views
```

---

## 5. Monorepo Structure

```
academy-platform/
│
├── backend/
├── frontend/
├── infra/
├── docs/
├── scripts/
├── docker-compose.yml
└── README.md
```

---

## 6. Backend Structure

```
backend/
│
├── app/
│   ├── core/
│   │   ├── config/
│   │   ├── database/
│   │   ├── security/
│   │   ├── middleware/
│   │   ├── logging/
│   │   └── utils/
│   │
│   ├── modules/
│   │   ├── auth/
│   │   ├── students/
│   │   ├── teachers/
│   │   ├── batches/
│   │   ├── classrooms/
│   │   ├── lectures/
│   │   ├── attendance/
│   │   ├── tests/
│   │   ├── analytics/
│   │   ├── reports/
│   │   ├── notifications/
│   │   └── audit/
│   │
│   ├── events/
│   ├── plugins/
│   ├── jobs/
│   └── main.py
│
├── tests/
├── migrations/
└── Dockerfile
```

---

## 7. Module Internal Structure

Every module follows the same structure:

```
module/
│
├── api/
├── services/
├── repositories/
├── models/
├── schemas/
├── validators/
├── permissions/
├── events/
└── tests/
```

---

## 8. Authentication Architecture

### Flow

```
Frontend Login
      ↓
Backend Auth Validation
      ↓
JWT Access Token Generated
      ↓
Refresh Token Generated
      ↓
Stored in HTTP-only secure cookies
```

### Token Strategy

| Token         | Duration |
|---------------|----------|
| Access Token  | 15 mins  |
| Refresh Token | 7 days   |

### Security Rules

Frontend MUST NOT:

- Store refresh tokens
- Validate permissions
- Control RBAC

Backend ALWAYS controls: auth, RBAC, access control.

---

## 9. Role-Based Access Control (RBAC)

### Roles

| Role          | Purpose               |
|---------------|-----------------------|
| Super Admin   | Full platform         |
| Branch Admin  | Branch operations     |
| Academic Head | Analytics & academics |
| Teacher       | Lecture & tests       |
| Student       | Attendance & marks    |
| Parent        | Student monitoring    |

### RBAC Tables

```
users
roles
permissions
user_roles
role_permissions
user_branch_roles
```

---

## 10. Core Academic Data Model

### Academic Hierarchy

```
Institute
 └── Branch
      └── Academic Year
           └── Course
                └── Subject
                     └── Chapter
                          └── Topic
                               └── Subtopic
```

### Student Model

```
Student
 ├── Parent
 ├── Batch History
 ├── Attendance
 ├── Test Results
 ├── Analytics
 └── Activity Timeline
```

### Teacher Model

```
Teacher
 ├── Subject Assignments
 ├── Lecture History
 ├── Productivity Metrics
 ├── Timetable
 └── Analytics
```

### Lecture Model

```
Lecture
 ├── Batch
 ├── Teacher
 ├── Subject
 ├── Topic
 ├── Planned Time
 ├── Actual Time
 ├── Attendance
 ├── Completion Status
 ├── Notes
 └── Events
```

### Test Model

```
Test
 ├── Subject
 ├── Topic Mapping
 ├── Questions
 ├── Marks
 ├── Difficulty Metadata
 └── Analytics
```

---

## 11. Stage-Wise Execution Plan

| Stage | Name                    | Goal                                    |
|-------|-------------------------|-----------------------------------------|
| 0     | Development Governance  | Documentation and standards             |
| 1     | Foundation              | FastAPI + Next.js + DB + Docker + CI/CD |
| 2     | Authentication          | JWT + RBAC + branch isolation            |
| 2.5   | Audit Engine            | Change tracking                         |
| 3     | Core Academic Foundation| Academic graph (students, teachers, etc) |
| 3.3   | Import Engine           | Reusable upload framework               |
| 4     | Lecture Engine          | Scheduling, lifecycle, topic tracking   |
| 5     | Attendance Engine       | Biometric sync, rule engine             |
| 6     | Test Engine             | Tests, marks, question mapping          |
| 7     | Event System            | Academic event bus                      |
| 8     | Analytics Engine        | Aggregations, dashboards, metrics       |
| 8.5   | Reporting Engine        | PDF/Excel export                        |
| 9     | Notification Engine     | Event-driven notifications              |
| 10    | Plugin System           | Plugin registry, extensibility          |
| 11    | AI Layer                | AI intelligence on top of data          |
| 12    | Observability           | Monitoring, alerts, backups             |

---

## 12. Final Architectural Principle

The system must ALWAYS evolve around:

```
Academic Core
     ↓
Events
     ↓
Analytics
     ↓
Plugins
     ↓
AI Intelligence
```

NOT around dashboards, pages, or isolated modules.
