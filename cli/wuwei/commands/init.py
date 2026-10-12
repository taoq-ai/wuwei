"""Create a workspace from the shipped skeleton."""

import copy
import json
import os
import re
import shlex
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib

from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED, SYMLINK
from wuwei import env, integrity, security, workspace
from wuwei.guards.edges import PERMISSIONS_DENY

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
    parser.add_argument("--shadow", action="store_true",
                        help="a new workspace with guards.enforce = false: guards log what they would refuse")
    parser.add_argument("--honeytoken-path", default=security.DEFAULT_HONEYTOKEN_PATH,
                        help="decoy credentials path relative to .wuwei")
    parser.set_defaults(func=run)


def run(args):
    shadow = getattr(args, 'shadow', False)
    if shadow and getattr(args, 'upgrade', False):
        raise ValueError('--shadow applies to a new workspace; run bin/wuwei config set guards.enforce false')
    if getattr(args, 'dry_run', False) and not getattr(args, 'upgrade', False):
        raise ValueError('--dry-run requires --upgrade; run bin/wuwei init --upgrade --dry-run')
    if getattr(args, 'upgrade', False):
        return upgrade(args)
    destination = Path(args.path).expanduser() / ".wuwei"
    if destination.exists() or destination.is_symlink():
        print(f"wuwei init: {destination} already exists; run wuwei init {args.path} --upgrade to update it", file=sys.stderr)
        return FINDINGS
    settings_path, data = settings(destination.parent)
    permissions = data.setdefault('permissions', {})
    denials = permissions.setdefault('deny', [])
    if not isinstance(denials, list) or not all(isinstance(rule, str) for rule in denials):
        raise ValueError(f'workspace permissions.deny must be a list of strings; {DAMAGED}')
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
        executable = integrity.launcher(destination.parent)
        (Path(staging) / "executable").write_text(str(executable) + "\n")
        config = Path(staging) / 'config.toml'
        text = config.read_text(encoding='utf-8')
        if shadow:
            text = text.replace('enforce = true', 'enforce = false', 1)
        config.write_text(_stamp(text), encoding='utf-8')
        integrity.initialize(Path(staging))
        settings_path.parent.mkdir(exist_ok=True)
        workspace.atomic_write(settings_path, json.dumps(data, indent=2) + '\n')
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


# #838: the register comment init --upgrade wrote above config sections; removed on upgrade.
GRAPH_COMMENT = ('# A view of .wuwei/graph.json: bin/wuwei config set and the cards write both; '
                 'bin/wuwei who walks it.')
# Paths under .wuwei/ (files or directories) no code reads or writes; init --upgrade removes
# them, never through a symlink and never under days/ (history).
RETIRED_FILES = ('memory/rehearsals.json', 'memory/rehearsals.lock', 'memory/targets.json', 'memory/targets.lock',
                 'memory/cruise.json', 'memory/forget.json',  # #814, #815, #833
                 'memory/voice.md', 'memory/digests', 'inbox', 'graph.json', 'ziran',  # #810, #833, #838, #840
                 *(f'{name}.{suffix}' for name in ('watch', 'shepherd', 'listen')  # #810, #847
                   for suffix in ('lock', 'stdout.log', 'stderr.log')))
RETIRED_UNITS = ('listen', 'watch', 'shepherd')  # #810, #847: user services no longer shipped
# #800: the guide block an older init wrote into the memory.export_to file.
GUIDE = ('<!-- wuwei:guide:start -->', '<!-- wuwei:guide:end -->')


def _retired(destination, generated):
    """(names to remove, (name, reason) left): each RETIRED_FILES path present and each stale
    generated copy; a symlink, or a path that resolves outside .wuwei/, is left and named."""
    remove, left = [], []
    for name in (*RETIRED_FILES, *generated):
        path = destination / name
        if not (path.exists() or path.is_symlink()):
            continue
        if destination.is_symlink() or path.is_symlink():
            left.append((name, 'a symlink'))
        elif not path.resolve().is_relative_to(destination.resolve()):
            left.append((name, 'resolves outside .wuwei'))
        else:
            remove.append(name)
    return remove, left


def _stale_generated(plugin, destination):
    """#848: generated copies of a skill, agent or charter the plugin no longer ships."""
    generated = destination / 'generated'
    if generated.is_symlink() or not generated.is_dir() or security.load(destination.parent) is None:
        return []
    from wuwei.commands.agents import workspace_files
    current = workspace_files(plugin, destination)
    kinds = {name.split('/')[0] for name in current}  # agents, charters, skills; never the config cache
    return sorted(name for name in (path.relative_to(generated).as_posix() for path in generated.rglob('*')
                                    if path.is_file() or path.is_symlink())
                  if name.split('/')[0] in kinds and '/' in name and name not in current)


def _remove(destination, name):
    path = destination / name
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    for parent in path.parents:  # an emptied generated/<kind>/<name>/ goes with its last file
        if parent == destination / 'generated' or not parent.is_relative_to(destination / 'generated'):
            break
        if any(parent.iterdir()):
            break
        parent.rmdir()


def _remove_unit(path, name):
    """Stop a retired user service and delete its unit; service failures are warnings."""
    from wuwei import registry
    service = registry.watch_service()

    def call(argv):
        try:
            service.call(argv)
        except (OSError, ValueError) as exc:
            print(f'wuwei init: {name} service: warning: {exc}; run bin/wuwei doctor', file=sys.stderr)
    if sys.platform == 'darwin':
        call(['launchctl', 'bootout', f'gui/{os.getuid()}', str(path)])
    else:
        call(['systemctl', '--user', 'disable', '--now', path.name])
    path.unlink(missing_ok=True)
    if sys.platform == 'linux':
        call(['systemctl', '--user', 'daemon-reload'])


def _guide(root, **kwargs):
    """Remove the old guide block; a file that cannot be written warns and never stops init (#476)."""
    from wuwei import memory
    try:
        return memory.write_block(root, *GUIDE, '', 'bin/wuwei init --upgrade', **kwargs)
    except (OSError, ValueError) as exc:
        print(f'wuwei init: warning: guide block not written: {exc}; '
              'run bin/wuwei doctor for the fix', file=sys.stderr)
        return None, False


def settings(root, name='settings.json'):
    """(path, data) for the project's .claude/<name>, refused when unsafe to write."""
    path = Path(root) / '.claude' / name
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError(f'workspace settings must not be symlinks; {SYMLINK}')
    if Path(root).resolve() == Path.home().resolve():
        raise ValueError('workspace settings must not be owner global settings; run bin/wuwei init in a project folder, not the home folder')
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get('permissions', {}), dict):
        raise ValueError(f'workspace settings and permissions must be objects; fix or move .claude/{name} in this folder, then rerun bin/wuwei init')
    return path, data


def _status_command(executable):
    return {"type": "command", "command": shlex.quote(str(executable)) + " status --line"}


def _status_line(executable):
    print(json.dumps({"statusLine": _status_command(executable)}))
    print('Status line: put the "statusLine" key above in .claude/settings.json (this project) '
          'or ~/.claude/settings.json (every project).')


def _finish(root):
    print(integrity.check(root).reason or 'plugin integrity: clean')
    return 0


def _linked_worktrees(root, vcs, config):
    """Every linked worktree of each configured repository, and any under worktrees/."""
    from wuwei import brief
    trees = {tree.resolve() for tree in (root / 'worktrees').glob('*') if (tree / '.git').is_file()}
    for repo in config['repos']:
        path = (root / Path(repo['path']).expanduser()).resolve()
        try:
            rows = brief.read(vcs.worktrees, str(path), root=root)
            if not isinstance(rows, list) or not all(isinstance(row, dict) and isinstance(row.get('path'), str)
                                                     for row in rows):
                raise ValueError(f'invalid worktree list; {DAMAGED}')
        except ValueError as exc:
            print(f"wuwei init warning: {repo['name']}: worktrees unread: {exc}", file=sys.stderr)
            continue
        trees |= {Path(row['path']).resolve() for row in rows if (Path(row['path']) / '.git').is_file()}
    return sorted(trees)


def _unhook(root, dry_run, config):
    """#847: unset the core.hooksPath WUWEI set in every linked worktree of each configured
    repository (an owner's own value stays), rewrite its anchor and remove the managed hooks
    once no worktree may still point at them; the repository's hooks run natively. True when
    it changed (or, dry, would change) something."""
    from wuwei import registry
    vcs = registry.load('vcs', config)
    root = root.resolve()
    changed, stuck = False, []
    for tree in _linked_worktrees(root, vcs, config):
        name = tree.relative_to(root).as_posix() if tree.is_relative_to(root) else str(tree)
        try:
            found = registry.data(vcs.unhook(str(tree), not dry_run, root=root))
            if found['unset']:
                changed = True
                print(f"{'Would upgrade' if dry_run else 'Upgraded'} worktree {name}: unset core.hooksPath")
            anchor = Path(found['git_dir']) / 'wuwei-workspace'
            if not dry_run and (anchor.is_file() or tree.parent == root / 'worktrees'):
                workspace.atomic_write(anchor, str(root) + '\n')
        except ValueError as exc:
            stuck.append(name)
            print(f'wuwei init warning: {name}: {exc}', file=sys.stderr)
    shims = root / '.wuwei/git-hooks'
    if shims.is_dir() and not shims.is_symlink():
        if stuck:
            for name in stuck:
                print(f'left .wuwei/git-hooks: worktree {name} may still point at it')
            return changed
        changed = True
        if dry_run:
            print('Would upgrade .wuwei/git-hooks: remove (no longer installed)')
        else:
            shutil.rmtree(shims)
            print('Upgraded .wuwei/git-hooks: remove (no longer installed)')
    return changed


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


def _stamp(text):
    """Raise the top-level template_version to this plugin's version; never lower it (#353)."""
    mine = integrity.version()
    current = tomllib.loads(text).get('template_version', '')
    if not integrity.release(mine) or (integrity.release(current) or ()) >= integrity.release(mine):
        return text
    sections = _sections(text)
    root = sections[0][1]
    for index, line in enumerate(root):
        if re.match(r'\s*template_version\s*=', line):
            root[index] = re.sub(r'=\s*("[^"\n]*"|\'[^\'\n]*\')', f'= "{mine}"', line, count=1)
            break
    else:
        root.insert(0, f'template_version = "{mine}"\n')
    return ''.join(''.join(lines) for _, lines in sections)


def _without_empty_repos(raw):
    """Drop a top-level one-line repos = [] that [[repos]] tables make a TOML error (#326)."""
    sections = _sections(raw)
    if not any(label == '[[repos]]' for label, _ in sections):
        return raw
    sections[0][1][:] = [line for line in sections[0][1]
                         if not re.fullmatch(r'\s*repos\s*=\s*\[\s*\]\s*(?:#.*)?\n?', line)]
    return ''.join(''.join(lines) for _, lines in sections)


def _today_tier(raw, before):
    """#816: merge.default_tier = "today" merged on each repository; merge.auto = true keeps
    that for a repository that does not set merge.auto itself; "today" never applied under strict."""
    if (before.get('merge', {}).get('default_tier') != 'today'
            or before.get('security', {}).get('posture') == 'strict'):
        return raw, []
    from wuwei.commands.config import write_value
    lines = []
    for index, repo in enumerate(tomllib.loads(raw).get('repos', [])):
        if 'auto' not in repo.get('merge', {}):
            raw = write_value(raw, f'repos.{index}.merge.auto', True)
            lines.append(f'repos.{index}.merge.auto = true (was merge.default_tier = "today")')
    return raw, lines


def _enforce(raw, before):
    """#837: security.posture = "observe" or guards.mode = "shadow" in the file as loaded
    (before) becomes guards.enforce = false; an explicit guards.enforce stays the owner's."""
    guards = before.get('guards', {})
    if before.get('security', {}).get('posture') == 'observe':
        was = 'security.posture = "observe"'
    elif guards.get('mode') == 'shadow':
        was = 'guards.mode = "shadow"'
    else:
        return raw, []
    if 'enforce' in guards:
        return raw, []
    from wuwei.commands.config import write_value
    return write_value(raw, 'guards.enforce', False), [f'guards.enforce = false (was {was})']


def _unread_keys(raw, warnings):
    """Remove the keys load_config reported as unknown (#799). A likely typo (a "did you
    mean" match) not in workspace.RETIRED is kept for the owner to fix; returns (text,
    removed, kept)."""
    present = tomllib.loads(raw)
    paths, removed, kept = [], [], []
    for warning in warnings:
        match = re.match(r'config\.toml: unknown key (.+?)(?: at line \d+)?; (?:did you mean (.+)\?)?', warning)
        name = re.sub(r'\.\d+(?=\.|$)', '', match.group(1)) if match else ''  # repos.0.tests is repos.tests
        retired = match and any(name == key or name.startswith(key + '.') for key in workspace.RETIRED)
        if match and match.group(2) and not retired:
            kept.append((match.group(1), match.group(2)))
        elif match:
            removed.append(match.group(1))
    if not removed:
        return raw, [], kept
    refusal = ValueError(f'cannot safely remove {", ".join(removed)} in this TOML layout; delete them '
                         'from config.toml by hand, then run bin/wuwei init --upgrade again')
    expected = copy.deepcopy(present)
    for key in removed:
        path, node = [], expected
        try:
            for part in key.split('.'):
                path.append(int(part) if isinstance(node, list) else part)
                parent, node = node, node[path[-1]]
            parent.pop(path[-1])
        except (KeyError, IndexError, TypeError, ValueError):
            raise refusal from None
        paths.append(tuple(path))

    def unread(path):
        return any(path[:len(gone)] == gone for gone in paths)

    counts, result = {}, []
    for label, lines in _sections(raw):
        if label.startswith('[['):
            name = label[2:-2]
            counts[name] = counts.get(name, -1) + 1
            section = (*name.split('.'), counts[name])
        else:
            section = tuple(label.split('.')) if label else ()
            name = next((name for name in counts if label.startswith(name + '.')), None)
            if name:  # [repos.merge] after [[repos]] belongs to the latest entry
                section = (*name.split('.'), counts[name], *label[len(name) + 1:].split('.'))
        if section and unread(section):
            tail = len(lines)  # comments and blank lines at the end belong to the next header
            while tail > 1 and re.fullmatch(r'\s*(#.*)?\n?', lines[tail - 1]):
                tail -= 1
            result.extend(lines[tail:])
            continue
        index = 0
        while index < len(lines):
            match = re.match(r'^\s*([A-Za-z0-9_."\' -]+?)\s*=', lines[index])
            if not match or index == 0 and section:
                result.append(lines[index])
                index += 1
                continue
            end = index + 1
            while end < len(lines):
                try:
                    tomllib.loads(''.join(lines[index:end]))
                    break
                except tomllib.TOMLDecodeError:
                    end += 1
            key = tuple(part.strip().strip('"\'') for part in match.group(1).split('.'))
            if not unread((*section, *key)):
                result.extend(lines[index:end])
            index = end
    text = ''.join(result)
    try:
        if tomllib.loads(text) != expected:
            raise refusal
    except tomllib.TOMLDecodeError:
        raise refusal from None
    return text, removed, kept


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
        raise ValueError('migration would change an owner value; cannot safely upgrade this TOML layout; the owner edits config.toml by hand, then run bin/wuwei init --upgrade again')
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
        print(f'wuwei init: {destination} is not a workspace; run bin/wuwei init <path> to create one', file=sys.stderr)
        return FINDINGS
    config_path = destination / 'config.toml'
    pointer_path = destination / 'executable'
    if config_path.is_symlink() or pointer_path.is_symlink():
        print('wuwei init: config.toml and executable must not be symlinks; replace them with regular files, then rerun bin/wuwei init --upgrade', file=sys.stderr)
        return UNRUN
    try:
        env.load(destination.parent)
        raw = config_path.read_text(encoding='utf-8')
        text = _without_empty_repos(raw)
        tomllib.loads(text)
        found = []
        config = workspace.load_config(destination.parent, raw=text, warnings=found)
        for warning in found:
            print(f'wuwei init: warning: {warning}; run bin/wuwei doctor for the fix', file=sys.stderr)
        from wuwei import integrity  # #799: an older plugin never removes a newer plugin's keys
        pruned, removed, kept = (text, [], []) if integrity.newer_template(config) else _unread_keys(text, found)
        plugin = Path(__file__).resolve().parents[3]
        template = (plugin / 'templates/workspace/config.toml').read_text(encoding='utf-8')
        migrated, added = _migrated_config(pruned, template)
        migrated, retired = _enforce(migrated, tomllib.loads(text))
        migrated, today = _today_tier(migrated, tomllib.loads(text))
        retired += today
        stamped = _stamp(migrated)
        stamp_changed, migrated = stamped != migrated, stamped
        uncommented = ''.join(line for line in migrated.splitlines(keepends=True)
                              if line.rstrip('\r\n') != GRAPH_COMMENT)  # #838: the register is gone
        graph_comments, migrated = uncommented != migrated, uncommented
        executable = integrity.launcher(destination.parent, config)
        pointer = pointer_path.read_text(encoding='utf-8') if pointer_path.exists() else ''
        conflicts = []
        for local in sorted((destination / 'charters').glob('*.md')):
            base = plugin / 'charters' / local.name
            local_version = _charter_version(local.read_text(encoding='utf-8'))
            base_version = _charter_version(base.read_text(encoding='utf-8')) if base.is_file() else None
            if local_version != base_version or base_version is None:
                conflicts.append((local.name, local_version, base_version))
        security_data = security.load(destination.parent, raw=text)
        guide_path, guide_changed = _guide(destination.parent, write=False, raw=text)
        config_changed = migrated != raw
        pointer_changed = pointer != str(executable) + '\n'
        env_changed = env.initialize(destination, dry_run=args.dry_run)
        prefix = 'Would upgrade' if args.dry_run else 'Upgraded'
        stale, left = _retired(destination, ['generated/' + name for name in _stale_generated(plugin, destination)])
        for name in [] if args.dry_run else stale:
            _remove(destination, name)
        from wuwei import tracker  # #741: stored bare GitHub ticket ids gain their repository
        tickets = tracker.upgrade(destination.parent, workspace.load_config(destination.parent, raw=migrated),
                                  write=not args.dry_run)
        if not args.dry_run:
            if security_data is None:
                security.initialize(destination, getattr(args, 'honeytoken_path', security.DEFAULT_HONEYTOKEN_PATH))
            from wuwei.commands.agents import write_workspace
            write_workspace(plugin, destination)
            if config_changed:
                workspace.atomic_write(config_path, migrated)
            try:  # #735: the checkouts find the workspace from anywhere
                workspace.index(destination.parent, workspace.load_config(destination.parent, raw=migrated))
            except (OSError, ValueError) as exc:
                print(f'wuwei init: warning: workspace index not written: {exc}; rerun bin/wuwei init --upgrade to write it', file=sys.stderr)
            if pointer_changed:
                workspace.atomic_write(pointer_path, str(executable) + '\n')
            if guide_changed:
                guide_path, guide_changed = _guide(destination.parent, raw=text)
            from wuwei import memory  # #848: the index the deleted index command wrote
            try:
                memory.write_index(destination.parent)
            except (OSError, ValueError) as exc:
                print(f'wuwei init: warning: memory index not written: {exc}; run bin/wuwei doctor for the fix', file=sys.stderr)
        if security_data is None:
            print(f'{prefix} workspace security material and instructions')
        if env_changed:
            print(f'{prefix} private .wuwei/env and Git ignore rule')
        if text != raw:
            print(f'{prefix} config.toml: remove repos = []; the [[repos]] tables define the repositories')
        for key in removed:
            print(f'{prefix} config.toml: remove {key} (no longer read)' + (
                '; set budget.<runtime>.five_hour and seven_day instead' if key == 'budget.tokens_per_day' else ''))
        for key, near in kept:
            print(f'config.toml: kept {key}, maybe a typo of {near}; fix it by hand')
        for key in added:
            print(f'{prefix} config.toml: add {key}')
        for line in retired:
            print(f'{prefix} config.toml: {line}')
        if stamp_changed:
            print(f'{prefix} config.toml: template_version {integrity.version()}')
        if graph_comments:
            print(f'{prefix} config.toml: remove the graph comments')
        if pointer_changed:
            print(f'{prefix} executable pointer')
        for name in stale:
            print(f'{prefix} .wuwei/{name}: remove (no longer read)')
        for name, reason in left:
            print(f'left .wuwei/{name}: {reason}')
        if guide_changed:
            print(f'{prefix} {guide_path.relative_to(destination.parent)}: remove the guide block')
        for line in tickets:
            print(f'{prefix} {line}')
        units = [name for name in RETIRED_UNITS if sys.platform in ('darwin', 'linux')
                 and workspace.watch_unit(destination.parent, name=name)[1].exists()]
        for name in units:
            if args.dry_run:
                print(f'Would remove the {name} service (no longer shipped)')
            else:
                _remove_unit(workspace.watch_unit(destination.parent, name=name)[1], name)
                print(f'Removed the {name} service (no longer shipped)')
        unhooked = _unhook(destination.parent, args.dry_run,
                           workspace.load_config(destination.parent, raw=migrated))
        # #670: doctor runs the dry run, which never contacts the tracker
        labelled = [] if args.dry_run else tracker.ensure_labels(  # a seat may run init: no tty, I49 decides
            destination.parent, prefix,
            tracker.creates_labels(workspace.load_config(destination.parent)) or sys.stdin.isatty())
        for line in labelled:
            print(line)
        for name, local_version, base_version in conflicts:
            print(f'Charter override needs review: {name} '
                  f'(local {local_version or "unversioned"}, base {base_version or "missing"})')
        if not args.dry_run:
            _status_line(executable)
        if (not added and not removed and not retired and not stamp_changed and not pointer_changed and not env_changed
                and not guide_changed and not stale and not graph_comments and text == raw
                and not tickets and not units and not unhooked and not any(line.startswith(prefix) for line in labelled)):  # a not-created line changes nothing
            print('No workspace changes needed')
        if args.dry_run:
            return CLEAN
        code = _finish(destination.parent)
        if integrity.other_versions():  # #353: another version's hooks still run
            print(integrity.RESTART)
        return code
    except workspace.ConfigError as exc:
        print(f'wuwei init: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f'wuwei init: {exc}', file=sys.stderr)
        return UNRUN
