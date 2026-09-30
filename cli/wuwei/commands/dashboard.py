"""Serve a passive view of today's state on loopback."""

from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from wuwei import brief_pack, drafts, state, workspace
from wuwei.decision import answered, clarification_fields, evaluate, lint_clarification, route
from wuwei.commands.status import snapshot as status_snapshot
from wuwei.signal import classify
from wuwei.exits import CLEAN


def cockpit_snapshot(directory):
    """Read today's owner surfaces without recording any outcome."""
    directory = Path(directory)
    data = state.read_state(directory=directory)
    decisions = []
    for path in sorted((directory / 'decisions').glob('*.md')):
        if path.is_symlink() or not path.name.startswith(('D-', 'C-')):
            continue
        content = path.read_text(encoding='utf-8')
        if path.name.startswith('D-'):
            fields, _ = evaluate(content)
            if fields['Outcome'].lower() != 'pending' or answered(data, path.stem):
                continue
            lines = fields['Options'].splitlines()
            options = [{'id': cells[0], 'description': cells[1]} for line in lines
                       if len(cells := [part.strip() for part in line.strip().strip('|').split('|')]) == 2
                       and cells[0] not in ('Option', '---')]
            decision_route = route(fields)
            question = fields['Question']
        else:
            fields = clarification_fields(content)
            code, reason = lint_clarification(content, fields=fields)
            if code:
                raise ValueError(f'{path.name}: {reason}')
            question = fields['Question'][0]
            option_lines = [line.removeprefix('- ').strip() for line in fields['Options']
                            if line.strip()]
            options = [{'id': str(index), 'description': line}
                       for index, line in enumerate(filter(None, option_lines), 1)]
            decision_route = 'owner'
        decisions.append({'id': path.stem, 'question': question, 'options': options,
                          'route': decision_route, 'record': content,
                          'command': (f'bin/wuwei decision route {path.stem}' if path.name.startswith('D-')
                                      else f'bin/wuwei decision lint {path}')})
    refs = dict.fromkeys(data['raised_prs'] + data['claimed_prs'])
    prs = []
    actions = data.get('watch', {}).get('actions', {})
    for ref in refs:
        episode = actions.get(ref)
        state_name = episode['state'] if episode else 'unmeasured'
        action = episode['action'] if episode else 'unmeasured'
        prs.append({'ref': ref, 'state': state_name, 'action': action,
                    'last_action': action,
                    'waiting_on': action if episode else 'run bin/wuwei pr state',
                    'deadline': episode['deadline'] if episode else 'unmeasured'})
    pack = None
    packs = data.get('brief_packs', {})
    if not isinstance(packs, dict):
        raise ValueError('brief packs: expected records')
    if packs:
        key = next(reversed(packs))
        entry = packs[key]
        if (not isinstance(key, str) or not re.fullmatch(r'daily|meeting-[0-9a-f]{16}', key)
                or not isinstance(entry, dict) or not isinstance(entry.get('path'), str)):
            raise ValueError('briefing pack path is invalid')
        relative = entry['path']
        expected = brief_pack.relative_path(directory.name, key)
        if relative != str(expected):
            raise ValueError('briefing pack path is invalid')
        pack = workspace.find_workspace(directory, use_environment=False) / relative
        if pack.parent.resolve() != pack.parent or pack.is_symlink() or not pack.is_file():
            raise ValueError('briefing pack must be a regular file')
    signals = []
    events = directory / 'events.jsonl'
    if events.exists():
        for line in events.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            tier, lane = classify(event, {**data, 'now': workspace.now().isoformat()})
            signals.append({'tier': tier, 'lane': lane,
                            'kind': event.get('kind', 'unreadable') if isinstance(event, dict)
                            else 'unreadable'})
    pending = [{**row, 'approve_command': f"bin/wuwei drafts approve {row['id']}"}
               for row in drafts.read(data).values() if row['status'] == 'pending']
    return {'decisions': decisions, 'drafts': pending,
            'people': data.get('reply_obligations', 'unmeasured'),
            'prs': prs, 'status': status_snapshot(directory), 'signals': signals,
            'briefing': pack.read_text(encoding='utf-8') if pack else 'unmeasured'}


class DayHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, directory, page, board, **kwargs):
        self.directory = Path(directory)
        self.page = page
        self.board = board
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send_error(403)
            return
        path = urlsplit(self.path).path
        if path in ('/', '/dashboard.html'):
            data, content_type = self.page, 'text/html; charset=utf-8'
        elif path == '/board.json':
            data, content_type = self.board, 'application/json'
        elif path == '/cockpit.json':
            try:
                data = json.dumps(cockpit_snapshot(self.directory)).encode()
            except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
                self.send_error(503, f'cockpit unmeasured: {exc}')
                return
            content_type = 'application/json'
        elif path in ('/state.json', '/events.jsonl'):
            file = self.directory / path[1:]
            if not file.resolve().is_relative_to(self.directory.resolve()):
                self.send_error(404)
                return
            try:
                data = file.read_bytes()
            except FileNotFoundError:
                self.send_error(404)
                return
            content_type = 'application/json' if path.endswith('.json') else 'application/x-ndjson'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send_error(403)
        else:
            self.send_error(405)


def register(subparsers):
    parser = subparsers.add_parser('dashboard', help='serve the day board on loopback')
    parser.set_defaults(func=run)


def run(args):
    directory = workspace.day_dir()
    snapshot = state.read_state(directory=directory)
    template = Path(__file__).resolve().parents[3] / 'templates/dashboard.html'
    page = template.read_bytes()
    phases = [phase for phase in state.PHASES if phase not in ('parked', 'escalated')]
    board = {'phases': phases, 'build_phases': state.BUILD_PHASES,
             'cap': snapshot['cap']}
    handler = partial(DayHandler, directory=directory, page=page,
                      board=json.dumps(board).encode())
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
        print(f'Serving on http://127.0.0.1:{server.server_port}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return CLEAN
