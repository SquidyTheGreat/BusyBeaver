from django import forms
from datetime import date


class RunSchedulerForm(forms.Form):
    target_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=date.today,
        label='Schedule for date',
    )
