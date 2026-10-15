"""The day report, the close checkpoint and the DORA keys, all read from the ledger, traces and the code host."""

from collections import Counter
import datetime
import statistics
from pathlib import Path

from wuwei import board, gh, plan, ws


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
    out += ['', '## Board', board.text(board.compute(root)), '', '## Merges']
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
    refused = rows('refused')
    questions = [r for r in refused if r['data'].get('tool') == 'AskUserQuestion']
    out += ['', '## Doors', f'Refused: {len(refused)} (questions sent back to the model: {len(questions)}). '
            f'Asked the owner (infrastructure): {len(rows("asked"))}. Notes: {len(rows("note"))}. '
            f'Stop reminders: {len(rows("stop.reminded"))}.']
    out += [f'- {n} x {reason}' for reason, n in _count(refused, 'reason').most_common(8)]
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
    broken = ws.verify(root)
    out += ['', 'Ledger: intact' if not broken else f'Ledger: broken at lines {broken}', '']
    return '\n'.join(out)


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
