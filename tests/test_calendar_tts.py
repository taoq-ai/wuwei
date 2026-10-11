"""Calendar ICS and speech adapter contract tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    return tmp_path


def test_say_accepts_rate_keyword(monkeypatch, tmp_path):
    from adapters.tts import say

    monkeypatch.setattr(say.sys, 'platform', 'darwin')
    monkeypatch.setattr(say.subprocess, 'run', lambda *args, **kwargs: type('Process', (), {'returncode': 0})())
    assert say.speak('hello', rate=180, out=tmp_path / 'audio.aiff').exit == 0


def test_ics_parser_and_secret_redaction(root, monkeypatch):
    from adapters.calendar import ics
    fixture = Path(__file__).parent / 'fixtures/calendar/meeting.ics'
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return fixture.read_bytes()
    monkeypatch.setenv('WUWEI_CALENDAR_URL', 'https://private.test/feed?token=secret')
    monkeypatch.setattr(ics.urllib.request, 'urlopen', lambda request, timeout: Response())
    result = ics.events('2026-09-29T12:00:00+00:00', '2026-09-29T13:00:00+00:00', root)
    assert result.exit == 0
    assert result.data[0]['summary'] == 'Release review'
    assert result.data[0]['attendees'] == ['pat@example.test']
    assert 'secret' not in json.dumps(result.data)
    def fail(request, timeout): raise OSError('https://private.test/feed?token=secret')
    monkeypatch.setattr(ics.urllib.request, 'urlopen', fail)
    result = ics.events('2026-09-29T12:00:00+00:00', '2026-09-29T13:00:00+00:00', root)
    assert result.exit == 2 and 'secret' not in result.reason


def test_ics_rejects_error_body(root, monkeypatch):
    from adapters.calendar import ics
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b'{"error":"feed unavailable"}'
    monkeypatch.setenv('WUWEI_CALENDAR_URL', 'https://private.test/feed')
    monkeypatch.setattr(ics.urllib.request, 'urlopen', lambda request, timeout: Response())
    result = ics.events('2026-09-29T12:00:00+00:00', '2026-09-29T13:00:00+00:00', root)
    assert result.exit == 2


def test_ics_tzid_uses_local_zone():
    from adapters.calendar.ics import parse
    raw = (b'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:local\n'
           b'DTSTART;TZID=Europe/Amsterdam:20260929T123000\n'
           b'SUMMARY:Local review\nATTENDEE:mailto:pat@example.test\n'
           b'END:VEVENT\nEND:VCALENDAR\n')
    rows = parse(raw, '2026-09-29T10:00:00+00:00', '2026-09-29T11:00:00+00:00')
    assert len(rows) == 1
    assert rows[0]['start'] == '2026-09-29T12:30:00+02:00'
