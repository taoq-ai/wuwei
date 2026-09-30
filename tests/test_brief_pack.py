"""Owner pack acceptance and adapter contract tests."""

import json
from pathlib import Path

import pytest

from wuwei import registry, state, workspace
from wuwei.__main__ import main


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(CONFIG)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    day(tmp_path, {'RELEASE-1': {'phase': 'parked', 'resume_phase': 'implement', 'decision': 'D-1'},
                   'SHIP-1': {'phase': 'merged', 'pr': 'org/repo#1'}},
        {'D-1': 'Delay release'})
    return tmp_path


CONFIG = '[adapters]\ntts = "none"\ncalendar = "none"\ncode_host = "none"\n'


def day(root, items, outcomes, **extra):
    state._write_state(lambda data: data.update(
        items={name: {**state.ITEM_DEFAULTS, **item} for name, item in items.items()}, **extra),
        root, reserved=False)
    decisions = workspace.day_dir(root) / 'decisions'
    decisions.mkdir(exist_ok=True)
    for ident, outcome in outcomes.items():
        (decisions / f'{ident}.md').write_text(f'Question: q\nOutcome: {outcome}\n')


def daily(capsys, root):
    assert main(['brief', 'pack']) == 0
    return (root / capsys.readouterr().out.strip()).read_text()


def section(pack, name):
    return pack.split(f'## {name}\n\n')[1].split('\n')[0]


def test_pack_reports_items_and_decisions_not_tool_messages(tmp_path, monkeypatch, capsys):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(CONFIG)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    day(tmp_path, {'DIVIDE-1': {'phase': 'merged', 'pr': 'org/repo#1'}}, {'D-1': 'defer'})
    state.append_event('tracker.call', {'exit': 2, 'reason': 'tracker adapter is none'}, tmp_path)
    state.append_event('hook.refusal', {'reason': 'guard refused the push'}, tmp_path)
    pack = daily(capsys, tmp_path)
    assert section(pack, 'Headline') == section(pack, 'Changed') == 'DIVIDE-1: merged (org/repo#1)'
    assert section(pack, 'Decided') == 'D-1: defer'
    assert section(pack, 'At risk') == 'No recorded risks'
    assert 'tracker adapter' not in pack and 'guard refused' not in pack


def test_pack_risks_are_parked_items_pending_decisions_and_open_prs(root, capsys):
    day(root, {'RELEASE-1': {'phase': 'parked', 'resume_phase': 'implement', 'decision': 'D-1'},
               'SHIP-1': {'phase': 'merged', 'pr': 'org/repo#1'}}, {'D-2': 'pending'},
        raised_prs=['org/repo#2'], watch={'actions': {'org/repo#2': {
            'state': 'ci_red', 'action': 'fix round', 'created_at': '2026-09-29T11:00:00+00:00',
            'deadline': '2026-09-29T13:00:00+00:00'}}})
    from wuwei import brief_pack
    _, _, risk = brief_pack._evidence(root, '')
    assert risk == ['RELEASE-1: parked', 'D-2: pending owner decision',
                    'org/repo#2: ci_red: fix round']
    assert section(daily(capsys, root), 'Headline') == 'RELEASE-1: parked'


def test_daily_pack_fixed_sections_card_and_no_audio(root, capsys):
    assert main(['brief', 'pack']) == 0
    output = capsys.readouterr().out.strip()
    pack = (root / output).read_text()
    headings = ['## Headline', '## Changed', '## Decided', '## At risk', '## You will be asked']
    assert [pack.index(heading) for heading in headings] == sorted(pack.index(heading) for heading in headings)
    assert pack.count('\n- ', pack.index('## Meeting card'), pack.index('## Defend drill')) == 3
    assert 'Audio unavailable (tts: none)' in pack
    assert '## What changed' in pack
    assert not list((root / '.wuwei').rglob('*.aiff'))
    assert main(['brief', 'pack']) == 0
    assert capsys.readouterr().out.strip() == output


def test_daily_pack_creates_audio_directory_before_say(root, monkeypatch, capsys):
    from adapters.tts import say

    (root / '.wuwei/config.toml').write_text(CONFIG.replace('"none"', '"say"', 1))
    monkeypatch.setattr(say.sys, 'platform', 'darwin')

    def fake_run(argv, **kwargs):
        output = Path(argv[argv.index('-o') + 1])
        assert output.parent.is_dir()
        output.write_bytes(b'audio')
        return type('Process', (), {'returncode': 0})()

    monkeypatch.setattr(say.subprocess, 'run', fake_run)
    assert main(['brief', 'pack']) == 0
    pack = root / capsys.readouterr().out.strip()
    assert 'Audio: pack-daily.aiff (five chapters)' in pack.read_text()
    assert pack.with_suffix('.aiff').read_bytes() == b'audio'


def test_speech_rate_config_rejects_unsupported_value(root):
    (root / '.wuwei/config.toml').write_text('[brief.style]\nspeed = 300\n')
    with pytest.raises(workspace.ConfigError, match='brief.style.speed'):
        workspace.load_config(root)


def test_say_accepts_rate_keyword(monkeypatch, tmp_path):
    from adapters.tts import say

    monkeypatch.setattr(say.sys, 'platform', 'darwin')
    monkeypatch.setattr(say.subprocess, 'run', lambda *args, **kwargs: type('Process', (), {'returncode': 0})())
    assert say.speak('hello', rate=180, out=tmp_path / 'audio.aiff').exit == 0


def test_meeting_pack_due_window_and_attendees(root, monkeypatch, capsys):
    class Calendar:
        def events(self, since, until, root=None):
            return registry.Result(0, [{'uid': 'review-1', 'start': '2026-09-29T12:30:00+00:00',
                                        'summary': 'Release review', 'attendees': ['pat@example.test']}])
    old_load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: Calendar() if kind == 'calendar' else old_load(kind, config))
    assert main(['brief', 'pack', '--meeting']) == 0
    assert 'Release review' in (root / capsys.readouterr().out.strip()).read_text()


def test_answer_feedback_streak_and_metric(root, capsys):
    from wuwei import metrics
    assert main(['brief', 'pack']) == 0
    capsys.readouterr()
    assert main(['brief', 'answer', '1', 'release risk']) == 0
    assert 'Correct' in capsys.readouterr().out
    assert state.read_state(root)['brief_drill']['streak'] == 1
    assert metrics.collect(root)['brief_drill_score']['streak'] == 1
    assert main(['brief', 'answer', '2', 'irrelevant']) == 0
    assert 'Incorrect' in capsys.readouterr().out
    assert state.read_state(root)['brief_drill']['streak'] == 0
    assert main(['state', 'set', 'brief_drill.streak', '99']) == 1


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


def test_calendar_secret_in_event_is_not_published(root, monkeypatch, capsys):
    secret = 'https://private.test/feed?token=hidden'
    monkeypatch.setenv('WUWEI_CALENDAR_URL', secret)
    class Calendar:
        def events(self, since, until, root=None):
            return registry.Result(0, [{'uid': 'review-2', 'start': '2026-09-29T12:30:00+00:00',
                                        'summary': f'Review {secret}', 'attendees': ['pat@example.test']}])
    old_load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: Calendar() if kind == 'calendar' else old_load(kind, config))
    assert main(['brief', 'pack', '--meeting']) == 0
    output = capsys.readouterr().out.strip()
    assert secret not in (root / output).read_text()
    assert secret not in (workspace.day_dir(root) / 'state.json').read_text()
    assert secret not in (workspace.day_dir(root) / 'events.jsonl').read_text()


def test_feedback_is_recorded_with_streak(root, capsys):
    assert main(['brief', 'pack']) == 0
    capsys.readouterr()
    assert main(['brief', 'answer', '1', 'release risk']) == 0
    entry = state.read_state(root)['brief_packs']['daily']['answers']['1']
    assert entry['feedback'].startswith('Correct')
    assert entry['streak'] == 1


def test_calendar_failure_does_not_publish_pack(root, monkeypatch, capsys):
    class Calendar:
        def events(self, since, until, root=None):
            return registry.Result(2, reason='private feed token')
    monkeypatch.setattr(registry, 'load', lambda kind, config: Calendar())
    assert main(['brief', 'pack', '--meeting']) == 2
    assert 'private feed token' not in capsys.readouterr().err
    assert not list((root / '.wuwei').rglob('pack-meeting-*.md'))


def test_recent_transcript_can_inform_pack(root, monkeypatch, capsys):
    class Transcripts:
        def recent(self, since, root=None):
            return registry.Result(0, [{'summary': 'Customer asked about launch timing'}])
    old_load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: Transcripts() if kind == 'transcripts' else old_load(kind, config))
    assert main(['brief', 'pack']) == 0
    assert 'Customer asked about launch timing' in (root / capsys.readouterr().out.strip()).read_text()


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


def test_recorded_metric_appears_in_visual(root, monkeypatch, capsys):
    from wuwei import metrics
    monkeypatch.setattr(metrics, 'collect', lambda root: {'fix_rounds_per_item': {'ISSUE-1': 3}})
    assert main(['brief', 'pack']) == 0
    assert 'ISSUE-1: 3 fix rounds' in (root / capsys.readouterr().out.strip()).read_text()


def test_untrusted_decision_html_is_escaped(root, capsys):
    (workspace.day_dir(root) / 'decisions/D-1.md').write_text('Outcome: <script>alert(1)</script>\n')
    assert main(['brief', 'pack']) == 0
    pack = (root / capsys.readouterr().out.strip()).read_text()
    assert '<script>' not in pack
    assert '&lt;script&gt;' in pack


def test_pack_rejects_linked_briefs_directory(root, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    directory = workspace.day_dir(root)
    (directory / 'briefs').symlink_to(outside, target_is_directory=True)
    assert main(['brief', 'pack']) == 2
    assert not list(outside.iterdir())


def test_pack_rejects_linked_audio_target(root, tmp_path):
    directory = workspace.day_dir(root) / 'briefs'
    directory.mkdir()
    target = tmp_path / 'outside.aiff'
    (directory / 'pack-daily.aiff').symlink_to(target)
    assert main(['brief', 'pack']) == 2
    assert not target.exists()
