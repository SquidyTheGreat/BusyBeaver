from datetime import timedelta, date
from django import forms
from .models import Task, ScheduleBlock, HealthLog, FeedbackResponse, Label


class DurationMinutesField(forms.IntegerField):
    """Accept duration as whole minutes; stores/retrieves as timedelta."""
    def to_python(self, value):
        minutes = super().to_python(value)
        if minutes is not None:
            return timedelta(minutes=minutes)
        return None

    def prepare_value(self, value):
        if isinstance(value, timedelta):
            return int(value.total_seconds() // 60)
        return value


DAY_CHOICES = [
    ('0', 'Mon'), ('1', 'Tue'), ('2', 'Wed'),
    ('3', 'Thu'), ('4', 'Fri'), ('5', 'Sat'), ('6', 'Sun'),
]


class TaskForm(forms.ModelForm):
    estimated_duration = DurationMinutesField(
        min_value=1,
        label='Estimated Duration (minutes)',
    )
    recur_days = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Repeat on days',
    )

    class Meta:
        model = Task
        fields = [
            'name', 'description', 'labels', 'estimated_duration',
            'priority', 'recurrence', 'recur_days', 'recur_time',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'recur_time': forms.TimeInput(attrs={'type': 'time'}),
            'labels': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['recur_days'] = [str(d) for d in (self.instance.recur_days or [])]

    def clean_recur_days(self):
        return [int(d) for d in self.cleaned_data.get('recur_days', [])]


class ScheduleBlockForm(forms.ModelForm):
    class Meta:
        model = ScheduleBlock
        fields = ['name', 'day_of_week', 'specific_date', 'start_time', 'end_time', 'allowed_labels', 'is_active']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'specific_date': forms.DateInput(attrs={'type': 'date'}),
            'allowed_labels': forms.CheckboxSelectMultiple,
        }

    def clean(self):
        cleaned = super().clean()
        day = cleaned.get('day_of_week')
        specific = cleaned.get('specific_date')
        if day is None and not specific:
            raise forms.ValidationError('Set either a day of week (recurring) or a specific date (one-off).')
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')
        if start and end and start >= end:
            raise forms.ValidationError('Start time must be before end time.')
        return cleaned


class HealthLogForm(forms.ModelForm):
    class Meta:
        model = HealthLog
        fields = ['date', 'energy_level', 'mood', 'stress_level', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('date'):
            self.initial['date'] = date.today()


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = FeedbackResponse
        fields = ['difficulty', 'actual_duration_minutes', 'completed', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'difficulty': 'How difficult was it? (1 = very easy, 5 = very hard)',
            'actual_duration_minutes': 'How long did it actually take? (minutes)',
        }
