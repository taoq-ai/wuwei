"""Create a workspace note."""

import json
import sys

from wuwei.exits import CLEAN, FINDINGS
from wuwei.notes import SLUG_RE, parse_note
from wuwei.workspace import atomic_write, find_workspace, now


def register(subparsers):
    parser = subparsers.add_parser('note', help='manage workspace notes')
    actions = parser.add_subparsers(dest='note_action', required=True)
    add = actions.add_parser('add', help='create a note')
    add.add_argument('slug')
    add.add_argument('--type', required=True)
    add.add_argument('--summary', default='')
    add.add_argument('--alias', action='append', default=[])
    add.add_argument('--body', default='')
    add.set_defaults(func=run_add)


def run_add(args):
    if not SLUG_RE.fullmatch(args.slug):
        print('wuwei note: invalid slug', file=sys.stderr)
        return FINDINGS
    fields = [('type', args.type), ('summary', args.summary),
              ('aliases', '[' + ', '.join(json.dumps(alias, ensure_ascii=False) for alias in args.alias) + ']'),
              ('status', 'active'), ('created', now().date().isoformat())]
    frontmatter = '\n'.join(f'{key}: {value if key == "aliases" else json.dumps(value, ensure_ascii=False)}' for key, value in fields)
    content = f'---\n{frontmatter}\n---\n{args.body}'
    if args.body and not args.body.endswith('\n'):
        content += '\n'
    try:
        parse_note(content)
    except ValueError as exc:
        print(f'wuwei note: {exc}', file=sys.stderr)
        return FINDINGS
    root = find_workspace()
    directory = root / '.wuwei/memory/notes'
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise ValueError('notes directory must be inside the workspace and not a symlink')
    path = directory / f'{args.slug}.md'
    try:
        atomic_write(path, content, replace=False)
    except FileExistsError:
        print(f'wuwei note: {path} already exists', file=sys.stderr)
        return FINDINGS
    print(path)
    return CLEAN
