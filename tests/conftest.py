import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cli'))

from wuwei import gh, ws  # noqa: E402

HEAD = 'a' * 40
OLD = 'b' * 40


@pytest.fixture
def root(tmp_path):
    (tmp_path / ws.DIR).mkdir()
    ws.write_config(tmp_path, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
    return tmp_path


class FakeGh:
    """Answers gh calls from a table of PR data; records every call."""

    def __init__(self):
        self.calls = []
        self.prs = {}
        self.threads = {}
        self.ancestors = set()
        self.paths = set()
        self.files = {}
        self.default = 'main'

    def __call__(self, args, timeout=30):
        self.calls.append(args)
        if args[:2] == ['pr', 'view']:
            if args[2] not in self.prs:
                raise gh.GhError('no pull requests found')
            return self.prs[args[2]]
        if args[:2] == ['pr', 'list']:
            state = args[args.index('--state') + 1]
            return [pr for pr in self.prs.values() if pr['state'].lower() == state]
        if args[:2] == ['api', 'graphql']:
            number = next(a.split('=', 1)[1] for a in args if a.startswith('number='))
            return {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': self.threads.get(number, [])}}}}}
        if args[0] == 'api' and '/compare/' in args[1]:
            older, newer = args[1].split('/compare/')[1].split('...')
            return {'status': 'ahead' if (older, newer) in self.ancestors else 'diverged'}
        if args[0] == 'api' and '/contents/' in args[1]:
            path = args[1].split('/contents/')[1]
            if path in self.files:
                import base64
                return {'encoding': 'base64', 'content': base64.b64encode(self.files[path].encode()).decode()}
            if path in self.paths:
                return {}
            raise gh.GhError('Not Found')
        if args[:2] == ['api', 'user']:
            return 'owner'
        if args[0] == 'api' and '--jq' in args and args[args.index('--jq') + 1] == '.default_branch':
            return self.default
        raise AssertionError(f'unexpected gh call {args}')


@pytest.fixture
def fake(monkeypatch):
    fake = FakeGh()
    monkeypatch.setattr(gh, 'run', fake)
    return fake


def make_pr(number=42, head=HEAD, files=('src/app.py', 'tests/test_app.py'), checks='SUCCESS',
            body='WUWEI-Item: I-1', reviews=(), requests=('alice',), state='OPEN', author='wuwei-bot',
            lines=20, created=None):
    return {'number': number, 'title': f'feat: change {number}', 'body': body, 'state': state, 'isDraft': False,
            'headRefName': f'i-1-change', 'headRefOid': head, 'baseRefName': 'main',
            'author': {'login': author}, 'url': f'https://github.com/acme/app/pull/{number}',
            'mergedAt': None, 'createdAt': created or ws.now().isoformat(timespec='seconds'),
            'files': [{'path': path, 'additions': lines, 'deletions': 0} for path in files],
            'statusCheckRollup': [] if checks is None else [{'name': 'test', 'conclusion': checks, 'status': 'COMPLETED'}],
            'reviewRequests': [{'login': login} for login in requests],
            'reviews': [{'author': {'login': login}, 'state': state} for login, state in reviews]}


def verdict_text(gate='quality', verdict='PASS', head=HEAD, item='I-1', pr='acme/app#42', findings='none'):
    return (f'Verdict: {verdict}\nGate: {gate}\nItem: {item}\nPR: {pr}\nHead: {head}\nConfidence: high\n\n'
            f'## Findings\n{findings}\n')


def write_plan(root, items):
    ws.atomic_write(Path(root) / ws.DIR / 'plan.json', json.dumps({'items': items}))
