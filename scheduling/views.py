from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from tasks.models import Task, ScheduleBlock
from tasks.forms import ScheduleBlockForm
from .forms import RunSchedulerForm
from .models import CalendarIntegration


# ── Schedule overview ─────────────────────────────────────────────────────────

def schedule_view(request):
    form = RunSchedulerForm(request.GET or None)
    target = date.today()
    if form.is_valid():
        target = form.cleaned_data['target_date']

    day_of_week = target.weekday()
    blocks = ScheduleBlock.objects.filter(is_active=True).filter(
        day_of_week=day_of_week
    ) | ScheduleBlock.objects.filter(is_active=True, specific_date=target)

    scheduled_tasks = Task.objects.filter(
        scheduled_start__date=target
    ).order_by('scheduled_start').prefetch_related('labels')

    return render(request, 'scheduling/schedule.html', {
        'form': form,
        'target': target,
        'blocks': blocks.distinct(),
        'scheduled_tasks': scheduled_tasks,
    })


# ── Schedule blocks ───────────────────────────────────────────────────────────

def block_list(request):
    blocks = ScheduleBlock.objects.prefetch_related('allowed_labels').order_by('day_of_week', 'start_time')
    return render(request, 'scheduling/block_list.html', {'blocks': blocks})


def block_create(request):
    form = ScheduleBlockForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        block = form.save()
        messages.success(request, f'Block "{block.name}" created.')
        return redirect('block_list')
    return render(request, 'scheduling/block_form.html', {'form': form, 'title': 'New Schedule Block'})


def block_edit(request, block_id):
    block = get_object_or_404(ScheduleBlock, id=block_id)
    form = ScheduleBlockForm(request.POST or None, instance=block)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Block "{block.name}" updated.')
        return redirect('block_list')
    return render(request, 'scheduling/block_form.html', {'form': form, 'title': 'Edit Block', 'block': block})


@require_POST
def block_delete(request, block_id):
    block = get_object_or_404(ScheduleBlock, id=block_id)
    name = block.name
    block.delete()
    messages.success(request, f'Block "{name}" deleted.')
    return redirect('block_list')


# ── Run auto-scheduler ────────────────────────────────────────────────────────

@require_POST
def run_scheduler(request):
    from .services.schedules_tasks import ScheduleTask

    target_str = request.POST.get('target_date', '')
    try:
        from datetime import datetime as dt
        target = dt.strptime(target_str, '%Y-%m-%d').date()
    except ValueError:
        target = date.today()

    pending = list(Task.objects.filter(status__in=[Task.STATUS_PENDING, Task.STATUS_SCHEDULED]).prefetch_related('labels'))
    blocks = list(ScheduleBlock.objects.filter(is_active=True).prefetch_related('allowed_labels'))

    integration = CalendarIntegration.objects.filter(is_active=True).first()
    if integration and integration.event_calendar_id:
        from .services.event_conflicts import apply_event_conflicts
        blocks = apply_event_conflicts(blocks, target, integration)

    result = ScheduleTask.create_schedule(pending, blocks, target)

    # Push newly scheduled tasks to Google Calendar if connected
    if integration:
        from .services.google_calendar import create_or_update_event
        for task in result['scheduled']:
            try:
                create_or_update_event(task, integration)
            except Exception as exc:
                messages.warning(request, f'Calendar push failed for "{task.name}": {exc}')

    messages.success(
        request,
        f'Scheduled {result["scheduled_count"]} tasks, '
        f'{result["unscheduled_count"]} could not be placed.'
    )
    return redirect(f'/schedule/?target_date={target_str}')


# ── Clear schedule for a date ─────────────────────────────────────────────────

@require_POST
def clear_schedule(request):
    from datetime import datetime as dt
    from tasks.models import Task

    target_str = request.POST.get('target_date', '')
    try:
        target = dt.strptime(target_str, '%Y-%m-%d').date()
    except ValueError:
        messages.warning(request, 'Invalid date.')
        return redirect('schedule_view')

    tasks = Task.objects.filter(scheduled_start__date=target).exclude(
        status__in=[Task.STATUS_COMPLETED, Task.STATUS_SKIPPED, Task.STATUS_CANCELLED]
    )

    integration = CalendarIntegration.objects.filter(is_active=True).first()
    if integration:
        from .services.google_calendar import delete_event

    count = 0
    for task in tasks:
        if integration and task.google_event_id:
            try:
                delete_event(task, integration)
            except Exception:
                pass
        task.status = Task.STATUS_PENDING
        task.scheduled_start = None
        task.scheduled_end = None
        task.save(update_fields=['status', 'scheduled_start', 'scheduled_end'])
        count += 1

    messages.success(request, f'Cleared {count} task(s) for {target.strftime("%b %d")}.')
    return redirect(f'/schedule/?target_date={target_str}')


# ── Google Calendar sync ──────────────────────────────────────────────────────

@require_POST
def sync_calendar(request):
    integration = CalendarIntegration.objects.filter(is_active=True).first()
    if not integration:
        messages.warning(request, 'No Google Calendar connected.')
        return redirect('calendar_list')
    from .services.google_calendar import sync_from_calendar
    moved = sync_from_calendar(integration)
    messages.success(request, f'Sync complete. {moved} task(s) moved.')
    return redirect('schedule_view')


# ── Calendar list / selection ─────────────────────────────────────────────────

def calendar_list(request):
    integration = CalendarIntegration.objects.filter(is_active=True).first()
    calendars = []
    if integration:
        try:
            from .services.google_calendar import list_calendars
            calendars = list_calendars(integration)
        except Exception as exc:
            messages.warning(request, f'Could not fetch calendars: {exc}')
    return render(request, 'scheduling/calendar_list.html', {
        'integration': integration,
        'calendars': calendars,
    })


@require_POST
def set_calendar(request):
    calendar_id = request.POST.get('calendar_id')
    calendar_name = request.POST.get('calendar_name', calendar_id)
    integration = CalendarIntegration.objects.filter(is_active=True).first()
    if integration:
        integration.calendar_id = calendar_id
        integration.calendar_name = calendar_name
        integration.save(update_fields=['calendar_id', 'calendar_name'])
        messages.success(request, f'Task calendar set to "{calendar_name}".')
    return redirect('calendar_list')


@require_POST
def set_event_calendar(request):
    calendar_id = request.POST.get('calendar_id')
    calendar_name = request.POST.get('calendar_name', calendar_id)
    integration = CalendarIntegration.objects.filter(is_active=True).first()
    if integration:
        integration.event_calendar_id = calendar_id
        integration.event_calendar_name = calendar_name
        integration.save(update_fields=['event_calendar_id', 'event_calendar_name'])
        messages.success(request, f'Event calendar set to "{calendar_name}".')
    return redirect('calendar_list')
