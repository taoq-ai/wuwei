"""init writes the workspace and merges WUWEI's few rules into the harness's own permissions;
doctor says how strongly each rule holds in each repository."""

import json
import os
from pathlib import Path
import shutil
import sys

from wuwei import gh, guards, ws

ALLOW = ['Bash(git:*)', 'Bash(gh:*)', 'Read', 'Edit', 'Write', 'Glob', 'Grep']
DENY = ['Bash(git push --force:*)', 'Bash(git push -f:*)', 'Bash(git push --mirror:*)',
        'Bash(gh pr merge --admin:*)', 'Bash(gh repo delete:*)',
        'Edit(.wuwei/ledger.jsonl)', 'Write(.wuwei/ledger.jsonl)',
        'Edit(.wuwei/ledger/**)', 'Write(.wuwei/ledger/**)']
ASK = [f'Bash({tool} {verb}:*)' for tool, verbs in (('terraform', ('apply', 'destroy')), ('tofu', ('apply', 'destroy')),
                                                     ('pulumi', ('up', 'destroy')), ('kubectl', ('apply', 'delete')),
                                                     ('helm', ('install', 'upgrade', 'uninstall'))) for verb in verbs]
GOALS = '''# Goals

One block per goal. The plan's items each name the goal they serve.

## G-1
Outcome:
Measure:
Target:
Date:
Priority: 1
'''


def merge_settings(directory, cloud=False):
    """Add WUWEI's rules, and in the cloud its hooks, to .claude/settings.json without touching anything else in it."""
    path = Path(directory) / '.claude' / 'settings.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    permissions = data.setdefault('permissions', {})
    for key, rules in (('allow', ALLOW), ('deny', DENY), ('ask', ASK)):
        current = permissions.setdefault(key, [])
        current.extend(rule for rule in rules if rule not in current)
    for event in EVENTS if cloud else ():
        command = f'"$CLAUDE_PROJECT_DIR"/.claude/wuwei/bin/wuwei hook {event}'
        entries = data.setdefault('hooks', {}).setdefault(event, [])
        if not any(h.get('command') == command for entry in entries for h in entry.get('hooks', [])):
            entries.append({'hooks': [{'type': 'command', 'command': command}]})
    ws.atomic_write(path, json.dumps(data, indent=2) + '\n')
    return path


EVENTS = ('SessionStart', 'PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop')
IGNORE = '# The state travels on the wuwei/state branch (wuwei sync), never in a working branch.\n*\n'


def vendor(directory):
    """Copy the plugin into the repository's .claude/ for cloud sessions, where a repository's
    plugins do not load but its settings, skills and agents do."""
    claude = Path(directory) / '.claude'
    shutil.rmtree(claude / 'wuwei', ignore_errors=True)
    for name in ('bin', 'cli', 'charters', '.claude-plugin'):
        shutil.copytree(ws.PLUGIN / name, claude / 'wuwei' / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    ws.atomic_write(claude / 'wuwei' / '.gitignore', '__pycache__/\n')
    if (old := claude / 'skills' / 'wuwei' / 'SKILL.md').is_file() and 'name: wuwei\n' in old.read_text(encoding='utf-8'):
        shutil.rmtree(old.parent)  # 2.0 renamed WUWEI's reference skill to wuwei-rules; a repository's own skills stay
    for skill in (ws.PLUGIN / 'skills').iterdir():
        shutil.copytree(skill, claude / 'skills' / skill.name, dirs_exist_ok=True)
    (claude / 'agents').mkdir(exist_ok=True)
    for agent in (ws.PLUGIN / 'agents').glob('*.md'):
        shutil.copy2(agent, claude / 'agents' / agent.name)
    return claude


def codex_files(directory):
    """Codex loads agent roles and exec-policy rules from the project's .codex/, not from a plugin:
    WUWEI's roles go there, and its doors as rules (forbidden, or prompt for infrastructure)."""
    from wuwei import agents
    base = Path(directory) / '.codex'
    for role in agents.DESCRIPTIONS:
        ws.atomic_write(base / 'agents' / f'{role}.toml', agents.render_codex(ws.PLUGIN, role))
    pattern = lambda rule: json.dumps(rule[len('Bash('):-len(':*)')].split())  # noqa: E731
    rules = [f'prefix_rule(pattern = {pattern(r)}, decision = "forbidden")' for r in DENY if r.startswith('Bash(')]
    rules += [f'prefix_rule(pattern = {pattern(r)}, decision = "prompt")' for r in ASK]
    ws.atomic_write(base / 'rules' / 'wuwei.rules',
                    '# WUWEI doors for Codex, written by wuwei init --codex.\n' + '\n'.join(rules) + '\n')
    return base


def init(directory, cloud=False, codex=False):
    directory = Path(directory).resolve()
    (base := directory / ws.DIR).mkdir(exist_ok=True)
    from wuwei import upgrade
    done = list(upgrade.run(directory))
    if not (base / 'config.toml').is_file():
        repo = guards.origin(str(directory))
        ws.write_config(directory, {**ws.DEFAULTS, 'repos': [repo] if repo else []})
        done.append(f'config: {base / "config.toml"} (repos: {repo or "none found; wuwei config repos owner/name"})')
    if not (base / 'goals.md').is_file():
        ws.atomic_write(base / 'goals.md', GOALS)
        done.append('goals: .wuwei/goals.md (fill G-1, or let the first plan pass propose goals)')
    if not (base / '.gitignore').is_file():
        ws.atomic_write(base / '.gitignore', IGNORE)
    if not (base / 'canary').is_file():
        ws.atomic_write(base / 'canary', f'wuwei-canary-{os.urandom(12).hex()}\n')
    done.append(f'permissions: {merge_settings(directory, cloud)} (allow everyday work, deny the doors, ask for infrastructure)')
    if codex:
        done.append(f'codex: role agents and door rules in {codex_files(directory)} (trust the WUWEI hooks once in Codex)')
    if cloud:
        done.append(f'cloud: the plugin copied into {vendor(directory)}; commit .claude/ so cloud sessions load it')
    ws.record(directory, 'workspace.init', {'version': ws.version()})
    return done


def _levels(rule_types):
    merge = 'wall + refused' if {'pull_request', 'required_status_checks'} <= rule_types else 'refused + detected'
    return {'merge with gaps': merge,
            'force push': 'wall + refused' if 'non_fast_forward' in rule_types else 'refused',
            'default branch deletion': 'wall + refused' if 'deletion' in rule_types else 'refused'}


def doctor(root):
    rows = [('python', 'ok' if sys.version_info >= (3, 11) else 'fail', sys.version.split()[0])]
    repos = (config := ws.config(root) if root else ws.DEFAULTS)['repos']
    try:  # a REST read, as WUWEI reads: in a cloud session the proxy's token fails auth status (#1062)
        gh.default_branch(repos[0]) if repos else gh.run(['auth', 'status'])
        rows.append(('gh', 'ok', f'reads {repos[0]}' if repos else 'authenticated'))
    except gh.GhError as exc:
        rows.append(('gh', 'fail', str(exc)))
    if root is None:
        return rows + [('workspace', 'fail', 'no .wuwei/ here or above: run wuwei init')]
    broken = ws.verify(root)
    rows += [('workspace', 'ok', str(root)),
             ('repos', 'ok' if config['repos'] else 'warn', ', '.join(config['repos']) or 'none configured'),
             ('ledger', 'ok' if not broken else 'fail', 'intact' if not broken else f'broken at {", ".join(broken)}'),
             ('canary', 'ok' if (Path(root) / ws.DIR / 'canary').is_file() else 'warn', '.wuwei/canary')]
    if (roles := Path(root) / '.codex' / 'agents').is_dir():
        from wuwei import agents
        stale = [r for r in agents.DESCRIPTIONS if not (roles / f'{r}.toml').is_file()
                 or (roles / f'{r}.toml').read_text(encoding='utf-8') != agents.render_codex(ws.PLUGIN, r)]
        rows.append(('codex roles', 'warn' if stale else 'ok',
                     f'stale: {", ".join(stale)}: run wuwei init --codex' if stale else 'match the charters'))
    if gone := ws.retired(root):
        rows.append(('retired config', 'warn', ', '.join(gone) + ': run wuwei init to upgrade the workspace'))
    settings = Path(root) / '.claude' / 'settings.json'
    have = json.loads(settings.read_text()).get('permissions', {}) if settings.is_file() else {}
    missing = [r for r in DENY if r not in have.get('deny', [])]
    rows.append(('harness rules', 'ok' if not missing else 'warn', 'present' if not missing else 'run wuwei init'))
    seen = ws.cache_get(root, 'hook-seen', 120)  # PreToolUse writes it, and the doctor's own Bash call fires PreToolUse
    rows.append(('hooks', 'ok', f'fired {max(0, round(ws.now().timestamp() - seen))}s ago') if isinstance(seen, (int, float))
                else ('hooks', 'warn', 'no hook fired in the last 2 minutes: inside a session, the doors and attestations are off'))
    for repo in config['repos']:
        try:
            branch = gh.default_branch(repo)
            types = {rule.get('type') for rule in gh.rules(repo, branch)}
        except gh.GhError as exc:
            rows.append((repo, 'warn', f'rules unreadable ({exc}): every door is refused + detected only'))
            continue
        for door, level in _levels(types).items():
            rows.append((f'{repo} {door}', 'ok' if level.startswith('wall') else 'warn', level))
    return rows
