"""Specification mode (design 5.10): every spec rule, read from the item's artifacts."""

import json
from pathlib import Path
import re

INSTALL = {
    'speckit': 'uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai claude',
    'superpowers': ('/plugin marketplace add obra/superpowers-marketplace, then '
                    '/plugin install superpowers@superpowers-marketplace'),
    'openspec': 'npm install -g @fission-ai/openspec, then openspec init',
}
# The directory that shows an engine is set up in a repository; superpowers is a plugin.
MARKER = {'speckit': '.specify', 'openspec': 'openspec'}
# The engine's own directories: edits there are the spec work itself.
OWN = {'speckit': ('specs', '.specify'), 'superpowers': ('docs/superpowers',), 'openspec': ('openspec',)}
# Where the item's artifacts live, relative to the worktree; {item} is the id lowercased.
LOCATION = {'speckit': ('specs/{item}', 'specs/*-{item}'),
            'openspec': ('openspec/changes/{item}', 'openspec/changes/archive/*-{item}'),
            'superpowers': ('.',)}
DATE = '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
# (step, artifact glob under the location or None, rule, command), in order.
STEPS = {
    'speckit': (('specify', 'spec.md', 'one', '/speckit.specify'),
                ('clarify', 'spec.md', 'clarified', '/speckit.clarify'),
                ('plan', 'plan.md', 'one', '/speckit.plan'),
                ('tasks', 'tasks.md', 'one', '/speckit.tasks'),
                ('analyze', 'analysis.md', 'clean', '/speckit.analyze, then save its report with '
                 'bin/wuwei spec analysis {item} < report (a subagent cannot write analysis.md)'),
                ('checklist', 'checklists/*.md', 'checked', '/speckit.checklist'),
                ('implement', 'tasks.md', 'checked', '/speckit.implement')),
    'superpowers': (('brainstorming', f'docs/superpowers/specs/{DATE}-{{item}}-design.md', 'one',
                     'superpowers:brainstorming'),
                    ('writing-plans', f'docs/superpowers/plans/{DATE}-{{item}}.md', 'one',
                     'superpowers:writing-plans'),
                    ('executing-plans', f'docs/superpowers/plans/{DATE}-{{item}}.md', 'checked',
                     'superpowers:executing-plans with superpowers:test-driven-development'),
                    ('verification-before-completion', None, None,
                     'superpowers:verification-before-completion')),
    'openspec': (('proposal', 'proposal.md', 'one', '/openspec:proposal'),
                 ('specs', 'specs/*/spec.md', 'some', '/openspec:proposal'),
                 ('tasks', 'tasks.md', 'one', '/openspec:proposal'),
                 ('validate', 'validation.json', 'valid',
                  'openspec validate {item} --strict --json > validation.json'),
                 ('apply', 'tasks.md', 'checked', '/openspec:apply'),
                 ('archive', None, 'archived', 'openspec archive {item} --yes')),
}
# The first implementation row of each engine; the rows before it gate source edits.
IMPLEMENT = ('implement', 'executing-plans', 'apply')
BOX = re.compile(r'^\s*[-*] \[([ xX])\]', re.M)


def _read(path):
    return path.read_text(encoding='utf-8')


def _names(paths, tree):
    return ', '.join(path.relative_to(tree).as_posix() for path in paths)


def _one(paths, glob, tree):
    if len(paths) == 1:
        return None
    return f'{glob} matches {_names(paths, tree)}' if paths else f'no {glob} yet'


def _some(paths, glob, tree):
    return None if paths else f'no {glob} yet'


def _clarified(paths, glob, tree):
    return _one(paths, glob, tree) or (
        None if re.search(r'^## Clarifications\s*$', _read(paths[0]), re.M)
        else f'{_names(paths, tree)} has no ## Clarifications section')


def _clean(paths, glob, tree):
    found = _one(paths, glob, tree)
    if found:
        return found
    for line in _read(paths[0]).splitlines():
        cells = {cell.strip().upper() for cell in line.strip().strip('|').split('|')}
        if line.lstrip().startswith('|') and cells & {'CRITICAL', 'HIGH'}:
            return f'{_names(paths, tree)} has an open finding: {line.strip()}'
    return None


def _checked(paths, glob, tree):
    if not paths:
        return f'no {glob} yet'
    boxes = [box for path in paths for box in BOX.findall(_read(path))]
    if ' ' in boxes:
        return f'{glob} has unchecked items'
    return None if boxes else f'{glob} has no checked items'


def _valid(paths, glob, tree):
    found = _one(paths, glob, tree)
    if found:
        return found
    data = json.loads(_read(paths[0]))
    items = data.get('items') if isinstance(data, dict) else None
    if (not isinstance(items, list) or not items
            or not all(isinstance(row, dict) and row.get('valid') is True for row in items)):
        return f'{_names(paths, tree)} does not show every entry valid'
    return None


RULES = {'one': _one, 'some': _some, 'clarified': _clarified, 'clean': _clean,
         'checked': _checked, 'valid': _valid}


def _location(tree, engine, item):
    """(relative location or None, reason)."""
    patterns = [pattern.format(item=item.lower()) for pattern in LOCATION[engine]]
    if tree is None:
        return None, 'no worktree recorded'
    if patterns == ['.']:
        return Path('.'), ''
    found = sorted({path.relative_to(tree) for pattern in patterns for path in Path(tree).glob(pattern)
                    if path.is_dir()})
    if len(found) == 1:
        return found[0], ''
    if found:
        return None, f'{" and ".join(map(str, found))} both match {item}'
    return None, f'no {" or ".join(patterns)} yet'


def _steps(engine, build):
    rows = STEPS[engine]
    if not build:
        rows = rows[:next(index for index, row in enumerate(rows) if row[0] in IMPLEMENT)]
    return rows


def _gap(tree, engine, item, location, row):
    """None when the step is done, else why not."""
    step, glob, rule, _ = row
    if rule == 'archived':
        return None if location.parts[:3] == ('openspec', 'changes', 'archive') else f'{location} is not archived yet'
    if rule is None:
        return None
    pattern = (location / glob.format(item=item.lower())).as_posix()
    paths = sorted(path for path in Path(tree).glob(pattern) if path.is_file())
    try:
        for path in paths:
            _read(path)  # An unreadable artifact is not done, whatever its rule.
        return RULES[rule](paths, pattern, tree)
    except (OSError, UnicodeError, ValueError) as exc:
        return f'cannot read {pattern}: {exc}'


def status(tree, engine, item, *, build=False):
    """None when every step (before implementation, or all with build) is done, else the
    first step not done: {step, artifact, command, reason, location}."""
    location, reason = _location(tree, engine, item)
    for row in _steps(engine, build):
        gap = reason if location is None else _gap(tree, engine, item, location, row)
        if gap:
            return {'step': row[0], 'artifact': row[1].format(item=item.lower()) if row[1] else None,
                    'command': row[3].format(item=item.lower()), 'reason': gap,
                    'location': str(location) if location is not None else ' or '.join(
                        pattern.format(item=item.lower()) for pattern in LOCATION[engine])}
    return None


def done(tree, engine, item):
    """[(step, relative path)] for each step whose artifact is present and reads as stated."""
    location, _ = _location(tree, engine, item)
    if location is None:
        return []
    result = []
    for row in STEPS[engine]:
        if row[1] is None or _gap(tree, engine, item, location, row):
            continue
        pattern = (location / row[1].format(item=item.lower())).as_posix()
        first = sorted(path for path in Path(tree).glob(pattern) if path.is_file())[0].relative_to(tree)
        result.append((row[0], first.as_posix()))
    return result


def own(engine, tree, path):
    """True when path lies in one of the engine's own directories in the worktree."""
    return any(Path(path).is_relative_to(Path(tree) / name) for name in OWN[engine])


def mode(config):
    """The effective mode: off, advisory or strict; strict runs as advisory under observe."""
    spec = config['spec']
    if spec['engine'] == 'none' or spec['mode'] == 'off':
        return 'off'
    from wuwei import workspace
    if spec['mode'] == 'advisory' or workspace.posture(config)[0] == 'observe':
        return 'advisory'
    return 'strict'


def label(config):
    return f"{config['spec']['engine']} {mode(config)}"


def skip(config, row, computed=None):
    """Why the item needs no spec, or None: the owner's override first, then the lead tier,
    which the diff's computed tier voids when it is not in skip_tiers."""
    override = row.get('spec') or {}
    if override.get('value') == 'skipped':
        return f"owner: {override.get('reason', '')}"
    if override.get('value') == 'required':
        return None
    tiers = config['spec']['skip_tiers']
    if row.get('tier') in tiers and (computed is None or computed in tiers):
        return f"lead tier {row['tier']}"
    return None


def once(root, kind, payload, keys):
    """Append kind unless today's events already hold it with the same values for keys;
    True when appended. Read and append share state.lock."""
    from wuwei import state, workspace
    directory = workspace.day_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'state.lock').open('a') as lock:
        state.lock_ex(lock, 'state.lock')
        path = directory / 'events.jsonl'
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        for line in lines:
            if f'"{kind}"' in line:
                row = json.loads(line)
                if row['kind'] == kind and all(row['payload'].get(key) == payload[key] for key in keys):
                    return False
        state._append_event(kind, payload, directory)
    return True


def present(path, engine, config):
    """True or False for the engine's files in a repository; None when unmeasured."""
    if engine == 'none':
        return True
    if engine in MARKER:
        return (Path(path) / MARKER[engine]).is_dir()
    try:
        text = Path(config['scanner']['mcp']['plugins_file']).expanduser().read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return None
    return '"superpowers@' in text


def _skipped(root, config, item, row, build):
    reason = skip(config, row)
    if reason and build and reason.startswith('lead tier'):
        computed = (row.get('gates') or {}).get('computed')
        if computed is None:
            from wuwei import dispatch
            computed = dispatch.tier(root, config, row)['computed']
        reason = skip(config, row, computed)
    if reason:
        once(root, 'spec.skipped', {'item': item, 'reason': reason}, ('item',))
    return reason


def check(root, config, item, row, tree, *, build, where):
    """(0, '') or (1, reason) for one enforcement point; advisory records spec.warned."""
    effective = mode(config)
    if effective == 'off' or _skipped(root, config, item, row, build):
        return 0, ''
    engine = config['spec']['engine']
    gap = status(tree, engine, item, build=build)
    if gap is None:
        return 0, ''
    if effective == 'advisory':
        once(root, 'spec.warned', {'item': item, 'engine': engine, 'step': gap['step'], 'where': where}, ('item',))
        return 0, ''
    text = (f"spec mode ({engine} strict): {item} needs {gap['step']} first: {gap['command']}; "
            f"artifact {gap['artifact'] or 'none'} in {gap['location']} ({gap['reason']}).")
    if tree is not None and present(tree, engine, config) is False:
        text += f' {engine} is not installed here: {INSTALL[engine]}.'
    return 1, text + f' For a trivial item the owner runs wuwei plan set {item} spec=skipped --reason <why>.'


def record(root, config, item, row, tree):
    """PostToolUse: one spec.step per item, step and day for each step now done."""
    if mode(config) == 'off' or _skipped(root, config, item, row, False):
        return
    engine = config['spec']['engine']
    for step, path in done(tree, engine, item):
        once(root, 'spec.step', {'item': item, 'engine': engine, 'step': step, 'path': path}, ('item', 'step'))


def named(root, config, item, row, tree, text):
    """SubagentStop: (0, '') when the builder's last message names the item's artifacts
    (the feature directory or change, or the superpowers files), else strict (1, reason)."""
    effective = mode(config)
    if effective == 'off' or _skipped(root, config, item, row, False):
        return 0, ''
    engine = config['spec']['engine']
    location, _ = _location(tree, engine, item)
    names = (sorted({path for _, path in done(tree, engine, item)}) if location == Path('.')
             else [location.as_posix()] if location else [])
    if names and all(name in text for name in names):
        return 0, ''
    if effective == 'advisory':
        once(root, 'spec.warned', {'item': item, 'engine': engine, 'step': 'name artifacts', 'where': 'stop'}, ('item',))
        return 0, ''
    if names:
        return 1, f"spec mode: the final message must name the spec artifacts; add them, then stop again: {', '.join(names)}"
    gap = status(tree, engine, item)
    return 1, (f"spec mode: no spec artifacts found for {item}; {gap['step']} first: {gap['command']}, then stop again"
               if gap else f'spec mode: no spec artifacts found for {item}; write them in the item worktree, then stop again')


def brief_line(config, item, row, tree, gate):
    """The brief's Spec: header line, or None when spec mode is off."""
    effective = mode(config)
    if effective == 'off':
        return None
    reason = skip(config, row)
    if reason:
        return f'Spec: skipped ({reason})'
    engine = config['spec']['engine']
    location, why = _location(tree, engine, item)
    if gate:
        return f'Spec: {engine} artifacts: {location}' if location else f'Spec: not found ({why})'
    where = location.as_posix() if location else ' or '.join(
        pattern.format(item=item.lower()) for pattern in LOCATION[engine])
    steps = '; '.join(f"{step} ({command.format(item=item.lower())})"
                      + (f" -> {glob.format(item=item.lower())}" if glob else '')
                      for step, glob, _, command in STEPS[engine])
    create = (f'; create the directory with .specify/scripts/bash/create-new-feature.sh --json '
              f'--short-name {item.lower()}' if engine == 'speckit' else '')
    return (f'Spec: {engine} {effective}; artifacts in {where}{create}; steps in order: {steps}; '
            'name the artifacts in your final message.')


def detect(paths, config):
    """The engine setup proposes: spec-kit, then OpenSpec, then superpowers where found; else spec-kit."""
    return next((engine for engine in ('speckit', 'openspec', 'superpowers')
                 if any(present(path, engine, config) for path in paths)), 'speckit')
