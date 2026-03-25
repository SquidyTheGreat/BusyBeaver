from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Task, ExecutionLog, HealthLog, FeedbackResponse
from .forms import TaskForm, HealthLogForm, FeedbackForm


# ── Task list / CRUD ──────────────────────────────────────────────────────────

def task_list(request):
    status_filter = request.GET.get('status', '')
    label_filter = request.GET.get('label', '')
    qs = Task.objects.prefetch_related('labels').exclude(
        status=Task.STATUS_COMPLETED, recurrence=Task.RECUR_NONE
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if label_filter:
        qs = qs.filter(labels__name=label_filter)

    from .models import Label
    return render(request, 'tasks/list.html', {
        'tasks': qs,
        'status_choices': Task.STATUS_CHOICES,
        'status_filter': status_filter,
        'label_filter': label_filter,
        'labels': Label.objects.all(),
    })


def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    executions = task.executions.order_by('-created_at')[:20]
    move_logs = task.move_logs.order_by('-moved_at')[:10]
    feedback = task.feedback_responses.order_by('-submitted_at')
    return render(request, 'tasks/detail.html', {
        'task': task,
        'executions': executions,
        'move_logs': move_logs,
        'feedback': feedback,
    })


def task_create(request):
    form = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save()
        messages.success(request, f'Task "{task.name}" created.')
        return redirect('task_detail', task_id=task.id)
    return render(request, 'tasks/form.html', {'form': form, 'title': 'New Task'})


def task_edit(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    form = TaskForm(request.POST or None, instance=task)
    if request.method == 'POST' and form.is_valid():
        old_start = task.scheduled_start
        task = form.save()
        # Log a move if scheduled_start changed via this edit
        if old_start and task.scheduled_start and old_start != task.scheduled_start:
            from .models import TaskMoveLog
            TaskMoveLog.objects.create(
                task=task,
                from_start=old_start,
                to_start=task.scheduled_start,
                moved_by=TaskMoveLog.MOVED_BY_USER,
                reason='Edited via task form',
            )
        messages.success(request, f'Task "{task.name}" updated.')
        return redirect('task_detail', task_id=task.id)
    return render(request, 'tasks/form.html', {'form': form, 'title': 'Edit Task', 'task': task})


def task_delete(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        name = task.name
        task.delete()
        messages.success(request, f'Task "{name}" deleted.')
        return redirect('task_list')
    return render(request, 'tasks/confirm_delete.html', {'task': task})


# ── Shared lifecycle helpers ──────────────────────────────────────────────────

def _mark_task_complete(task):
    log = task.executions.filter(status=ExecutionLog.STATUS_IN_PROGRESS).order_by('-actual_start').first()
    if log:
        log.actual_end = timezone.now()
        log.status = ExecutionLog.STATUS_COMPLETED
        log.save()
    task.status = Task.STATUS_COMPLETED
    task.save(update_fields=['status'])
    from scheduling.services.schedules_tasks import ScheduleTask
    ScheduleTask.update_task_estimates()
    if task.google_event_id:
        try:
            from scheduling.models import CalendarIntegration
            from scheduling.services.google_calendar import create_or_update_event
            integration = CalendarIntegration.objects.filter(is_active=True).first()
            if integration:
                create_or_update_event(task, integration)
        except Exception:
            pass


def _mark_task_skip(task):
    log = task.executions.filter(status=ExecutionLog.STATUS_IN_PROGRESS).order_by('-actual_start').first()
    if log:
        log.status = ExecutionLog.STATUS_SKIPPED
        log.save()
    else:
        ExecutionLog.objects.create(
            task=task,
            scheduled_start=task.scheduled_start,
            actual_start=timezone.now(),
            actual_end=timezone.now(),
            status=ExecutionLog.STATUS_SKIPPED,
        )
    task.status = Task.STATUS_SKIPPED
    task.save(update_fields=['status'])
    if task.google_event_id:
        try:
            from scheduling.models import CalendarIntegration
            from scheduling.services.google_calendar import create_or_update_event
            integration = CalendarIntegration.objects.filter(is_active=True).first()
            if integration:
                create_or_update_event(task, integration)
        except Exception:
            pass


# ── Task lifecycle actions ────────────────────────────────────────────────────

@require_POST
def task_start(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    ExecutionLog.objects.create(
        task=task,
        scheduled_start=task.scheduled_start,
        actual_start=timezone.now(),
        status=ExecutionLog.STATUS_IN_PROGRESS,
    )
    task.status = Task.STATUS_IN_PROGRESS
    task.save(update_fields=['status'])
    messages.success(request, f'Started "{task.name}".')
    return redirect('task_detail', task_id=task.id)


@require_POST
def task_complete(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    _mark_task_complete(task)
    messages.success(request, f'Completed "{task.name}".')
    return redirect('task_detail', task_id=task.id)


@require_POST
def task_skip(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    _mark_task_skip(task)
    messages.info(request, f'Skipped "{task.name}".')
    return redirect('task_list')


@require_POST
def task_cancel(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    log = task.executions.filter(status=ExecutionLog.STATUS_IN_PROGRESS).order_by('-actual_start').first()
    if log:
        log.status = ExecutionLog.STATUS_CANCELLED
        log.save()
    task.status = Task.STATUS_CANCELLED
    task.save(update_fields=['status'])
    messages.warning(request, f'Cancelled "{task.name}".')
    return redirect('task_list')


# ── Labels ────────────────────────────────────────────────────────────────────

def label_list(request):
    from .models import Label
    labels = Label.objects.annotate(task_count=models.Count('tasks')).order_by('name')
    return render(request, 'tasks/label_list.html', {'labels': labels})


def label_create(request):
    from .models import Label
    from django import forms as dj_forms

    class LabelForm(dj_forms.ModelForm):
        class Meta:
            model = Label
            fields = ['name', 'color']
            widgets = {'color': dj_forms.RadioSelect}

    form = LabelForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        label = form.save()
        messages.success(request, f'Label "{label.name}" created.')
        return redirect('label_list')
    return render(request, 'tasks/label_form.html', {'form': form, 'title': 'New Label'})


def label_edit(request, label_id):
    from .models import Label
    from django import forms as dj_forms

    class LabelForm(dj_forms.ModelForm):
        class Meta:
            model = Label
            fields = ['name', 'color']
            widgets = {'color': dj_forms.RadioSelect}

    label = get_object_or_404(Label, id=label_id)
    form = LabelForm(request.POST or None, instance=label)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Label "{label.name}" updated.')
        return redirect('label_list')
    return render(request, 'tasks/label_form.html', {'form': form, 'title': 'Edit Label', 'label': label})


@require_POST
def label_delete(request, label_id):
    from .models import Label
    label = get_object_or_404(Label, id=label_id)
    name = label.name
    label.delete()
    messages.success(request, f'Label "{name}" deleted.')
    return redirect('label_list')


# ── Health log ────────────────────────────────────────────────────────────────

def health_list(request):
    logs = HealthLog.objects.all()
    return render(request, 'health/list.html', {'logs': logs})


def health_create(request):
    form = HealthLogForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Health entry logged.')
        return redirect('health_list')
    return render(request, 'health/form.html', {'form': form})


# ── Feedback form ─────────────────────────────────────────────────────────────

def feedback_form(request, token):
    task = get_object_or_404(Task, feedback_token=token)
    initial = {}
    if task.scheduled_start:
        initial['actual_start'] = task.scheduled_start
    if task.scheduled_end:
        initial['actual_end'] = task.scheduled_end
    form = FeedbackForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action', 'complete')

        actual_start = form.cleaned_data.get('actual_start')
        actual_end = form.cleaned_data.get('actual_end')
        if actual_start and actual_end:
            actual_start = timezone.make_aware(actual_start) if actual_start.tzinfo is None else actual_start
            actual_end = timezone.make_aware(actual_end) if actual_end.tzinfo is None else actual_end

        fb = form.save(commit=False)
        fb.task = task
        if actual_start and actual_end:
            fb.actual_duration_minutes = max(1, round((actual_end - actual_start).total_seconds() / 60))
        fb.save()

        if action == 'skip':
            ExecutionLog.objects.create(
                task=task,
                scheduled_start=task.scheduled_start,
                actual_start=timezone.now(),
                actual_end=timezone.now(),
                status=ExecutionLog.STATUS_SKIPPED,
                notes='Logged via feedback form',
            )
            _mark_task_skip(task)
        else:
            if actual_start and actual_end:
                ExecutionLog.objects.create(
                    task=task,
                    scheduled_start=task.scheduled_start,
                    actual_start=actual_start,
                    actual_end=actual_end,
                    status=ExecutionLog.STATUS_COMPLETED,
                    notes='Logged via feedback form',
                )
            _mark_task_complete(task)

        if action == 'health':
            return redirect('health_create')
        return redirect('feedback_thanks', token=token)
    return render(request, 'feedback/form.html', {'form': form, 'task': task})


def feedback_thanks(request, token):
    task = get_object_or_404(Task, feedback_token=token)
    return render(request, 'feedback/thanks.html', {'task': task})
