"""Brief evidence and ordered source refusals shared with launch checks."""

import hashlib
import json
from pathlib import Path
import re

from wuwei import registry, security, state, workspace


REFERENCE_PREFIX = 'WUWEI brief: '


def launch_prompt(brief_path, charter, *, root=None):
    """Format every Claude seat's instructions with a workspace-relative reference."""
    root = workspace.find_workspace(root)
    relative = Path(brief_path).resolve(strict=True).relative_to(root)
    return f'{REFERENCE_PREFIX}{relative}\nRead instructions {charter} and brief {relative}.'


class Refused(ValueError):
    """A measured policy finding, exit 1."""


def read(call, *args, root):
    result = call(*args, root=root)
    if type(result.exit) is not int or result.exit not in (0, 1, 2):
        raise ValueError('invalid adapter result')
    if result.exit:
        raise ValueError(result.reason or 'adapter read unavailable')
    return result.data


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('invalid brief role, item or name')
    return value


def read_day(root):
    directory = workspace.day_dir(root)
    if not (directory / 'state.json').is_file():
        raise ValueError('no state.json for this day')
    return directory, state.read_state(root)


def transcript_reference(path):
    """Read the same brief reference for session binding and seat stop."""
    with Path(path).open(encoding='utf-8') as transcript:
        for line in transcript:
            row = json.loads(line)
            if row.get('type') != 'user':
                continue
            content = row['message']['content']
            if isinstance(content, list):
                content = '\n'.join(part['text'] for part in content if part.get('type') == 'text')
            if content.startswith(REFERENCE_PREFIX):
                return content.splitlines()[0].removeprefix(REFERENCE_PREFIX)
    return None


def seats(data):
    records = data.get('seats')
    if not isinstance(records, dict):
        raise ValueError('seats must be an object')
    for seat in records.values():
        if (not isinstance(seat, dict) or seat.get('status') not in (*state.STATUSES, 'stopped')
                or not isinstance(seat.get('role'), str) or not seat['role']
                or not isinstance(seat.get('item'), str) or not seat['item']):
            raise ValueError('invalid seat record')
    return records


def gate_ready(data, item):
    if item not in data['items']:
        raise ValueError(f'unknown gate item: {item}')
    phase = data['items'][item]['phase']
    if phase not in ('gate', 'delta', 'raised', 'merged'):
        raise Refused(f"gate brief while item phase is '{phase}'; wait for builder SubagentStop, then run wuwei state transition {item} gate")
    for seat in seats(data).values():
        if seat['item'] == item and seat['role'] == 'builder' and seat['status'] == 'running':
            raise Refused('gate refused: builder is live; wait for its SubagentStop before the gate brief')


def status(vcs, tree, root):
    changes = read(vcs.status, tree, root=root)
    if not isinstance(changes, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('path'), str)
            or not row['path'] for row in changes):
        raise ValueError('invalid worktree status')
    return changes


def rulings(body, directory, tree, data):
    ids = sorted(set(re.findall(r'D-[A-Z0-9]+(?:-[A-Za-z0-9]+)+', body)))
    ids = [key for key in ids if not key.endswith('-N')]
    if not ids:
        return []
    paths = sorted((directory / 'decisions').glob('*.md'))
    paths += sorted(p for p in directory.parent.glob('*/decisions/*.md') if p not in paths)
    if tree:
        paths += sorted((tree / 'specs').rglob('*.md'))
    lines = [(str(path), number, line) for path in paths if not path.name.startswith('gate-')
             for number, line in enumerate(path.read_text().splitlines(), 1)]
    lines += [('state.json:gate_policy', 1, json.dumps(data.get('gate_policy', '')))]
    result, missing = [], []
    for key in ids:
        exact = re.compile(r'(?<![\w-])' + re.escape(key) + r'(?![\w-])')
        hits = [row for row in lines if exact.search(row[2])]
        prefix, _, number = key.rpartition('-')
        if not hits and number.isdigit():
            ranges = re.compile(re.escape(prefix) + r'-(\d+)\.\.(?:' + re.escape(prefix) + r'-)?(\d+)')
            hits = [row for row in lines if any(int(a) <= int(number) <= int(b)
                    for a, b in ranges.findall(row[2]))]
        if not hits:
            missing.append(key)
            continue
        _, _, text = hits[0]
        # ponytail: preserve source keyword status until rulings have a structured schema.
        label = 'OPEN' if re.search('pending|open|recommend', text, re.I) and not re.search(
            'ruled|accept', text, re.I) else 'RULED'
        result.append(f'Ruling {key} [{label}] {text}')
    if missing:
        raise Refused('ruling id(s) ' + ' '.join(missing) + ' resolve in no decisions, specs or gate_policy')
    return result


def write(role, item, name, body, *, worktree=None, pr=None, gate=False, track=None, root=None):
    root = workspace.find_workspace(root)
    directory, data = read_day(root)
    for value in (role, item, name):
        identifier(value)
    config = workspace.load_config(root)
    gate = gate or role.startswith('sentinel-')
    output = directory / 'briefs' / (name + '.md')
    output.parent.mkdir(exist_ok=True)
    if output.parent.resolve() != output.parent:
        raise ValueError('brief directory must not be a symlink')
    # ponytail: serialize brief publication for this day.
    with (directory / 'brief.lock').open('a') as lock:
        state.lock_ex(lock, 'brief.lock')
        if output.exists() or output.is_symlink():
            raise Refused('brief exists (one brief per name)')
        _, data = read_day(root)
        if gate and re.search(r'return (the verdict )?inline|verdict inline|no verdict file|retro( note)? inline', body, re.I):
            raise Refused('gate verdict goes in its verdict file, never inline')
        if gate and 'decisions/gate-' in body:
            raise Refused('body restates a verdict path')
        current = data['items'].get(item, {})
        track = track or current.get('track', 'SLICE')
        if track not in ('SLICE', 'FULL'):
            raise Refused('track must be SLICE or FULL')
        tree_arg = worktree or current.get('worktree')
        tree = (root / tree_arg).resolve() if tree_arg else None
        if gate and tree is None:
            raise ValueError('gate requires a worktree')
        vcs = registry.load('vcs', config) if tree or gate else None
        now = workspace.now().isoformat()
        charter_root = Path(__file__).resolve().parents[2] / 'charters'
        charters = ['_common'] + ([] if role.startswith('sentinel-') else ['_common-authoring']) + [role]
        secured = security.load(root) is not None
        if secured:
            from wuwei.commands.agents import write_workspace
            write_workspace(charter_root.parent, root / '.wuwei')
        header = []
        for charter in charters:
            local = root / '.wuwei/charters' / (charter + '.md')
            path = (root / '.wuwei/generated/charters' / (charter + '.md') if secured
                    else local if local.is_file() else charter_root / (charter + '.md'))
            if not path.is_file():
                raise ValueError(f'unknown charter: {charter}')
            header.append(f'Charter: {path}')
        header += [f'Written: {now}', f'Item: {item}', f'Seat policy: {json.dumps(data["seat_policy"])}']
        changed = []
        if tree:
            changed = status(vcs, tree, root)
            head = read(vcs.head, tree, root=root)['sha']
            repo = next((r for r in config['repos'] if (root / r['path']).resolve() == tree), {})
            ref = config['brief']['remote'] + '/' + repo.get('default_branch', 'main')
            base = read(vcs.merge_base, tree, ref, root=root)['sha']
            prior = read(vcs.branches, tree, config['brief']['prior_branch_pattern'].format(item=item.lower()), root=root)
            header += [f'Worktree: {tree}', f'HEAD: {head}', f'Merge-base: {base} ({ref})',
                       f'Status: {json.dumps(changed)}', f'Prior branches: {json.dumps(prior)}']
            if gate and changed:
                raise Refused('gate brief on a dirty tree: ' + ', '.join(row['path'] for row in changed))
            changed += read(vcs.diff_stat, tree, base, head, root=root)
        else:
            header += ['Worktree: none', 'HEAD: not applicable', 'Merge-base: not applicable',
                       'Status: not applicable', 'Prior branches: not applicable']
        paths = [row['path'] for row in changed]
        paths += [row['original_path'] for row in changed if row.get('original_path')]
        if tree:
            paths.append(tree.name + '/')
        for line in body.splitlines():
            if line.startswith('Paths:'):
                paths.extend(re.split(r'[,\s]+', line[6:].strip()))
        patterns = [re.compile(p, re.I) for p in config['brief']['full_path_patterns']]
        protected = [path for path in paths if any(p.search(path) for p in patterns)]
        if track == 'SLICE' and protected:
            raise Refused('SLICE brief touches protected paths: ' + ', '.join(protected) + '; use --track FULL')
        header.append(f'Track: {track}')
        host = registry.load('code_host', config) if pr else None
        header.append('PR head (no-cache): ' + (json.dumps(read(host.pr, pr, root=root)) if pr else 'not applicable'))
        if gate:
            gate_ready(data, item)
        row = [value for key, value in data['gate_verdicts'].items()
               if key == item or value.get('item') == item or value.get('pr') in (item, pr) and value.get('pr')]
        header.append(f'Gate row: {json.dumps(row)}')
        if gate:
            verdict = (directory / 'decisions' / ('gate-' + name + '.md')).relative_to(root)
            header.append(f'Verdict file: {verdict} (your only write). Include the retro note here.')
        header += rulings(body, directory, tree, data)
        for repo in config['repos']:
            for other in sorted(set(re.findall(re.escape(repo['name']) + r'#[0-9]+', body))):
                if other != pr:
                    host = host or registry.load('code_host', config)
                    header.append(f'Counterpart {other} head (no-cache): {json.dumps(read(host.pr, other, root=root))}')
        text = '\n'.join(header) + '\n\n' + body + '\n'
        relative = str(output.relative_to(root))
        payload = {'name': name, 'item': item, 'role': role, 'path': relative, 'gate': gate,
                   'worktree': str(tree) if tree else None, 'pr': pr,
                   'head': head if tree else None,
                   'sha256': hashlib.sha256(text.encode()).hexdigest()}
        created = False
        try:
            def update(fresh):
                nonlocal created
                if gate:
                    gate_ready(fresh, item)
                    fresh_changes = status(vcs, tree, root)
                    if fresh_changes:
                        raise Refused('gate brief on a dirty tree: ' + ', '.join(row['path'] for row in fresh_changes))
                if (fresh['items'].get(item) != data['items'].get(item)
                        or fresh['seat_policy'] != data['seat_policy']
                        or fresh['gate_verdicts'] != data['gate_verdicts']
                        or fresh.get('gate_policy') != data.get('gate_policy')):
                    raise ValueError('state changed while collecting brief evidence; retry')
                if role != 'steward':
                    fresh['items'].setdefault(item, {})['track'] = track
                    if tree:
                        fresh['items'][item]['worktree'] = str(tree)
                workspace.atomic_write(output, text, replace=False)
                created = True
            state._write_state(update, root, reserved=False, kind='brief written', payload=payload)
        except BaseException:
            if created:
                output.unlink()
            raise
        return relative
