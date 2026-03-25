"""
Management command: fetch all events for a given day from the event calendar
and create EventLog records for any that don't already exist.
"""
import logging
from datetime import datetime, date

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync events from the event calendar into EventLog for a given day (default: today).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            default=None,
            help='Target date in YYYY-MM-DD format (default: today)',
        )

    def handle(self, *args, **options):
        from googleapiclient.discovery import build
        from scheduling.models import CalendarIntegration
        from scheduling.services.google_calendar import refresh_if_needed
        from tasks.models import EventLog

        integration = CalendarIntegration.objects.filter(is_active=True).first()
        if not integration:
            self.stderr.write('No active CalendarIntegration found.')
            return
        if not integration.event_calendar_id:
            self.stderr.write('No event calendar configured on the integration.')
            return

        target_str = options.get('date')
        if target_str:
            target = datetime.strptime(target_str, '%Y-%m-%d').date()
        else:
            target = date.today()

        import pytz
        local_tz = pytz.timezone(settings.TIME_ZONE)
        day_start = local_tz.localize(datetime.combine(target, datetime.min.time()))
        day_end   = local_tz.localize(datetime.combine(target, datetime.max.time().replace(microsecond=0)))

        try:
            creds = refresh_if_needed(integration)
            service = build('calendar', 'v3', credentials=creds)
            result = service.events().list(
                calendarId=integration.event_calendar_id,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy='startTime',
            ).execute()
            events = result.get('items', [])
        except Exception as exc:
            self.stderr.write(f'Failed to fetch events: {exc}')
            return

        created = 0
        skipped = 0
        for event in events:
            start_dt = _parse_dt(event.get('start', {}), local_tz)
            end_dt   = _parse_dt(event.get('end',   {}), local_tz)

            if start_dt is None or end_dt is None:
                # Skip all-day events
                skipped += 1
                continue

            name        = event.get('summary', '(no title)')
            description = event.get('description', '') or ''
            location    = event.get('location', '') or ''

            if not EventLog.objects.filter(
                name=name, start=start_dt, end=end_dt
            ).exists():
                EventLog.objects.create(
                    name=name,
                    description=description,
                    location=location,
                    start=start_dt,
                    end=end_dt,
                )
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {created} event(s) created, {skipped} all-day event(s) skipped.'
            )
        )


def _parse_dt(raw, local_tz):
    """Return an aware datetime from a Google event start/end dict, or None for all-day events."""
    dt_str = raw.get('dateTime')
    if not dt_str:
        return None
    try:
        from dateutil.parser import isoparse
        dt = isoparse(dt_str)
        if dt.tzinfo is None:
            dt = local_tz.localize(dt)
        return dt
    except Exception:
        return None
