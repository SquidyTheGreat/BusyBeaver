from django.db import models


class CalendarIntegration(models.Model):
    """Stores Google Calendar OAuth tokens and the chosen calendar."""
    calendar_id = models.CharField(max_length=500)
    calendar_name = models.CharField(max_length=200)
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True)
    token_expiry = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.calendar_name} ({self.calendar_id})'
