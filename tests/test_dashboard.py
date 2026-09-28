"""Dashboard command, HTTP boundary, and rendered board behavior."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

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
  'decisions','people','prs','signals','signal-events','briefing']
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
    cockpit = {'decisions': [{'id': 'D-3', 'question': '<owner>?', 'route': 'owner',
               'options': [{'id': 'A', 'description': '<script>alert(1)</script>'}],
               'record': 'Question: <owner>?' }],
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
    assert 'D-3' in cells['decisions']['innerHTML']
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


def test_cockpit_snapshot_reads_pending_records_and_optional_lanes(workspace, monkeypatch):
    from wuwei.commands.dashboard import cockpit_snapshot

    day = workspace / '.wuwei/days/2026-09-28'
    decision = day / 'decisions'
    decision.mkdir()
    (decision / 'D-3.md').write_text('''Question: Choose <fix>?
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
''')
    (decision / 'C-2.md').write_text('Question: Which scope?\nContext: owner needs to choose.\nOptions:\n- Keep\n- Defer\n')
    (day / 'briefing-pack.md').write_text('Today <important>')
    (day / 'state.json').write_text(json.dumps({'items': {}, 'cap': 3,
        'claimed_prs': ['https://example.test/pull/1'], 'raised_prs': [],
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
    assert data['prs'][0]['state'] == 'unmeasured'
    assert data['status']['pages'] == 1
    assert data['signals'] == [{'tier': 'page', 'lane': 'Work', 'kind': 'security.finding'}]
    assert data['briefing'] == 'Today <important>'


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
