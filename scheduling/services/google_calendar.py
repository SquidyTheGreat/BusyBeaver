"""
Google Calendar integration helpers.

Requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI in settings.
"""
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']


def _build_client_config():
    return {
        'web': {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [settings.GOOGLE_REDIRECT_URI],
        }
    }


def get_auth_url(request):
    """Return (authorization_url, state) for starting the OAuth flow."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    return authorization_url, state


def exchange_code(code, state):
    """Exchange an OAuth code for credentials. Returns a google.oauth2.credentials.Credentials object."""
    import os
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        state=state,
    )
    # Allow Google to return a superset of the requested scopes (e.g. when the
    # OAuth client already has broader grants from other apps).
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_from_db(integration):
    """Reconstruct a Credentials object from a CalendarIntegration row."""
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=integration.access_token,
        refresh_token=integration.refresh_token or None,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    if integration.token_expiry:
        creds.expiry = integration.token_expiry.replace(tzinfo=None)
    return creds


def refresh_if_needed(integration):
    """Refresh the access token if expired; persist new token to DB."""
    import google.auth.transport.requests as google_requests

    creds = credentials_from_db(integration)
    if creds.expired and creds.refresh_token:
        creds.refresh(google_requests.Request())
        integration.access_token = creds.token
        if creds.expiry:
            integration.token_expiry = timezone.make_aware(creds.expiry) if creds.expiry.tzinfo is None else creds.expiry
        integration.save(update_fields=['access_token', 'token_expiry'])
    return creds


def list_calendars(integration):
    """Return list of {id, summary} dicts for all calendars the user can write to."""
    from googleapiclient.discovery import build

    creds = refresh_if_needed(integration)
    service = build('calendar', 'v3', credentials=creds)
    result = service.calendarList().list().execute()
    return [
        {'id': cal['id'], 'name': cal.get('summary', cal['id'])}
        for cal in result.get('items', [])
        if cal.get('accessRole') in ('writer', 'owner')
    ]


def create_or_update_event(task, integration):
    """
    Push task to Google Calendar.  Attaches the feedback form link to the event description.
    Logs a TaskMoveLog if the event's start time changed from what we previously stored.
    """
    from googleapiclient.discovery import build
    from tasks.models import TaskMoveLog

    if not task.scheduled_start or not task.scheduled_end:
        logger.warning('Task %s has no scheduled time; skipping calendar push', task.id)
        return None

    creds = refresh_if_needed(integration)
    service = build('calendar', 'v3', credentials=creds)

    feedback_link = task.feedback_url(settings.BASE_URL)
    description = task.description or ''
    if feedback_link not in description:
        description = description.rstrip() + f'\n\n📝 Feedback: {feedback_link}'

    first_label = task.labels.order_by('name').first()
    if task.status == 'completed':
        summary = f'✅ {task.name}'
        color_id = '10'  # Basil
    elif task.status == 'skipped':
        summary = f'⏭ {task.name}'
        color_id = '8'  # Graphite
    else:
        summary = task.name
        color_id = first_label.color if first_label else None

    event_body = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': task.scheduled_start.isoformat(), 'timeZone': settings.TIME_ZONE},
        'end': {'dateTime': task.scheduled_end.isoformat(), 'timeZone': settings.TIME_ZONE},
    }
    if color_id:
        event_body['colorId'] = color_id

    if task.google_event_id:
        try:
            event = service.events().patch(
                calendarId=integration.calendar_id,
                eventId=task.google_event_id,
                body=event_body,
            ).execute()
            return event
        except Exception as exc:
            # Event may have been deleted from Calendar or moved to a different
            # calendar — clear the stale ID and fall through to insert.
            logger.warning(
                'Could not update event %s for task %s (%s); re-creating.',
                task.google_event_id, task.id, exc,
            )
            task.google_event_id = ''
            task.save(update_fields=['google_event_id'])

    event = service.events().insert(
        calendarId=integration.calendar_id,
        body=event_body,
    ).execute()
    task.google_event_id = event['id']
    task.save(update_fields=['google_event_id'])
    return event


def delete_event(task, integration):
    """Remove the task's event from Google Calendar."""
    from googleapiclient.discovery import build

    if not task.google_event_id:
        return
    creds = refresh_if_needed(integration)
    service = build('calendar', 'v3', credentials=creds)
    try:
        service.events().delete(
            calendarId=integration.calendar_id,
            eventId=task.google_event_id,
        ).execute()
        task.google_event_id = ''
        task.save(update_fields=['google_event_id'])
    except Exception as exc:
        logger.warning('Could not delete calendar event for task %s: %s', task.id, exc)
        task.google_event_id = ''
        task.save(update_fields=['google_event_id'])


def push_block_summaries(block_groups, integration):
    """
    For each block group returned by create_schedule, create or update a BlockSummary
    record and push a 15-minute summary event to Google Calendar immediately after the block.
    """
    from datetime import timedelta
    from googleapiclient.discovery import build
    from tasks.models import BlockSummary

    creds = refresh_if_needed(integration)
    service = build('calendar', 'v3', credentials=creds)

    for group in block_groups:
        summary, _ = BlockSummary.objects.get_or_create(
            block_name=group['block_name'],
            block_start=group['block_start'],
            defaults={'block_end': group['block_end']},
        )
        summary.block_end = group['block_end']
        summary.save(update_fields=['block_end'])
        summary.tasks.set(group['tasks'])

        summary_link = summary.summary_url(settings.BASE_URL)
        task_names = ', '.join(t.name for t in group['tasks'])
        description = (
            f"Summary for block: {group['block_name']}\n"
            f"Tasks: {task_names}\n\n"
            f"📋 Submit feedback: {summary_link}"
        )

        event_start = group['block_end']
        event_end = event_start + timedelta(minutes=15)
        event_body = {
            'summary': f'📋 {group["block_name"]} — Summary',
            'description': description,
            'start': {'dateTime': event_start.isoformat(), 'timeZone': settings.TIME_ZONE},
            'end': {'dateTime': event_end.isoformat(), 'timeZone': settings.TIME_ZONE},
            'colorId': '8',  # Graphite
        }

        if summary.calendar_event_id:
            try:
                service.events().patch(
                    calendarId=integration.calendar_id,
                    eventId=summary.calendar_event_id,
                    body=event_body,
                ).execute()
                continue
            except Exception:
                summary.calendar_event_id = ''

        event = service.events().insert(
            calendarId=integration.calendar_id,
            body=event_body,
        ).execute()
        summary.calendar_event_id = event['id']
        summary.save(update_fields=['calendar_event_id'])


def sync_from_calendar(integration):
    """
    Fetch all tasks with a google_event_id and detect moves.
    For each task whose event start differs from task.scheduled_start, log a TaskMoveLog
    and update the task's scheduled_start/end.
    """
    from googleapiclient.discovery import build
    from tasks.models import Task, TaskMoveLog

    creds = refresh_if_needed(integration)
    service = build('calendar', 'v3', credentials=creds)

    moved = 0
    tasks = Task.objects.exclude(google_event_id='').filter(google_event_id__isnull=False)
    for task in tasks:
        try:
            event = service.events().get(
                calendarId=integration.calendar_id,
                eventId=task.google_event_id,
            ).execute()
        except Exception as exc:
            logger.warning('Could not fetch event for task %s: %s', task.id, exc)
            continue

        raw_start = event['start'].get('dateTime') or event['start'].get('date')
        if not raw_start:
            continue

        # Parse ISO datetime; handle date-only events
        try:
            if 'T' in raw_start:
                from dateutil.parser import isoparse
                event_start = isoparse(raw_start)
                if event_start.tzinfo is None:
                    event_start = timezone.make_aware(event_start)
            else:
                from dateutil.parser import parse as dateparse
                event_start = timezone.make_aware(dateparse(raw_start))
        except Exception:
            continue

        if task.scheduled_start and abs((event_start - task.scheduled_start).total_seconds()) > 60:
            TaskMoveLog.objects.create(
                task=task,
                from_start=task.scheduled_start,
                to_start=event_start,
                moved_by=TaskMoveLog.MOVED_BY_CALENDAR,
                reason='Detected during calendar sync',
            )
            # Shift end by the same delta
            if task.scheduled_end:
                delta = event_start - task.scheduled_start
                task.scheduled_end = task.scheduled_end + delta
            task.scheduled_start = event_start
            task.save(update_fields=['scheduled_start', 'scheduled_end'])
            moved += 1

    integration.last_synced = timezone.now()
    integration.save(update_fields=['last_synced'])
    logger.info('Sync complete: %d tasks moved', moved)
    return moved
