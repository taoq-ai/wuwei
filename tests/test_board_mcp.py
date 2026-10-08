"""The day board MCP server: protocol, read-only tool, UI resource and shipping."""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_dashboard import D3

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-09-28T12:34:56+02:00'
PR = 'https://example.test/pull/1'


def rpc(*messages):
    from wuwei.commands import board
    lines = [m if isinstance(m, str) else json.dumps(m) for m in messages]
    out = io.StringIO()
    assert board.serve(io.StringIO('\n'.join(lines) + '\n'), out) == 0
    return [json.loads(line) for line in out.getvalue().splitlines()]


def call(method, params=None, id=1):
    return {'jsonrpc': '2.0', 'id': id, 'method': method, 'params': params or {}}


def board_call():
    return rpc(call('tools/call', {'name': 'wuwei_board', 'arguments': {}}))[0]['result']


@pytest.fixture
def day(tmp_path, monkeypatch):
    day = tmp_path / '.wuwei/days/2026-09-28'
    (day / 'decisions').mkdir(parents=True)
    (day / 'decisions/D-3.md').write_text(D3)
    (tmp_path / '.wuwei/config.toml').write_text('')
    (day / 'state.json').write_text(json.dumps({
        'cap': 3, 'raised_prs': [PR],
        'items': {'b': {'phase': 'planned'},
                  'a': {'phase': 'implement', 'status': 'running', 'pr_url': PR}},
        'gate_verdicts': {'a:security:gate': {'item': 'a', 'role': 'security',
                                              'round': 'gate', 'verdict': 'pass'}},
        'watch': {'actions': {PR: {'state': 'ci_red', 'action': 'start a fix round',
                                   'deadline': '2026-09-28T15:00:00+02:00'}}},
        'decision_routes': {'D-3': {'reversibility': 'one-way', 'recommendation': 'A'}}}))
    (day / 'events.jsonl').write_text(json.dumps({'kind': 'security.finding', 'ts': NOW}) + '\n')
    monkeypatch.setenv('WUWEI_NOW', NOW)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('CLAUDE_PROJECT_DIR', str(tmp_path))
    return day


def test_tools_list_and_ui_resource():
    init, tools, listed, read = rpc(
        call('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}}),
        call('tools/list', id=2), call('resources/list', id=3),
        call('resources/read', {'uri': 'ui://wuwei/board.html'}, id=4))
    assert init['result']['protocolVersion'] == '2025-06-18'
    assert init['result']['serverInfo']['name'] == 'wuwei'
    [tool] = tools['result']['tools']
    assert tool['name'] == 'wuwei_board'
    assert tool['inputSchema'] == {'type': 'object', 'properties': {}, 'additionalProperties': False}
    assert tool['annotations']['readOnlyHint'] is True
    assert tool['annotations']['destructiveHint'] is False
    assert tool['_meta'] == {'ui': {'resourceUri': 'ui://wuwei/board.html'}}
    assert listed['result']['resources'] == [{'uri': 'ui://wuwei/board.html', 'name': 'wuwei-board',
                                              'mimeType': 'text/html;profile=mcp-app'}]
    [content] = read['result']['contents']
    assert content['mimeType'] == 'text/html;profile=mcp-app'
    assert content['text'] == (ROOT / 'templates/dashboard.html').read_text(encoding='utf-8')


def test_protocol_errors_keep_serving():
    replies = rpc('{nope', '[]', {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                  call('unknown/method', id=2), call('tools/call', {'name': 'other'}, id=3),
                  call('resources/read', {'uri': 'ui://other'}, id=4), call('ping', id=5))
    assert [(r.get('id'), r.get('error', {}).get('code')) for r in replies] == [
        (None, -32700), (None, -32600), (2, -32601), (3, -32602), (4, -32602), (5, None)]
    assert replies[-1]['result'] == {}


def test_issue_acceptance_board_matches_status_and_dashboard(day):
    from wuwei import state
    from wuwei.commands import dashboard, status
    result = board_call()
    assert result['isError'] is False
    text = result['content'][0]['text']
    lines = text.splitlines()
    assert lines[0] == status.line(status.snapshot(day))
    work = [line for line in lines if line.startswith('| a |') or line.startswith('| b |')]
    assert [line[2] for line in work] == ['b', 'a']
    for part in ('implement', 'running', 'security gate: pass', PR):
        assert part in work[1]
    assert any(PR in line and 'ci_red' in line and 'start a fix round' in line for line in lines)
    assert any('D-3' in line and 'Choose <fix>?' in line and 'owner' in line
               and 'bin/wuwei decision route D-3' in line for line in lines)
    attention = text.split('## Attention', 1)[1].splitlines()
    assert len([line for line in attention if line.startswith('| ') and '---' not in line]) == \
        len(status.attention(day)) + 1
    assert lines[-1].startswith('Full cockpit:')
    files = result['structuredContent']
    assert json.loads(files['./board.json']) == {**dashboard.board_snapshot(day),
                                                 'build_phases': list(state.BUILD_PHASES)}
    assert json.loads(files['./state.json']) == state.read_state(directory=day)
    assert files['./events.jsonl'] == (day / 'events.jsonl').read_text()
    assert json.loads(files['./cockpit.json']) == dashboard.cockpit_snapshot(day)


def test_scope_and_unmeasured(day, tmp_path, monkeypatch):
    from wuwei.commands import board
    outside = tmp_path.parent / (tmp_path.name + '-outside')
    outside.mkdir()
    monkeypatch.setenv('CLAUDE_PROJECT_DIR', str(outside))
    result = board_call()
    assert result['content'][0]['text'] == 'No WUWEI workspace here; run bin/wuwei init to create one.'
    assert result['isError'] is False and 'structuredContent' not in result

    monkeypatch.setenv('CLAUDE_PROJECT_DIR', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T09:00:00+02:00')
    result = board_call()
    assert result['content'][0]['text'].startswith('WUWEI no plan yet')
    assert not (tmp_path / '.wuwei/days/2026-09-29').exists()

    monkeypatch.setenv('WUWEI_NOW', NOW)
    (day / 'state.json').write_text('{corrupt')
    result = board_call()
    assert result['isError'] is True
    assert result['content'][0]['text'].startswith('WUWEI board unmeasured:')
    assert 'structuredContent' not in result
    assert board._cell('x|y\nz') == 'x\\|y z'


def test_issue_acceptance_no_write_path(day, tmp_path, monkeypatch):
    from wuwei import state, workspace

    def tree():
        return {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    before = tree()

    def refuse(*_, **__):
        raise AssertionError('board wrote')

    monkeypatch.setattr(workspace, 'atomic_write', refuse)
    monkeypatch.setattr(state, 'append_event', refuse)
    replies = rpc(call('initialize'), call('ping'), call('tools/list'), call('resources/list'),
                  call('resources/read', {'uri': 'ui://wuwei/board.html'}), call('unknown'),
                  call('tools/call', {'name': 'wuwei_board'}))
    assert replies[-1]['result']['isError'] is False
    assert tree() == before


def test_bin_wuwei_board_smoke(tmp_path):
    lines = [json.dumps(call('initialize', {'protocolVersion': '2025-06-18'}, id=1)),
             json.dumps(call('tools/list', id=2))]
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'board'],
                            input='\n'.join(lines) + '\n',
                            env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli')}, cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert [r['id'] for r in replies] == [1, 2]
    assert replies[1]['result']['tools'][0]['name'] == 'wuwei_board'


@pytest.mark.skipif(shutil.which('node') is None, reason='node unavailable')
def test_template_renders_from_tool_result(day):
    page = (ROOT / 'templates/dashboard.html').read_text()
    script = page.split('<script>', 1)[1].split('</script>', 1)[0]
    content = board_call()['structuredContent']
    forged = {**content, './state.json': json.dumps({'cap': 1, 'items': {'FORGED-MARK': {}}})}
    harness = '''
const cells = Object.fromEntries(['blocked','blocked-count','blocked-items','columns','updated','error',
  'decisions','drafts','people','prs','signals','signal-events','briefing']
  .map(id => [id, {innerHTML:'', textContent:'', hidden:false}]));
global.document = {getElementById: id => cells[id]};
global.setInterval = () => {};
global.fetch = async () => { throw new Error('no fetch in a frame'); };
const methods = [], listeners = [];
const deliver = (data, source) => listeners.forEach(fn => fn({data, source}));
const host = {postMessage(message) {
  methods.push(message.method);
  if (message.method === 'ui/initialize') {
    deliver({jsonrpc: '2.0', method: 'ui/notifications/tool-result',
             params: {structuredContent: FORGED}}, {});
    deliver({jsonrpc: '2.0', id: 1, result: {}}, host);
  }
  if (message.method === 'ui/notifications/initialized')
    deliver({jsonrpc: '2.0', method: 'ui/notifications/tool-result',
             params: {structuredContent: CONTENT}}, host);
}};
global.window = {parent: host, addEventListener: (type, fn) => type === 'message' && listeners.push(fn)};
SCRIPT
setImmediate(() => process.stdout.write(JSON.stringify({cells, methods})));
'''
    source = (harness.replace('FORGED', json.dumps(forged)).replace('CONTENT', json.dumps(content))
              .replace('SCRIPT', script))
    result = subprocess.run(['node', '-e', source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    cells = output['cells']
    assert output['methods'] == ['ui/initialize', 'ui/notifications/initialized']
    assert '<strong>a</strong>' in cells['columns']['innerHTML']
    assert '<strong>b</strong>' in cells['columns']['innerHTML']
    assert 'D-3' in cells['decisions']['innerHTML']
    assert 'Choose &lt;fix&gt;?' in cells['decisions']['innerHTML']
    assert 'ci_red' in cells['prs']['innerHTML']
    assert cells['error']['textContent'] == ''
    assert 'FORGED-MARK' not in result.stdout


def test_plugin_json_declares_one_stdio_server():
    # A root .mcp.json would double as a project server of every WUWEI checkout.
    assert not (ROOT / '.mcp.json').exists()
    plugin = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
    assert plugin['mcpServers'] == {'cockpit': {
        'command': '${CLAUDE_PLUGIN_ROOT}/bin/wuwei', 'args': ['board'],
        'env': {'CLAUDE_PROJECT_DIR': '${CLAUDE_PROJECT_DIR}'}}}


def test_board_exposes_the_why_chain_per_item(day):
    from wuwei.commands import why
    root = day.parents[2]
    (day / 'events.jsonl').write_text(json.dumps({'kind': 'note', 'payload': {}, 'ts': NOW}) + '\n')
    chains = json.loads(board_call()['structuredContent']['./why.json'])
    assert chains == {name: why.render(why.item(root, name), 'brief', root) for name in ('a', 'b')}
    assert chains['b'][-1] == 'now: planned (queued)'


def test_board_why_chain_unmeasured_never_fails_the_board(day):
    result = board_call()
    assert result['isError'] is False
    assert list(json.loads(result['structuredContent']['./why.json'])) == ['unmeasured']


def test_board_telemetry_table(day, tmp_path):
    # #422: the current week's aggregate, or unmeasured with the reason the step skipped.
    def table():
        text = board_call()['content'][0]['text']
        return text.split('## Telemetry', 1)[1].split('\n## ', 1)[0]
    assert '| unmeasured | no aggregate yet |' in table()
    (tmp_path / '.wuwei/metrics').mkdir()
    (tmp_path / '.wuwei/metrics/2026-W40.json').write_text(json.dumps(
        {'week': '2026-W40', 'metrics': {'days': 1, 'refusals': {'pr': 2}}}))
    assert '| days | 1 |' in table() and '| refusals | {"pr": 2} |' in table()
    data = json.loads((day / 'state.json').read_text())
    data['watch']['telemetry'] = {'week': '2026-W40', 'skipped': 'size'}
    (day / 'state.json').write_text(json.dumps(data))
    assert '| unmeasured | size |' in table() and '| days |' not in table()


def test_board_work_table_has_a_docs_column(day, tmp_path):
    (tmp_path / '.wuwei/config.toml').write_text('[docs]\nsystem = "notion"\n')
    data = json.loads((day / 'state.json').read_text())
    data['items']['a']['gates'] = {'tier': 'standard'}
    (day / 'state.json').write_text(json.dumps(data))
    lines = board_call()['content'][0]['text'].splitlines()
    assert '| Item | Phase | Status | Ticket | Gates | PR | Docs |' in lines
    assert next(line for line in lines if line.startswith('| a |')).endswith('| missing |')
    assert next(line for line in lines if line.startswith('| b |')).endswith('| n/a |')


def test_board_marks_adopted_items(day):
    data = json.loads((day / 'state.json').read_text())
    data['items']['PR-8'] = {'phase': 'raised', 'source': 'adopted'}
    (day / 'state.json').write_text(json.dumps(data))
    lines = board_call()['content'][0]['text'].splitlines()
    assert any(line.startswith('| PR-8 (adopted) | raised |') for line in lines)
    assert any(line.startswith('| a | implement |') for line in lines)


def test_board_shows_tickets(day):
    data = json.loads((day / 'state.json').read_text())
    data['tickets'] = {'a': {'id': 'ENG-1', 'source': 'create'}}
    data['tracker_log'] = {'progress:a:1': {'outcome': 'folded', 'ticket': 'ENG-1'}}
    (day / 'state.json').write_text(json.dumps(data))
    with (day / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'kind': 'tracker.created', 'ts': NOW, 'payload': {
            'class': 'bugs', 'subject': 'a', 'ticket': 'ENG-2', 'parent': 'ENG-1'}}) + '\n')
    text = board_call()['content'][0]['text']
    assert '| Item | Phase | Status | Ticket | Gates | PR |' in text
    row, = [line for line in text.splitlines() if line.startswith('| a |')]
    assert '| ENG-1, 1 folded |' in row
    created = text.split('## Tickets created', 1)[1].splitlines()
    assert '| bugs | a | ENG-2 | ENG-1 |' in created


def test_board_shows_running_seats_per_goal(day):
    data = json.loads((day / 'state.json').read_text())
    data['items']['a']['goal'] = 'G-1'
    data.update(gate_approved=True, seats={'a-1': {'id': 'a-1', 'role': 'builder', 'item': 'a',
                                                   'status': 'running'}})
    (day / 'state.json').write_text(json.dumps(data))
    assert 'seats 1/3 (G-1 1)' in board_call()['content'][0]['text'].splitlines()[0]
