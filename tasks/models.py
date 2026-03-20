from django.db import models

# Create your models here.
class Task(models.Model):
    title = models.CharField(max_length=200)
    estimated_duration = models.FloatField()
    priority = models.IntegerField()
    #recurrence_rule_id = models.ForeignKey("app.Model", verbose_name=_(""), on_delete=models.CASCADE)

# TODO: Define recurrence types
#class RecurrenceRule(models.Model):

class ExecutionLog(models.Model):
    task_id = models.ForeignKey(Task, on_delete=None)
    scheduled_start = models.DateTimeField(auto_now=False, auto_now_add=False)
    actual_start = models.DateTimeField(auto_now=False, auto_now_add=False)
    actual_end   = models.DateTimeField(auto_now=False, auto_now_add=False)
    skipped      = models.BooleanField()

class ScheduleBlock(models.Model):
    task_id    = models.ForeignKey(Task, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now=False, auto_now_add=False)
    end_time   = models.DateTimeField(auto_now=False, auto_now_add=False)
    calender_event_id = models.CharField(max_length=200)