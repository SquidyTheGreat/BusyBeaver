from tasks.models import Task, ScheduleBlock
from django.db import transaction

class ScheduleTask:

    @staticmethod
    @transaction.atomic
    def create_schedule(tasks, available_time_blocks):
        # Organize tasks by priority then add by descending duration
        # Respect time > priority
        return None