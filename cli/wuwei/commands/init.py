"""Create a workspace from the shipped skeleton."""

import json
import os
import re
import shlex
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei import env, security, workspace
from wuwei.guards.deploy import PERMISSIONS_DENY

LAYOUT = '''Recommended publishing layout (design 4.5, 9.1):
  protect each repository's default_branch: required status checks including the test jobs,
  at least 1 approving review (or shepherd.min_reviewers = 0 for a solo owner),
  no force pushes, no deletions
  keep write-scoped GH_TOKEN and GITHUB_TOKEN out of .wuwei/env and the environment seats
  inherit; publish from the owner's own gh login
Verify with: wuwei config check'''


def register(subparsers):
    parser = subparsers.add_parser("init", help="create a workspace")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--upgrade", action="store_true", help="upgrade an existing workspace")
    parser.add_argument("--dry-run", action="store_true", help="show the upgrade plan")
    parser.add_argument("--posture", choices=tuple(workspace.POSTURES),
                        help="security posture for a new workspace: observe, guarded or strict")
    parser.add_argument("--shadow", action="store_true", help="same as --posture observe")
    parser.add_argument("--menu-bar", action="store_true", help="show SwiftBar setup instructions")
    parser.add_argument("--honeytoken-path", default=security.DEFAULT_HONEYTOKEN_PATH,
                        help="decoy credentials path relative to .wuwei")
    parser.set_defaults(func=run)


def run(args):
    posture = 'observe' if getattr(args, 'shadow', False) else getattr(args, 'posture', None)
    if posture and (getattr(args, 'upgrade', False) or getattr(args, 'menu_bar', False)):
        flag = '--shadow' if getattr(args, 'shadow', False) else '--posture'
        raise ValueError(f'{flag} applies to a new workspace; set security.posture in config.toml')
    if getattr(args, 'menu_bar', False):
        if getattr(args, 'upgrade', False) or getattr(args, 'dry_run', False):
            raise ValueError('--menu-bar cannot be combined with --upgrade or --dry-run')
        if sys.platform != 'darwin':
            print('SwiftBar menu bar is macOS only')
            return CLEAN
        template = Path(__file__).resolve().parents[3] / 'templates/swiftbar/wuwei.1m.sh'
        print(f'Copy {template} into your SwiftBar Plugins folder as wuwei.1m.sh.')
        print('Add this line near the top of the copied script:')
        print(f'export WUWEI_WORKSPACE={shlex.quote(str(Path(args.path).expanduser().resolve()))}')
        print('Install SwiftBar first if it is absent. No menu bar plugin runs until installed.')
        return CLEAN
    if getattr(args, 'dry_run', False) and not getattr(args, 'upgrade', False):
        raise ValueError('--dry-run requires --upgrade')
    if getattr(args, 'upgrade', False):
        return upgrade(args)
    destination = Path(args.path).expanduser() / ".wuwei"
    if destination.exists() or destination.is_symlink():
        print(f"wuwei init: {destination} already exists; run wuwei init {args.path} --upgrade to update it", file=sys.stderr)
        return FINDINGS
    settings = destination.parent / '.claude/settings.json'
    if settings.parent.is_symlink() or settings.is_symlink():
        raise ValueError('workspace settings must not be symlinks')
    if destination.parent.resolve() == Path.home().resolve():
        raise ValueError('workspace settings must not be owner global settings')
    data = json.loads(settings.read_text()) if settings.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get('permissions', {}), dict):
        raise ValueError('workspace settings and permissions must be objects')
    permissions = data.setdefault('permissions', {})
    denials = permissions.setdefault('deny', [])
    if not isinstance(denials, list) or not all(isinstance(rule, str) for rule in denials):
        raise ValueError('workspace permissions.deny must be a list of strings')
    permissions['deny'] = list(dict.fromkeys([*denials, *PERMISSIONS_DENY]))
    template = Path(__file__).resolve().parents[3] / "templates/workspace"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".wuwei-init-", dir=destination.parent)
    try:
        shutil.copytree(template, staging, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".gitkeep"))
        security.initialize(Path(staging), getattr(args, "honeytoken_path", security.DEFAULT_HONEYTOKEN_PATH))
        env.initialize(Path(staging))
        from wuwei.commands.agents import write_workspace
        write_workspace(template.parents[1], Path(staging))
        executable = Path(__file__).resolve().parents[3] / "bin/wuwei"
        (Path(staging) / "executable").write_text(str(executable) + "\n")
        if posture:
            config = Path(staging) / 'config.toml'
            text = config.read_text(encoding='utf-8').replace(
                'posture = "guarded"', f'posture = "{posture}"', 1)
            if posture == 'observe':
                text = text.replace(
                    'shadow_since = ""', f'shadow_since = "{workspace.now().date().isoformat()}"', 1)
            config.write_text(text, encoding='utf-8')
        from wuwei import integrity
        integrity.initialize(Path(staging))
        settings.parent.mkdir(exist_ok=True)
        workspace.atomic_write(settings, json.dumps(data, indent=2) + '\n')
        os.rename(staging, destination)
    finally:
        if os.path.exists(staging):
            shutil.rmtree(staging)
    print(f"Created {destination.resolve()}")
    _status_line(executable)
    if (destination.parent / '.git').exists():
        print('This project is a Git repository; add these lines to its .gitignore:')
        print('.wuwei/\n.claude/')
    print(LAYOUT)
    return _finish(destination.parent)


def _status_line(executable):
    print(json.dumps({"statusLine": {"type": "command",
                                   "command": shlex.quote(str(executable)) + " status --line"}}))
    print('Status line: put the "statusLine" key above in .claude/settings.json (this project) '
          'or ~/.claude/settings.json (every project).')


def _finish(root):
    code = _register_mcp(root)
    from wuwei import integrity
    print(integrity.check(root).reason or 'plugin integrity: clean')
    return code


def _register_mcp(root):
    from wuwei import mcp
    result = mcp.check(root)
    if result.reason:
        print(result.reason, file=sys.stderr)
    return result.exit


def _sections(raw):
    """Return table sections, including the root section, with source lines."""
    sections = [('', [])]
    for line in raw.splitlines(keepends=True):
        match = re.match(r'^\s*\[\[([A-Za-z_.]+)\]\]\s*(?:#.*)?$', line)
        if match:
            sections.append((f'[[{match.group(1)}]]', [line]))
        else:
            match = re.match(r'^\s*\[([A-Za-z_.]+)\]\s*(?:#.*)?$', line)
            if match:
                sections.append((match.group(1), [line]))
            else:
                sections[-1][1].append(line)
    return sections


def _without_empty_repos(raw):
    """Drop a top-level one-line repos = [] that [[repos]] tables make a TOML error (#326)."""
    sections = _sections(raw)
    if not any(label == '[[repos]]' for label, _ in sections):
        return raw
    sections[0][1][:] = [line for line in sections[0][1]
                         if not re.fullmatch(r'\s*repos\s*=\s*\[\s*\]\s*(?:#.*)?\n?', line)]
    return ''.join(''.join(lines) for _, lines in sections)


def _migrated_config(raw, template):
    present = tomllib.loads(raw)
    source = _sections(template)
    target = _sections(raw)
    changed = []
    for name, lines in source:
        section = next((chunk for label, chunk in reversed(target) if label == name), None)
        if section is None:
            target.append((name, ['\n', *lines]))
            changed.append(name)
            continue
        table = present
        for part in name.split('.') if name else ():
            table = table.get(part, {}) if isinstance(table, dict) else {}
        additions = []
        for line in lines:
            match = re.match(r'^([A-Za-z_][A-Za-z_0-9]*)\s*=', line)
            if match and match.group(1) not in table:
                additions.append(line)
                changed.append(f'{name + "." if name else ""}{match.group(1)}')
        if additions:
            if section and not section[-1].endswith('\n'):
                section.append('\n')
            section.extend(['# Added by wuwei init --upgrade from the current template.\n',
                            *additions])
    if not changed:
        return raw, []
    result = ''.join(''.join(lines) for _, lines in target)
    upgraded = tomllib.loads(result)
    if not _preserves_values(present, upgraded):
        raise ValueError('migration would change an owner value; cannot safely upgrade this TOML layout')
    return result, changed


def _preserves_values(before, after):
    if isinstance(before, dict):
        return isinstance(after, dict) and all(
            key in after and _preserves_values(value, after[key]) for key, value in before.items())
    if isinstance(before, list):
        return isinstance(after, list) and len(before) == len(after) and all(
            _preserves_values(old, new) for old, new in zip(before, after))
    return before == after


def _charter_version(raw):
    if not raw.startswith('---\n'):
        return None
    frontmatter = raw.split('---', 2)
    if len(frontmatter) < 3:
        return None
    match = re.search(r'^version:\s*([^\s#]+)', frontmatter[1], re.MULTILINE)
    return match.group(1) if match else None


def upgrade(args):
    destination = Path(args.path).expanduser() / '.wuwei'
    if not destination.is_dir():
        print(f'wuwei init: {destination} is not a workspace', file=sys.stderr)
        return FINDINGS
    config_path = destination / 'config.toml'
    pointer_path = destination / 'executable'
    if config_path.is_symlink() or pointer_path.is_symlink():
        print('wuwei init: config.toml and executable must not be symlinks', file=sys.stderr)
        return UNRUN
    try:
        env.load(destination.parent)
        raw = config_path.read_text(encoding='utf-8')
        text = _without_empty_repos(raw)
        tomllib.loads(text)
        workspace.load_config(destination.parent, raw=text)
        plugin = Path(__file__).resolve().parents[3]
        template = (plugin / 'templates/workspace/config.toml').read_text(encoding='utf-8')
        migrated, added = _migrated_config(text, template)
        executable = plugin / 'bin/wuwei'
        pointer = pointer_path.read_text(encoding='utf-8') if pointer_path.exists() else ''
        conflicts = []
        for local in sorted((destination / 'charters').glob('*.md')):
            base = plugin / 'charters' / local.name
            local_version = _charter_version(local.read_text(encoding='utf-8'))
            base_version = _charter_version(base.read_text(encoding='utf-8')) if base.is_file() else None
            if local_version != base_version or base_version is None:
                conflicts.append((local.name, local_version, base_version))
        security_data = security.load(destination.parent, raw=text)
        config_changed = migrated != raw
        pointer_changed = pointer != str(executable) + '\n'
        env_changed = env.initialize(destination, dry_run=args.dry_run)
        prefix = 'Would upgrade' if args.dry_run else 'Upgraded'
        if not args.dry_run:
            if security_data is None:
                security.initialize(destination, getattr(args, 'honeytoken_path', security.DEFAULT_HONEYTOKEN_PATH))
            from wuwei.commands.agents import write_workspace
            write_workspace(plugin, destination)
            if config_changed:
                workspace.atomic_write(config_path, migrated)
            if pointer_changed:
                workspace.atomic_write(pointer_path, str(executable) + '\n')
        if security_data is None:
            print(f'{prefix} workspace security material and instructions')
        if env_changed:
            print(f'{prefix} private .wuwei/env and Git ignore rule')
        if text != raw:
            print(f'{prefix} config.toml: remove repos = []; the [[repos]] tables define the repositories')
        for key in added:
            print(f'{prefix} config.toml: add {key}')
        if pointer_changed:
            print(f'{prefix} executable pointer')
        for name, local_version, base_version in conflicts:
            print(f'Charter override needs review: {name} '
                  f'(local {local_version or "unversioned"}, base {base_version or "missing"})')
        if not args.dry_run:
            _status_line(executable)
        if not added and not pointer_changed and not env_changed and text == raw:
            print('No workspace changes needed')
        return CLEAN if args.dry_run else _finish(destination.parent)
    except workspace.ConfigError as exc:
        print(f'wuwei init: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f'wuwei init: {exc}', file=sys.stderr)
        return UNRUN
