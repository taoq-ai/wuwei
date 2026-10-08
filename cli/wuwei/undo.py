"""#557: measured reversibility (design 5.8): a record is two-way only when the CLI knows the
undo for its action and that undo ran once in this workspace."""

import json
from pathlib import Path
import re

from wuwei import state, workspace

NAME = 'memory/rehearsals.json'
# kind -> (the undo, the proof event). A kind not here has no undo: one-way.
REGISTRY = {'commit': ('git revert on the item branch, or delete the unmerged branch', 'undo.rehearsed'),
            'decision': ('wuwei undo D-n', 'decision.reversed'),
            'merge': ('wuwei undo <event id> (a revert PR), only while the base does not deploy', 'undo.done')}
SCRATCH = ('commit', 'decision')  # kinds wuwei undo rehearse exercises on a scratch target
# Design 5.8 class -> action kind; other and a record without a class have none.
KIND = {**dict.fromkeys(('approach', 'retry', 'accept-residual', 'scope-cut', 'design',
                         'boundary', 'refactor', 'dependency-bump'), 'commit'),
        **dict.fromkeys(('park', 'defer', 're-plan'), 'decision'),
        'merge': 'merge', 'message': 'message'}
CARD = 'ask the owner: wuwei decision route sends the card'


def _path(root):
    return Path(root) / '.wuwei' / NAME


def ledger(root):
    """The rehearsed kinds {kind: {at, by}}; {} without the file; ValueError when damaged."""
    path = _path(root)
    if path.is_symlink():
        raise ValueError(f'{NAME} is damaged (a symlink); move it aside, then run wuwei undo rehearse for each kind')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f'{NAME} is damaged ({type(exc).__name__}); move it aside, then run wuwei undo rehearse for each kind') from None
    kinds = data.get('kinds') if isinstance(data, dict) and set(data) == {'kinds'} else None
    if not isinstance(kinds, dict) or any(
            kind not in REGISTRY or not isinstance(row, dict) or set(row) != {'at', 'by'}
            or not isinstance(row['at'], str) or row['by'] not in ('rehearsal', 'undo')
            for kind, row in kinds.items()):
        raise ValueError(f'{NAME} is damaged (not a kinds table); move it aside, then run wuwei undo rehearse for each kind')
    return kinds


def record(root, kind, by):
    """Write kind as exercised; the first exercise stays."""
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        state.lock_ex(lock, 'rehearsals.lock')
        kinds = ledger(root)
        if kind in kinds:
            return
        kinds[kind] = {'at': workspace.now().isoformat(), 'by': by}
        workspace.atomic_write(path, json.dumps({'kinds': kinds}, indent=2, sort_keys=True) + '\n')


def missing(root):
    """Registry kinds with no exercise recorded; all of them when the ledger is damaged."""
    try:
        kinds = ledger(root)
    except ValueError:
        kinds = {}
    return [kind for kind in REGISTRY if kind not in kinds]


def measured(fields, root, config):
    """(kind, reason): reason is None when the written door may stand, else why it is one-way."""
    name = fields.get('Class')
    kind = KIND.get(name)
    if kind == 'message':
        return kind, f'a message has no undo (4.9); {CARD}'
    if kind is None:
        return kind, f'{name or "no class"} has no registered undo; {CARD}'
    if kind == 'merge':
        from wuwei import novelty
        named = [key for key in novelty.record_keys(fields) if key.startswith('repo:')]
        if not named:
            return kind, 'a merge record names no repository; add repo:<org>/<name> to Context'
        safe = {f'repo:{repo["name"]}' for repo in config['repos'] if repo['merge_deploys'] is False}
        deploys = next((key for key in named if key not in safe), None)
        if deploys:
            return kind, f'a merge to {deploys} deploys (merge_deploys is not false, 4.6); {CARD}'
    try:
        kinds = ledger(root)
    except ValueError as exc:
        return kind, str(exc)
    if kind not in kinds:
        return kind, (f'the {kind} undo was never rehearsed in this workspace; run wuwei undo rehearse {kind}'
                      + ('; it counts after the first wuwei undo of a merge here' if kind == 'merge' else ''))
    return kind, None


def line(written, reason):
    return f'Reversibility: one-way, not {written}: {reason}'


def correct(ident, path, text, fields, root):
    """On a first route, lower a door the CLI cannot back to one-way in the record: (text,
    fields, the line to print or '')."""
    data = state.read_state(root)
    if (fields['Reversibility'] == 'one-way' or ident in data.get('decision_routes', {})
            or ident in data.get('decision_outcomes', {})):
        return text, fields, ''
    _, reason = measured(fields, root, workspace.load_config(root))
    if reason is None:
        return text, fields, ''
    stamp = workspace.now().isoformat(timespec='seconds')
    # ponytail: the first Reversibility: line, as set_outcome does for Outcome:.
    text = (re.sub(r'^((?:#{1,6} )?Reversibility:).*$', r'\1 one-way', text, count=1, flags=re.M).rstrip('\n')
            + f'\nNotes: Reversibility corrected at {stamp}: {reason}.\n')
    workspace.atomic_write(path, text)
    return text, {**fields, 'Reversibility': 'one-way'}, line(fields['Reversibility'], reason)


def run(root, target, answer=None):
    """wuwei undo: a D-n through #283's undo (decision undo is its alias), or a merge event."""
    from wuwei.decision import DECISION_ID
    if re.fullmatch(DECISION_ID, target):
        from types import SimpleNamespace
        from wuwei.commands import decision
        try:
            return decision.undo(SimpleNamespace(id=target, answer=answer), root=root)
        except OSError:  # no planner card answer and no host terminal: a seat never undoes
            return 1, f'run wuwei undo {target} in a host terminal and answer y'
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}:[1-9][0-9]*', target):
        return 1, f'undo: {target} is neither D-n nor an event id; run wuwei undo D-n or wuwei undo <YYYY-MM-DD:N>'
    return _merge(root, target)


def _merge(root, target):
    """Undo a merge.completed event: its revert PR, after the owner's y at a host terminal."""
    import hashlib
    from wuwei import merge, registry, watch
    from wuwei.integrity import _host_confirm
    name, _, number = target.partition(':')
    day = next((day for day in watch.days(root) if day.name == name), None)
    rows = watch.records(day / 'events.jsonl') if day else []
    if int(number) > len(rows):
        return 1, f'undo: no event {target}; read the day with wuwei status, then name a recorded event id'
    event = rows[int(number) - 1]
    if event['kind'] != 'merge.completed':
        return 1, (f'{event["kind"]} has no registered undo, so it cannot be undone here; '
                   f'run wuwei why {target} to see what it changed')
    ref = event['payload']['pr']
    digest = hashlib.sha256(f'{target}\nundo\n{ref}'.encode()).hexdigest()
    try:
        if not _host_confirm(digest, prompt=f'{target}: merge of {ref}\nOpen its revert PR?'):
            return 1, f'undo: owner confirmation declined; rerun wuwei undo {target} in a host terminal and answer y'
    except OSError:
        return 1, f'run wuwei undo {target} in a host terminal and answer y'
    try:
        with merge.locked(root):
            entry = state.read_state(directory=day)['merges'][ref]
            host = registry.load('code_host', workspace.load_config(root))
            url = merge.revert(root, day, ref, entry, host)
    except merge.ERRORS as exc:
        return 2, f'undo: the revert PR for {ref} was not opened: {exc}; retry wuwei undo {target}'
    state.append_event('undo.done', {'target': target, 'kind': 'merge', 'pr': ref, 'revert_pr': url}, root)
    record(root, 'merge', 'undo')
    return 0, f'undone {target}: revert PR {url}'


def rehearse(root, kind):
    """Exercise the undo of kind once on a scratch target; then the event and the ledger row."""
    if kind == 'merge':
        return 1, ('merge: its undo is a revert PR on the code host, which has no scratch target; '
                   'it counts after the first wuwei undo <event id> of a merge here')
    if kind not in SCRATCH:
        return 1, f'{kind} has no scratch rehearsal; run wuwei undo rehearse commit or wuwei undo rehearse decision'
    try:
        (_commit if kind == 'commit' else _decision)(root)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return 2, f'rehearse {kind}: {exc}; run wuwei doctor, then rerun wuwei undo rehearse {kind}'
    state.append_event('undo.rehearsed', {'kind': kind}, root)
    record(root, kind, 'rehearsal')
    return 0, f'rehearsed {kind}'


def _commit(root):
    import tempfile
    from wuwei import registry
    vcs = registry.load('vcs', workspace.load_config(root))
    with tempfile.TemporaryDirectory() as scratch:
        result = vcs.rehearse_revert(scratch, root=root)
    if result.exit or not isinstance(result.data, dict) or result.data.get('reverted') is not True:
        raise ValueError(result.reason or 'the revert did not restore the tree; run git --version to check git')


def _decision(root):
    """Route a scratch park record under the mandate and undo it, in a scratch workspace."""
    import os
    import tempfile
    from types import SimpleNamespace
    from wuwei.commands import decision
    previous = os.environ.get('WUWEI_WORKSPACE')
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch).resolve()
        (scratch / '.wuwei/memory').mkdir(parents=True)
        (scratch / '.wuwei/config.toml').write_text('', encoding='utf-8')
        (scratch / '.wuwei' / NAME).write_text(json.dumps({'kinds': {'decision': {
            'at': workspace.now().isoformat(), 'by': 'rehearsal'}}}), encoding='utf-8')
        # find_workspace reads WUWEI_WORKSPACE first: pin it so nothing inside reaches the real root.
        os.environ['WUWEI_WORKSPACE'] = str(scratch)
        try:
            path = workspace.day_dir(scratch) / 'decisions' / 'D-1.md'
            path.parent.mkdir(parents=True)
            path.write_text(decision.template().replace('Class: design', 'Class: park'), encoding='utf-8')
            routed = decision.decide(SimpleNamespace(id='D-1', external=None))
            if routed != (0, 'mandate'):
                raise ValueError(f'the scratch record routed {routed[1]!r}, not mandate; run wuwei config check')
            code, said = decision.undo(SimpleNamespace(id='D-1', answer='Undo'), root=scratch,
                                       where='in an undo rehearsal')
            if code or 'D-1' in state.read_state(scratch).get('decision_outcomes', {}):
                raise ValueError(f'the scratch undo did not revert the answer ({said}); run wuwei config check')
        finally:
            if previous is None:
                os.environ.pop('WUWEI_WORKSPACE', None)
            else:
                os.environ['WUWEI_WORKSPACE'] = previous


def report_lines(day, data):
    """(undone, cannot be undone) report lines for one day; ['none'] when empty."""
    from wuwei import watch
    undone, one_way = [], []
    for row in watch.records(Path(day) / 'events.jsonl'):
        payload = row['payload']
        if row['kind'] == 'decision.reversed' and payload.get('undo') is True:
            undone.append(f'- {payload.get("id")}: undone ({payload.get("class")})')
        elif row['kind'] == 'undo.done':
            undone.append(f'- {payload.get("target")}: {payload.get("kind")} undone ({payload.get("revert_pr")})')
        elif row['kind'] == 'draft.sent':
            one_way.append(f'- message {payload.get("id")}: a message has no undo')
    one_way[:0] = [f'- {ident}: {row.get("option")} (one-way)'
                   for ident, row in sorted(data.get('decision_outcomes', {}).items())
                   if isinstance(row, dict) and row.get('reversibility') == 'one-way']
    return undone or ['none'], one_way or ['none']
