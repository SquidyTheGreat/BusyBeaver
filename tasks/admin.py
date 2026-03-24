from django.contrib import admin
from .models import Label, Task, ScheduleBlock, ExecutionLog, TaskMoveLog, HealthLog, FeedbackResponse


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'color']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'priority', 'status', 'estimated_duration', 'scheduled_start', 'recurrence']
    list_filter = ['status', 'priority', 'recurrence', 'labels']
    search_fields = ['name', 'description']
    filter_horizontal = ['labels']


@admin.register(ScheduleBlock)
class ScheduleBlockAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'day_of_week', 'specific_date', 'start_time', 'end_time', 'is_active']
    filter_horizontal = ['allowed_labels']


@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'status', 'scheduled_start', 'actual_start', 'actual_end', 'actual_duration', 'delay']
    list_filter = ['status']


@admin.register(TaskMoveLog)
class TaskMoveLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'moved_at', 'from_start', 'to_start', 'moved_by']
    list_filter = ['moved_by']


@admin.register(HealthLog)
class HealthLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'date', 'energy_level', 'mood', 'stress_level']


@admin.register(FeedbackResponse)
class FeedbackResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'submitted_at', 'difficulty', 'completed', 'actual_duration_minutes']
