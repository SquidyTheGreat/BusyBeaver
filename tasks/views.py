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
    qs = Task.objects.prefetch_related('labels')
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
    log = task.executions.filter(status=ExecutionLog.STATUS_IN_PROGRESS).order_by('-actual_start').first()
    if log:
        log.actual_end = timezone.now()
        log.status = ExecutionLog.STATUS_COMPLETED
        log.save()
    task.status = Task.STATUS_COMPLETED
    task.save(update_fields=['status'])

    # Update estimates based on all completed executions
    from scheduling.services.schedules_tasks import ScheduleTask
    ScheduleTask.update_task_estimates()

    # Reset recurring tasks back to pending for next occurrence
    if task.recurrence != Task.RECUR_NONE:
        task.status = Task.STATUS_PENDING
        task.scheduled_start = None
        task.scheduled_end = None
        task.save(update_fields=['status', 'scheduled_start', 'scheduled_end'])

    messages.success(request, f'Completed "{task.name}".')
    return redirect('task_detail', task_id=task.id)


@require_POST
def task_skip(request, task_id):
    task = get_object_or_404(Task, id=task_id)
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
    form = FeedbackForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        fb = form.save(commit=False)
        fb.task = task
        fb.save()
        return redirect('feedback_thanks', token=token)
    return render(request, 'feedback/form.html', {'form': form, 'task': task})


def feedback_thanks(request, token):
    task = get_object_or_404(Task, feedback_token=token)
    return render(request, 'feedback/thanks.html', {'task': task})
