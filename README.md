# BusyBeaver
A smart task tracking tool for busy beavers (with ADD)

## What It Is
A Django 6.0.3 + PostgreSQL personal task scheduler that integrates with Google Calendar. It automatically schedules tasks into available time blocks, tracks execution history, and learns from past completions to improve time estimates and scheduling preferences.

## How to Run (Docker)
```bash
docker-compose up --build
docker-compose exec web python3 manage.py makemigrations
docker-compose exec web python3 manage.py migrate
```
Copy `.env.example` → `.env` and set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` for Calendar integration.

## Apps

### `tasks/`
Core domain. Models: `Task` (with labels, duration estimates, recurrence, Google Calendar link, feedback token), `Label`, `ScheduleBlock` (recurring time windows), `ExecutionLog` (tracks actual duration/delay), `TaskMoveLog`, `HealthLog`, `FeedbackResponse`. All user-facing views live here.

### `scheduling/`
Auto-scheduler and Google Calendar sync. Fills schedule blocks with priority-sorted tasks (`ScheduleTask.create_schedule`), recalculates duration estimates from history (`update_task_estimates`), handles OAuth flow and bi-directional calendar sync (push events, detect moves, refresh tokens, attach feedback URLs).

### `analytics/`
Single dashboard view. Aggregates metrics over the last 30 days: skip rate, cancellation rate, avg delay, on-time %, and per-task duration accuracy.

## Todo
 - Remove google calendar event on task deletion
 - Fix scheduling so that it respects task duration
 - Make labels color coded on google calender
 - Visualize schedule blocks
 - Add required days or times to certain tasks
 - Add health metrics to feedback form