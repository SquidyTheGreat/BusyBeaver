from django.core.management.base import BaseCommand

from scheduling.services.task_reset import reset_stale_tasks


class Command(BaseCommand):
    help = 'Reset skipped/completed tasks to pending based on elapsed time.'

    def handle(self, *args, **options):
        counts = reset_stale_tasks()
        self.stdout.write(
            self.style.SUCCESS(
                f"Reset {counts['skipped']} skipped and {counts['completed']} completed tasks to pending."
            )
        )
