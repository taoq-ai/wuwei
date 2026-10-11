"""Build and check Claude Code agents from versioned charters."""

import json
import os
from pathlib import Path
import sys

from wuwei import security, verdict, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED, SYMLINK


ROLES = (
    'planner', 'lead', 'builder', 'sentinel-arch', 'sentinel-quality',
    'sentinel-security', 'sentinel-goal', 'shepherd', 'steward',
)
TOOLS = {'Read', 'Glob', 'Grep', 'Bash', 'Write', 'Edit', 'Agent'}
ROOT = Path(__file__).resolve().parents[3]


def register(subparsers):
    parser = subparsers.add_parser('agents', help='Build or check generated role agents')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('build', help='Regenerate agent files').set_defaults(func=lambda args: run('build'))
    actions.add_parser('check', help='Report generated agent drift').set_defaults(func=lambda args: run('check'))


def _charter(root, name, overrides=None):
    local = overrides / f'{name}.md' if overrides else None
    path = local if local and local.is_file() else root / 'charters' / f'{name}.md'
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)
    if len(lines) < 4 or lines[0] != '---\n' or not lines[1].startswith('version: ') or lines[2] != '---\n':
        raise ValueError(f'{name}: expected versioned charter frontmatter; reinstall the plugin, then run bin/wuwei doctor')
    if not lines[1][len('version: '):].strip():
        raise ValueError(f'{name}: empty charter version; reinstall the plugin, then run bin/wuwei doctor')
    return text


def render(root, overrides=None):
    """Return every expected agent; validate all sources before any write."""
    root = Path(root)
    allowlist = json.loads((root / 'agents/allowlist.json').read_text(encoding='utf-8'))
    if not isinstance(allowlist, dict) or set(allowlist) != set(ROLES):
        raise ValueError(f'allowlist must contain exactly the nine roles; {DAMAGED}')
    common = _charter(root, '_common', overrides)
    authoring = _charter(root, '_common-authoring', overrides)
    output = {}
    for role in ROLES:
        tools = allowlist[role]
        if (not isinstance(tools, list) or not tools or
                any(not isinstance(tool, str) or tool not in TOOLS for tool in tools) or
                len(tools) != len(set(tools))):
            raise ValueError(f'{role}: expected a nonempty, explicit, unique tool list; {DAMAGED}')
        charter = _charter(root, role, overrides)
        if any('## Verdict format' in text for text in (common, authoring, charter)):
            raise ValueError(f'{role}: a charter carries its own Verdict format section; the format '
                             'lives in cli/wuwei/verdict.py FORMAT and agents build renders it; '
                             'remove the section')
        verdict_format = verdict.section() + '\n' if role.startswith('sentinel-') else ''  # #665
        body = common + '\n' + verdict_format + authoring + '\n' + charter
        description = f'Follow the {role.replace("-", " ")} charter for assigned WUWEI work.'
        output[f'{role}.md'] = (
            f'---\nname: {role}\ndescription: {description}\n'
            f'tools: {", ".join(tools)}\n---\n\n{body}'
        )
    return output


def _error(action, exc):
    print(f'wuwei agents {action}: {str(exc) or type(exc).__name__}', file=sys.stderr)
    return UNRUN


def build(root=ROOT, *, workspace_root=None):
    try:
        if workspace_root is not None:
            directory = Path(workspace_root) / '.wuwei'
            security.load(workspace_root)
            write_workspace(root, directory)
            return CLEAN
        output = render(root)
        for name, content in output.items():
            workspace.atomic_write(Path(root) / 'agents' / name, content)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return _error('build', exc)
    return CLEAN


def check(root=ROOT):
    try:
        expected = render(root)
        directory = Path(root) / 'agents'
        actual = {path.name for path in directory.glob('*.md') if path.name != 'README.md'}
        drift = set(expected) ^ actual
        for name in set(expected) & actual:
            if (directory / name).read_text(encoding='utf-8') != expected[name]:
                drift.add(name)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return _error('check', exc)
    for name in sorted(drift):
        print(f'wuwei agents check: drift in {name}', file=sys.stderr)
    return FINDINGS if drift else CLEAN


def workspace_files(root, directory):
    """Render private workspace copies without touching the plugin sources."""
    root, directory = Path(root), Path(directory)
    # Init calls this on its unpublished staging directory.
    data = json.loads((directory / 'security.json').read_text(encoding='utf-8'))
    line = security.instruction(data)
    overrides = directory / 'charters'
    output = {'agents/' + name: content + line
              for name, content in render(root, overrides).items()}
    for path in (root / 'charters').glob('*.md'):
        output['charters/' + path.name] = _charter(root, path.stem, overrides) + line
    for path in (root / 'skills').rglob('*.md'):
        output[str(path.relative_to(root))] = path.read_text(encoding='utf-8') + line
    return output


def run(action):
    try:
        try:
            root = workspace.find_workspace()
        except FileNotFoundError:
            if 'WUWEI_WORKSPACE' in os.environ:
                raise ValueError(f'invalid WUWEI_WORKSPACE override; {DAMAGED}') from None
            return build(ROOT) if action == 'build' else check(ROOT)
        if security.load(root) is None:
            return build(ROOT) if action == 'build' else check(ROOT)
        if action == 'build':
            return build(ROOT, workspace_root=root)
        directory = root / '.wuwei'
        expected = workspace_files(ROOT, directory)
        drift = any(not (directory / 'generated' / name).is_file() or
                    (directory / 'generated' / name).read_text(encoding='utf-8') != content
                    for name, content in expected.items())
        if drift:
            print('wuwei agents check: workspace instruction drift', file=sys.stderr)
        return FINDINGS if drift else CLEAN
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return _error(action, exc)


def write_workspace(root, directory):
    for name, content in workspace_files(root, directory).items():
        path = directory / 'generated' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != directory.resolve() / 'generated' / name:
            raise ValueError(f'generated instructions must not traverse symlinks; {SYMLINK}')
        workspace.atomic_write(path, content, mode=0o400)
