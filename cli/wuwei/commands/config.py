"""Validate workspace configuration."""

import os
import re
import sys

from wuwei import configtext, env, outward, registry, workspace

from wuwei.exits import CLEAN, FINDINGS, UNRUN, SYMLINK
from wuwei.workspace import ConfigError, load_config


PIN_MISSING = 'control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)'


def register(subparsers):
    parser = subparsers.add_parser("config", help="inspect workspace configuration")
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser("check", help="validate config.toml")
    check.set_defaults(func=run)
    parser = actions.add_parser('promote', help='apply the calibration proposal (owner, host terminal)')
    only = parser.add_mutually_exclusive_group()
    only.add_argument('--measure', action='store_true',
                      help='time each test runner once through the checks port (runs repository commands)')
    only.add_argument('--keys', nargs='+', metavar='KEY',
                      help="apply only these dotted keys of today's answers, also over a value already "
                           'set (#604); no repository survey')
    parser.set_defaults(func=promote)
    from wuwei.commands import setup
    parser = actions.add_parser('set', help='set one config value (owner, host terminal)')
    parser.add_argument('key', nargs='?',
                        help='dotted key, for example owner.verbosity.default or repos.0.merge_deploys; '
                             'optional with --from-card, which reads it from the answered option')
    parser.add_argument('value', nargs='?', help='one TOML value, for example \'"standard"\' or false')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--add', action='store_true',
                      help='add the items to the current list, or the entries to the current table, '
                           'instead of replacing it (#673)')
    mode.add_argument('--replace', action='store_true',
                      help='write the value as given; the default (#673)')
    parser.add_argument('--from-card', dest='from_card', metavar='D-n',
                        help="the decision card whose answer is this assignment (#529): the owner's "
                             'answer is the confirmation outside strict')
    parser.set_defaults(func=setup.set_value)
    parser = actions.add_parser('show', help='print the effective value, each row tagged default or owner')
    parser.add_argument('key', help='dotted key, for example outward.tool_patterns')
    parser.set_defaults(func=show)
    parser = actions.add_parser('add-repo', help='add one repository (owner, host terminal)')
    parser.add_argument('--name', required=True, help='owner/repo')
    parser.add_argument('--path', required=True, help='relative to the workspace, or absolute')
    parser.add_argument('--branch', required=True, help='the default branch')
    parser.add_argument('--identity', help='commit identity, "Name <email>"')
    parser.set_defaults(func=setup.add_repo)


def run(args):
    found = []
    try:
        root = workspace.find_workspace()
        config = load_config(root, warnings=found)
    except ConfigError as exc:
        print(f"wuwei config check: {exc}", file=sys.stderr)
        return FINDINGS
    for text in found:  # #353: unknown keys warn below strict; the exit code ignores them.
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
    if config['adapters']['inbound'] != 'none':
        from wuwei.remote import PIN
        pin = config['control_plane']['owner']
        valid = bool(re.fullmatch(PIN, pin))
        print('Control plane:\n  ' + ('control_plane.owner: set' if valid else
              'control_plane.owner: invalid (expected <team id>/<user id>)' if pin else PIN_MISSING))
        status = max(status, CLEAN if valid else FINDINGS)
        # Reported, not a finding: without it a confirm reply is the second factor.
        print('  WUWEI_TOTP_SECRET: ' + ('set' if os.environ.get('WUWEI_TOTP_SECRET') else
                                        'missing (confirm replies are the only second factor)'))
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
    import json
    from wuwei.commands import setup
    try:
        config = load_config()
    except ConfigError as exc:
        print(f'wuwei config show: {exc}', file=sys.stderr)
        return FINDINGS
    parts = [int(part) if part.isdigit() else part for part in args.key.split('.')]
    rule = configtext.declared(parts)
    try:
        value = setup.effective(config, parts) if rule is not None else None
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
        ('inbound', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
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
    """Offline findings of config check: credential variables, codex.command, owner pin."""
    from wuwei.remote import PIN
    needed = requirements(config)
    names = [' or '.join(alternatives) for kind, name in config['adapters'].items()
             for alternatives in needed.get((kind, name), ())
             if not any(os.environ.get(key) for key in alternatives)]
    if config['adapters']['runtime'] == 'codex' and not config['codex']['command']:
        names.append('codex.command')
    if (config['adapters']['inbound'] != 'none'
            and not re.fullmatch(PIN, config['control_plane']['owner'])):
        names.append('control_plane.owner')
    return names


def read(root):
    """(path, raw text) of config.toml, refusing a symlinked config or calibration snapshot."""
    path = root / '.wuwei/config.toml'
    if path.is_symlink() or (root / '.wuwei/calibration.json').is_symlink():
        raise ValueError(f'config.toml and calibration.json must not be symlinks; {SYMLINK}')
    return path, path.read_text(encoding='utf-8')


def proposal(root, raw, base, config, results, extra=(), keys=None):
    """(text, diff, edits, summary, snapshot): the calibration of base, diffed against raw.

    #604: keys None (setup) applies every answer; () keeps a present key an answer would
    change and lists it; named keys apply only those answer and profile settings."""
    import difflib
    import json
    from wuwei import calibrate, interview, profiles, workspace

    answers = interview.load(root, config)
    name, imported = profiles.load(root, config)
    asked = interview.settings(answers, config)
    # An interview answer wins over the profile for the same key, and both over a setup default.
    imported = [s for s in imported if s[:2] not in {a[:2] for a in asked}]
    skipped, missing = [], []
    dotted = lambda s: '.'.join(map(str, (*s[0], s[1])))  # noqa: E731
    if keys:
        missing = [key for key in keys if key not in {dotted(s) for s in imported + asked}]
        imported, asked = ([s for s in found if dotted(s) in keys] for found in (imported, asked))
    elif keys is not None:
        asked, skipped = calibrate.kept(base, asked)
    owned = {s[:2] for s in imported + asked}
    text, diff, edits = calibrate.propose(
        base, results, [s for s in extra if s[:2] not in owned] + imported + asked)
    if base != raw:
        diff = ''.join(difflib.unified_diff(raw.splitlines(keepends=True), text.splitlines(keepends=True),
                                            'config.toml', 'config.toml (proposed)'))
    today = workspace.now().date().isoformat()
    snapshot = {r['repo']['name']: {**calibrate.drift_facts(r['facts']),
                                    'baseline': r['baseline'] or 'unmeasured', 'date': today}
                for r in results}
    summary = (diff or 'No config.toml changes\n') + ''.join(
        f'Config differs; edit by hand: {key}\n' for key, _, _ in edits) + ''.join(
        f'Skipped {key}: kept {json.dumps(current)}; to apply the answer run '
        f'bin/wuwei config promote --keys {key}\n' for key, current in skipped) + ''.join(
        f"Not in today's answers: {key}; use a key listed under Interview answers, or answer its "
        'question first: bin/wuwei calibrate --questions\n' for key in missing) + (
        'Interview answers:\n' + ''.join(line + '\n' for line in interview.describe(answers, config))
        if answers else '') + ''.join(
        f"Profile {name}: {'.'.join(map(str, (*path, key)))} = {json.dumps(value)}\n"
        for path, key, value in imported) + ''.join(
        f"Flagged {f['kind']}: {f['source']} ({f['value']})\n" for r in results
        for f in r['findings'] if f['kind'] in ('instruction_like', 'unsafe')) + ''.join(
        f'CI only, not proposed as a fast check: {repo}: {command} ({note})\n'
        for repo, command, note in calibrate.ci_only(results)) + (
        'Approved calibration for .wuwei/calibration.json:\n'
        + json.dumps(snapshot, indent=2, sort_keys=True) + '\n' if not keys else '')
    return text, diff, edits, summary, snapshot


def offer(root, raw, text, summary, *, label, what, confirm=None, snapshot=None):
    """The one owner digest path: print, confirm on the host terminal, re-read, write."""
    import hashlib
    import json
    from wuwei import integrity, workspace

    print(summary, end='')
    digest = hashlib.sha256(summary.encode()).hexdigest()[:12]
    if not (confirm or integrity._host_confirm)(
            digest, prompt=f'Apply the {what} above.'):
        print(f'wuwei {label}: declined; nothing written; rerun it in a host terminal and answer y', file=sys.stderr)
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
    """Owner action: recompute the calibration, show it, and apply it after a terminal digest."""
    from wuwei import calibrate, workspace

    try:
        root = workspace.find_workspace()
        config = load_config(root)
        _, raw = read(root)
        keys = tuple(getattr(args, 'keys', None) or ())  # doctor passes a bare Namespace()
        if keys:  # #604: today's answers only: no survey, no calibration.json
            text, _, _, summary, _ = proposal(root, raw, raw, config, [], keys=keys)
            missing = "Not in today's answers: " in summary  # a named key no answer sets: nothing written
            if text == raw or missing:
                print(summary, end='')
                return FINDINGS if missing else CLEAN
            return offer(root, raw, text, summary, label='config promote', what='calibration',
                         confirm=confirm)
        if not config['repos']:
            raise ValueError(calibrate.NO_REPOS)
        results = calibrate.survey(root, config, list(enumerate(config['repos'])), style=False,
                                   measure=getattr(args, 'measure', False))
        text, _, _, summary, snapshot = proposal(root, raw, raw, config, results, keys=())
        return offer(root, raw, text, summary, label='config promote', what='calibration',
                     confirm=confirm, snapshot=snapshot)
    except ConfigError as exc:
        print(f'wuwei config promote: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'wuwei config promote: {exc}', file=sys.stderr)
        return UNRUN


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
          "seats can read it (publish from the owner's own gh login)")
    return FINDINGS
