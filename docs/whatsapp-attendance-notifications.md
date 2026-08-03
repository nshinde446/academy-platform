# WhatsApp attendance notifications (Meta Cloud API)

Send transactional **utility** WhatsApp messages to parents — starting with an
**absent alert** the evening a student is marked absent — straight through
Meta's Cloud API, with no BSP middleman. This doc is the operator runbook; the
code lives in `app/modules/notifications/`.

## Why this shape

- **Cheapest category.** Attendance is a *utility* template (~₹0.115/msg + GST),
  ~7× cheaper than marketing. A daily "absentees-only" send to a 1,000-student
  branch is well under ₹2,000/month.
- **No middleman.** We call `graph.facebook.com` directly, so there's no monthly
  BSP platform fee — you pay Meta per message and nothing else.
- **Built on the existing engine.** The absent sweep already emits a
  `STUDENT_ABSENT` event carrying the parent's mobile. This feature adds the
  provider client, the event→queue consumer, and the queue drainer.

## Delivery path

```
nightly absent sweep ──emit──▶ academic_events (STUDENT_ABSENT)
        │                              │
        │        consume_events()      ▼
        │   ┌──────────────────▶ notification_queue (PENDING)
        │   │                          │
   Celery beat: notifications.process_pipeline (*/5 min)
        │   │                          │  process_queue()
        │   └──────────────────────────┘
        ▼                              ▼
  (idempotent via processed_events)   Meta Cloud API  ──▶ parent's WhatsApp
```

`notifications.process_pipeline` runs both steps against one session:
`consume_events()` then `process_queue()`. It is registered in
`app/core/jobs/celery_app.py` and scheduled every 5 minutes, but the actual send
is gated (see below), so scheduling it is safe before go-live.

## The safety gate

Everything ships **dormant behind `WHATSAPP_ENABLED` (default `false`)**, the
same pattern as `BIOMAX_PROVISIONING_ENABLED`. While it's off:

- `send_notification` returns `SKIP` for WHATSAPP rows — they stay `PENDING` and
  **no Meta request is made and no charge is incurred**.
- Flip the flag on (with a valid token) and the next drain flushes the backlog.

## Configuration (`.env`)

```env
WHATSAPP_ENABLED=true
WHATSAPP_ACCESS_TOKEN=<permanent System User token>
WHATSAPP_PHONE_NUMBER_ID=<from Meta > WhatsApp > API Setup>
WHATSAPP_API_VERSION=v21.0            # optional; pinned default
```

## One-time Meta setup (operator)

1. **Meta Business + app.** Create a Meta Business account, verify the business,
   add the **WhatsApp** product to a Meta app.
2. **Phone number.** Register the academy's sending number; note its
   **Phone Number ID** (not the number itself).
3. **Permanent token.** Create a **System User** with a permanent access token
   scoped to `whatsapp_business_messaging` — a temporary token expires in 24h.
4. **Approve a template** (category **Utility**). Example body — placeholders are
   positional `{{1}}`, `{{2}}`:

   > Namaste, this is an attendance update from *{{academy}}*. Your ward
   > *{{1}}* was marked **ABSENT** on *{{2}}*. Please contact us if this is
   > unexpected.

   Approval usually lands within a few hours.

## Wiring the template in the platform

A WHATSAPP `NotificationTemplate` must carry the Meta-approved name + language.
The template's free-text `body_template` **defines the parameter order**: its
`{placeholders}`, in appearance order, fill the Meta template's `{{1}}, {{2}}, …`
Keep the two in the same order.

```http
POST /api/v1/notifications/templates
{
  "name": "absent_alert_whatsapp",
  "event_type": "STUDENT_ABSENT",
  "channel": "WHATSAPP",
  "body_template": "{student_name} was absent on {attendance_date}.",
  "provider_template_name": "attendance_absent_alert",
  "provider_language": "en",
  "is_active": true,
  "branch_id": "<branch uuid or null for all branches>"
}
```

Here `{student_name}` → `{{1}}` and `{attendance_date}` → `{{2}}`, both pulled
from the `STUDENT_ABSENT` event metadata.

## Recipient handling

`normalize_recipient` reduces `parent_mobile` to the digits-only, country-code
form Meta wants (bare 10-digit Indian numbers get `91` prefixed; a leading trunk
`0` is dropped). Unusable numbers fail that row permanently (no retry burn)
rather than being sent malformed.

## Failure semantics

- **Permanent** (bad number, unknown template, auth/permission, any 4xx except
  429): marked `FAILED` immediately — retrying can't help.
- **Transient** (5xx, 429, network): `mark_failed` increments `retry_count`; the
  next drain retries until `max_retries`, then `FAILED`.
- Inspect delivery via `GET /api/v1/notifications/queue?delivery_status=FAILED`.

## Go-live checklist

- [ ] Meta business verified, template **approved**.
- [ ] `.env` has token + phone-number id; `WHATSAPP_ENABLED=true`.
- [ ] WHATSAPP `NotificationTemplate` created for `STUDENT_ABSENT`.
- [ ] Celery worker running **with beat** (`-B`) so the pipeline fires — note the
      worker currently runs without beat in prod (see the attendance-status
      memory); enabling beat also arms the nightly sweep, which is the intended
      producer here.
- [ ] Parent mobiles populated and consented (utility templates to your own
      enrolled families; honour opt-outs).

## Not yet built (deferred)

- **Daily digest to *all* parents** (present + absent). The consumer/sender are
  channel-generic; this needs only a new daily emission for every active student
  plus its own approved "daily status" template — drops in as a second event.
- **Per-parent opt-out flag** and a frontend template-management UI.
- **Delivery-status webhooks** (read receipts) — we currently record only the
  send outcome and the returned `wamid`.
