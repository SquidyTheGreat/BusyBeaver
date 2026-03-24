from django.shortcuts import render
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta, date
from tasks.models import Task, ExecutionLog, HealthLog


def analytics_dashboard(request):
    # Overall task counts by status
    status_counts = {
        s: Task.objects.filter(status=s).count()
        for s, _ in Task.STATUS_CHOICES
    }

    # Completed executions in the last 30 days
    since = timezone.now() - timedelta(days=30)
    recent_executions = ExecutionLog.objects.filter(
        status=ExecutionLog.STATUS_COMPLETED,
        created_at__gte=since,
    )

    total_recent = recent_executions.count()
    skipped_recent = ExecutionLog.objects.filter(
        status=ExecutionLog.STATUS_SKIPPED,
        created_at__gte=since,
    ).count()
    cancelled_recent = ExecutionLog.objects.filter(
        status=ExecutionLog.STATUS_CANCELLED,
        created_at__gte=since,
    ).count()
    all_recent = total_recent + skipped_recent + cancelled_recent

    skip_rate = round(skipped_recent / all_recent * 100, 1) if all_recent else 0
    cancel_rate = round(cancelled_recent / all_recent * 100, 1) if all_recent else 0

    # Average delay (late start) across recent completed executions
    delays = [
        ex.delay.total_seconds()
        for ex in recent_executions
        if ex.delay is not None
    ]
    avg_delay_minutes = round(sum(delays) / len(delays) / 60, 1) if delays else 0

    # On-time rate (within 5 min)
    on_time = sum(1 for d in delays if abs(d) <= 300)
    on_time_pct = round(on_time / len(delays) * 100, 1) if delays else 0

    # Per-task stats
    task_stats = []
    for task in Task.objects.all():
        execs = task.executions.filter(status=ExecutionLog.STATUS_COMPLETED, actual_duration__isnull=False)
        count = execs.count()
        if count == 0:
            continue
        avg_sec = sum(e.actual_duration.total_seconds() for e in execs) / count
        task_stats.append({
            'task': task,
            'executions': count,
            'avg_minutes': round(avg_sec / 60, 1),
            'estimated_minutes': task.estimated_minutes,
        })

    task_stats.sort(key=lambda x: -x['executions'])

    # Recent health logs
    recent_health = HealthLog.objects.order_by('-date')[:14]

    return render(request, 'analytics/dashboard.html', {
        'status_counts': status_counts,
        'skip_rate': skip_rate,
        'cancel_rate': cancel_rate,
        'avg_delay_minutes': avg_delay_minutes,
        'on_time_pct': on_time_pct,
        'total_recent': all_recent,
        'task_stats': task_stats[:20],
        'recent_health': recent_health,
    })
