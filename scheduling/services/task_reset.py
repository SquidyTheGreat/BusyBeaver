"""
Periodic task-status reset logic.

reset_stale_tasks() should be called on a schedule (e.g. daily cron or
management command).  It resets tasks to STATUS_PENDING when:

  - status == skipped  AND  it has been ≥ 1 day since the skip
  - status == completed AND  it has been ≥ the task's recurrence interval
    since the completion  (only applies to recurring tasks)

The reference time for "since" is the actual_end of the most recent
matching ExecutionLog; if no log exists the task's updated_at is used.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

_RECURRENCE_DELTAS = {
    'daily':   timedelta(days=1),
    'weekly':  timedelta(weeks=1),
    'monthly': timedelta(days=30),
}


def _last_execution_time(task, status):
    log = (
        task.executions
        .filter(status=status)
        .order_by('-actual_end', '-created_at')
        .first()
    )
    if log:
        return log.actual_end or log.created_at
    return task.updated_at


def reset_stale_tasks():
    """
    Reset stale skipped / completed tasks back to pending.
    Returns a dict with counts: {'skipped': N, 'completed': N}.
    """
    from tasks.models import Task

    now = timezone.now()
    counts = {'skipped': 0, 'completed': 0}

    # ── Skipped tasks ─────────────────────────────────────────────────────────
    for task in Task.objects.filter(status=Task.STATUS_SKIPPED):
        marked_at = _last_execution_time(task, 'skipped')
        if marked_at and (now - marked_at) >= timedelta(days=1):
            task.status = Task.STATUS_PENDING
            task.scheduled_start = None
            task.scheduled_end = None
            task.save(update_fields=['status', 'scheduled_start', 'scheduled_end'])
            counts['skipped'] += 1
            logger.info('Reset skipped task %s (%s) to pending', task.id, task.name)

    # ── Completed tasks (recurring only) ──────────────────────────────────────
    for task in Task.objects.filter(
        status=Task.STATUS_COMPLETED,
    ).exclude(recurrence='none'):
        delta = _RECURRENCE_DELTAS.get(task.recurrence)
        if delta is None:
            continue
        marked_at = _last_execution_time(task, 'completed')
        if marked_at and (now - marked_at) >= delta:
            task.status = Task.STATUS_PENDING
            task.scheduled_start = None
            task.scheduled_end = None
            task.save(update_fields=['status', 'scheduled_start', 'scheduled_end'])
            counts['completed'] += 1
            logger.info(
                'Reset completed task %s (%s) to pending after %s recurrence',
                task.id, task.name, task.recurrence,
            )

    return counts
