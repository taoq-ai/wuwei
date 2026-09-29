"""Read a private ICS feed without exposing its URL."""

from datetime import datetime, timezone
import os
import re
import urllib.request
from zoneinfo import ZoneInfo

from wuwei import workspace
from wuwei.registry import Result


def _date(value, zone=None):
    if re.fullmatch(r'\d{8}T\d{6}Z', value):
        return datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    if re.fullmatch(r'\d{8}T\d{6}', value):
        return datetime.strptime(value, '%Y%m%dT%H%M%S').replace(tzinfo=ZoneInfo(zone) if zone else timezone.utc)
    if re.fullmatch(r'\d{8}', value):
        return datetime.strptime(value, '%Y%m%d').replace(tzinfo=timezone.utc)
    raise ValueError('unsupported calendar date')


def parse(raw, since, until):
    text = raw.decode('utf-8-sig')
    if 'BEGIN:VCALENDAR' not in text or 'END:VCALENDAR' not in text:
        raise ValueError('invalid calendar feed')
    lines = []
    for line in text.replace('\r\n', '\n').split('\n'):
        if line.startswith((' ', '\t')) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    results, current = [], None
    lower, upper = datetime.fromisoformat(since), datetime.fromisoformat(until)
    for line in lines:
        if line == 'BEGIN:VEVENT':
            current = {}
        elif line == 'END:VEVENT' and current is not None:
            if 'DTSTART' in current:
                start = _date(current['DTSTART'], current.get('TZID'))
                if lower <= start <= upper:
                    results.append({'uid': current.get('UID', start.isoformat()),
                                    'start': start.isoformat(), 'summary': current.get('SUMMARY', 'Meeting'),
                                    'attendees': current.get('ATTENDEE', [])})
            current = None
        elif current is not None and ':' in line:
            key, value = line.split(':', 1)
            if key.startswith('DTSTART;TZID='):
                current['TZID'] = key.removeprefix('DTSTART;TZID=')
            key = key.split(';', 1)[0]
            if key == 'ATTENDEE':
                current.setdefault(key, []).append(value.removeprefix('mailto:'))
            elif key in ('UID', 'DTSTART', 'SUMMARY'):
                current[key] = value.replace('\\n', ' ').replace('\\,', ',')
    return results


def events(since, until, root=None):
    try:
        url = os.environ.get('WUWEI_CALENDAR_URL') or workspace.load_config(root)['calendar']['url']
        if not url.startswith('https://'):
            return Result(2, reason='calendar feed URL missing or invalid')
        request = urllib.request.Request(url, headers={'Accept': 'text/calendar'})
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            return Result(2, reason='calendar feed too large')
        return Result(0, parse(raw, since, until))
    except (OSError, ValueError, UnicodeError, KeyError, TypeError):
        return Result(2, reason='calendar feed unavailable or invalid')
