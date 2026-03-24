# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations after model changes
python3 manage.py makemigrations
python3 manage.py migrate

# Run dev server
python3 manage.py runserver

# Run all tests
python3 manage.py test

# Run tests for a specific app
python3 manage.py test tasks
python3 manage.py test scheduling
python3 manage.py test analytics

# Run a specific test class
python3 manage.py test tasks.tests.MyTestCase
```

Docker (recommended — includes PostgreSQL):
```bash
docker-compose up --build
docker-compose exec web python3 manage.py makemigrations
docker-compose exec web python3 manage.py migrate
docker-compose exec web python3 manage.py test
```

## Environment

Copy `.env.example` → `.env` and set values. Required for Google Calendar: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. Everything else has defaults for local dev.

## Architecture

Django 6.0.3 + PostgreSQL. Three apps:

**`tasks/`** — Core domain models and all user-facing views:
- `Label` — colored tags for tasks
- `Task` — name, description, labels (M2M), `estimated_duration` (DurationField), priority, status, recurrence fields, `scheduled_start/end`, `google_event_id`, `feedback_token` (UUID), and learned `preferred_days`/`preferred_start_time`
- `ScheduleBlock` — recurring time windows (day_of_week or specific_date + start/end time, optional label restrictions)
- `ExecutionLog` — one row per task run; auto-calculates `actual_duration` and `delay` on save
- `TaskMoveLog` — written whenever a task's scheduled time changes (by user, scheduler, or calendar sync)
- `HealthLog` — daily energy/mood/stress ratings
- `FeedbackResponse` — submitted through a tokenized public URL embedded in calendar events

**`scheduling/`** — Auto-scheduler, schedule block management, and Google Calendar OAuth:
- `CalendarIntegration` model — stores OAuth tokens and the chosen calendar ID
- `auth_views.py` + `auth_urls.py` — Google OAuth flow (login → callback → calendar selection)
- `services/schedules_tasks.py` — `ScheduleTask.create_schedule(tasks, blocks, date)` fills blocks with priority-sorted tasks; `update_task_estimates()` recalculates duration estimates and preferred times from completed execution history
- `services/google_calendar.py` — push events, detect calendar-side moves (`sync_from_calendar`), refresh tokens, attach feedback URL to event descriptions

**`analytics/`** — Single dashboard view (`analytics/views.py`) aggregating skip rate, cancellation rate, avg delay, on-time %, and per-task duration accuracy over the last 30 days.

**URL layout:**
```
/                       → task list
/tasks/new/             → create task
/tasks/<id>/            → task detail + history
/tasks/<id>/edit/       → edit task
/tasks/<id>/start|complete|skip|cancel/  → lifecycle POST actions
/health/                → health log list
/health/new/            → log entry
/feedback/<uuid>/       → public feedback form (no login needed)
/schedule/              → schedule view for a date
/schedule/blocks/       → schedule block management
/schedule/run/          → POST: run auto-scheduler for a date
/schedule/sync/         → POST: pull calendar changes + detect moves
/schedule/calendars/    → list/select Google Calendar
/auth/login|callback|logout/  → Google OAuth
/analytics/             → analytics dashboard
```

**Feedback flow:** Every `Task` has a `feedback_token` (UUID). When `create_or_update_event` pushes a task to Google Calendar it appends `{BASE_URL}/feedback/{token}/` to the event description. That URL is publicly accessible and writes a `FeedbackResponse`. After ≥2 completions, `update_task_estimates()` recalculates `estimated_duration`, `preferred_days`, and `preferred_start_time` on the task using a linearly weighted average (more recent = higher weight).

**Duration field:** Tasks store `estimated_duration` as `DurationField` (timedelta). Forms use `DurationMinutesField` in `tasks/forms.py` which accepts an integer number of minutes. Use `task.estimated_minutes` for display.

**Settings note:** `INSTALLED_APPS` already includes `tasks`, `scheduling`, and `analytics`. Project-level templates live in `templates/` (registered in `TEMPLATES[0]['DIRS']`).
