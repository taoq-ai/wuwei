"""The day report, the close checkpoint and the DORA keys, all read from the ledger, traces and the code host."""

from collections import Counter
import datetime
import hashlib
import statistics
from pathlib import Path

from wuwei import board, evidence, gh, plan, ws


def _repos(root):
    return sorted(set(ws.config(root)['repos']) | {i['repo'] for i in plan.items(root) if i.get('repo')})


def _count(rows, key):
    return Counter(str(r['data'].get(key, '')).splitlines()[0][:100] if r['data'].get(key) else '?' for r in rows)


def day(root, date=None):
    date = date or ws.today()
    out = [f'# WUWEI report {date}', '']
    rows = lambda kind: ws.rows(root, kind, date)  # noqa: E731
    passes, closes = rows('plan.pass'), rows('day.closed')
    done, parked = rows('item.done'), rows('item.parked')
    out += ['## Plan', f'Plan passes: {len(passes)}. Checkpoints: {len(closes)}. '
            f'Done today: {len(done)}. Parked today: {len(parked)}.']
    out += [f'- parked {r["data"]["id"]}: {r["data"].get("reason", "")}' for r in parked]
    out += since_checkpoint(root, date)
    out += ['', '## Board', board.text(board.compute(root), root), '', '## Merges']
    checked = {r['data'].get('pr') for r in ws.rows(root, 'merge.checked')}
    for repo in _repos(root):
        try:
            merged = [pr for pr in gh.merged_prs(repo, date) if (pr.get('mergedAt') or '').startswith(date)]
        except gh.GhError as exc:
            out.append(f'- {repo}: unmeasured ({exc})')
            continue
        for pr in merged:
            ref = f'{repo}#{pr["number"]}'
            out.append(f'- {ref} merged through WUWEI\'s check' if ref in checked else
                       f'- {ref} merged without WUWEI reading its evidence (an exception for the retro)')
    out += [f'- {r["data"]["pr"]} merged with process gaps: {"; ".join(r["data"]["process"])}'
            for r in rows('merge.checked') if r['data'].get('process')]
    refused = rows('refused')
    questions = [r for r in refused if r['data'].get('tool') == 'AskUserQuestion']
    out += ['', '## Doors', f'Refused: {len(refused)} (questions sent back to the model: {len(questions)}). '
            f'Asked the owner (infrastructure): {len(rows("asked"))}. Notes: {len(rows("note"))}. '
            f'Stop reminders: {len(rows("stop.reminded"))}.']
    out += [f'- {n} x {reason}' for reason, n in _count(refused, 'reason').most_common(8)]
    replies = [i for i in plan.items(root) if i.get('kind') == 'reply']
    now = ws.now().isoformat(timespec='seconds')
    still = [i for i in replies if i.get('status') == 'open']
    took = sorted(_hours(r['ts'], d['ts']) * 60 for r in rows('reply.owed') for d in rows('item.done')
                  if d['data'].get('id') == r['data']['id'])
    out += ['', '## Replies', f'Replies: {len(rows("reply.owed"))} owed today, {len(took)} closed, {len(still)} open, '
            f'{sum(1 for i in still if i["due"] < now)} overdue'
            + (f'; median response {statistics.median(took):.0f} min.' if took else '.')]
    prompts = rows('prompt')
    out += ['', '## Owner', f'Owner prompts: {len(prompts)}.']
    out += [f'- {q}' for r in prompts for q in r['data'].get('questions', [])]
    stops = Counter(r['data'].get('role') for r in rows('seat.stopped'))
    verdicts = Counter(f'{r["data"].get("gate")} {r["data"].get("verdict")}' for r in rows('attest'))
    out += ['', '## Seats and gates', 'Seats: ' + (', '.join(f'{k} {v}' for k, v in sorted(stops.items())) or 'none') + '.',
            'Verdicts: ' + (', '.join(f'{k} {v}' for k, v in sorted(verdicts.items())) or 'none') + '.',
            f'Verdicts missing after a reminder: {len(rows("verdict.missing"))}.']
    traces = ws.traces(root, date)
    tools = Counter(t.get('tool') for t in traces)
    out += ['', '## Telemetry', f'Tool calls: {len(traces)}; outward (MCP) calls: '
            f'{sum(n for k, n in tools.items() if str(k).startswith("mcp__"))}.',
            'Top tools: ' + (', '.join(f'{k} {v}' for k, v in tools.most_common(8)) or 'none') + '.',
            f'Hook errors: {len(rows("hook.error"))}.']
    out += learning(root)
    broken = ws.verify(root)
    out += ['', 'Ledger: intact' if not broken else f'Ledger: broken at {", ".join(broken)}', '']
    return '\n'.join(out)


def since_checkpoint(root, date):
    """What changed since the day's last checkpoint, so a second close reads as a diff."""
    rows = ws.ledger(root)
    if not (marks := [i for i, row in enumerate(rows) if row.get('kind') == 'day.closed' and row.get('ts', '').startswith(date)]):
        return []
    after = Counter(row['kind'] for row in rows[marks[-1] + 1:])
    return ['', f'## Since the last checkpoint ({rows[marks[-1]]["ts"][11:16]} UTC)',
            ', '.join(f'{kind} {n}' for kind, n in sorted(after.items())) or 'nothing recorded']


def learning(root):
    """What the shipped work teaches: escapes traced to their gates, gate yield, cost, autonomy, a sample."""
    out, attests = ['', '## Learning'], ws.rows(root, 'attest')
    since = (ws.now() - datetime.timedelta(days=28)).date().isoformat()
    week = (ws.now() - datetime.timedelta(days=7)).isoformat()
    for repo in _repos(root):
        try:
            merged = [pr for pr in gh.merged_prs(repo, since) if pr.get('mergedAt')]
            unplanned = [pr for pr in gh.open_prs(repo) if evidence.item_for(root, pr, repo) is None]
        except gh.GhError as exc:
            out.append(f'- {repo}: unmeasured ({exc})')
            continue
        for pr in merged:  # a finding written after the merge: the gate ran too late (#1050)
            late = [f'{r["data"]["gate"]} {r["data"]["verdict"]}' for r in attests if r['data'].get('verdict') != 'PASS'
                    and r['data'].get('pr', '').lower() == f'{repo}#{pr["number"]}'.lower() and r['ts'][:19] > pr['mergedAt'][:19]]
            out += [f'- escaped (post-merge): {repo}#{pr["number"]} merged before {", ".join(late)}'] if late else []
        titles = {pr['title']: pr for pr in merged}
        for revert in (pr for pr in merged if pr['title'].startswith('Revert "')):
            if original := titles.get(revert['title'][8:].rstrip('"')):
                ref = f'{repo}#{original["number"]}'
                passed = [f'{r["data"]["gate"]} ({r["data"].get("confidence") or "?"})' for r in attests
                          if r['data'].get('pr') == ref and r['data'].get('verdict') == 'PASS']
                out.append(f'- escaped: {ref} reverted by #{revert["number"]}; it passed: {", ".join(passed) or "no gate"}')
        spent = evidence.budget(root, repo)
        if spent['cfr'] is not None:
            out.append(f'- {repo}: change failure rate {spent["cfr"]:.0%} over 28 days ({spent["merged"]} merges; '
                       + ('tiers raised one step)' if spent['raised'] else 'tiers as planned)'))
        out += [f'- Unplanned: {repo}#{pr["number"]} {pr["title"]}' for pr in unplanned[:10]]
        if recent := sorted((pr for pr in merged if pr['mergedAt'] >= week), key=lambda pr: pr['number']):
            pick = int(hashlib.sha256(f'{ws.now().isocalendar()[:2]}{repo}'.encode()).hexdigest(), 16) % len(recent)
            out.append(f'- Sample for you this week: {repo}#{recent[pick]["number"]} (read its evidence comment)')
    for gate in sorted({r['data'].get('gate') for r in attests if r['data'].get('gate')}):
        rows = [r for r in attests if r['data'].get('gate') == gate]
        fixes = sum(1 for r in rows if r['data'].get('verdict') == 'FIX')
        out.append(f'- gate yield {gate}: {len(rows)} verdicts, {fixes} FIX ({fixes / len(rows):.0%})')
    spent = Counter()
    for row in ws.rows(root, 'seat.stopped'):
        spent[row['data'].get('role')] += row['data'].get('tokens') or 0
    out.append('- tokens by role: ' + (', '.join(f'{k} {v}' for k, v in sorted(spent.items()) if v) or 'unmeasured'))
    out += [f'- exception: {d["pr"]} at {d["head"]}: {d["gap"]}' for d in (row['data'] for row in ws.rows(root, 'ruling'))
            if d.get('kind') == 'exception' and d.get('approved')]
    return out


def close(root):
    """A checkpoint: write the report for the day so far. A later plan pass reopens the day."""
    path = Path(root) / ws.DIR / 'days' / ws.today() / 'report.md'
    ws.atomic_write(path, day(root))
    ws.record(root, 'day.closed', {'report': str(path.relative_to(root))})
    return path


def _hours(start, end):
    parse = lambda text: datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))  # noqa: E731
    return (parse(end) - parse(start)).total_seconds() / 3600


def dora(root, window=28, today=None):
    end = datetime.date.fromisoformat(today or ws.today())
    since = (end - datetime.timedelta(days=window)).isoformat()
    table = {}
    for repo in _repos(root):
        try:
            merged = [pr for pr in gh.merged_prs(repo, since) if pr.get('mergedAt')]
            deploys, source = [d for d in gh.deployments(repo) if d.get('created_at', '') >= since], 'deployments'
            if not deploys:
                deploys, source = [r for r in gh.releases(repo) if (r.get('published_at') or '') >= since], 'releases'
        except gh.GhError as exc:
            table[repo] = {'unmeasured': str(exc)}
            continue
        reverts = sum(1 for pr in merged if pr.get('title', '').startswith('Revert'))
        table[repo] = {
            'lead_time_hours': round(statistics.median(_hours(pr['createdAt'], pr['mergedAt']) for pr in merged), 1)
            if merged else 'unmeasured',
            'deploys': len(deploys), 'deploy_source': source,
            'change_failure_rate': round(reverts / len(merged), 2) if merged else 'unmeasured',
            'merged': len(merged), 'time_to_restore': 'unmeasured'}
    return table
