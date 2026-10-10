"""The docs system (#419, design 5.12): the obligation per tier, the item's docs value,
pages written from the item's records, publishing and the close lines.

Module imports stay stdlib, state and workspace: wuwei next runs at SessionStart."""

import re
from pathlib import Path

from wuwei import state, workspace


COMMAND = 'bin/wuwei plan set {item} docs=<page>|new|none --reason "<why>"'
MARKDOWN_COMMAND = ('bin/wuwei docs page {item}, or bin/wuwei plan set {item} '
                    'docs=<path>|none --reason "<why>"')


def required(config, row):
    rules = config['docs']
    return rules['system'] != 'none' and (row.get('gates') or {}).get('tier') in rules['required_tiers']


def unmet(config, row):
    return required(config, row) and not row.get('docs')


def shown(config, row):
    if not required(config, row):
        return 'n/a'
    return row['docs']['value'] if row.get('docs') else 'missing'


def command(config, item):
    return (MARKDOWN_COMMAND if config['docs']['system'] == 'markdown' else COMMAND).format(item=item)


def _relative(config, value):
    """A markdown value: a relative path under docs.root, never absolute or with '..'."""
    path = Path(value)
    rules = Path(config['docs']['root'])
    if (path.is_absolute() or value.startswith('~') or '..' in path.parts
            or path.parts[:len(rules.parts)] != rules.parts or len(path.parts) <= len(rules.parts)):
        raise state.StateError(f'docs: {value} must be a relative path under {rules}/; '
                               f'pass a path such as {rules}/<page>.md')
    return path


def _worktree(data, item):
    tree = data['items'][item].get('worktree')
    if not isinstance(tree, str) or not tree:
        raise state.StateError(f'docs: {item} has no worktree for the markdown page; '
                               f'create it with bin/wuwei worktree add {item}')
    return Path(tree)


def _read(result):
    if result.exit == 1:
        raise state.StateError(result.reason or 'docs: no page at that reference; pass an existing page, '
                                                'or docs=new to create one')
    if result.exit:
        raise OSError(result.reason or 'docs: could not read the page; run bin/wuwei doctor to check the '
                                       'docs credentials, then retry')
    return result.data


def assign(item, value, reason, root=None):
    """plan set <item> docs=<value>: record the item's docs value, reading a page first."""
    from wuwei import registry
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    system = config['docs']['system']
    reason = ' '.join((reason or '').split())
    if system == 'none':
        raise state.StateError('docs: docs.system is none, so no item needs a docs value; stop here')
    data = state.read_state(root)
    if item not in data['items']:
        raise state.StateError(f'docs: unknown item {item}; check the name with bin/wuwei status')
    if value == 'none' and not reason:
        raise state.StateError(f'docs: docs=none needs a reason; run bin/wuwei plan set {item} '
                               'docs=none --reason "<why>"')
    if value == 'new' and system == 'markdown':
        raise state.StateError(f'docs: under markdown write the page with bin/wuwei docs page {item}')
    if value not in ('new', 'none'):
        adapter = registry.load('docs', config)
        ref = value
        if system == 'markdown':
            ref = str(_worktree(data, item) / _relative(config, value))
        _read(adapter.read(ref, root=root))

    def update(fresh):
        if item not in fresh['items']:
            raise state.StateError(f'docs: unknown item {item}; check the name with bin/wuwei status')
        fresh['items'][item]['docs'] = {'value': value, 'reason': reason}
    state._write_state(update, root, reserved=False, kind='docs.set',
                       payload={'item': item, 'value': value, 'reason': reason})
    return f'{item}: docs {value}'


def exempt(root, config, item, tier):
    """Once, when dispatch next tiers an item outside docs.required_tiers."""
    rules = config['docs']
    if rules['system'] != 'none' and tier not in rules['required_tiers']:
        state.append_event('docs.exempt', {'item': item, 'tier': tier}, root)


def brief_line(config, row, item, role):
    """The Docs: header line of a builder brief; None otherwise (#667: a gate reads why --json)."""
    rules = config['docs']
    if rules['system'] == 'none' or role != 'builder':
        return None
    return (f"Docs: {rules['system']}; items tiered {', '.join(rules['required_tiers'])} need a "
            f'docs value before you stand down: {command(config, item)}.')


def _candidate(root, data, item):
    import json
    path = workspace.day_dir(root) / 'proposal.json'
    rows = json.loads(path.read_text(encoding='utf-8'))['candidates'] if path.is_file() else []
    found = next((row for row in rows if isinstance(row, dict) and row.get('id') == item), None)
    return found or (data.get('discovery_candidates') or {}).get(item) or {}


def _how_to_use(text):
    found = re.search(r'^#+ *How to use[^\n]*\n(.*?)(?=^#|\Z)', text, re.M | re.S | re.I)
    return found[1].strip() if found else ''


def render(root, config, data, item):
    """(title, Markdown body) of the item's page from its records."""
    from wuwei import brief, goals, registry
    candidate = _candidate(root, data, item)
    scope = str(candidate.get('scope') or '').strip()
    if not scope:
        raise state.StateError(f'docs: {item} has no recorded scope to write a page from; write the page '
                               f'by hand, then record it with bin/wuwei plan set {item} docs=<page>')
    row = data['items'].get(item, {})
    pr = {}
    if row.get('pr'):
        pr = brief.read(registry.load('code_host', config).pr, row['pr'], root=root)
    goal = candidate.get('goal') or row.get('goal')
    path = Path(root) / '.wuwei/memory/goals.md'
    outcome = goals.parse(path.read_text(encoding='utf-8')).get(goal, {}).get('outcome') \
        if goal and path.is_file() else None
    ticket = ((data.get('tickets') or {}).get(item) or {}).get('id')
    changed = [scope] + ([f"Pull request: {pr['title']}"] if pr.get('title') else [])
    why = ([f'Goal: {outcome}'] if outcome else []) + (
        [str(candidate['evidence']).strip()] if candidate.get('evidence') else [])
    sections = [('What changed', changed), ('Why', why),
                ('How to use it', [_how_to_use(pr.get('body') or '')]),
                ('Links', ([f"- Pull request: {pr['url']}"] if pr.get('url') else [])
                 + ([f'- Ticket: {ticket}'] if ticket else []))]
    body = '\n'.join(f'### {name}\n' + '\n'.join(lines) + '\n'
                     for name, lines in sections if any(lines))
    return f'{item}: {scope.splitlines()[0]}', body


ABSOLUTE = r'''(?:^|[\s(\[`"'=])(?:/|~/|[A-Za-z]:\\)[\w.-]'''


def check(text, again='the same command'):
    """Refuse (never strip) raw records, absolute paths and credentials in page text."""
    from wuwei import redact
    for pattern, name in ((r'\.wuwei/', 'a .wuwei/ path'), (r'\bstate\.json\b', 'state.json'),
                          (r'\bevents\.jsonl\b', 'events.jsonl'), (ABSOLUTE, 'an absolute path')):
        if re.search(pattern, text, re.M):
            raise state.StateError(f'docs: the page holds {name}; remove it from the record it came from, '
                                   f'then run {again}')
    if any(redact.redact(line) != line for line in text.splitlines()):
        raise state.StateError(f'docs: the page holds a credential; remove it from the record it came from, '
                               f'then run {again}')


def record(root, draft, adapter, page, draft_id=None):
    """One docs.written event; a page write also records a new page link as the value."""
    item = draft.get('item') or None

    def update(data):
        row = data['items'].get(item)
        if draft['kind'] == 'page' and row is not None and (row.get('docs') or {}).get('value', 'new') == 'new':
            row['docs'] = {'value': page, 'reason': ''}
    state._write_state(update, root, reserved=False, kind='docs.written',
                       payload={'item': item, 'kind': draft['kind'], 'adapter': adapter,
                                'page': page, 'draft': draft_id})


def _outcome(root, result, draft, adapter):
    if result.exit == 0:
        record(root, draft, adapter, result.data['link'])
        return 0, f"docs: wrote {draft['kind']} page {result.data['link']}"
    if result.exit == 1 and result.reason.startswith('outward: draft '):
        return 0, result.reason
    return result.exit, result.reason


def _dated(body):
    return f'## {workspace.now().date().isoformat()}\n' + body


def page(root, item):
    """docs page <item>: write or draft the item's page from its records."""
    from wuwei import outward, registry
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    rules = config['docs']
    if rules['system'] == 'none':
        result = registry.record_none('docs', 'write', root, measurement=False)
        return result.exit, result.reason
    data = state.read_state(root)
    if item not in data['items']:
        raise state.StateError(f'docs: unknown item {item}; check the name with bin/wuwei status')
    value = (data['items'][item].get('docs') or {}).get('value')
    if value == 'none':
        raise state.StateError(f'docs: {item} is recorded as docs=none, so there is no page to write; stop '
                               f'here, or change the value with bin/wuwei plan set {item} docs=<page>')
    title, body = render(root, config, data, item)
    check(title + '\n' + body, f'bin/wuwei docs page {item}')
    adapter = registry.load('docs', config)
    if rules['system'] == 'markdown':
        tree = _worktree(data, item)
        relative = _relative(config, value or f"{rules['root']}/{item}.md")
        target = tree / relative
        if value and not target.is_file():
            raise state.StateError(f'docs: {relative} is missing from the worktree; restore it or '
                                   f'record another path with bin/wuwei plan set {item} docs=<path>')
        draft = {'kind': 'page', 'item': item, 'title': title, 'body': _dated(body) if value else body,
                 'parent': str(tree / rules['root']), 'ref': str(target) if value else ''}
        code, reason = outward.humanize_lint({'draft': draft}, root, config, {'docs'})
        if code:
            return code, reason
        result = adapter.write(draft, root=root)
        if result.exit:
            return result.exit, result.reason
        record(root, draft, 'markdown', str(relative))
        return 0, f'docs: wrote page {relative}'
    if not rules['space']:
        raise state.StateError("docs: docs.space is empty; bin/wuwei config set docs.space '\"<page link>\"'")
    if not value:
        assign(item, 'new', '', root)
        value = 'new'
    ref = '' if value == 'new' else value
    draft = {'kind': 'page', 'item': item, 'title': title, 'body': _dated(body) if ref else body,
             'parent': rules['space'], 'ref': ref}
    return _outcome(root, adapter.write(draft, root=root), draft, rules['system'])


def _events(root):
    from wuwei import watch
    return watch.records(workspace.day_dir(root) / 'events.jsonl')


def findings(root, config, data):
    """The close lines for merged required-tier items whose docs obligation is unmet."""
    from wuwei import brief, registry
    lines, rows = [], None
    for name in sorted(data['items']):
        row = data['items'][name]
        if row['phase'] != 'merged' or not required(config, row):
            continue
        value = (row.get('docs') or {}).get('value')
        if not value:
            lines.append(f"{name}: no docs value (tier {row['gates']['tier']}); {command(config, name)}")
            continue
        if value == 'none':
            continue
        pending = next((key for key, draft in sorted((data.get('drafts') or {}).items())
                        if draft.get('channel') == 'docs' and draft.get('status') == 'pending'
                        and draft.get('item') == name
                        and draft['inputs']['draft'].get('kind') == 'page'), None)
        if pending:
            lines.append(f'{name}: docs draft {pending} pending; bin/wuwei drafts approve {pending}')
        elif config['docs']['system'] == 'markdown':
            host = registry.load('code_host', config)
            paths = [entry['path'] for entry in brief.read(host.files, row['pr'], root=root)] \
                if row.get('pr') else []
            if value not in paths:
                lines.append(f"{name}: docs page {value} is not in {row.get('pr') or 'its pull request'}; "
                             f'{command(config, name)}')
        else:
            rows = _events(root) if rows is None else rows
            start = next((index for index, event in enumerate(rows)
                          if (event['payload'].get('phase_changes') or {}).get(name) == 'merged'), len(rows))
            if not any(event['kind'] == 'docs.written' and event['payload'].get('item') == name
                       and event['payload'].get('kind') == 'page' for event in rows[start:]):
                lines.append(f'{name}: docs page {value} not written since the merge; '
                             f'bin/wuwei docs page {name}')
    return lines


def close(root):
    """(code, text) for wuwei close: findings refuse unless docs.strict_close is false."""
    from wuwei import watch
    try:
        config = workspace.load_config(root)
        if config['docs']['system'] == 'none' or not config['docs']['strict_close']:
            return 0, ''
        lines = findings(root, config, state.read_state(root))
        return int(bool(lines)), '\n'.join(lines)
    except watch.ERRORS as exc:
        return 2, f'docs unmeasured: {exc}'


def report_lines(root, config, data):
    """The report's ## Docs lines; [] under none so the report is unchanged."""
    if config['docs']['system'] == 'none':
        return []
    lines = []
    for name, row in sorted(data['items'].items()):
        if required(config, row):
            value = row.get('docs')
            reason = f" ({value['reason']})" if value and value.get('reason') else ''
            lines.append(f"- {name}: {value['value']}{reason}" if value else f'- {name}: missing')
    if not config['docs']['strict_close']:
        lines += [f'- {line}' for line in findings(root, config, data)]
    return lines or ['none']


SOURCES = {'report': ('wuwei report', ('Merged', 'Parked', 'Decisions answered', 'Carry', 'Docs')),
           'retro': ('wuwei retro', ('Applied', 'Proposed'))}


def _sections(text, names):
    found = dict(re.findall(r'^## ([^\n]+)\n(.*?)(?=^## |\Z)', text, re.M | re.S))
    return '\n'.join(f'## {name}\n{found[name].strip()}\n' for name in names if name in found)


def publish(root, kind):
    """Publish today's report or retro page once per kind per day (notion or confluence)."""
    from wuwei import registry
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    rules = config['docs']
    if rules['system'] == 'markdown':
        return 0, 'docs: publish has no effect under markdown'
    if rules['system'] == 'none':
        result = registry.record_none('docs', 'write', root, measurement=False)
        return result.exit, result.reason
    day = workspace.day_dir(root)
    data = state.read_state(root)
    earlier = [row['id'] for row in sorted((data.get('drafts') or {}).values(), key=lambda row: row['created'])
               if row.get('channel') == 'docs' and row['inputs'].get('draft', {}).get('kind') == kind]
    earlier += [event['payload']['page'] for event in _events(root)
                if event['kind'] == 'docs.written' and event['payload'].get('kind') == kind]
    if earlier:
        return 0, f'docs: {kind} page for {day.name} already {earlier[0]}'
    command_name, names = SOURCES[kind]
    path = day / 'report.md' if kind == 'report' else day / 'retro' / f'{day.name}.md'
    if not path.is_file() or path.is_symlink():
        raise state.StateError(f'docs: no {kind} for {day.name}; run {command_name} first')
    # A charter pointer names the workspace-relative file, like the report's decisions/D-n.md.
    body = _sections(path.read_text(encoding='utf-8'), names).replace('`.wuwei/', '`')
    title = f'{kind.capitalize()} {day.name}'
    check(title + '\n' + body, f'bin/wuwei docs publish {kind}')
    if not rules['space']:
        raise state.StateError("docs: docs.space is empty; bin/wuwei config set docs.space '\"<page link>\"'")
    draft = {'kind': kind, 'item': '', 'title': title, 'body': body, 'parent': rules['space'], 'ref': ''}
    return _outcome(root, registry.load('docs', config).write(draft, root=root), draft, rules['system'])


def published(root, kind):
    """wuwei report and wuwei retro: publish when docs.publish lists the kind; else None."""
    rules = workspace.load_config(workspace.find_workspace(root))['docs']
    if kind in rules['publish'] and rules['system'] in ('notion', 'confluence'):
        return publish(root, kind)
    return None


LINKS = {'notion': r'''https://[\w.-]*notion\.(?:so|site)/[^\s)>\]"']+''',
         'confluence': r'''https://[\w-]+\.atlassian\.net/wiki/[^\s)>\]"']+'''}


def detect(paths):
    """The first Notion or Confluence link in a repository README or CONTRIBUTING, or None."""
    pattern = '|'.join(LINKS.values())
    for path in paths:
        for name in ('README.md', 'README', 'CONTRIBUTING.md', 'CONTRIBUTING'):
            file = Path(path) / name
            if file.is_file() and not file.is_symlink():
                found = re.search(pattern, file.read_text(encoding='utf-8', errors='replace'))
                if found:
                    return found[0]
    return None
