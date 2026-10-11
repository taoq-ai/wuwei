"""Serve the read-only day board to Claude Code as a stdio MCP server."""

import json
import os
from pathlib import Path
import sys

from wuwei import state, workspace
from wuwei.commands import dashboard, status
from wuwei.exits import CLEAN
from wuwei.integrity import PLUGIN


URI = 'ui://wuwei/board.html'
MIME = 'text/html;profile=mcp-app'
TOOL = {'name': 'wuwei_board', 'title': 'WUWEI day board',
        'description': ("Read-only view of today's WUWEI board: items by phase with status and "
                        'gate verdicts, owned PRs and what they wait on, pending decisions, pages '
                        'and nudges, the status line, and why each item is where it is (why.json). '
                        'Takes no arguments and writes nothing.'),
        'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        '_meta': {'ui': {'resourceUri': URI}}}


def register(subparsers):
    parser = subparsers.add_parser('board', help='serve the day board to Claude Code over MCP stdio')
    parser.set_defaults(func=run)


def run(args):
    return serve(sys.stdin, sys.stdout)


def serve(stdin, stdout):
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            reply = _reply(None, error=(-32700, 'parse error'))
        else:
            reply = handle(message)
        if reply is not None:
            stdout.write(json.dumps(reply) + '\n')
            # The CLI's redacting stdout does not flush on newline; the host waits on each reply.
            stdout.flush()
    return CLEAN


def _reply(id, result=None, error=None):
    if error:
        return {'jsonrpc': '2.0', 'id': id, 'error': {'code': error[0], 'message': error[1]}}
    return {'jsonrpc': '2.0', 'id': id, 'result': result}


def handle(message):
    if not isinstance(message, dict):
        return _reply(None, error=(-32600, 'invalid request'))
    if 'id' not in message:
        return None
    id, method = message['id'], message.get('method')
    params = message.get('params') if isinstance(message.get('params'), dict) else {}
    if method == 'initialize':
        version = params.get('protocolVersion')
        plugin = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
        return _reply(id, {'protocolVersion': version if isinstance(version, str) else '2025-06-18',
                           'capabilities': {'tools': {}, 'resources': {}},
                           'serverInfo': {'name': 'wuwei', 'version': plugin['version']}})
    if method == 'ping':
        return _reply(id, {})
    if method == 'tools/list':
        return _reply(id, {'tools': [TOOL]})
    if method == 'tools/call':
        if params.get('name') != TOOL['name']:
            return _reply(id, error=(-32602, 'unknown tool'))
        return _reply(id, call())
    if method == 'resources/list':
        return _reply(id, {'resources': [{'uri': URI, 'name': 'wuwei-board', 'mimeType': MIME}]})
    if method == 'resources/read':
        if params.get('uri') != URI:
            return _reply(id, error=(-32602, 'unknown resource'))
        return _reply(id, {'contents': [{'uri': URI, 'mimeType': MIME,
                                         'text': dashboard.TEMPLATE.read_text(encoding='utf-8')}]})
    return _reply(id, error=(-32601, 'method not found'))


def _text(text, error=False):
    return {'content': [{'type': 'text', 'text': text}], 'isError': error}


def call():
    try:
        root = workspace.guard_scope({'cwd': os.environ.get('CLAUDE_PROJECT_DIR') or str(Path.cwd())})
        if root is None:
            return _text('No WUWEI workspace here; run bin/wuwei init to create one.')
        text, files = read(root)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError) as exc:
        return _text(f'WUWEI board unmeasured: {exc}', True)
    return {**_text(text), 'structuredContent': files}


def _cell(value):
    return ' '.join(str(value).split()).replace('|', '\\|')


def _table(title, header, rows):
    lines = ['', f'## {title}']
    if not rows:
        return lines + ['None']
    lines += ['| ' + ' | '.join(header) + ' |', '| ' + ' | '.join('---' for _ in header) + ' |']
    return lines + ['| ' + ' | '.join(_cell(value) for value in row) + ' |' for row in rows]


def _telemetry(root, data):
    """#422: the current week's aggregate, or unmeasured with the reason today's step skipped."""
    from wuwei import telemetry
    skipped = data.get('watch', {}).get('telemetry', {}).get('skipped')
    if skipped:
        return [('unmeasured', skipped)]
    found = telemetry.load_week(root, telemetry.current_week(root))
    if found is None:
        return [('unmeasured', 'no aggregate yet')]
    return [(key, json.dumps(value)) for key, value in found['metrics'].items()]


def read(root):
    directory = workspace.day_dir(root)
    cockpit = dashboard.cockpit_snapshot(directory)
    data = state.read_state(directory=directory)
    path = directory / 'events.jsonl'
    events = path.read_text(encoding='utf-8') if path.exists() else ''
    order = list(state.PHASES)
    from wuwei import docs
    config = workspace.load_config(root)
    work = []
    log = data.get('tracker_log', {}).values()
    for name, item in sorted(data['items'].items(), key=lambda row: order.index(row[1]['phase'])):
        gates = ', '.join(f"{v['role']} {v['round']}: {v['verdict']}"
                          for v in data['gate_verdicts'].values() if v.get('item') == name)
        ticket = data.get('tickets', {}).get(name, {}).get('id')
        folded = sum(row.get('ticket') == ticket and row.get('outcome') == 'folded' for row in log)
        work.append((name + (' (adopted)' if item.get('source') == 'adopted' else ''),
                     item['phase'], item['status'],
                     (ticket + (f', {folded} folded' if folded else '')) if ticket else 'none',
                     gates or 'none', item.get('pr_url') or 'none', docs.shown(config, item)))
    created = [json.loads(line).get('payload', {}) for line in events.splitlines()
               if '"tracker.created"' in line]
    lines = [status.line(cockpit['status']),
             *_table('Work', ('Item', 'Phase', 'Status', 'Ticket', 'Gates', 'PR', 'Docs'), work),
             *_table('Tickets created', ('Class', 'Subject', 'Ticket', 'Parent', 'Seat'),
                     [(row.get('class'), row.get('subject'), row.get('ticket'), row.get('parent') or 'none',
                       row.get('seat') or 'none') for row in created]),
             *_table('PRs', ('PR', 'State', 'Waiting on', 'Deadline'),
                     [(r['ref'], r['state'], r['waiting_on'], r['deadline']) for r in cockpit['prs']]),
             *_table('Decisions', ('Id', 'Question', 'Route', 'Command'),
                     [(r['id'], r['question'], r['route'], r['command']) for r in cockpit['decisions']]),
             *_table('Telemetry', ('Metric', 'Value'), _telemetry(root, data)),
             *_table('Attention', ('Tier', 'Lane', 'Reason'),
                     [(r['tier'], r['lane'], r['reason'])
                      for r in status.surfaced(directory, status.attention(directory), data)[1]]),
             '', 'Full cockpit: run bin/wuwei dashboard and open the printed loopback URL.']
    files = {'./board.json': json.dumps(dashboard.board_snapshot(directory)),
             './state.json': json.dumps(data), './events.jsonl': events,
             './cockpit.json': json.dumps(cockpit)}
    from wuwei.commands import why
    try:
        chains = {name: why.render(why.item(root, name), why.level(root, False), root) for name in data['items']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, why.Missing) as exc:
        chains = {'unmeasured': str(exc)}
    files['./why.json'] = json.dumps(chains)
    return '\n'.join(lines), files
