from django.contrib import admin
from .models import CalendarIntegration


@admin.register(CalendarIntegration)
class CalendarIntegrationAdmin(admin.ModelAdmin):
    list_display = ['id', 'calendar_name', 'calendar_id', 'is_active', 'last_synced', 'created_at']
    list_filter = ['is_active']
