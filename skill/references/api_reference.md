# BusyBeaver API Reference

Base URL: `http://localhost:8000` (configurable via `BB_BASE_URL` env var)

All POST endpoints require a `csrfmiddlewaretoken` field matching the `csrftoken` cookie.
Successful writes respond with HTTP 302 → redirect to a detail or list page.

---

## Tasks

### GET `/`
List all tasks. Supports query params:
- `status` — filter by status string (see below)
- `label` — filter by label name

### GET `/tasks/new/`
Render the create-task form.

### POST `/tasks/new/`
Create a task.

| Field | Type | Notes |
|---|---|---|
| `name` | string | required |
| `description` | string | optional |
| `labels` | int[] | Label PKs (multi-value) |
| `estimated_duration` | int | minutes, min 1 |
| `priority` | int | 1=Low 2=Medium 3=High 4=Critical |
| `recurrence` | string | `none` `daily` `weekly` `monthly` |
| `recur_days` | int[] | 0=Mon … 6=Sun, used when recurrence=weekly |
| `recur_time` | HH:MM | optional |

### GET `/tasks/<id>/`
Task detail — executions, move logs, feedback history.

### POST `/tasks/<id>/edit/`
Same fields as create. Partial edits not supported (send all fields).

### POST `/tasks/<id>/delete/`
Delete task. No extra fields beyond CSRF.

### POST `/tasks/<id>/start/`
Transitions task to `in_progress`, creates an open ExecutionLog.

### POST `/tasks/<id>/complete/`
Closes the open ExecutionLog, sets status `completed`. Triggers estimate recalculation and Google Calendar grey-colour update.

### POST `/tasks/<id>/skip/`
Sets status `skipped`, closes any open log.

### POST `/tasks/<id>/cancel/`
Sets status `cancelled`, closes any open log.

**Status values:** `pending` `scheduled` `in_progress` `completed` `skipped` `cancelled`

**Priority values:** `1` (Low) `2` (Medium) `3` (High) `4` (Critical)

---

## Schedule

### GET `/schedule/`
Schedule view for a date. Query param: `target_date=YYYY-MM-DD` (defaults today).

### POST `/schedule/run/`
Run the auto-scheduler.

| Field | Type | Notes |
|---|---|---|
| `target_date` | YYYY-MM-DD | required |

Fills active blocks with pending/scheduled tasks, updates `scheduled_start`/`scheduled_end`, pushes to Google Calendar if connected.

### POST `/schedule/sync/`
Pull changes from Google Calendar. Detects moved events, updates task times, writes TaskMoveLogs.

### GET `/schedule/blocks/`
List all schedule blocks.

### POST `/schedule/blocks/new/`
Create a schedule block.

| Field | Type | Notes |
|---|---|---|
| `name` | string | required |
| `day_of_week` | int | 0=Mon … 6=Sun (recurring); omit for one-off |
| `specific_date` | YYYY-MM-DD | one-off date; omit for recurring |
| `start_time` | HH:MM | required |
| `end_time` | HH:MM | required, must be after start |
| `allowed_labels` | int[] | Label PKs; empty = accept all |
| `is_active` | checkbox | `on` to enable |

### POST `/schedule/blocks/<id>/edit/`
Same fields as create.

### POST `/schedule/blocks/<id>/delete/`
Delete block.

---

## Labels

### GET `/labels/`
List all labels with task counts.

### POST `/labels/new/`
| Field | Type | Notes |
|---|---|---|
| `name` | string | unique |
| `color` | #rrggbb | hex colour |

### POST `/labels/<id>/edit/`
Same fields as create.

### POST `/labels/<id>/delete/`
Delete label.

---

## Health Log

### GET `/health/`
List all health entries (newest first).

### POST `/health/new/`
| Field | Type | Notes |
|---|---|---|
| `date` | YYYY-MM-DD | required |
| `energy_level` | 1-5 | required |
| `mood` | 1-5 | required |
| `stress_level` | 1-5 | required |
| `notes` | string | optional |

---

## Feedback (public, no login required)

### GET `/feedback/<uuid>/`
Feedback form for a task, identified by its `feedback_token`.

### POST `/feedback/<uuid>/`
| Field | Type | Notes |
|---|---|---|
| `difficulty` | 1-5 | required |
| `completed` | checkbox | `on` if completed |
| `notes` | string | optional |
| `actual_start` | YYYY-MM-DDTHH:MM | optional; combined with end creates ExecutionLog |
| `actual_end` | YYYY-MM-DDTHH:MM | optional |

When `actual_start` + `actual_end` are provided, `actual_duration_minutes` is computed automatically and an ExecutionLog is written.

---

## Google Calendar / Auth

### GET `/auth/login/`
Initiates Google OAuth flow. Redirects to Google consent screen.

### GET `/auth/callback/`
OAuth redirect URI. Handled automatically by Google.

### POST `/auth/logout/`
Disconnects Google Calendar (deactivates CalendarIntegration).

### GET `/schedule/calendars/`
Lists writable Google Calendars for the connected account.

### POST `/schedule/calendars/set/`
| Field | Type | Notes |
|---|---|---|
| `calendar_id` | string | Google Calendar ID |
| `calendar_name` | string | Display name |

---

## Analytics

### GET `/analytics/`
HTML dashboard. No parameters. Shows last-30-day stats:
- Total executions, skip rate, cancel rate, on-time %, avg start delay
- Per-task duration accuracy (estimated vs actual)
- Last-14-day health log table
