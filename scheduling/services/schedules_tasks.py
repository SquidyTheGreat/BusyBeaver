from datetime import datetime, timedelta, time
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ScheduleTask:

    @staticmethod
    @transaction.atomic
    def create_schedule(pending_tasks, schedule_blocks, target_date):
        """
        Fill schedule blocks for target_date with pending tasks.

        Algorithm:
        1. Find blocks applicable to target_date (by day_of_week or specific_date).
        2. For each block, filter tasks whose labels intersect the block's allowed_labels
           (or all tasks if the block has no label restrictions).
        3. Sort eligible tasks by priority descending, then place them sequentially
           into the block until it is full.
        4. Update task.scheduled_start / scheduled_end / status on each placed task.

        Returns a dict with 'scheduled', 'unscheduled', and counts.
        """
        from tasks.models import Task

        day_of_week = target_date.weekday()

        applicable_blocks = [
            b for b in schedule_blocks
            if b.is_active and (
                b.day_of_week == day_of_week or b.specific_date == target_date
            )
        ]

        # Sort tasks: highest priority first; break ties by shortest duration (more tasks fit)
        sorted_tasks = sorted(pending_tasks, key=lambda t: (-t.priority, t.estimated_duration))

        scheduled_ids = set()
        scheduled = []
        result_details = []

        for block in applicable_blocks:
            block_start = datetime.combine(target_date, block.start_time, tzinfo=timezone.utc)
            block_end = datetime.combine(target_date, block.end_time, tzinfo=timezone.utc)
            cursor = block_start

            block_label_ids = set(block.allowed_labels.values_list('id', flat=True))

            for task in sorted_tasks:
                if task.id in scheduled_ids:
                    continue

                # Label check: if block restricts labels, task must share at least one
                if block_label_ids:
                    task_label_ids = set(task.labels.values_list('id', flat=True))
                    if not (task_label_ids & block_label_ids):
                        continue

                task_end = cursor + task.estimated_duration
                if task_end > block_end:
                    continue  # doesn't fit remaining time in this block

                task.scheduled_start = cursor
                task.scheduled_end = task_end
                task.status = Task.STATUS_SCHEDULED
                task.save(update_fields=['scheduled_start', 'scheduled_end', 'status'])

                scheduled_ids.add(task.id)
                scheduled.append(task)
                result_details.append({
                    'task_id': task.id,
                    'task_name': task.name,
                    'block': block.name,
                    'start': cursor.isoformat(),
                    'end': task_end.isoformat(),
                })
                cursor = task_end
                logger.info('Scheduled "%s" in block "%s" %s–%s', task.name, block.name, cursor, task_end)

        unscheduled = [t for t in pending_tasks if t.id not in scheduled_ids]

        logger.info(
            'Schedule run for %s: %d scheduled, %d unscheduled',
            target_date, len(scheduled), len(unscheduled),
        )
        return {
            'scheduled': scheduled,
            'unscheduled': unscheduled,
            'details': result_details,
            'scheduled_count': len(scheduled),
            'unscheduled_count': len(unscheduled),
            'total': len(pending_tasks),
        }

    @staticmethod
    def update_task_estimates():
        """
        Re-derive estimated_duration, preferred_days, and preferred_start_time
        for every task that has at least 2 completed executions.

        Uses a linearly weighted average so recent executions carry more weight.
        """
        from tasks.models import Task, ExecutionLog

        updated = 0
        for task in Task.objects.all():
            executions = list(
                task.executions
                .filter(status=ExecutionLog.STATUS_COMPLETED, actual_duration__isnull=False)
                .order_by('created_at')
            )
            if len(executions) < 2:
                continue

            # Weighted average duration (weight = position index + 1)
            total_weight = 0
            weighted_seconds = 0.0
            for i, ex in enumerate(executions):
                w = i + 1
                weighted_seconds += ex.actual_duration.total_seconds() * w
                total_weight += w
            new_estimate = timedelta(seconds=weighted_seconds / total_weight)
            task.estimated_duration = new_estimate

            # Preferred days and start time from successful starts
            day_counts: dict = {}
            hour_counts: dict = {}
            for ex in executions:
                if ex.actual_start:
                    d = ex.actual_start.weekday()
                    h = ex.actual_start.hour
                    day_counts[d] = day_counts.get(d, 0) + 1
                    hour_counts[h] = hour_counts.get(h, 0) + 1

            if day_counts:
                task.preferred_days = sorted(day_counts, key=day_counts.get, reverse=True)[:3]
            if hour_counts:
                best_hour = max(hour_counts, key=hour_counts.get)
                task.preferred_start_time = time(best_hour, 0)

            task.save(update_fields=['estimated_duration', 'preferred_days', 'preferred_start_time'])
            updated += 1

        logger.info('Updated estimates for %d tasks', updated)
        return updated
