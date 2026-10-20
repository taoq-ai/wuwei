import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cli'))

from wuwei import gh, ws  # noqa: E402

HEAD = 'a' * 40
OLD = 'b' * 40


def footer(item='I-1'):
    """The WUWEI footer that links a PR body to its plan item."""
    return f'<sub>[WUWEI 4.2.2](https://taoq-ai.github.io/wuwei/) \u00b7 Item `{item}` \u00b7 change \u00b7 Goal G-1 \u00b7 Tier standard</sub>'


@pytest.fixture
def root(tmp_path):
    (tmp_path / ws.DIR).mkdir()
    ws.write_config(tmp_path, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
    return tmp_path


class FakeGh:
    """Answers gh calls the way GitHub's REST API would, from a table of PR data; records every call.
    graphql = False plays a cloud session, where GraphQL is refused and the CCR thread route answers."""

    def __init__(self):
        self.calls = []
        self.prs = {}
        self.threads = {}
        self.ccr = {}
        self.comments = {}
        self.graphql = True
        self.ancestors = set()
        self.deltas = {}
        self.branches = {}
        self.paths = set()
        self.files = {}
        self.default = 'main'
        self.runs = {}  # workflow run id -> (workflow path, event); None plays an Actions read that fails

    @staticmethod
    def rest(pr):
        return {'number': pr['number'], 'title': pr['title'], 'body': pr['body'],
                'state': 'open' if pr['state'] == 'OPEN' else 'closed', 'draft': pr['isDraft'],
                'head': {'ref': pr['headRefName'], 'sha': pr['headRefOid']}, 'base': {'ref': pr['baseRefName']},
                'user': {'login': pr['author']['login']}, 'html_url': pr['url'], 'merged_at': pr['mergedAt'],
                'created_at': pr['createdAt'], 'updated_at': pr.get('updatedAt'), 'requested_reviewers': pr['reviewRequests'], 'requested_teams': []}

    def pr(self, number):
        if number not in self.prs:
            raise gh.GhError('HTTP 404: Not Found')
        return self.prs[number]

    def __call__(self, args, timeout=30):
        import re
        self.calls.append(args)
        if args[:2] == ['api', 'graphql']:
            if not self.graphql:
                raise gh.GhError('HTTP 403: GitHub GraphQL is not available from Claude Code sessions')
            number = next(a.split('=', 1)[1] for a in args if a.startswith('number='))
            return {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': self.threads.get(number, [])}}}}}
        path, _, query = (args[1].partition('?') if len(args) > 1 else ('', '', ''))
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/pulls/(\d+)', path)):
            return self.rest(self.pr(m[1]))
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/pulls/(\d+)/files', path)):
            return [{'filename': f['path'], 'additions': f['additions'], 'deletions': f['deletions'],
                     **{k: f[k] for k in ('patch', 'previous_filename') if k in f}} for f in self.pr(m[1])['files']]
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/pulls/(\d+)/reviews', path)):
            return [{'user': {'login': r['author']['login']}, 'state': r['state'], 'commit_id': r.get('commit')}
                    for r in self.pr(m[1])['reviews']]
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/pulls/(\d+)/ccr/review_threads', path)):
            if self.graphql:
                raise gh.GhError('HTTP 404: Not Found')
            return self.ccr.get(m[1], [])
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/pulls/(\d+)/comments', path)):
            return self.comments.get(m[1], [])
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/commits/(\w+)/(check-runs|status)', path)):
            rollup = next((pr['statusCheckRollup'] for pr in self.prs.values() if pr['headRefOid'] == m[1]), [])
            if m[2] == 'check-runs':
                return {'check_runs': [{'name': c['name'], 'status': c['status'].lower(),
                                        'conclusion': (c.get('conclusion') or '').lower() or None}
                                       for c in rollup if 'name' in c]}
            return {'statuses': [{'context': c['context'], 'state': c['state'].lower(), 'target_url': c.get('url')}
                                 for c in rollup if 'context' in c]}
        if args[0] == 'api' and (m := re.fullmatch(r'repos/[^/]+/[^/]+/actions/runs(?:/(\d+))?', path)):
            if self.runs is None:
                raise gh.GhError('HTTP 403: Resource not accessible by integration')
            if m[1]:
                return {'id': int(m[1]), 'path': self.runs[m[1]][0], 'event': self.runs[m[1]][1]}
            event = re.search(r'event=(\w+)', query)[1]
            return {'workflow_runs': [{'id': int(i), 'path': p, 'event': e} for i, (p, e) in self.runs.items() if e == event]}
        if args[0] == 'api' and re.fullmatch(r'repos/[^/]+/[^/]+/pulls', path):
            wanted = 'open' if 'state=open' in query else 'closed'
            return [self.rest(pr) for pr in self.prs.values() if self.rest(pr)['state'] == wanted]
        if args[0] == 'api' and '/compare/' in path:
            older, newer = path.split('/compare/')[1].split('...')
            pr = next((pr for pr in self.prs.values() if newer in (pr['headRefOid'], pr['headRefName'])), None)
            files = self.deltas.get((older, newer), pr['files'] if pr else [])
            return {'status': 'ahead' if (older, newer) in self.ancestors else 'diverged',
                    'commits': [{'sha': pr['headRefOid'] if pr else self.branches.get(newer, newer)}],
                    'files': [{'filename': f['path'], 'additions': f['additions'], 'deletions': f['deletions']} for f in files]}
        if args[0] == 'api' and '/contents/' in path:
            path = path.split('/contents/')[1]
            children = sorted({key[len(path) + 1:].split('/')[0] for key in self.files if key.startswith(path + '/')})
            if children:
                return [{'name': name, 'path': f'{path}/{name}',
                         'type': 'file' if f'{path}/{name}' in self.files else 'dir'} for name in children]
            if path in self.files:
                import base64
                return {'encoding': 'base64', 'content': base64.b64encode(self.files[path].encode()).decode()}
            if path in self.paths:
                return {}
            raise gh.GhError('Not Found')
        if args[:2] == ['auth', 'status']:
            return 'Logged in'
        if args[0] == 'api' and '/rules/branches/' in path:
            return []
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
            body=footer(), reviews=(), requests=('alice',), state='OPEN', author='wuwei-bot',
            lines=20, created=None):
    return {'number': number, 'title': f'feat: change {number}', 'body': body, 'state': state, 'isDraft': False,
            'headRefName': f'i-1-change', 'headRefOid': head, 'baseRefName': 'main',
            'author': {'login': author}, 'url': f'https://github.com/acme/app/pull/{number}',
            'mergedAt': None, 'createdAt': created or ws.now().isoformat(timespec='seconds'),
            'files': [{'path': path, 'additions': lines, 'deletions': 0} for path in files],
            'statusCheckRollup': [] if checks is None else [{'name': 'test', 'conclusion': checks, 'status': 'COMPLETED'}],
            'reviewRequests': [{'login': login} for login in requests],
            'reviews': [{'author': {'login': r[0]}, 'state': r[1], 'commit': r[2] if len(r) > 2 else head} for r in reviews]}


def verdict_text(gate='quality', verdict='PASS', head=HEAD, item='I-1', pr='acme/app#42', findings='none', breaking='no'):
    said = f'Breaking: {breaking}\n' if gate == 'arch' and breaking is not None else ''
    return (f'Verdict: {verdict}\nGate: {gate}\nItem: {item}\nPR: {pr}\nHead: {head}\nConfidence: high\n{said}\n'
            f'## Findings\n{findings}\n')


def write_plan(root, items):
    ws.atomic_write(Path(root) / ws.DIR / 'plan.json', json.dumps({'items': items}))
