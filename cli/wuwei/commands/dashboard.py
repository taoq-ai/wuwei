"""Serve a passive view of today's state on loopback."""

from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from wuwei import state, workspace
from wuwei.exits import CLEAN


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
