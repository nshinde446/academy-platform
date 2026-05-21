# UI / UX Roadmap

Notes for making the dashboard feel like a coaching-institute product
instead of a CRUD scaffold. Tackle in priority order; each tier is
self-contained and shippable.

## Tier 1 — quick branding wins (1-2 hours total)

### Replace "Academy Platform" with real institute name + logo
- Top-left of `components/layout/sidebar.tsx` (the `<span>Navigation</span>` area).
- Drop a logo at `frontend/public/logo.svg`.
- Pattern:
  ```tsx
  <img src="/logo.svg" alt="" className="h-10 w-10" />
  <span className="text-lg font-semibold">Eduworld Coaching</span>
  ```

### Personalized greeting on `/home`
- "Good morning, {firstName} 👋" with date.
- One-liner status: "3 lectures today · 2 tests due this week".
- Sets a friendlier tone than a blank dashboard.

### Pick a single brand accent color
- Right now everything is default neutral.
- Edit `frontend/app/globals.css` (or wherever the Tailwind theme lives).
- Coaching-institute palette suggestions:
  - Deep blue `#1e40af` — trust, academic
  - Dark green `#15803d` — calm, growth
  - Burgundy `#9f1239` — serious, traditional Indian education brand

## Tier 2 — dashboard widgets that matter (4-6 hours)

The `/home` page should answer these in 5 seconds every morning. Build
each as a self-contained card.

| Card | Data source | Notes |
|---|---|---|
| **Today's lectures** | `GET /api/v1/lectures?from=today` | Schedule strip with status (upcoming / in-progress / done) |
| **Today's attendance** | `GET /api/v1/attendance/...` aggregated | "37 / 45 present" + delta vs yesterday |
| **At-risk students** | `GET /api/v1/analytics/batches/{id}/risk-students` | Top 5 by risk score, clickable to student page |
| **Upcoming tests** | `GET /api/v1/tests?status=scheduled` | Next 3, with date + batch + student count |
| **Recent activity** | `GET /api/v1/events` (already exists) | Live feed of attendance marks, lecture status changes |
| **Quick actions** | n/a — just buttons | "+ Add student", "Mark attendance", "Schedule lecture" |

## Tier 3 — broader UX polish (over time)

- **Calendar view** for lectures — `<Calendar>` from shadcn/ui
- **Parent communication log** — last SMS/notification sent per student
- **Empty states with art** — friendlier than "No data"
- **Loading skeletons** instead of blank → content flash
- **Global search in header** — jump to any student/batch by name
- **Print-friendly report cards** — the `infra/monitoring/grafana/dashboards` already has templates that can be adapted
- **Mobile responsiveness pass** — many coaching staff use phones; current breakpoints are desktop-first

## Reusable design vocabulary

Stack already in place:
- Next.js 16 + Tailwind 4
- `@base-ui/react` for dialogs/menus
- `lucide-react` for icons
- React Query for data fetching

Add as needed:
- **shadcn/ui** for prebuilt Card, Badge, Skeleton, Sheet components (copy-paste, no runtime deps)
- **recharts** for charts (Tier 2 metric cards may want trend lines)
- **date-fns** if not already present — for the greeting's date formatting

## What to do first (if you only have 3 hours)

1. **Real institute name + logo** in sidebar header — 30 min
2. **`/home` greeting + 4 metric cards** (today's attendance, lectures, total students, at-risk count) — 2 hours
3. **Global search bar in the top header** for quick student lookup — 30 min

Those three changes alone take the dashboard from "CRUD scaffold" to "looks like a product the coaching director would actually want to log into."
