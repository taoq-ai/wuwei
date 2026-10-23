"""The board: each open plan item, its pull request and what it still lacks. Gaps, never commands."""

import concurrent.futures
import datetime
import os
from pathlib import Path
import re
import sys
import time

from wuwei import evidence, gh, plan, view, ws

TTL, STALE_HOURS = 60, 4


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


def running(root, hours=6, hosted=False):
    """The live seats of every session: started within hours under a named session, with no stop or unconfirmed row. Past that bound a seat is dead: a session that ended without a stop row holds nothing (1180-probe).
    hosted adds the builder of each open --host session item with a recorded session: its record is the seat (builder-host). The hook's held check leaves it out, so gates launch here."""
    gone, since = {a for k in ('seat.stopped', 'seat.unconfirmed') for r in ws.rows(root, k) if isinstance(a := r['data'].get('agent'), str)}, (ws.now() - datetime.timedelta(hours=hours)).isoformat(timespec='seconds')
    return [d for r in ws.rows(root, 'seat.started') if r.get('ts', '') >= since and isinstance((d := r['data']).get('session'), str) and d['session'] and isinstance(a := d.get('agent'), str) and a not in gone] + [
        {'role': 'builder', 'item': i['id'], 'session': i['session'], 'agent': 'session ' + i['session']} for i in (plan.items(root) if hosted else ())
        if i.get('host') == 'session' and i.get('status', 'open') == 'open' and isinstance(i.get('session'), str) and i['session']]


def names(root, pr, repo, item_id):
    named = {i.lower() for i in evidence.ITEM.findall(pr.get('body') or '')} or {(evidence.item_for(root, pr, repo) or {}).get('id', '').lower()}
    return item_id.lower() in named


def compute(root, everything=False):
    out, answers = [], replies(root)
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
                         if repo in held else evidence.gap(f'run: {"; ".join(filter(None, [item.get("reason"), item.get("job") and job(root, item["job"])])) or "no run evidence yet"}', actionable=False)
                         if item.get('kind') == 'run' else evidence.gap(f'PR {taken} not linked: add the WUWEI footer naming {item["id"]}' if taken else 'no pull request yet') if item.get('approved', True)
                         else evidence.gap('awaiting plan approval', actionable=False, owner=True))
                out.append({'item': item['id'], 'title': item['title'], 'pr': None, 'gaps': [first] + evidence.uncounted(root, item['id'])})
            for pr in linked:
                out.append({'item': item['id'], 'title': item['title'], 'pr': f'{repo}#{pr["number"]}',
                            'gaps': read[pr['number']], 'opened': pr.get('createdAt'), 'updated': pr.get('updatedAt')})
    for item in (i for i in open_items if not i.get('repo')):  # a reply has no repository; see replies()
        out.append({'item': item['id'], 'title': item['title'], 'pr': None,
                    'gaps': [evidence.gap('no repository named for this item')]})
    out = answers + flow(root, out)  # owed replies stay first
    (busy, cap), live, prs = queue(root, out, open_items), running(root, hosted=True), [r for r in out if r['pr']]  # a duty's text moves only with its count, so a Stop reminds again only then
    crowd, ceiling = max([[s['session'] for s in live].count(s['session']) for s in live], default=0), limit(root, 'Seat ceiling', 8)
    owed = any(any(evidence.GATES.search(g['text']) for g in r['gaps']) and not any(g['text'].startswith('CI failing') for g in r['gaps']) for r in prs)  # gates start at push (#1221)
    duties = [evidence.gap('orchestration: open PRs with no shepherd seat running')] * (len({r['pr'] for r in prs}) > 2 and 'shepherd' not in [s.get('role') for s in live]) + [
        evidence.gap('orchestration: gates owed with no gate seat running')] * (owed and not any(str(s.get('role')).startswith('sentinel-') for s in live)) + [
        evidence.gap(f'orchestration: {busy} items in progress, over the WIP limit of {cap}: finish before starting')] * (busy > cap) + [
        evidence.gap(f'orchestration: {crowd} seats running, over the ceiling of {ceiling}', actionable=False)] * (crowd > ceiling)  # one session's seats; another cannot stop them
    return [{'item': 'team', 'title': 'seats', 'pr': None, 'gaps': duties}] * bool(duties) + [{**r, 'gaps': r['gaps'] + [  # first: the Stop and session start cut from the end
        evidence.gap(f'{s.get("role")} running in session {s["session"]}', actionable=False) for s in live if str(s.get('item') or '').lower() == str(r['item']).lower()]} for r in out]  # the holder of each item


def limit(root, name, default):  # the owner's last '<name>: <n>' line in .wuwei/standards.md, a date before it allowed, else the planner's default
    try:
        text = (Path(root) / ws.DIR / 'standards.md').read_text(encoding='utf-8', errors='replace')
    except OSError:  # missing or unreadable: the defaults hold
        text = ''
    return int(([default] + re.findall(rf'(?im)^[-*\s]*(?:[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}[ \t]+)?{name}:[ \t]*([0-9]{{1,4}})\b', text))[-1])


def queue(root, out, items):
    """Finish before starting: an open item is in progress with an open PR, a live builder seat under STALE_HOURS or a running
    Codex job. Free slots under the WIP limit go to the highest-score items with no PR; the rest wait, queued."""
    cap, found = limit(root, 'WIP limit', 4), {i['id'].lower(): i for i in items}
    busy = found.keys() & ({r['item'].lower() for r in out if r['pr']}
                           | {str(s.get('item')).lower() for s in running(root, STALE_HOURS, hosted=True) if s.get('role') == 'builder'}
                           | {k for k, i in found.items() if i.get('job') and job(root, i['job']).startswith('job running')})
    free = cap - len(busy)
    fresh = [r for r in out if r['item'].lower() not in busy and r['gaps'][:1] and r['gaps'][0]['text'] == 'no pull request yet']
    for row in sorted(fresh, key=lambda r: r.get('score') if isinstance(r.get('score'), (int, float)) else 0, reverse=True):
        if (free := free - 1) < 0:
            row['gaps'] = [evidence.gap(f'queued: {len(busy)} items in progress, WIP limit {cap}: finish one first', actionable=False),
                           *(dict(g, actionable=False) for g in row['gaps'][1:])]
    return len(busy), cap


def when(text):  # an ISO time or date as UTC; None when it is not one
    try:
        found = datetime.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return found if found.tzinfo else found.replace(tzinfo=datetime.timezone.utc)


def flow(root, out):
    """Kanban flow policy: class of service, stale first in its class, then right to left, then age (oldest first).
    A row waiting on an open item says so and asks nothing; one idle STALE_HOURS with no live seat on its item says stale."""
    rows, goals, last = plan.items(root), view.goals(root), {}
    live = {str(s.get('item') or '').lower() for s in running(root, hosted=True)}  # a live seat in any session
    found = {i['id']: i for i in rows}
    for r in ws.ledger(root):
        for key in (d.get('id'), d.get('item'), d.get('pr')) if isinstance(d := r.get('data'), dict) else ():
            last.update({key.lower(): r.get('ts')} if isinstance(key, str) else {})
    days = {row['item']: (ws.now() - start).days for row in sorted(out, key=lambda r: str(r.get('opened')), reverse=True)
            if (start := when(row.get('opened')))}  # the first PR's age is the last written
    for row in out:
        own = [(g, evidence.GATES.search(g['text'])) for g in row['gaps'] if g['kind'] == 'safety']  # before flow adds any gap
        row['stage'] = (4 if not row['pr'] else 3 if any(g['actionable'] and not gate for g, gate in own)  # building 4, fix round 3,
                        else 2 if any(gate for _, gate in own) else 1 if any(g['owner'] for g, _ in own) else 0)  # gates, owner, ready 0
        if (item := found.get(row['item'])) is None:
            continue
        dated = (goals.get(item.get('goal')) or ('', ''))[1]
        row['class'] = c if (c := item.get('class')) in plan.CLASSES else 'fixed-date' if dated else 'standard'
        row['score'] = plan.cost(item, rows, days)
        seen = max(filter(None, map(when, (row.get('updated'), row.get('opened'), item.get('added'), last.get(row['item'].lower()),
                                           last.get((row['pr'] or '').lower())))), default=None)
        row['last'] = seen and seen.isoformat(timespec='seconds')
        if waits := [a for a in item.get('after') or () if (found.get(a) or {}).get('status', 'open') == 'open']:
            row['gaps'] = [evidence.gap(f'waiting on {", ".join(waits)}', actionable=False),
                           *(dict(g, actionable=False) for g in row['gaps'])]
        elif seen and ws.now() - seen >= datetime.timedelta(hours=STALE_HOURS) and (row['pr'] and row['item'].lower() not in live
                                                                                   or not row['pr'] and item.get('host') == 'session' and item.get('session')):
            row['stale'] = True  # a session builder with no PR: a dead session surfaces here (builder-host)
            row['gaps'] = [evidence.gap(f'stale: no event since {row["last"][:16]}, ' + ('no live seat' if row['pr'] else f'no PR from builder session {item["session"]}')), *row['gaps']]
    return sorted(out, key=lambda r: (plan.CLASSES.index(r.get('class', 'standard')), not r.get('stale'), r['stage'],
                                      r.get('opened') or (found.get(r['item']) or {}).get('added') or ''))


def job(root, path):  # only the Codex companion job file the planner registered with plan run --job; no plugin folder is scanned (#1201)
    found = next((d for _ in range(3) if isinstance(d := ws.read_json(os.path.join(root, path)), dict) or time.sleep(0.2)), {})  # mid-write: again (#1212)
    said = (o.rstrip() if isinstance(o := r.get('rawOutput'), str) else '') if isinstance(r := found.get('result'), dict) else ''
    status = 'asked a question' if (s := found.get('status')) == 'completed' and said.endswith('?') else s if isinstance(s, str) and s else 'state unreadable'
    return f'job {status}' + ''.join(f', handoff {w}' for w in [w for w in (w.strip('`\'"<>[]*,.:;') for w in said.replace('(', ' ').replace(')', ' ').split()) if w.endswith('HANDOFF.md')][-1:])


def rows(root):
    return evidence._cached(root, 'board', lambda: compute(root), TTL)


def text(found, root=None):
    held = andons(root) if root is not None else {}
    cords = [f'ANDON {repo}: {reason}' for repo, reason in held.items()]
    if not found:
        return '\n'.join(cords + ['Board: nothing open in the plan.'])
    lines = cords + ['Board (what each open item still lacks):']
    for row in found:
        idle = row.get('last') and f', last event {(ws.now() - when(row["last"])) // datetime.timedelta(hours=1)}h ago'
        head = f'{row["item"]} {row["title"]}' + (f' ({row["pr"]})' if row['pr'] else '') + (
            f' [{row["class"]}{idle or ""}]' if row.get('class') else '')
        gaps = '; '.join(g['text'] + ('' if g['actionable'] else ' [waiting]') for g in row['gaps']) or 'ready to merge'
        lines.append(f'- {head}: {gaps}')
    return '\n'.join(lines)
