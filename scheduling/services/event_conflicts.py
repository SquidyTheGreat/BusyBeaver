"""
Adjust schedule blocks to avoid clashes with existing Google Calendar events.

apply_event_conflicts(blocks, target_date, integration) returns a new list of
block-like objects with start_time / end_time shifted (or the block omitted)
so that no block overlaps an event from integration.event_calendar_id.

The original ScheduleBlock instances are never mutated and .save() is never
called, so the database is not affected.
"""
import copy
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

def apply_event_conflicts(blocks, target_date, integration):
    """
    Return a list of (possibly copied and adjusted) blocks with event
    conflicts removed.  Blocks whose entire window falls inside an event
    are excluded from the result.

    Parameters
    ----------
    blocks       : iterable of ScheduleBlock instances
    target_date  : datetime.date
    integration  : CalendarIntegration — must have event_calendar_id set

    Returns
    -------
    list of block objects (shallow copies where adjusted, originals otherwise)
    """
    if not getattr(integration, 'event_calendar_id', None):
        return list(blocks)

    events = _fetch_day_events(integration, target_date)
    if not events:
        return list(blocks)

    result = []
    for block in blocks:
        adjusted = _adjust_block(block, events)
        if adjusted is not None:
            result.append(adjusted)
    return result


# ── Internals ─────────────────────────────────────────────────────────────────

def _fetch_day_events(integration, target_date):
    """Return a list of Google Calendar event dicts for target_date."""
    try:
        from googleapiclient.discovery import build
        from scheduling.services.google_calendar import refresh_if_needed

        creds = refresh_if_needed(integration)
        service = build('calendar', 'v3', credentials=creds)

        import pytz
        local_tz = pytz.timezone(settings.TIME_ZONE)
        day_start = local_tz.localize(datetime.combine(target_date, datetime.min.time()))
        day_end   = local_tz.localize(datetime.combine(target_date, datetime.max.time().replace(microsecond=0)))

        result = service.events().list(
            calendarId=integration.event_calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy='startTime',
        ).execute()
        return result.get('items', [])
    except Exception as exc:
        logger.warning('Could not fetch event calendar events: %s', exc)
        return []


def _parse_event_time(raw):
    """
    Return a datetime.time object from a Google event start/end dict.
    All-day events (date-only) return None and are ignored.
    """
    dt_str = raw.get('dateTime')
    if not dt_str:
        return None
    try:
        from dateutil.parser import isoparse
        import pytz
        dt = isoparse(dt_str)
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        local_tz = pytz.timezone(settings.TIME_ZONE)
        return dt.astimezone(local_tz).time()
    except Exception:
        return None


def _adjust_block(block, events):
    """
    Apply all event conflicts to a single block.

    Overlap rules (all comparisons use local time objects):
      1. Event covers block start  (ev_start ≤ blk_start < ev_end ≤ blk_end)
             → move block start to ev_end
      2. Event covers block end    (blk_start ≤ ev_start < blk_end ≤ ev_end)
             → move block end to ev_start
      3. Event is inside block     (blk_start < ev_start < ev_end < blk_end)
             → move block start to ev_end  (skip over the event)
      4. Event covers entire block (ev_start ≤ blk_start and ev_end ≥ blk_end)
             → skip block entirely (return None)

    Multiple events are applied sequentially against the (possibly already
    adjusted) block bounds.
    """
    adjusted = copy.copy(block)

    for event in events:
        ev_start = _parse_event_time(event.get('start', {}))
        ev_end   = _parse_event_time(event.get('end',   {}))

        if ev_start is None or ev_end is None:
            continue

        blk_start = adjusted.start_time
        blk_end   = adjusted.end_time

        # No overlap
        if ev_end <= blk_start or ev_start >= blk_end:
            continue

        # Rule 4: event covers entire block → skip
        if ev_start <= blk_start and ev_end >= blk_end:
            return None

        # Rule 1: event overlaps block start
        if ev_start <= blk_start and ev_end < blk_end:
            adjusted.start_time = ev_end
            continue

        # Rule 2: event overlaps block end
        if ev_start > blk_start and ev_end >= blk_end:
            adjusted.end_time = ev_start
            continue

        # Rule 3: event is fully inside block
        if ev_start > blk_start and ev_end < blk_end:
            adjusted.start_time = ev_end
            continue

    # Discard degenerate blocks produced by multiple overlapping adjustments
    if adjusted.start_time >= adjusted.end_time:
        return None

    return adjusted
