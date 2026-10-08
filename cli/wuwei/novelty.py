"""#556: the seen set; a target the workspace never touched runs one level lower (design 5.8.1)."""

from contextlib import contextmanager
from datetime import date, timedelta
import json
from pathlib import Path
import re
import sys

from wuwei import state, workspace
from wuwei.grants import REPO

_FREE = r'[^\s,;`\'"()\[\]<>]+'  # markdown and quote marks around a key are not part of it
KEY = (rf'repo:{REPO}|channel:{_FREE}|person:[A-Za-z0-9_-]+:{_FREE}'
       rf'|tool:[A-Za-z0-9_-]+/[A-Za-z0-9_-]+|dependency:[A-Za-z0-9_.-]+/{_FREE}'
       rf'|env:{_FREE}|workflow:{_FREE}')
CLEARS = 'one owner answer on a card clears it'
DAYS = 30
NAME = 'memory/targets.json'


def keys(text):
    """The target keys in free text, in order, without trailing punctuation or placeholders."""
    found = []
    for match in re.finditer(rf'(?<![\w:/.-])(?:{KEY})', text):
        key = match[0].rstrip('.):')
        if re.fullmatch(KEY, key) and '<' not in key and '>' not in key and key not in found:
            found.append(key)
    return found


def record_keys(fields):
    """The targets a decision record names in its Question, Context and Blast radius."""
    return keys('\n'.join(fields.get(name, '') for name in ('Question', 'Context', 'Blast radius')))


def configured(config):
    """What the owner declared in config: always seen, never copied into the seen set."""
    outbound = config['outbound']
    channels = [*outbound['work_channels'], *outbound['external_channels'], *outbound['channel_classes'],
                *(row.get('channel', '') for row in outbound['tiers']),
                config['shepherd']['review_channel'], outbound['owner']['slack']['dm']]
    return ({f'repo:{repo["name"]}' for repo in config['repos']}
            | {f'channel:{value}' for value in channels if value}
            | {f'person:{value}' for value in outbound['people']}
            | {f'person:slack:{value}' for value in [outbound['owner']['slack']['user']] if value}
            | {f'env:{value}' for value in config['environments']}
            | {f'workflow:{value}' for value in config['deploy']['workflows']}
            | {line['target'] for line in config['grants']['standing'] if not re.search(r'[*?\[]', line['target'])})


def _path(root):
    return Path(root) / '.wuwei' / NAME




def _read(root):
    """The seen set, or None when the file is missing; a damaged file raises ValueError."""
    path = _path(root)
    if path.is_symlink():
        raise ValueError(f'{NAME} is damaged (a symlink); the owner moves it aside and runs bin/wuwei init --upgrade, which seeds it again')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f'{NAME} is damaged ({type(exc).__name__}); the owner moves it aside and runs bin/wuwei init --upgrade, which seeds it again') from None
    if not isinstance(data, dict) or set(data) != {'targets'} or not isinstance(data['targets'], dict):
        raise ValueError(f'{NAME} is damaged (not a targets table); the owner moves it aside and runs bin/wuwei init --upgrade, which seeds it again')
    for key, row in data['targets'].items():
        cleared = row.get('cleared') if isinstance(row, dict) else None
        try:
            valid = (re.fullmatch(KEY, key) and set(row) == {'first_seen', 'cleared'}
                     and date.fromisoformat(row['first_seen']).isoformat() == row['first_seen']
                     and (cleared is None or set(cleared) == {'by', 'evidence', 'at'}
                          and cleared['by'] in ('owner', 'seed')
                          and all(isinstance(cleared[name], str) for name in ('evidence', 'at'))))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError(f'{NAME} is damaged (invalid row {key!r}); the owner moves it aside and runs bin/wuwei init --upgrade, which seeds it again')
    return data


@contextmanager
def _lock(root):
    path = _path(root).with_suffix('.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        state.lock_ex(lock, 'targets.lock')
        yield


def _update(root, change, start=None):
    """Apply change to the targets under the lock; a missing file starts from start, else
    from the history seed. Writes when the file was missing or change returned true."""
    with _lock(root):
        data = _read(root)
        missing = data is None
        if missing:
            # ponytail: the lazy seed reads 30 days once, inside whichever hook first asks.
            data = {'targets': _history(root) if start is None else start}
        if change(data['targets']) or missing:
            workspace.atomic_write(_path(root), json.dumps(data, indent=2, sort_keys=True) + '\n')


def novel(root, config, found):
    """The keys in found that are neither configured nor cleared; records first_seen."""
    known = configured(config) if found else set()
    found, result = [key for key in dict.fromkeys(found) if key not in known], []
    if not found:
        return []  # nothing to read: a configured target never opens the file (hook fast path)

    def change(targets):
        result.extend(key for key in found if not (targets.get(key) or {}).get('cleared'))
        added = [key for key in result if key not in targets]
        for key in added:
            targets[key] = {'first_seen': workspace.now().date().isoformat(), 'cleared': None}
        return added

    _update(root, change)
    return result


def clear(root, key, evidence):
    """The owner answered for key: it stops being novel. A cleared row stays as it was."""
    def change(targets):
        row = targets.setdefault(key, {'first_seen': workspace.now().date().isoformat(), 'cleared': None})
        if row['cleared']:
            return False
        row['cleared'] = {'by': 'owner', 'evidence': evidence, 'at': workspace.now().isoformat()}
        return True

    _update(root, change)


def _history(root):
    """{key: row} for the targets CLI-written records of the last DAYS days name."""
    from wuwei.commands.event import FREE_KINDS
    from wuwei.consolidation import day_records
    from wuwei.watch import _rows
    today, found = workspace.now().date(), {}
    for back in range(DAYS, -1, -1):
        name = (today - timedelta(days=back)).isoformat()
        try:
            records = day_records(root, name)
            if records is None:
                continue
            named = []
            for row in _rows(records.get('events.jsonl', '')):
                payload = row['payload']
                if row['kind'] in FREE_KINDS:
                    continue  # a seat may append a note; it never seeds
                if isinstance(payload.get('repo'), str) and re.fullmatch(REPO, payload['repo']):
                    named.append('repo:' + payload['repo'])
                if row['kind'] == 'grant.used' and isinstance(payload.get('target'), str):
                    named.append(payload['target'])
            drafts = json.loads(records['state.json']).get('drafts', {}) if 'state.json' in records else {}
            for row in drafts.values():
                if (row.get('channel') in ('chat', 'slack') and row.get('status') in ('sent', 'approved')
                        and isinstance(row.get('destination'), str)):
                    named.append('channel:' + row['destination'])
        except (OSError, UnicodeError, ValueError, AttributeError, TypeError) as exc:
            print(f'warning: novelty seed skipped {name}: {exc}; run bin/wuwei doctor', file=sys.stderr)
            continue
        for key in named:
            if re.fullmatch(KEY, key) and key not in found:
                found[key] = {'first_seen': name, 'cleared': {
                    'by': 'seed', 'evidence': f'days/{name}', 'at': workspace.now().isoformat()}}
    return found


def seed(root, write=True):
    """Add the history targets not in the seen set; returns how many (#556 upgrade)."""
    found = _history(root)
    if not write:
        current = _read(root) or {'targets': {}}
        return len(set(found) - set(current['targets']))

    new = []

    def change(targets):
        new.extend(key for key in found if key not in targets)
        targets.update({key: found[key] for key in new})
        return new

    _update(root, change, start={})
    return len(new)


def line(found, how=CLEARS):
    return f'first time for {", ".join(found)}; {how}'


def _how(row):
    cleared = row['cleared']
    return ('not cleared' if cleared is None else f'cleared by {cleared["by"]}'
            + (f' ({cleared["evidence"]})' if cleared['by'] == 'owner' else ''))


def today_lines(root):
    """The report lines for targets first seen today; read only."""
    today = workspace.now().date().isoformat()
    rows = (_read(root) or {'targets': {}})['targets']
    return [f'- {key}: {_how(row)}' for key, row in sorted(rows.items()) if row['first_seen'] == today] or ['none']


def explain(root, config, key):
    """The wuwei why lines for one target key."""
    if key in configured(config):
        return [f'target: {key}', 'seen: configured in config.toml']
    row = (_read(root) or {'targets': {}})['targets'].get(key)
    if row is None:
        return [f'target: {key}', 'not seen yet']
    cleared = row['cleared']
    return [f'target: {key}', f'first seen: {row["first_seen"]}',
            f'cleared: not yet; {CLEARS}' if cleared is None else
            f'cleared: by {cleared["by"]} on {cleared["at"][:10]} ({cleared["evidence"]})']
