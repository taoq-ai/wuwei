"""Bring a 0.34 workspace to 1.0 in place: the config shape, the goals, the open items with their
PRs, the latest proposal, and the gate verdicts as attestations. Idempotent; it says what it moved."""

import hashlib
import json
from pathlib import Path
import re
import tomllib

from wuwei import evidence, plan, ws
from wuwei.verdict import GATES


def _days(root):
    days = Path(root) / ws.DIR / 'days'
    return sorted((d for d in days.iterdir() if d.is_dir() and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', d.name)),
                  reverse=True) if days.is_dir() else []


def _json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def review_channel(root):
    """0.34's [shepherd] review_channel, from the config or an earlier upgrade's backup, as a standards line."""
    backup = Path(root) / ws.DIR / 'config.0x.toml'
    old = tomllib.loads(backup.read_text(encoding='utf-8')) if backup.is_file() else ws.raw_config(root)
    channel = (old.get('shepherd') or {}).get('review_channel') if isinstance(old.get('shepherd'), dict) else None
    if not isinstance(channel, str) or not channel.strip() or evidence.review_place(root):
        return []
    path = Path(root) / ws.DIR / 'standards.md'
    text = path.read_text(encoding='utf-8') if path.is_file() else '# Standards\n'
    ws.atomic_write(path, text.rstrip('\n') + f'\n\nReview requests: {channel.strip()}\n')
    return [f'standards: Review requests: {channel.strip()} (from the 0.34 review_channel)']


def config(root):
    if not (gone := ws.retired(root)):
        return []
    backup = Path(root) / ws.DIR / 'config.0x.toml'
    if not backup.exists():
        backup.write_text((Path(root) / ws.DIR / 'config.toml').read_text(encoding='utf-8'), encoding='utf-8')
    ws.write_config(root, ws.config(root))
    return [f'config: rewritten to the six keys (the old file is .wuwei/config.0x.toml); retired: '
            + ', '.join(gone)]


def goals(root):
    target = Path(root) / ws.DIR / 'goals.md'
    if target.is_file() and re.search(r'^(Outcome|outcome):[ \t]*\S', target.read_text(encoding='utf-8'), re.M):
        return []
    sources = [d / 'goals.md' for d in _days(root)] + [Path(root) / ws.DIR / 'memory' / 'goals.md']
    found = next((s for s in sources if s.is_file() and s.read_text(encoding='utf-8').strip()), None)
    if found is None:
        return []
    ws.atomic_write(target, found.read_text(encoding='utf-8'))
    return [f'goals: copied from {found.relative_to(root)}']


def _scores(row, framework):
    score = row.get('score') if isinstance(row.get('score'), dict) else {}
    try:
        if framework == 'wsjf':
            return {'value': score['value'], 'time': score['time_criticality'], 'risk': score['risk_reduction'],
                    'size': score['job_size']}
        return {key: score[key] for key in ('reach', 'impact', 'confidence', 'effort')}
    except KeyError:
        return None


def _add(root, item_id, title, row, framework, why, prs=(), approved=False):
    scores = _scores(row, framework)
    item = {'id': item_id, 'title': title, 'goal': row.get('goal') or 'unplanned', 'repo': row.get('repo', ''),
            'tier': row.get('tier') if row.get('tier') in plan.TIERS else 'standard', 'status': 'open',
            'framework': framework, 'scores': scores or {}, 'why': why, 'added': ws.today(), 'prs': list(prs),
            'approved': approved}
    try:
        item['score'] = plan.score(framework, scores) if scores else 0
    except ValueError:
        item['score'] = 0
    plan.save(root, plan.items(root) + [item])
    ws.record(root, 'item.added', {'id': item_id, 'goal': item['goal'], 'repo': item['repo'], 'imported': True})


def items(root):
    framework, known = ws.config(root)['prioritisation'], {i['id'].lower() for i in plan.items(root)}
    before = len(known)  # each import adds one new id
    state = next((_json(d / 'state.json') for d in _days(root) if (d / 'state.json').is_file()), None) or {}
    for name, row in (state.get('items') or {}).items():
        if not isinstance(row, dict) or row.get('phase') in ('merged', 'parked') or row.get('status') == 'done':
            continue
        if name.lower() not in known:
            title = (row.get('approved_as') or name).split(';')[0].strip() or name
            _add(root, name, title, row, framework, 'imported from 0.34; rescore at the next pass',
                 [row['pr']] if isinstance(row.get('pr'), str) else (), approved=True)
            known.add(name.lower())
    lead = next((_json(p) for d in _days(root) for p in sorted(d.glob('lead*.json'), reverse=True)), None)
    candidates = lead.get('candidates', []) if isinstance(lead, dict) else lead if isinstance(lead, list) else []
    for row in candidates:
        if isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'].lower() not in known:
            _add(root, row['id'], row.get('title') or row.get('scope') or row['id'], row, framework,
                 'imported from the 0.34 proposal')
            known.add(row['id'].lower())
    return [f'plan: imported {len(known) - before} open items from 0.34'] if len(known) > before else []


def verdicts(root):
    ids = sorted((i['id'] for i in plan.items(root)), key=len, reverse=True)
    done = {row['data'].get('path') for row in ws.rows(root, 'attest')}
    moved = 0
    for day in sorted(_days(root)):
        for path in sorted((day / 'decisions').glob('gate-*.md')):
            relative = str(path.relative_to(root))
            text = path.read_text(encoding='utf-8', errors='replace')
            verdict = re.search(r'^Verdict:\s*(PASS|FIX|ESCALATE|PARK)\b', text, re.M)
            head = re.search(r'^Head:\s*([0-9a-f]{7,40})\b', text, re.M | re.I)
            gate = next((g for g in GATES if re.search(rf'(^|-){g}(-|$)', path.stem.lower())), None)
            item = next((i for i in ids if i.lower() in path.stem.lower()), None)
            if relative in done or not (verdict and head and gate and item):
                continue
            ws.record(root, 'attest', {'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                       'gate': gate, 'item': item, 'head': head[1].lower(), 'verdict': verdict[1],
                                       'imported': True, 'role': f'sentinel-{gate}'})
            moved += 1
    return [f'verdicts: imported {moved} verdicts from 0.34 as attestations'] if moved else []


def run(root):
    return review_channel(root) + config(root) + goals(root) + items(root) + verdicts(root)
