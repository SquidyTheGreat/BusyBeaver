"""
Management command: run the auto-scheduler for today and push results to
Google Calendar (if a CalendarIntegration is active).
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the auto-scheduler for today and push to Google Calendar.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            default=None,
            help='Target date in YYYY-MM-DD format (default: today)',
        )

    def handle(self, *args, **options):
        from scheduling.models import CalendarIntegration
        from scheduling.services.google_calendar import create_or_update_event
        from scheduling.services.schedules_tasks import ScheduleTask
        from tasks.models import ScheduleBlock, Task

        target_str = options.get('date')
        if target_str:
            from datetime import datetime as dt
            target = dt.strptime(target_str, '%Y-%m-%d').date()
        else:
            target = date.today()

        pending = list(
            Task.objects.filter(
                status__in=[Task.STATUS_PENDING, Task.STATUS_SCHEDULED]
            ).prefetch_related('labels')
        )
        blocks = list(
            ScheduleBlock.objects.filter(is_active=True).prefetch_related('allowed_labels')
        )

        result = ScheduleTask.create_schedule(pending, blocks, target)
        self.stdout.write(
            f'Scheduled {result["scheduled_count"]} tasks, '
            f'{result["unscheduled_count"]} could not be placed.'
        )

        integration = CalendarIntegration.objects.filter(is_active=True).first()
        if integration:
            for task in result['scheduled']:
                try:
                    create_or_update_event(task, integration)
                except Exception as exc:
                    logger.warning('Calendar push failed for task %s: %s', task.id, exc)
                    self.stderr.write(f'Calendar push failed for "{task.name}": {exc}')
            self.stdout.write(self.style.SUCCESS('Calendar sync complete.'))
        else:
            self.stdout.write('No active CalendarIntegration — skipping calendar push.')
