from django.contrib import admin

# Register your models here.
from .models import Task, ExecutionLog, ScheduleBlock
TaskAdmin = admin.ModelAdmin(list_display=['id', 'title', 'estimated_duration', 'priority'])
ExecutionLogAdmin = admin.ModelAdmin(list_display=['id', 'task_id', 'scheduled_start', 'actual_start', 'actual_end', 'skipped'])
ScheduleBlockAdmin = admin.ModelAdmin(list_display=['id', 'start_time', 'end_time'])