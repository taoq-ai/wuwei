"""Validate workspace configuration."""

import json
import os
import re
import shlex
import sys

from wuwei import configtext, env, outward, registry, workspace

from wuwei.exits import CLEAN, FINDINGS, UNRUN, SYMLINK
from wuwei.workspace import ConfigError, load_config


KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*(?:\.(?:[A-Za-z_][A-Za-z0-9_-]*|[0-9]+))*')
IDENTITY = re.compile(r'(.+?) <([^<>\s]+@[^<>\s]+)>')


def register(subparsers):
    parser = subparsers.add_parser("config", help="inspect workspace configuration")
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser("check", help="validate config.toml")
    check.set_defaults(func=run)
    parser = actions.add_parser('promote', help='apply the calibration proposal (owner, asks on a card)')
    parser.add_argument('--measure', action='store_true',
                        help='time each test runner once through the checks port (runs repository commands)')
    parser.set_defaults(func=promote)
    parser = actions.add_parser('set', help='set one config value (owner, asks on a card)')
    parser.add_argument('key', help='dotted key, for example owner.verbosity.default or repos.0.merge_deploys')
    parser.add_argument('value', help='one TOML value, for example \'"standard"\' or false')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--add', action='store_true',
                      help='add the items to the current list, or the entries to the current table, '
                           'instead of replacing it (#673)')
    mode.add_argument('--replace', action='store_true',
                      help='write the value as given; the default (#673)')
    parser.set_defaults(func=set_value)
    parser = actions.add_parser('show', help='print the effective value, each row tagged default or owner')
    parser.add_argument('key', help='dotted key, for example outward.tool_patterns')
    parser.set_defaults(func=show)
    parser = actions.add_parser('add-repo', help='add one repository (owner, asks on a card)')
    parser.add_argument('--name', required=True, help='owner/repo')
    parser.add_argument('--path', required=True, help='relative to the workspace, or absolute')
    parser.add_argument('--branch', required=True, help='the default branch')
    parser.add_argument('--identity', help='commit identity, "Name <email>"')
    parser.set_defaults(func=add_repo)


def run(args):
    found = []
    try:
        root = workspace.find_workspace()
        config = load_config(root, warnings=found)
    except ConfigError as exc:
        print(f"wuwei config check: {exc}", file=sys.stderr)
        return FINDINGS
    for text in found:  # #799: unknown keys warn in every posture; the exit code ignores them.
        print(f'wuwei config check: warning: {text}', file=sys.stderr)
    print('Credentials:')
    status = CLEAN
    from wuwei import configtext  # Local: tomllib stays off the hook path.
    for line in configtext.misplaced((root / '.wuwei/config.toml').read_text(encoding='utf-8')):
        print(f'wuwei config check: {line}', file=sys.stderr)
        status = FINDINGS
    needed = requirements(config)
    for kind, name in config['adapters'].items():
        if name == 'none':
            continue
        label = f'{kind}.{name}'
        if (kind, name) == ('code_host', 'github'):
            result = registry.load(kind, config).auth_status()
            print(f'  {label}: gh auth: ' + ('set' if result.exit == 0 else
                  'missing' if result.exit == 1 else 'unmeasured'))
            if result.exit == 2:
                print(result.reason, file=sys.stderr)
            status = max(status, result.exit)
        elif (kind, name) == ('tracker', 'github') and config['tracker']['auth'] == 'gh':
            # #602: the token, when set, is used before the gh login; the login is not measured here.
            shape = _shape('GITHUB_TRACKER_TOKEN')
            print(f'  {label}: ' + ('gh login (tracker.auth = "gh"; GITHUB_TRACKER_TOKEN not set)'
                                   if shape == 'missing' else
                                   f'GITHUB_TRACKER_TOKEN: {shape} (used before tracker.auth = "gh")'))
            status = max(status, FINDINGS if shape.startswith('malformed') else CLEAN)
        elif (kind, name) == ('runtime', 'codex'):
            present = bool(config['codex']['command'])
            print(f'  {label}: codex.command: {"set" if present else "missing"}')
            status = max(status, CLEAN if present else FINDINGS)
        elif (kind, name) in needed:
            for alternatives in needed[kind, name]:
                present = any(os.environ.get(key) and not env.malformed(key) for key in alternatives)
                fields = ', '.join(f'{key}: {_shape(key)}' for key in alternatives)
                suffix = ' (one required)' if len(alternatives) > 1 else ''
                print(f'  {label}: {fields}{suffix}')
                status = max(status, CLEAN if present else FINDINGS)
        else:
            print(f'  {label}: no credential variables required')
    # Reported, not a finding: the outward lint already fails closed without a name.
    print('Owner:\n  ' + ('owner.name: set' if config['owner']['name'].strip() else outward.OWNER_UNSET))
    # Reported, not a finding (#331): a floor violation already failed load_config above.
    name, levels = workspace.posture(config)
    print(f'Posture: {name} (from {workspace.posture_source(config)})')
    for area in workspace.AREAS:
        mark = (' (floor)' if area in workspace.FLOORS else
                ' (security.areas)' if config['security']['areas'][area] else '')
        print(f'  {area}: {levels[area]}{mark}')
    print('  owner-only actions ask on a card below strict (deploys, releases, approve-tier '
          'messages); merges and approvals stay owner-only; records always block')
    block = config['scanner']['mcp']['block']
    if block:  # Reported, not a finding (#351): the list against the posture default.
        ignored = levels['mcp'] == 'off' or name == 'observe' and levels['mcp'] == 'warn'
        print(f'  scanner.mcp.block ({", ".join(block)}): ' + (
            f'no effect under {name} (mcp: {levels["mcp"]}); remove the key' if ignored else
            f'blocks launches at these severities on top of the {name} default'))
    # Design 4.5 and 9.1: the publishing guarantee lives in host rules and the credential layout.
    host = registry.load('code_host', config)
    print('Host protections:')
    for repo in config['repos']:
        status = max(status, _protection(host, repo, config['shepherd']['min_reviewers'] == 0,
                                         config['shepherd']['review_gate_check']))
    print('Seat credentials:')
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        status = max(status, _token(host, name))
    return status


def show(args):
    """#492: the effective value of one key, one row per list item or table entry."""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f'wuwei config show: {exc}', file=sys.stderr)
        return FINDINGS
    parts = [int(part) if part.isdigit() else part for part in args.key.split('.')]
    rule = configtext.declared(parts)
    try:
        value = effective(config, parts) if rule is not None else None
    except (KeyError, IndexError, TypeError):
        rule = None
    if rule is None:
        print(f'config show: unknown key {args.key}; run bin/wuwei config check for the documented keys',
              file=sys.stderr)
        return FINDINGS
    default = workspace._default(rule)
    if isinstance(value, dict):
        rows = [(f'{name} = {json.dumps(item)}', name in rule and item == workspace._default(rule[name]))
                for name, item in value.items()]
    elif isinstance(value, list):
        rows = [(json.dumps(item), item in default) for item in value]
    else:
        rows = [(json.dumps(value), value == default)]
    for text, from_default in rows:
        print(f"{text}  {'default' if from_default else 'owner'}")
    return CLEAN


def requirements(config):
    """Credential variables per selected adapter; each tuple needs one of its names."""
    needed = {
        ('tracker', 'linear'): [('LINEAR_API_KEY',)],
        ('tracker', 'jira'): [('JIRA_SITE',), ('JIRA_EMAIL',), ('JIRA_API_TOKEN',)],
        ('tracker', 'github'): [('GITHUB_TRACKER_TOKEN',)],
        ('chat', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
        ('review_bot', 'greptile'): [('GREPTILE_API_KEY',)],
        ('calendar', 'ics'): [('WUWEI_CALENDAR_URL',)],
        ('docs', 'notion'): [('NOTION_TOKEN',)],
        ('docs', 'confluence'): [('CONFLUENCE_EMAIL',), ('CONFLUENCE_API_TOKEN',)],
    }
    if config['chat']['identity'] == 'custom_app':
        needed['chat', 'slack'][0] = ('SLACK_BOT_TOKEN',)
    if config['tracker']['auth'] == 'gh':  # #602: the gh login stands in for the token
        del needed['tracker', 'github']
    return needed


def _shape(name):
    """set, missing or malformed (<why>): never the value."""
    if not os.environ.get(name):
        return 'missing'
    return f'malformed ({why})' if (why := env.malformed(name)) else 'set'


def missing(config):
    """Offline findings of config check: credential variables and codex.command."""
    needed = requirements(config)
    names = [' or '.join(alternatives) for kind, name in config['adapters'].items()
             for alternatives in needed.get((kind, name), ())
             if not any(os.environ.get(key) for key in alternatives)]
    if config['adapters']['runtime'] == 'codex' and not config['codex']['command']:
        names.append('codex.command')
    return names


def read(root):
    """(path, raw text) of config.toml, refusing a symlinked config or calibration snapshot."""
    path = root / '.wuwei/config.toml'
    if path.is_symlink() or (root / '.wuwei/calibration.json').is_symlink():
        raise ValueError(f'config.toml and calibration.json must not be symlinks; {SYMLINK}')
    return path, path.read_text(encoding='utf-8')


def proposal(root, raw, config, results):
    """(text, diff, edits, summary, snapshot): the calibration survey proposed against raw."""
    from wuwei import calibrate, workspace

    text, diff, edits = calibrate.propose(raw, results)
    today = workspace.now().date().isoformat()
    snapshot = {r['repo']['name']: {**calibrate.drift_facts(r['facts']),
                                    'baseline': r['baseline'] or 'unmeasured', 'date': today}
                for r in results}
    summary = (diff or 'No config.toml changes\n') + ''.join(
        f'Config differs; edit by hand: {key}\n' for key, _, _ in edits) + ''.join(
        f"Flagged {f['kind']}: {f['source']} ({f['value']})\n" for r in results
        for f in r['findings'] if f['kind'] in ('instruction_like', 'unsafe')) + ''.join(
        f'CI only, not proposed as a fast check: {repo}: {command} ({note})\n'
        for repo, command, note in calibrate.ci_only(results)) + (
        'Approved calibration for .wuwei/calibration.json:\n'
        + json.dumps(snapshot, indent=2, sort_keys=True) + '\n')
    return text, diff, edits, summary, snapshot


def offer(root, raw, text, summary, *, label, what, confirm=None, snapshot=None, command=None):
    """The one owner digest path: print, confirm on the owner's Owner step card, re-read, write."""
    import hashlib
    import json
    from wuwei import sessions, workspace

    print(summary, end='')
    digest = hashlib.sha256(summary.encode()).hexdigest()[:12]
    if confirm is None:  # #831
        if owner := sessions.needs_owner(root, command or f'bin/wuwei {label}', f'Apply the {what}:\n{summary}', digest):
            print(owner, file=sys.stderr)
            return FINDINGS
    elif not confirm(digest, prompt=f'Apply the {what} above.'):
        print(f'wuwei {label}: declined; nothing written; run it again', file=sys.stderr)
        return FINDINGS
    path = root / '.wuwei/config.toml'
    if path.read_text(encoding='utf-8') != raw:
        raise ValueError('config.toml changed during confirmation; nothing written, run it again')
    if text != raw:
        from wuwei import graph  # #552: the register first, from the same validated text
        try:
            graph.sync(root, workspace.load_config(root, raw=text))
        except (OSError, ValueError) as exc:  # A13: an explanation record never stops a write
            graph.warn(label, exc)
        workspace.atomic_write(path, text)
        try:
            workspace.index(root, workspace.load_config(root, raw=text))  # #735: checkouts find it
        except (OSError, ValueError) as exc:
            print(f'wuwei {label}: warning: workspace index not written: {exc}; rerun bin/wuwei init --upgrade to write it', file=sys.stderr)
    if snapshot is not None:
        workspace.atomic_write(root / '.wuwei/calibration.json',
                               json.dumps(snapshot, indent=2, sort_keys=True) + '\n')
    print(f'Applied the {what}' + (' and recorded .wuwei/calibration.json' if snapshot is not None else ''))
    return CLEAN


def promote(args, confirm=None):
    """Owner action: recompute the calibration, show it, and apply it on the owner's card answer."""
    from wuwei import calibrate, workspace

    try:
        root = workspace.find_workspace()
        config = load_config(root)
        _, raw = read(root)
        if not config['repos']:
            raise ValueError(calibrate.NO_REPOS)
        results = calibrate.survey(root, config, list(enumerate(config['repos'])),
                                   measure=getattr(args, 'measure', False))
        text, _, _, summary, snapshot = proposal(root, raw, config, results)
        return offer(root, raw, text, summary, label='config promote', what='calibration', confirm=confirm,
                     snapshot=snapshot, command='bin/wuwei config promote' + (' --measure' if getattr(args, 'measure', False) else ''))
    except ConfigError as exc:
        print(f'wuwei config promote: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'wuwei config promote: {exc}', file=sys.stderr)
        return UNRUN


def _edit(label, what, confirm, change, root=None, keys=(), add=False, command=None):
    """The owner edit frame: validate change(root, raw) -> text, then the digest path; after the
    write one replaced or added line per key in keys (#673)."""
    import difflib

    try:
        root = workspace.find_workspace(root)
        _, raw = read(root)
    except (OSError, ValueError) as exc:
        print(f'wuwei {label}: {exc}', file=sys.stderr)
        return UNRUN
    try:
        try:
            before = load_config(root, raw=raw)
        except ValueError:
            before = None  # #831: a config that does not load is repaired here; the new text must load
        text = change(root, raw)
        if text == raw:
            print('No config.toml changes')
            return CLEAN
        after = load_config(root, raw=text)
        diff = ''.join(difflib.unified_diff(raw.splitlines(keepends=True), text.splitlines(keepends=True),
                                            'config.toml', 'config.toml (proposed)'))
    except ValueError as exc:  # ConfigError, a TOML error and calibrate.LAYOUT included
        print(f'wuwei {label}: {exc}', file=sys.stderr)
        return FINDINGS
    try:
        code = offer(root, raw, text, diff, label=label, what=what, confirm=confirm, command=command)
    except (OSError, ValueError) as exc:
        print(f'wuwei {label}: {exc}', file=sys.stderr)
        return UNRUN
    if code == CLEAN:
        for line in filter(None, (changed(key, before, after, add) for key in keys)):
            print(line)
    return code


def _settle(raw, settings):
    """raw with the settings applied; a table set to a single value raises naming it."""
    from wuwei import calibrate

    additions, edits = calibrate.settle(raw, settings)
    for dotted, current, _ in edits:  # settle lists only a table answered with a non-table
        raise ValueError(f'{dotted}: a table; set one of its keys'
                         + (f', for example {dotted}.default' if 'default' in current else ''))
    return calibrate.apply(raw, additions)


def _parts(key):
    if not KEY.fullmatch(key):
        raise ValueError(f'{key}: expected a dotted key such as owner.name or repos.0.merge_deploys; use a dotted key such as owner.name')
    parts = [int(p) if p.isdigit() else p for p in key.split('.')]
    if isinstance(parts[-1], int):
        raise ValueError(f'{key}: name a key, not a list index; use the key itself, for example repos.0.merge_deploys')
    return parts


def write_value(raw, key, value, mode='replace'):
    """The one config writer entry point (#494); #492 passes mode='append' for list keys."""
    import tomllib

    from wuwei import calibrate

    parts = _parts(key)
    path, name = tuple(parts[:-1]), parts[-1]
    if mode not in ('replace', 'append'):
        raise ValueError(f'{mode}: unknown mode; use replace or append')
    if mode == 'append':
        current = (calibrate._table(tomllib.loads(raw), path) or {}).get(name, [])
        if not isinstance(current, list) or not isinstance(value, list):
            raise ValueError(f'{key}: append needs a list; use replace')
        value = [*current, *(v for v in value if v not in current)]
    return _settle(raw, [(path, name, value)])


def effective(config, parts):
    """The loaded value at a dotted key's parts; KeyError or IndexError when it has none."""
    for part in parts:
        config = config[part]
    return config


def changed(key, before, after, add):
    """#673: 'replaced: <key> = <new> (was <old>)', or 'added' for --add and a deploy list;
    None when either value cannot be read, so the report never fails a done write."""
    from wuwei import calibrate

    parts = [int(part) if part.isdigit() else part for part in key.split('.')]
    try:
        old, new = effective(before, parts), effective(after, parts)
    except (KeyError, IndexError, TypeError):
        return None
    verb = 'added' if add or calibrate.grows(tuple(parts[:-1]), old) else 'replaced'
    return f'{verb}: {key} = {configtext.dumps(new, inline=True)} (was {configtext.dumps(old, inline=True)})'


def merged(config, parts, value, add=False):
    """The settings for one key: the value as given (#673); with add (#492) a list gets the
    effective items plus the new ones, a named-entry table one setting per entry."""
    rule = configtext.declared(parts)
    table = isinstance(rule, dict) and '*' in rule
    if add and isinstance(rule, list) and isinstance(value, list):
        if not value:
            return []
        try:
            current = effective(config, parts)
        except (KeyError, IndexError):  # repos.<n> past the end: settle names the layout
            current = []
        return [(tuple(parts[:-1]), parts[-1], [*current, *(item for item in value if item not in current)])]
    if add and table and isinstance(value, dict):
        return [(tuple(parts), name, item) for name, item in value.items()]
    if add:
        raise ValueError(f"{'.'.join(map(str, parts))}: --add applies to a list or a "
                         'named-entry table; remove --add')
    return [(tuple(parts[:-1]), parts[-1], value)]


def set_value(args, confirm=None):
    """Owner action: set one config value on the owner's Owner step card answer (#831)."""
    import tomllib

    def change(root, raw):
        parts = _parts(args.key)
        node = configtext.declared(parts)
        try:
            parsed = tomllib.loads(f'value = {args.value}\n')
        except tomllib.TOMLDecodeError:
            if node is None:
                parsed = {}
            else:
                kind, example = configtext.describe(node)
                raise ValueError(f"{args.key}: {args.value!r} is not TOML; pass {kind}, for example '{example}'") from None
        if list(parsed) != ['value']:
            raise ValueError(f'{args.value!r}: expected one TOML value; pass one TOML value, for example \'"standard"\' or false')
        add = getattr(args, 'add', False)  # only --add reads the current values
        return _settle(raw, merged(load_config(root, raw=raw) if add else None, parts, parsed['value'], add))

    command = shlex.join(['bin/wuwei', 'config', 'set', args.key, args.value])
    return _edit('config set', 'change', confirm, change, keys=[args.key], add=getattr(args, 'add', False),
                 command=command)


def repo_tables(raw, repos):
    """raw plus one [[repos]] table per repository; every value escaped through json.dumps."""
    text = raw if raw.endswith('\n') else raw + '\n'
    for repo in repos:
        text += ''.join(f'\n[[repos]]\nname = {json.dumps(repo["name"])}\npath = {json.dumps(repo["path"])}\n'
                        f'default_branch = {json.dumps(repo["default_branch"])}\n')
        if repo.get('identity'):
            text += (f'identity = {{name = {json.dumps(repo["identity"]["name"])}, '
                     f'email = {json.dumps(repo["identity"]["email"])}}}\n')
    return text


def add_repo(args, confirm=None):
    """Owner action: add one [[repos]] table on the owner's Owner step card answer (#831)."""
    from wuwei import references

    def change(root, raw):
        repo = {'name': references.repository(args.name), 'path': args.path, 'default_branch': args.branch}
        if args.identity is not None:
            found = IDENTITY.fullmatch(args.identity)
            if not found:
                raise ValueError('--identity: expected "Name <email>"; pass --identity "Name <email>"')
            repo['identity'] = {'name': found[1], 'email': found[2]}
        return repo_tables(raw, [repo])

    command = shlex.join(['bin/wuwei', 'config', 'add-repo', '--name', args.name, '--path', args.path,
                          '--branch', args.branch, *(['--identity', args.identity] if args.identity is not None else [])])
    return _edit('config add-repo', 'repository', confirm, change, command=command)


def _protection(host, repo, solo, gate):
    branch = repo['default_branch']
    label = f"  {repo['name']} {branch}"
    result = host.protection(repo['name'], branch)
    try:
        if result.exit:
            raise ValueError(result.reason)
        data = result.data
        names = sorted({check['name'] for check in data['required_checks']})
        listed = ', '.join(names)
        absent = [name for name in repo['review_required_checks'] if name not in names]
        rows = [
            # Information only: a 404 means unprotected or no admin; rulesets still measure below.
            ('protected ref', 'ok', '') if data['classic'] else
            ('classic protection', 'none visible (404: unprotected or no admin)', ''),
            ('required checks', f'ok ({listed})' if names and not absent else None,
             f'require status checks on {branch}' + (': ' + ', '.join(absent) if absent else '')
             + (f'; required now: {listed}' if names else '')),
            ('required reviews', 'ok' if data['approvals'] >= 1 else
             'ok (solo owner: shepherd.min_reviewers = 0)' if solo else None,
             f'require at least 1 approving review on {branch}, '
             'or set shepherd.min_reviewers = 0 for a solo owner'
             + (f'; the required check {gate} (shepherd.review_gate_check) may be satisfying it'
                if gate in names else '')),
            ('force pushes', 'ok' if data['allow_force_pushes'] is False else None,
             f'block force pushes on {branch}'),
            ('deletions', 'ok' if data['allow_deletions'] is False else None,
             f'block deletions of {branch}'),
        ]
    except (KeyError, TypeError, ValueError):
        print(f'{label}: protection: unmeasured')
        print(result.reason or f"{repo['name']}: unreadable protection result; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter", file=sys.stderr)
        return UNRUN
    for name, state, fix in rows:
        print(f'{label}: {name}: {state or f"missing ({fix})"}')
    if all(state for _, state, _ in rows):
        return CLEAN
    print(f"{label}: fix in https://github.com/{repo['name']}/settings/branches")
    if not data['classic']:  # Nothing to overwrite: one PUT sets the whole recommended layout.
        import shlex
        from urllib.parse import quote
        contexts = repo['review_required_checks']
        argv = ['gh', 'api', '-X', 'PUT', f"repos/{repo['name']}/branches/{quote(branch, safe='')}/protection",
                '-F', 'enforce_admins=false', '-F', 'restrictions=null',
                '-F', 'allow_force_pushes=false', '-F', 'allow_deletions=false',
                '-F', 'required_pull_request_reviews=null' if solo else
                'required_pull_request_reviews[required_approving_review_count]=1',
                *(['-F', 'required_status_checks[strict]=false',
                   *(arg for name in contexts for arg in ('-f', f'required_status_checks[contexts][]={name}'))]
                  if contexts else ['-F', 'required_status_checks=null'])]
        print(f'{label}: or run in your own terminal: {shlex.join(argv)}')
    return FINDINGS


def _token(host, name):
    if not os.environ.get(name):
        print(f'  {name}: not set')
        return CLEAN
    source = '.wuwei/env' if name in env._loaded else 'the environment'
    if name in env._shadowed:
        print(f'  {name} ({source}): unmeasured')
        print(f'{name}: the environment value shadows the .wuwei/env value, which was not measured; unset it in the environment, or remove it from .wuwei/env',
              file=sys.stderr)
        return UNRUN
    result = host.token_scopes(name)
    scopes = result.data.get('scopes') if result.exit == 0 and isinstance(result.data, dict) else None
    if not scopes or not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        print(f'  {name} ({source}): unmeasured')
        print(result.reason or f'{name}: unreadable scopes; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter', file=sys.stderr)
        return UNRUN
    if all(scope.startswith('read:') for scope in scopes):
        print(f'  {name} ({source}): read-only')
        return CLEAN
    print(f"  {name} ({source}): write scopes {', '.join(scopes)}; remove it from {source}, "
          "seats can read it (publish from your own gh login)")
    return FINDINGS
