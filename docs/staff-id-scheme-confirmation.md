# Staff Employee-Code Scheme — Client Confirmation Needed

**Status:** awaiting client sign-off
**Owner:** Nitin
**Module:** Staff Attendance (`backend/app/modules/staff`, migrations 0057 / 0060)

The Staff Attendance module is built and live. One decision from the original
requirement (*Staff_Attendance_Module_Requirement.pdf*, Section 2–3) was made
on technical grounds and now needs the client's explicit confirmation, because
it changes the employee-code numbers staff will see.

## The point to confirm

The requirement asked for six departments with small, contiguous code ranges:

| Department | Requested range (client PDF) |
|---|---|
| MSA-Teachers | 1 – 50 |
| MSA-Administration | 51 – 70 |
| MSA-Accounts | 71 – 80 |
| Security | 81 – 90 |
| Cleaning Unit | 91 – 100 |
| MSA-Marketing | 101 – 110 |

**We shipped a different numbering** — a per-department block in the 9xxxx
range instead:

| Department | Shipped range | Example codes |
|---|---|---|
| MSA-Teachers | 91000 – 91999 | 91001, 91002, … |
| MSA-Administration | 92000 – 92999 | 92001, … |
| MSA-Accounts | 93000 – 93999 | 93001, … |
| Security | 94000 – 94999 | 94001, … |
| Cleaning Unit | 95000 – 95999 | 95001, … |
| MSA-Marketing | 96000 – 96999 | 96001, … |

The scheme (predictable, non-overlapping, one reserved block per department,
2nd digit = department) is exactly what the client wanted — **only the numbers
are higher.**

## Why we diverged

Staff and students punch on the **same** BioMax terminals. On each punch the
device only reports a `userId`. Our ingestion matches that id **first against a
student** (`Student.rfid_number`), and **only if unmatched, against a staff
member** (`Staff.emp_code`) — see
`backend/app/modules/attendance/integrations/biomax/service.py`. The two id
namespaces therefore **must not overlap**: if a staff code equalled an existing
student device id, that staff member's punches would silently be recorded
against the student.

Student device ids already occupy the low numbers. Putting staff at 1–110 would
sit squarely inside that space and risk collisions. The 9xxxx block keeps staff
codes clearly out of the student range while preserving the reserved,
department-blocked structure the client asked for.

## What this means for existing staff (requirement Section 3)

The client's current list uses sequential ids 1–53 that don't line up with any
department range. Those come in as **legacy codes**: kept as-is and flagged
(`Staff.is_legacy_code = true`), so history is preserved. New joiners are
allocated from their department's 9xxxx block going forward. No existing person
is renumbered unless the client asks for it.

## Options for the client

1. **Confirm the 9xxxx scheme (recommended).** No code change. Staff codes read
   as 91001, 92001, etc. This is what is live today.
2. **Insist on the exact 1–110 numbers.** Possible, but it re-introduces the
   collision risk above; before doing it we would need to confirm no student
   device id falls in 1–110 (very likely some do), and would probably have to
   renumber those students. Higher risk, more migration work.

## Ask

Please confirm **Option 1 (9xxxx per-department blocks)** so we can close this
item, or tell us if the client specifically needs the literal 1–110 numbers —
in which case we'll scope the student-id reconciliation first.
