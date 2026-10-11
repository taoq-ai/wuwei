"""Create a workspace note, or record a small fix a seat found (#646)."""

import json
import re
import sys

from wuwei.exits import CLEAN, FINDINGS, SYMLINK, UNRUN
from wuwei.notes import OWNER_NOTES, SLUG_RE, parse_note
from wuwei.workspace import atomic_write, find_workspace, now


def register(subparsers):
    parser = subparsers.add_parser('note', help='manage workspace notes')
    parser.add_argument('--fix', metavar='TITLE',
                        help='Record a small fix a seat found; wuwei next proposes it as an item')
    parser.set_defaults(func=run_fix)
    actions = parser.add_subparsers(dest='note_action')
    add = actions.add_parser('add', help='create a note')
    add.add_argument('slug')
    add.add_argument('--type', required=True)
    add.add_argument('--summary', default='')
    add.add_argument('--alias', action='append', default=[])
    add.add_argument('--body', default='')
    add.set_defaults(func=run_add)


def run_fix(args):
    """#646: today's seat_findings.<id>; plan add <id> --from-finding admits it as a small item."""
    from wuwei import profiles, state
    if args.fix is None:
        print('wuwei note: pass add <slug> or --fix "<title>"', file=sys.stderr)
        return UNRUN
    title = ' '.join(args.fix.split())
    words = re.findall(r'[a-z0-9]+', title.lower())
    reason = ('the title must be one line; pass --fix "<title>"' if not title or '\n' in args.fix
              else 'the title must be at most 120 characters' if len(title) > 120
              else 'the title must hold letters or digits' if not words
              else 'the title must not hold an absolute path; name the file from the repository root'
              if profiles.ABSOLUTE.search(title) else '')
    if reason:
        print(f'wuwei note: {reason}', file=sys.stderr)
        return FINDINGS
    ident = 'fix-' + '-'.join(words[:6])

    def update(data):
        if ident in data.get('seat_findings', {}) or ident in data['items']:
            raise state.StateError(f'{ident} is already recorded; wuwei next proposes it')
        data.setdefault('seat_findings', {})[ident] = {
            'scope': title, 'evidence': 'seat finding', 'track': 'SLICE', 'at': now().isoformat()}
    try:
        state._write_state(update, find_workspace(), reserved=False, kind='finding.noted',
                           payload={'id': ident, 'title': title})
    except state.StateError as exc:
        print(f'wuwei note: {exc}', file=sys.stderr)
        return FINDINGS
    print(ident)
    return CLEAN


def run_add(args):
    if args.slug in OWNER_NOTES:
        print('wuwei note: the owner keeps the baseline outside agent tools; write the change as a proposal. The owner edits the baseline in a host terminal', file=sys.stderr)
        return FINDINGS
    if not SLUG_RE.fullmatch(args.slug):
        print('wuwei note: invalid slug; use lowercase letters, digits and dashes', file=sys.stderr)
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
    if (root / '.wuwei').is_symlink():
        raise ValueError('.wuwei must not be a symlink')
    directory = root / '.wuwei/memory/notes'
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise ValueError(f'notes directory must be inside the workspace and not a symlink; {SYMLINK}')
    path = directory / f'{args.slug}.md'
    try:
        atomic_write(path, content, replace=False)
    except FileExistsError:
        print(f'wuwei note: {path} already exists; use another slug, or edit that note', file=sys.stderr)
        return FINDINGS
    print(path)
    return CLEAN
