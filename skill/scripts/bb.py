#!/usr/bin/env python3
"""
BusyBeaver CLI helper.

Interacts with the local BusyBeaver Django app via HTTP.
CSRF tokens are fetched automatically per session.

Usage:
  python bb.py tasks [--status STATUS]
  python bb.py create-task --name TEXT --duration MINUTES [--priority 1-4] [--description TEXT] [--labels ID ...]
  python bb.py start TASK_ID
  python bb.py complete TASK_ID
  python bb.py skip TASK_ID
  python bb.py cancel TASK_ID
  python bb.py schedule [--date YYYY-MM-DD]
  python bb.py sync
  python bb.py health --energy N --mood N --stress N [--notes TEXT] [--date YYYY-MM-DD]
  python bb.py labels
"""

import argparse
import os
import re
import sys
from datetime import date
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    sys.exit("requests is required: pip install requests")

BASE_URL = os.getenv("BB_BASE_URL", "http://localhost:8000")
session = requests.Session()


# ── Helpers ──────────────────────────────────────────────────────────────────

def url(path):
    return urljoin(BASE_URL, path)


def csrf():
    """Return a fresh CSRF token, fetching the home page if needed."""
    if "csrftoken" not in session.cookies:
        session.get(url("/"), timeout=10)
    return session.cookies["csrftoken"]


def post(path, data=None, **kwargs):
    payload = dict(data or {})
    payload["csrfmiddlewaretoken"] = csrf()
    r = session.post(url(path), data=payload, allow_redirects=True, timeout=10, **kwargs)
    return r


def get(path, **kwargs):
    return session.get(url(path), timeout=10, **kwargs)


def ok(r, action):
    """Print success/failure based on final URL after redirects."""
    if r.status_code == 200:
        print(f"OK  {action}  →  {r.url}")
    else:
        print(f"ERR {action}  HTTP {r.status_code}", file=sys.stderr)
        sys.exit(1)


def scrape_table_rows(html, header_pattern):
    """Very simple regex scrape — good enough for CLI output."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    results = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
        cleaned = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if cleaned:
            results.append(cleaned)
    return results


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_tasks(args):
    params = {}
    if args.status:
        params["status"] = args.status
    r = get("/", params=params)
    # Pull task rows from the list page
    rows = scrape_table_rows(r.text, "task")
    if not rows:
        print("(no tasks found or could not parse page)")
        return
    for row in rows[1:]:   # skip header row
        print("  ".join(row))


def cmd_create_task(args):
    data = {
        "name": args.name,
        "description": args.description or "",
        "estimated_duration": args.duration,
        "priority": args.priority,
        "recurrence": "none",
    }
    if args.labels:
        data["labels"] = args.labels   # list; requests sends multiple values
    r = post("/tasks/new/", data)
    ok(r, f"create-task '{args.name}'")


def cmd_lifecycle(args):
    action = args.command   # start | complete | skip | cancel
    r = post(f"/tasks/{args.task_id}/{action}/")
    ok(r, f"{action} task {args.task_id}")


def cmd_schedule(args):
    target = args.date or date.today().isoformat()
    r = post("/schedule/run/", {"target_date": target})
    ok(r, f"schedule {target}")


def cmd_sync(args):
    r = post("/schedule/sync/")
    ok(r, "sync calendar")


def cmd_health(args):
    data = {
        "date": args.date or date.today().isoformat(),
        "energy_level": args.energy,
        "mood": args.mood,
        "stress_level": args.stress,
        "notes": args.notes or "",
    }
    r = post("/health/new/", data)
    ok(r, "log health")


def cmd_labels(args):
    r = get("/labels/")
    rows = scrape_table_rows(r.text, "label")
    for row in rows[1:]:
        print("  ".join(row))


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(description="BusyBeaver CLI helper")
    sub = p.add_subparsers(dest="command", required=True)

    # tasks
    t = sub.add_parser("tasks", help="List tasks")
    t.add_argument("--status", help="Filter by status")

    # create-task
    c = sub.add_parser("create-task", help="Create a new task")
    c.add_argument("--name", required=True)
    c.add_argument("--duration", required=True, type=int, help="Estimated duration in minutes")
    c.add_argument("--priority", type=int, default=2, choices=[1, 2, 3, 4])
    c.add_argument("--description", default="")
    c.add_argument("--labels", nargs="*", type=int, metavar="ID")

    # lifecycle actions
    for action in ("start", "complete", "skip", "cancel"):
        a = sub.add_parser(action, help=f"Mark task as {action}ed")
        a.add_argument("task_id", type=int)

    # schedule
    s = sub.add_parser("schedule", help="Run the auto-scheduler")
    s.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")

    # sync
    sub.add_parser("sync", help="Sync moves from Google Calendar")

    # health
    h = sub.add_parser("health", help="Log a health entry")
    h.add_argument("--energy", required=True, type=int, choices=range(1, 6), metavar="1-5")
    h.add_argument("--mood",   required=True, type=int, choices=range(1, 6), metavar="1-5")
    h.add_argument("--stress", required=True, type=int, choices=range(1, 6), metavar="1-5")
    h.add_argument("--notes", default="")
    h.add_argument("--date", help="YYYY-MM-DD (default: today)")

    # labels
    sub.add_parser("labels", help="List labels")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "tasks":       cmd_tasks,
        "create-task": cmd_create_task,
        "start":       cmd_lifecycle,
        "complete":    cmd_lifecycle,
        "skip":        cmd_lifecycle,
        "cancel":      cmd_lifecycle,
        "schedule":    cmd_schedule,
        "sync":        cmd_sync,
        "health":      cmd_health,
        "labels":      cmd_labels,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
