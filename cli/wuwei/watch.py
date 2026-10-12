"""Day record readers and PR evidence helpers."""

import json
import re

from wuwei import obligations, registry, state, workspace
from wuwei.references import pull_request
from wuwei.exits import DAMAGED


ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)


def records(path):
    """Read complete event records; missing streams are empty, corrupt ones fail."""
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    return _rows(text)


def _rows(text):
    if text and not text.endswith('\n'):
        raise ValueError(f'incomplete event line; {DAMAGED}')
    rows = []
    for line in text.splitlines():
        # The decoder refuses what json.dumps(allow_nan=False) would (NaN, Infinity and
        # floats that overflow): half the cost of encoding every row again.
        row = json.loads(line, parse_constant=_not_json, parse_float=_finite)
        if (not isinstance(row, dict) or not isinstance(row.get('kind'), str)
                or not isinstance(row.get('payload'), dict)):
            raise ValueError(f'invalid event record; {DAMAGED}')
        obligations._time(row['ts'])
        rows.append(row)
    return rows


def _not_json(value):
    raise ValueError(f'Out of range float values are not JSON compliant: {value}')


def _finite(text):
    value = float(text)
    if value in (float('inf'), float('-inf')):
        _not_json(text)
    return value


def days(root):
    today = workspace.now().date().isoformat()
    return sorted((p for p in (root / '.wuwei/days').glob('*')
                   if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name)
                   and p.name <= today), reverse=True)


# The last events text health decoded and its rows: SessionStart asks for watch health,
# and an unchanged day decodes once. Only health reads it (kinds and stamps).


def saved(root):
    value = state.read_state(root).get('watch', {})
    if not isinstance(value, dict):
        raise ValueError(f'invalid watch state; {DAMAGED}')
    return value


def save(root, changes, kind='watch: observation', payload=None):
    def update(data):
        data.setdefault('watch', {}).update(changes)
    return state._write_state(update, root, kind=kind, payload=payload)


def owned(root, config):
    data = state.read_state(root)
    host = registry.load('code_host', config)
    refs = sorted({pull_request(ref) for ref in data['raised_prs'] + data['claimed_prs']})
    return host, refs


def previous(root):
    for directory in days(root):
        if directory != workspace.day_dir(root):
            value = state.read_state(directory=directory).get('watch', {})
            if not isinstance(value, dict):
                raise ValueError(f'invalid prior watch state; {DAMAGED}')
            return value
    return {}


def evidence(host, ref, root):
    pr = obligations._read(host.pr, ref, root=root)
    if (pr['state'] not in ('open', 'closed') or
            f'{pr["repo"]}#{pr["number"]}' != ref or
            not isinstance(pr['head'], str) or
            not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', pr['head']) or
            (pr['mergeable'] is not None and type(pr['mergeable']) is not bool)):
        raise ValueError(f'invalid PR evidence; {DAMAGED}')
    obligations._time(pr['updated_at'])
    reviews, threads = obligations._evidence(host, ref, root)
    checks = obligations._list(obligations._read(host.checks, ref, pr['head'], root=root))
    for check in checks:
        if (not isinstance(check, dict) or check.get('sha') != pr['head']
                or not isinstance(check.get('name'), str) or not check['name']
                or not isinstance(check.get('state'), str) or not check['state']
                or 'conclusion' not in check):
            raise ValueError(f'invalid checks evidence; {DAMAGED}')
    return dict(pr=pr, reviews=reviews, threads=threads, checks=checks)


