"""The board: each open plan item, its pull request and what it still lacks. Gaps, never commands."""

import concurrent.futures
import datetime
import os
import re
import sys

from wuwei import evidence, gh, plan, ws

TTL = 60


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


def answered(root, prs, since):  # each PR has an unresolved review thread, each ending with the owner's reply at or after since (#1199)
    try:
        return all(gh.unanswered_threads(repo, n, (evidence.owner_login(root),), since) == 0 < gh.unanswered_threads(repo, n, ())
                   for repo, n in (p.split('#') for p in prs))
    except (gh.GhError, TypeError):  # an unreadable host keeps the owe
        return False


def replies(root):
    out, now = [], ws.now().isoformat(timespec='seconds')
    for item in plan.items(root):
        if item.get('kind') == 'reply' and item.get('status') == 'open':
            prs, opened = evidence.refs(item['where']), item.get('opened') or item.get('added', '')
            if prs and ((row := next((r for r in ws.rows(root, 'sent') if r['ts'] >= opened and prs & set(r['data'].get('refs', ()))), None)) or answered(root, prs, opened)):
                plan.mark(root, item['id'], 'done', f'sent naming {", ".join(sorted(prs))} via {row["data"].get("tool")}' if row else 'answered by the owner on the PR')
                continue  # a send that names the owe's PR, recorded in any session (#1169)
            when = (f'overdue since {item["due"][:16]}' if item['due'] < now else f'due {item["due"][:16]}')
            out.append({'item': item['id'], 'title': item['title'], 'pr': None,
                        'gaps': [evidence.gap(f'reply owed to {item["who"]} in {item["where"]}, {when}')]})
    return out


ADOPT_DAYS = 7


def adopted(root, repo, prs, keep):
    """Open PRs, drafts too, this session's identity raised on the repository without a plan link: shepherded all the same."""
    since = (ws.now() - datetime.timedelta(days=ADOPT_DAYS)).isoformat()
    login = evidence.owner_login(root)
    return [{'item': 'unplanned', 'title': pr['title'], 'pr': f'{repo}#{pr["number"]}',
             'gaps': keep(evidence.gaps(root, repo, pr['number'], pr))}
            for pr in prs if (pr.get('author') or {}).get('login') == login
            and (pr.get('createdAt') or '') >= since and evidence.item_for(root, pr, repo) is None]


def running(root, session):
    """Roles of the seats the session started today with no stop or unconfirmed row: a dead session's never count (1180-probe)."""
    gone = {a for k in ('seat.stopped', 'seat.unconfirmed') for r in ws.rows(root, k, ws.today()) if isinstance(a := r['data'].get('agent'), str)}
    return {r['data'].get('role') for r in ws.rows(root, 'seat.started', ws.today()) if session and r['data'].get('session') == session
            and isinstance(a := r['data'].get('agent'), str) and a not in gone}


def names(root, pr, repo, item_id):
    named = {i.lower() for i in evidence.ITEM.findall(pr.get('body') or '')} or {(evidence.item_for(root, pr, repo) or {}).get('id', '').lower()}
    return item_id.lower() in named


def compute(root, everything=False):
    out = replies(root)
    held = andons(root)
    keep = (lambda gaps: gaps) if everything else evidence.visible
    open_items = [item for item in plan.items(root) if item.get('status', 'open') == 'open' and item.get('kind') != 'reply']
    for repo in sorted({item.get('repo') for item in open_items if item.get('repo')} | set(ws.config(root)['repos'])):
        mine = [item for item in open_items if item.get('repo') == repo]
        since = min((item.get('added', ws.today()) for item in mine), default=ws.today())
        try:
            slug = repo.replace('/', '__')  # a list read also drops PR and compare entries a day old (#1161)
            prs = evidence._cached(root, 'prs-' + slug, lambda: ws.cache_prune(root, 86400, f'pr-{slug}-*', f'cmp-{slug}-*')
                                   or gh.open_prs(repo), TTL)
            merged = gh.merged_prs(repo, since, limit=1) if mine else []  # read fresh, one page: an item's PR may have just merged
        except gh.GhError as exc:
            out += [{'item': i['id'], 'title': i['title'], 'pr': None,
                     'gaps': [evidence.gap(f'{repo} unreadable: {exc}', actionable=False)]} for i in mine]
            continue
        out += adopted(root, repo, prs, keep)
        print(f'wuwei: reading {repo}: {len(prs)} open PRs', file=sys.stderr)
        links = [[pr for pr in prs if names(root, pr, repo, item['id'])] for item in mine]
        any(links) and evidence.budget(root, repo)  # read once here: each pool thread would read it again (#1177)
        with concurrent.futures.ThreadPoolExecutor(8) as pool:  # the host calls dominate a cold board (#1121)
            read = dict(zip(want := {pr['number']: pr for linked in links for pr in linked}, pool.map(lambda pr: keep(evidence.gaps(root, repo, pr['number'], pr)), want.values())))
        for item, linked in zip(mine, links):
            done = [pr for pr in merged if names(root, pr, repo, item['id'])]
            if not linked and done and item.get('kind') != 'run':
                plan.mark(root, item['id'], 'done', f'merged as {repo}#{done[0]["number"]}')
                continue
            if not linked and done and 'run owed' not in item.get('reason', ''):  # merged code is not the run; plan done closes it (#1200)
                item['reason'] = plan.mark(root, item['id'], 'open', '; '.join(filter(None, [item.get('reason'), f'code merged as {repo}#{done[0]["number"]}, run owed'])))['reason']
            if not linked:  # an open PR the item names by owner/repo#n or a bare #n, linked to no item: say so (#1202)
                named = evidence.refs(re.sub(r'(?<![\w/.-])#', repo + '#', f'{item["title"]} {item.get("promise") or ""}'))
                taken = next((ref for pr in prs if (ref := f'{repo}#{pr["number"]}').lower() in named and evidence.item_for(root, pr, repo) is None), None)
                first = (evidence.gap(f'andon: {held[repo]} (no new builds in {repo} until cleared)', actionable=False)
                         if repo in held else evidence.gap(f'run: {item.get("reason") or "no run evidence yet"}', actionable=False)
                         if item.get('kind') == 'run' else evidence.gap(f'PR {taken} not linked: add the WUWEI footer naming {item["id"]}' if taken else 'no pull request yet') if item.get('approved', True)
                         else evidence.gap('awaiting plan approval', actionable=False, owner=True))
                out.append({'item': item['id'], 'title': item['title'], 'pr': None, 'gaps': [first] + evidence.uncounted(root, item['id'])})
            for pr in linked:
                out.append({'item': item['id'], 'title': item['title'], 'pr': f'{repo}#{pr["number"]}',
                            'gaps': read[pr['number']]})
    for item in (i for i in open_items if not i.get('repo')):  # a reply has no repository; see replies()
        out.append({'item': item['id'], 'title': item['title'], 'pr': None,
                    'gaps': [evidence.gap('no repository named for this item')]})
    seats, prs = running(root, os.environ.get('CLAUDE_CODE_SESSION_ID')), [r for r in out if r['pr']]  # duties with no count, so a Stop reminds once while they hold
    owed = any(any(evidence.GATES.search(g['text']) for g in r['gaps']) and not any(g['text'].startswith(('CI ', 'required check')) for g in r['gaps']) for r in prs)
    duties = [evidence.gap('orchestration: open PRs with no shepherd seat running')] * (len({r['pr'] for r in prs}) > 2 and 'shepherd' not in seats) + [
        evidence.gap('orchestration: gates owed on green heads with no gate seat running')] * (owed and not any(str(s).startswith('sentinel-') for s in seats))
    return [{'item': 'team', 'title': 'seats', 'pr': None, 'gaps': duties}] * bool(duties) + out  # first: the Stop and session start cut from the end


def rows(root):
    return evidence._cached(root, 'board', lambda: compute(root), TTL)


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
