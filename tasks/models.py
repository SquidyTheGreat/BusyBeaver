import uuid
from datetime import timedelta
from django.db import models


GCAL_COLOR_CHOICES = [
    ('1',  'Lavender'),
    ('2',  'Sage'),
    ('3',  'Grape'),
    ('4',  'Flamingo'),
    ('5',  'Banana'),
    ('6',  'Tangerine'),
    ('7',  'Peacock'),
    ('8',  'Graphite'),
    ('9',  'Blueberry'),
    ('10', 'Basil'),
    ('11', 'Tomato'),
]

GCAL_COLOR_HEX = {
    '1':  '#7986CB',
    '2':  '#33B679',
    '3':  '#8E24AA',
    '4':  '#E67C73',
    '5':  '#F6BF26',
    '6':  '#F4511E',
    '7':  '#039BE5',
    '8':  '#616161',
    '9':  '#3F51B5',
    '10': '#0B8043',
    '11': '#D50000',
}


class Label(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=2, choices=GCAL_COLOR_CHOICES, default='7')

    def __str__(self):
        return self.name

    @property
    def color_hex(self):
        return GCAL_COLOR_HEX.get(self.color, '#039BE5')


class Task(models.Model):
    PRIORITY_LOW = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_HIGH = 3
    PRIORITY_CRITICAL = 4
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    ]

    RECUR_NONE = 'none'
    RECUR_DAILY = 'daily'
    RECUR_WEEKLY = 'weekly'
    RECUR_MONTHLY = 'monthly'
    RECUR_CHOICES = [
        (RECUR_NONE, 'None'),
        (RECUR_DAILY, 'Daily'),
        (RECUR_WEEKLY, 'Weekly'),
        (RECUR_MONTHLY, 'Monthly'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    labels = models.ManyToManyField('Label', blank=True, related_name='tasks')
    estimated_duration = models.DurationField(default=timedelta(hours=1))
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Scheduled slot (filled by auto-scheduler)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    # Recurrence
    recurrence = models.CharField(max_length=10, choices=RECUR_CHOICES, default=RECUR_NONE)
    # List of day numbers (0=Mon … 6=Sun) for weekly recurrence
    recur_days = models.JSONField(default=list, blank=True)
    recur_time = models.TimeField(null=True, blank=True)

    # Google Calendar
    google_event_id = models.CharField(max_length=500, blank=True)

    # Learned scheduling preferences (updated by scheduler based on completion history)
    preferred_days = models.JSONField(default=list, blank=True)
    preferred_start_time = models.TimeField(null=True, blank=True)

    # Unique token used in the feedback form URL embedded in calendar events
    feedback_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name

    def feedback_url(self, base_url=''):
        return f'{base_url}/feedback/{self.feedback_token}/'

    @property
    def estimated_minutes(self):
        return int(self.estimated_duration.total_seconds() // 60)


class ScheduleBlock(models.Model):
    """A recurring or one-off time window during which certain tasks can be scheduled."""
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    name = models.CharField(max_length=100)
    # Recurring: set day_of_week. One-off: set specific_date.
    day_of_week = models.IntegerField(choices=DAY_CHOICES, null=True, blank=True)
    specific_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    # Empty = accept any label
    allowed_labels = models.ManyToManyField('Label', blank=True, related_name='schedule_blocks')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ExecutionLog(models.Model):
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='executions')
    scheduled_start = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    actual_duration = models.DurationField(null=True, blank=True)
    delay = models.DurationField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.actual_start and self.actual_end:
            self.actual_duration = self.actual_end - self.actual_start
        if self.scheduled_start and self.actual_start:
            self.delay = self.actual_start - self.scheduled_start
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.task.name} [{self.status}] {self.created_at:%Y-%m-%d %H:%M}'


class TaskMoveLog(models.Model):
    MOVED_BY_USER = 'user'
    MOVED_BY_CALENDAR = 'google_calendar'
    MOVED_BY_SCHEDULER = 'scheduler'
    MOVED_BY_CHOICES = [
        (MOVED_BY_USER, 'User'),
        (MOVED_BY_CALENDAR, 'Google Calendar'),
        (MOVED_BY_SCHEDULER, 'Scheduler'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='move_logs')
    moved_at = models.DateTimeField(auto_now_add=True)
    from_start = models.DateTimeField()
    to_start = models.DateTimeField()
    reason = models.TextField(blank=True)
    moved_by = models.CharField(max_length=20, choices=MOVED_BY_CHOICES, default=MOVED_BY_USER)

    def __str__(self):
        return f'{self.task.name} moved {self.moved_at:%Y-%m-%d %H:%M}'


class HealthLog(models.Model):
    LEVEL_CHOICES = [(i, str(i)) for i in range(1, 6)]

    date = models.DateField()
    logged_at = models.DateTimeField(auto_now_add=True)
    energy_level = models.IntegerField(choices=LEVEL_CHOICES)
    mood = models.IntegerField(choices=LEVEL_CHOICES)
    stress_level = models.IntegerField(choices=LEVEL_CHOICES)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'Health {self.date} — energy {self.energy_level}, mood {self.mood}, stress {self.stress_level}'


class EventLog(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=300, blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start']

    def __str__(self):
        return f'{self.name} ({self.start:%Y-%m-%d %H:%M})'

    @property
    def duration(self):
        return self.end - self.start


class FeedbackResponse(models.Model):
    DIFFICULTY_CHOICES = [(i, str(i)) for i in range(1, 6)]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='feedback_responses')
    submitted_at = models.DateTimeField(auto_now_add=True)
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES)
    actual_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    completed = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f'Feedback for {self.task.name} at {self.submitted_at:%Y-%m-%d %H:%M}'
