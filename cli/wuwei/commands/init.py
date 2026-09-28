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
from wuwei import workspace
from wuwei.guards.deploy import PERMISSIONS_DENY


def register(subparsers):
    parser = subparsers.add_parser("init", help="create a workspace")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--upgrade", action="store_true", help="upgrade an existing workspace")
    parser.add_argument("--dry-run", action="store_true", help="show the upgrade plan")
    parser.add_argument("--menu-bar", action="store_true", help="show SwiftBar setup instructions")
    parser.set_defaults(func=run)


def run(args):
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
        print(f"wuwei init: {destination} already exists; choose another path", file=sys.stderr)
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
        executable = Path(__file__).resolve().parents[3] / "bin/wuwei"
        (Path(staging) / "executable").write_text(str(executable) + "\n")
        settings.parent.mkdir(exist_ok=True)
        workspace.atomic_write(settings, json.dumps(data, indent=2) + '\n')
        os.rename(staging, destination)
    finally:
        if os.path.exists(staging):
            shutil.rmtree(staging)
    print(f"Created {destination.resolve()}")
    print(json.dumps({"statusLine": {"type": "command",
                                   "command": shlex.quote(str(executable)) + " status --line"}}))
    return CLEAN


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
        raw = config_path.read_text(encoding='utf-8')
        tomllib.loads(raw)
        workspace.load_config(destination.parent)
        plugin = Path(__file__).resolve().parents[3]
        template = (plugin / 'templates/workspace/config.toml').read_text(encoding='utf-8')
        migrated, added = _migrated_config(raw, template)
        executable = plugin / 'bin/wuwei'
        pointer = pointer_path.read_text(encoding='utf-8') if pointer_path.exists() else ''
        conflicts = []
        for local in sorted((destination / 'charters').glob('*.md')):
            base = plugin / 'charters' / local.name
            local_version = _charter_version(local.read_text(encoding='utf-8'))
            base_version = _charter_version(base.read_text(encoding='utf-8')) if base.is_file() else None
            if local_version != base_version or base_version is None:
                conflicts.append((local.name, local_version, base_version))
        config_changed = migrated != raw
        pointer_changed = pointer != str(executable) + '\n'
        prefix = 'Would upgrade' if args.dry_run else 'Upgraded'
        if not args.dry_run:
            if config_changed:
                workspace.atomic_write(config_path, migrated)
            if pointer_changed:
                workspace.atomic_write(pointer_path, str(executable) + '\n')
        for key in added:
            print(f'{prefix} config.toml: add {key}')
        if pointer_changed:
            print(f'{prefix} executable pointer')
        for name, local_version, base_version in conflicts:
            print(f'Charter override needs review: {name} '
                  f'(local {local_version or "unversioned"}, base {base_version or "missing"})')
        if not args.dry_run:
            print(json.dumps({'statusLine': {'type': 'command',
                                            'command': shlex.quote(str(executable)) + ' status --line'}}))
        if not added and not pointer_changed:
            print('No workspace changes needed')
        return CLEAN
    except workspace.ConfigError as exc:
        print(f'wuwei init: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f'wuwei init: {exc}', file=sys.stderr)
        return UNRUN
