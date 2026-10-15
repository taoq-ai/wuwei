"""The board: each open plan item, its pull request and what it still lacks. Gaps, never commands."""

from wuwei import evidence, gh, plan, ws

TTL = 60


def _list(root, name, read, ttl=TTL):
    found = ws.cache_get(root, name, ttl)
    return ws.cache_put(root, name, read()) if found is None else found


def andons(root):
    """Repositories where a seat pulled the cord: no new builds there until it is cleared."""
    active = {}
    for row in ws.ledger(root):
        if row.get('kind') == 'andon.raised':
            active[row['data']['repo']] = row['data'].get('reason', '')
        elif row.get('kind') == 'andon.cleared':
            active.pop(row['data']['repo'], None)
    return active


def andon(root, repo, reason='', clear=False):
    ws.record(root, 'andon.cleared' if clear else 'andon.raised', {'repo': repo, 'reason': reason})
    ws.cache_put(root, 'board', None)


def compute(root):
    out = []
    held = andons(root)
    open_items = [item for item in plan.items(root) if item.get('status', 'open') == 'open']
    for repo in sorted({item.get('repo') for item in open_items if item.get('repo')}):
        key = repo.replace('/', '__')
        since = min(item.get('added', ws.today()) for item in open_items if item.get('repo') == repo)
        try:
            prs = _list(root, f'prs-{key}', lambda: gh.open_prs(repo))
            merged = _list(root, f'merged-{key}', lambda: gh.merged_prs(repo, since), 300)
        except gh.GhError as exc:
            out += [{'item': i['id'], 'title': i['title'], 'pr': None,
                     'gaps': [evidence.gap(f'{repo} unreadable: {exc}', actionable=False)]}
                    for i in open_items if i.get('repo') == repo]
            continue
        for item in (i for i in open_items if i.get('repo') == repo):
            linked = [pr for pr in prs if (evidence.item_for(root, pr, repo) or {}).get('id') == item['id']]
            done = [pr for pr in merged if (evidence.item_for(root, pr, repo) or {}).get('id') == item['id']]
            if not linked and done:
                plan.mark(root, item['id'], 'done', f'merged as {repo}#{done[0]["number"]}')
                continue
            if not linked:
                first = (evidence.gap(f'andon: {held[repo]} (no new builds in {repo} until cleared)', actionable=False)
                         if repo in held else evidence.gap('no pull request yet') if item.get('approved', True)
                         else evidence.gap('awaiting plan approval', actionable=False, owner=True))
                out.append({'item': item['id'], 'title': item['title'], 'pr': None, 'gaps': [first]})
            for pr in linked:
                out.append({'item': item['id'], 'title': item['title'], 'pr': f'{repo}#{pr["number"]}',
                            'gaps': evidence.gaps(root, repo, pr['number'])})
    for item in (i for i in open_items if not i.get('repo')):
        out.append({'item': item['id'], 'title': item['title'], 'pr': None,
                    'gaps': [evidence.gap('no repository named for this item')]})
    return out


def rows(root):
    found = ws.cache_get(root, 'board', TTL)
    return ws.cache_put(root, 'board', compute(root)) if found is None else found


def text(found, root=None):
    held = andons(root) if root is not None else {}
    cords = [f'ANDON {repo}: {reason}' for repo, reason in held.items()]
    if not found:
        return '\n'.join(cords + ['Board: nothing open in the plan.'])
    lines = cords + ['Board (what each open item still lacks):']
    for row in found:
        head = f'{row["item"]} {row["title"]}' + (f' ({row["pr"]})' if row['pr'] else '')
        gaps = '; '.join(g['text'] + ('' if g['actionable'] else ' [waiting]') for g in row['gaps']) or 'ready to merge'
        lines.append(f'- {head}: {gaps}')
    return '\n'.join(lines)
