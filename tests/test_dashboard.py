"""Dashboard command, HTTP boundary, and rendered board behavior."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from wuwei.workspace import owner_cli

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:34:56+02:00'


def test_dashboard_cli_help_uses_current_interpreter():
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'dashboard', '--help'],
                            env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--host' not in result.stdout
    assert '--serve' not in result.stdout


@pytest.fixture
def workspace(tmp_path):
    day = tmp_path / '.wuwei/days/2026-09-28'
    day.mkdir(parents=True)
    (day / 'state.json').write_text('{"items":{},"cap":3}\n')
    (day / 'events.jsonl').write_text('')
    (day / 'briefs').mkdir()
    (day / 'briefs/private.md').write_text('secret')
    return tmp_path


def test_dashboard_serves_in_memory_without_writing_day(workspace, monkeypatch, capsys):
    from wuwei.commands import dashboard
    day = workspace / '.wuwei/days/2026-09-28'
    before = {p.relative_to(day): p.read_bytes() for p in day.rglob('*') if p.is_file()}
    seen = {}

    class FakeServer:
        server_port = 8123

        def __init__(self, address, handler):
            seen['address'] = address
            seen['handler'] = handler

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setenv('WUWEI_WORKSPACE', str(workspace))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    monkeypatch.setattr(dashboard, 'ThreadingHTTPServer', FakeServer)
    assert dashboard.run(None) == 0
    assert seen['address'] == ('127.0.0.1', 0)
    assert capsys.readouterr().out.strip() == 'Serving on http://127.0.0.1:8123/'
    assert seen['handler'].keywords['page'].lower().startswith(b'<!doctype html>')
    board = json.loads(seen['handler'].keywords['board'])
    assert board['phases'] == ['planned', 'spec', 'implement', 'gate', 'fix', 'delta', 'raised', 'merged']
    assert board['build_phases'] == ['spec', 'implement', 'fix']
    assert board['cap'] == 3
    assert {p.relative_to(day): p.read_bytes() for p in day.rglob('*') if p.is_file()} == before


def test_board_snapshot_and_template_are_shared(workspace):
    from wuwei.commands import dashboard
    day = workspace / '.wuwei/days/2026-09-28'
    assert dashboard.board_snapshot(day) == {
        'phases': ['planned', 'spec', 'implement', 'gate', 'fix', 'delta', 'raised', 'merged'],
        'build_phases': ('spec', 'implement', 'fix'), 'cap': 3}
    assert dashboard.TEMPLATE == ROOT / 'templates/dashboard.html'


def test_http_allows_only_board_resources_and_loopback_host(workspace):
    from io import BytesIO
    from wuwei.commands.dashboard import DayHandler

    day = workspace / '.wuwei/days/2026-09-28'
    for path, host, expected in [
        ('/state.json?t=1', '127.0.0.1:8123', 200),
        ('/events.jsonl', '127.0.0.1:8123', 200),
        ('/briefs/private.md', '127.0.0.1:8123', 404),
        ('/briefs/', '127.0.0.1:8123', 404),
        ('/state.json', 'attacker.example', 403),
    ]:
        handler = object.__new__(DayHandler)
        handler.directory = day
        handler.page = b'page'
        handler.board = b'{}'
        handler.path = path
        handler.headers = {'Host': host}
        handler.server = type('Server', (), {'server_port': 8123})()
        handler.wfile = BytesIO()
        statuses = []
        handler.send_response = lambda code, statuses=statuses: statuses.append(code)
        handler.send_header = lambda *_: None
        handler.end_headers = lambda: None
        handler.send_error = lambda code, statuses=statuses: statuses.append(code)
        handler.do_GET()
        assert statuses == [expected], (path, host)


@pytest.mark.skipif(shutil.which('node') is None, reason='node unavailable')
def test_page_renders_columns_other_and_escalated_decision():
    page = (ROOT / 'templates/dashboard.html').read_text()
    script = page.split('<script>', 1)[1].split('</script>', 1)[0]
    board = {'phases': ['planned', 'spec', 'implement', 'gate', 'fix', 'delta', 'raised', 'merged'],
             'build_phases': ['spec', 'implement', 'fix'], 'cap': 1}
    state = {'cap': '<img src=x>', 'items': {
        'mystery': {'phase': 'future', 'repo': 'sample'},
        'blocked': {'phase': 'escalated', 'decision_id': 'D-3'},
        '<img src=x onerror=1>': {'phase': 'spec', 'status': 'queued',
                                  'repo': '<b>r</b>', 'pr_url': 'javascript:alert(1)'},
        'old': {'phase': 'planned', 'updated_at': '2026-09-28T12:00:00+02:00'},
    }}
    events = [{'kind': 'state.transition', 'payload': {'item': 'blocked'},
               'ts': '2026-09-28T12:04:56+02:00'}]
    harness = '''
const cells = Object.fromEntries(['blocked','blocked-count','blocked-items','columns','updated','error',
  'decisions','drafts','people','prs','signals','signal-events','briefing']
  .map(id => [id, {innerHTML:'', textContent:'', hidden:false}]));
global.document = {getElementById: id => cells[id]};
Date.now = () => Date.parse('2026-09-28T12:34:56+02:00');
global.setInterval = () => {};
const files = {'./board.json': JSON.stringify(BOARD), './state.json': JSON.stringify(STATE),
  './events.jsonl': EVENTS.map(e => JSON.stringify(e)).join('\\n'),
  './cockpit.json': JSON.stringify(COCKPIT)};
global.fetch = async url => ({ok:true, text:async () => files[url.split('?')[0]]});
SCRIPT
setImmediate(() => process.stdout.write(JSON.stringify(cells)));
'''
    cockpit = {'drafts': [{'id': 'draft-test', 'text': '<script>private</script>',
               'destination': '<channel>', 'tier_reason': 'approve',
               'approve_command': 'bin/wuwei drafts approve draft-test'}], 'decisions': [{'id': 'D-3', 'question': '<owner>?', 'route': 'owner',
               'options': [{'id': 'A', 'description': '<script>alert(1)</script>'}],
               'record': 'Question: <owner>?', 'command': 'bin/wuwei decision route D-3' }],
               'people': [{'person': '<Ada>', 'reason': 'reply', 'due': NOW}],
               'prs': [{'ref': 'javascript:alert(1)', 'state': 'unmeasured',
                        'last_action': 'unmeasured', 'waiting_on': 'unmeasured',
                        'deadline': 'unmeasured'}],
               'status': {'pages': 1, 'nudges': 2},
               'signals': [{'kind': '<bad>', 'tier': 'page', 'lane': 'Work'}],
               'briefing': 'Today <important>'}
    source = (harness.replace('BOARD', json.dumps(board)).replace('STATE', json.dumps(state))
              .replace('EVENTS', json.dumps(events)).replace('COCKPIT', json.dumps(cockpit))
              .replace('SCRIPT', script))
    result = subprocess.run(['node', '-e', source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    cells = json.loads(result.stdout)
    columns = cells['columns']['innerHTML']
    assert columns.count('class="column ') == 9
    assert 'WIP 1' in columns
    assert 'CAP 0/&lt;img src=x&gt;' in columns
    assert 'CAP 0/<img src=x>' not in columns
    assert 'WIP 1 | CAP 0/&lt;img src=x&gt;' in columns
    assert 'class="card stale"><strong>old</strong>' in columns
    rendered = columns + cells['blocked-items']['innerHTML']
    assert '&lt;img src=x onerror=1&gt;' in rendered
    assert '&lt;b&gt;r&lt;/b&gt;' in rendered
    assert '<img' not in rendered
    assert '<b>' not in rendered
    assert 'javascript:' not in rendered
    assert '<h3>other ' in columns and '<strong>mystery</strong>' in columns
    assert '<strong>blocked</strong>' not in columns
    assert cells['blocked']['hidden'] is False
    assert '<strong>blocked</strong>' in cells['blocked-items']['innerHTML']
    assert 'D-3' in cells['blocked-items']['innerHTML']
    assert '30m' in cells['blocked-items']['innerHTML']
    assert cells['error']['textContent'] == ''
    assert 'bin/wuwei drafts approve draft-test' in cells['drafts']['innerHTML']
    assert '&lt;script&gt;private&lt;/script&gt;' in cells['drafts']['innerHTML']
    assert '<script>' not in cells['drafts']['innerHTML']
    assert 'D-3' in cells['decisions']['innerHTML']
    assert 'bin/wuwei decision route D-3' in cells['decisions']['innerHTML']
    assert '&lt;owner&gt;' in cells['decisions']['innerHTML']
    assert '<script>' not in cells['decisions']['innerHTML']
    assert '&lt;Ada&gt;' in cells['people']['innerHTML']
    assert 'unmeasured' in cells['prs']['innerHTML']
    assert 'href="javascript:' not in cells['prs']['innerHTML']
    assert '1 page' in cells['signals']['textContent']
    assert '2 nudges' in cells['signals']['textContent']
    assert '&lt;bad&gt;' in cells['signal-events']['innerHTML']
    assert 'Today <important>' in cells['briefing']['textContent']


@pytest.mark.skipif(shutil.which('node') is None, reason='node unavailable')
def test_page_keeps_work_board_when_cockpit_fetch_fails():
    page = (ROOT / 'templates/dashboard.html').read_text()
    script = page.split('<script>', 1)[1].split('</script>', 1)[0]
    source = '''
const cells = Object.fromEntries(['blocked','blocked-count','blocked-items','columns','updated','error']
  .map(id => [id, {innerHTML:'', textContent:'', hidden:false}]));
global.document = {getElementById: id => cells[id]};
global.setInterval = () => {};
global.fetch = async url => url.startsWith('./cockpit.json') ? {ok:false, status:503} :
  {ok:true, text:async () => ({'./board.json':'{"phases":["planned"],"build_phases":[],"cap":1}',
    './state.json':'{"items":{"task":{"phase":"planned"}},"cap":1}',
    './events.jsonl':''})[url.split('?')[0]]};
SCRIPT
setImmediate(() => process.stdout.write(JSON.stringify(cells)));
'''.replace('SCRIPT', script)
    result = subprocess.run(['node', '-e', source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    cells = json.loads(result.stdout)
    assert '<strong>task</strong>' in cells['columns']['innerHTML']
    assert './cockpit.json 503' in cells['error']['textContent']


def test_build_phases_are_state_phases():
    from wuwei.state import BUILD_PHASES, PHASES
    assert set(BUILD_PHASES) <= set(PHASES)
    assert BUILD_PHASES == ('spec', 'implement', 'fix')


D3 = '''Question: Choose <fix>?
Context: Tests fail.
Options:
| Option | Description |
| --- | --- |
| A | Fix now |
| B | Defer |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Value | 10 | 8 | 2 |
Recommendation: A
Confidence: high
Reversibility: one-way
Blast radius: team
Pre-mortem: Regression.
Revisit: Tomorrow.
Decided-by: owner
Outcome: pending
'''


def test_cockpit_snapshot_reads_pending_records_and_optional_lanes(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot

    day = workspace / '.wuwei/days/2026-09-28'
    decision = day / 'decisions'
    decision.mkdir()
    (decision / 'D-3.md').write_text(D3)
    (decision / 'C-2.md').write_text('Question: Which scope?\nContext: owner needs to choose.\nOptions:\n- Keep\n- Defer\n')
    (day / 'briefs/pack-daily.md').write_text('Today <important>')
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3,
        'claimed_prs': ['https://example.test/pull/1'], 'raised_prs': [],
        'watch': {'actions': {'https://example.test/pull/1': {
            'state': 'ci_red', 'action': 'start a fix round',
            'deadline': '2026-09-28T15:00:00+02:00'}}},
        'brief_packs': {'daily': {'path': '.wuwei/days/2026-09-28/briefs/pack-daily.md'}},
        'drafts': {'draft-1': {'id': 'draft-1', 'channel': 'chat', 'operation': 'post', 'adapter': 'slack',
                               'destination': 'C1', 'inputs': {'channel': 'C1', 'text': 'hi'}, 'text': 'hi',
                               'created': '2026-09-29T12:00:00+00:00', 'tier_reason': 'approve tier',
                               'audience': 'default', 'status': 'pending', 'item': None}},
        'reply_obligations': [{'person': '<Ada>', 'due': NOW, 'reason': 'Review'}]}))
    (day / 'events.jsonl').write_text(json.dumps({'kind': 'security.finding',
                                                   'ts': NOW}) + '\n')
    monkeypatch.setenv('WUWEI_NOW', NOW)
    data = cockpit_snapshot(day)
    assert [(row['id'], row['route']) for row in data['decisions']] == [('C-2', 'owner'), ('D-3', 'owner')]
    assert data['decisions'][1]['question'] == 'Choose <fix>?'
    assert [row['description'] for row in data['decisions'][0]['options']] == ['Keep', 'Defer']
    assert [row['id'] for row in data['decisions'][1]['options']] == ['A', 'B']
    assert data['people'][0]['person'] == '<Ada>'
    assert data['prs'][0]['state'] == 'ci_red'
    assert data['prs'][0]['action'] == 'start a fix round'
    assert data['decisions'][1]['command'] == 'bin/wuwei decision route D-3'
    assert [row['id'] for row in data['drafts']] == ['draft-1']
    assert data['drafts'][0]['approve_command'] == f'{owner_cli(day.parents[2])} drafts approve draft-1'
    assert data['status']['pages'] == 1
    assert data['signals'] == [{'tier': 'page', 'lane': 'Work', 'kind': 'security.finding'}]
    assert data['briefing'] == 'Today <important>'


def test_cockpit_skips_owner_answered_decision_with_pending_line(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot
    day = workspace / '.wuwei/days/2026-09-28'
    (day / 'decisions').mkdir()
    (day / 'decisions/D-3.md').write_text(D3)
    (day / 'decisions/C-2.md').write_text('Question: Which scope?\nContext: owner needs to choose.\nOptions:\n- Keep\n- Defer\n')
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3, 'claimed_prs': [], 'raised_prs': [],
        'decision_outcomes': {'D-3': {'option': 'A', 'decided_by': 'owner'}}}))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert [row['id'] for row in cockpit_snapshot(day)['decisions']] == ['C-2']


def test_cockpit_two_owned_prs_keep_measured_actions_and_failures(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot
    day = workspace / '.wuwei/days/2026-09-28'
    refs = ['https://example.test/pull/1', 'https://example.test/pull/2']
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3,
        'raised_prs': refs, 'claimed_prs': [], 'watch': {'actions': {
            refs[0]: {'state': 'ci_red', 'action': 'start a fix round',
                      'deadline': '2026-09-28T15:00:00+02:00'},
            refs[1]: {'state': 'approved', 'action': 'wuwei merge or merge decision',
                      'deadline': '2026-09-28T16:00:00+02:00'}}}}))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    rows = cockpit_snapshot(day)['prs']
    assert [(row['state'], row['action'], row['deadline']) for row in rows] == [
        ('ci_red', 'start a fix round', '2026-09-28T15:00:00+02:00'),
        ('approved', 'wuwei merge or merge decision', '2026-09-28T16:00:00+02:00')]


def test_cockpit_unrecorded_pr_stays_unmeasured_and_does_not_write(workspace):
    from wuwei.commands.dashboard import cockpit_snapshot
    day = workspace / '.wuwei/days/2026-09-28'
    ref = 'https://example.test/pull/1'
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3,
        'raised_prs': [ref], 'claimed_prs': []}))
    before = {name: (day / name).read_bytes() for name in ('state.json', 'events.jsonl')}
    row = cockpit_snapshot(day)['prs'][0]
    assert row['state'] == 'unmeasured'
    assert row['action'] == row['deadline'] == 'unmeasured'
    assert row['waiting_on'] == 'run bin/wuwei pr state'
    assert {name: (day / name).read_bytes() for name in before} == before


def test_cockpit_reads_meeting_pack_recorded_today(workspace):
    from wuwei.commands.dashboard import cockpit_snapshot
    day = workspace / '.wuwei/days/2026-09-28'
    (day / 'briefs/pack-meeting-a1b2c3d4e5f60708.md').write_text('Meeting brief')
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3,
        'brief_packs': {'meeting-a1b2c3d4e5f60708': {
            'path': '.wuwei/days/2026-09-28/briefs/pack-meeting-a1b2c3d4e5f60708.md'}}}))
    assert cockpit_snapshot(day)['briefing'] == 'Meeting brief'


def test_cockpit_rejects_linked_briefs_directory(workspace, tmp_path):
    from wuwei.commands.dashboard import cockpit_snapshot
    day = workspace / '.wuwei/days/2026-09-28'
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'pack-daily.md').write_text('outside')
    (day / 'briefs/private.md').unlink()
    (day / 'briefs').rmdir()
    (day / 'briefs').symlink_to(outside, target_is_directory=True)
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3,
        'brief_packs': {'daily': {
            'path': '.wuwei/days/2026-09-28/briefs/pack-daily.md'}}}))
    with pytest.raises(ValueError, match='regular file'):
        cockpit_snapshot(day)


def test_cockpit_snapshot_marks_missing_producers_unmeasured(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot

    monkeypatch.setenv('WUWEI_NOW', NOW)
    data = cockpit_snapshot(workspace / '.wuwei/days/2026-09-28')
    assert data['prs'] == []
    assert data['people'] == 'unmeasured'
    assert data['briefing'] == 'unmeasured'


def test_cockpit_snapshot_uses_clarification_fields(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot

    day = workspace / '.wuwei/days/2026-09-28'
    decisions = day / 'decisions'
    decisions.mkdir()
    (decisions / 'C-1.md').write_text('''## Question: Which?
Options:
- Keep
- Defer
Context: owner decides.
''')
    monkeypatch.setenv('WUWEI_NOW', NOW)
    row = cockpit_snapshot(day)['decisions'][0]
    assert row['question'] == 'Which?'
    assert [option['description'] for option in row['options']] == ['Keep', 'Defer']


def test_http_cockpit_read_and_all_posts_refused_without_writes(workspace, monkeypatch):
    from io import BytesIO
    from wuwei.commands.dashboard import DayHandler

    day = workspace / '.wuwei/days/2026-09-28'
    monkeypatch.setenv('WUWEI_NOW', NOW)
    before = {p.relative_to(day): p.read_bytes() for p in day.rglob('*') if p.is_file()}
    for method, host, token, expected in [('GET', '127.0.0.1:8123', None, 200),
                                          ('GET', 'attacker.example', None, 403),
                                          ('POST', '127.0.0.1:8123', None, 405),
                                          ('POST', '127.0.0.1:8123', 'forged', 405),
                                          ('POST', 'attacker.example', 'forged', 403)]:
        handler = object.__new__(DayHandler)
        handler.directory = day
        handler.page = b'page'
        handler.board = b'{}'
        handler.path = '/cockpit.json'
        handler.headers = {'Host': host, **({'X-Session-Token': token} if token else {})}
        handler.server = type('Server', (), {'server_port': 8123})()
        handler.wfile = BytesIO()
        statuses = []
        handler.send_response = lambda code, statuses=statuses: statuses.append(code)
        handler.send_header = lambda *_: None
        handler.end_headers = lambda: None
        handler.send_error = lambda code, statuses=statuses: statuses.append(code)
        getattr(handler, 'do_' + method)()
        assert statuses == [expected], (method, host)
        if method == 'GET' and expected == 200:
            assert json.loads(handler.wfile.getvalue())['briefing'] == 'unmeasured'
    assert {p.relative_to(day): p.read_bytes() for p in day.rglob('*') if p.is_file()} == before


def test_cockpit_names_the_mcp_decide_command(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot

    day = workspace / '.wuwei/days/2026-09-28'
    (day / 'decisions').mkdir()
    (day / 'decisions/D-3.md').write_text(D3)
    (day / 'decisions/D-4.md').write_text(D3)
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3, 'claimed_prs': [], 'raised_prs': []}))
    status = workspace / '.wuwei/ziran/status.json'
    status.parent.mkdir()
    status.write_text(json.dumps({'exit': 1, 'day': '2026-09-28', 'reason': '', 'generation': 'g', 'reports': [],
                                  'pending': '.wuwei/days/2026-09-28/decisions/D-4.md'}))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    commands = {row['id']: row['command'] for row in cockpit_snapshot(day)['decisions']}
    assert commands == {'D-3': 'bin/wuwei decision route D-3', 'D-4': 'bin/wuwei mcp decide D-4 proceed'}
