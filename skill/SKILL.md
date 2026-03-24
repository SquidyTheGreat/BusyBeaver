---
name: busybeaver
description: Task and schedule management via the local BusyBeaver app. Use when: (1) Creating, editing, or querying tasks, (2) Running the auto-scheduler for a date, (3) Logging health entries, (4) Checking analytics or execution history, (5) Managing schedule blocks or labels, (6) Syncing or interacting with Google Calendar tasks.
---

# BusyBeaver

## Overview

BusyBeaver is a local Django app (default: `http://localhost:8000`) that tracks tasks, auto-schedules them into time blocks, syncs with Google Calendar, and analyses execution patterns over time.

Use `scripts/bb.py` to interact with it from the command line. All write operations (POST) are handled automatically — CSRF tokens are fetched per request.

## Quick Start

```bash
# List all pending tasks
python skill/scripts/bb.py tasks

# Create a task
python skill/scripts/bb.py create-task --name "Write report" --duration 60 --priority 3

# Run the auto-scheduler for today
python skill/scripts/bb.py schedule

# Run the auto-scheduler for a specific date
python skill/scripts/bb.py schedule --date 2026-03-25

# Mark a task started / completed
python skill/scripts/bb.py start 7
python skill/scripts/bb.py complete 7

# Log a health entry
python skill/scripts/bb.py health --energy 4 --mood 3 --stress 2
```

## Core Operations

### Tasks
- **List** — `bb.py tasks [--status pending|scheduled|in_progress|completed|skipped|cancelled]`
- **Create** — `bb.py create-task --name TEXT --duration MINUTES [--priority 1-4] [--description TEXT]`
- **Lifecycle** — `bb.py start|complete|skip|cancel TASK_ID`

### Schedule
- **Run scheduler** — `bb.py schedule [--date YYYY-MM-DD]`
  Fills active schedule blocks with pending/scheduled tasks by priority. Pushes results to Google Calendar if connected.
- **Sync from calendar** — `bb.py sync`
  Pulls moves detected in Google Calendar and writes TaskMoveLogs.

### Health
- **Log entry** — `bb.py health --energy 1-5 --mood 1-5 --stress 1-5 [--notes TEXT] [--date YYYY-MM-DD]`

### Analytics
Open `http://localhost:8000/analytics/` for the dashboard (skip rate, cancel rate, avg delay, on-time %, per-task accuracy, health history).

## References

See `references/api_reference.md` for the full URL layout, field names, and expected form data for every endpoint.
