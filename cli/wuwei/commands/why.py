"""Explain from recorded events why an item or a refusal is where it is."""

import json
import re
import sys

from wuwei import references, security, state, verdict, watch, workspace
from wuwei.commands.event import EVENT_PRODUCERS
from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.redact import redact

NOT = 'not recorded'
EVENT_ID = r'\d{4}-\d{2}-\d{2}:[1-9][0-9]*'
REFUSALS = ('hook.refusal', 'guard.would_refuse')
DRAFT = r'draft-[0-9a-f]{32}'
GROUPS = ('queued', 'approved', 'worktree', 'seat', 'tier', 'gate', 'phase', 'merge')
REQUIRED = {'queued': 'queued', 'tier': 'tier', 'gate': 'gate verdicts', 'merge': 'merge policy check'}


class Missing(Exception):
    """The target has no record (exit 1)."""  # Not LookupError: a KeyError must stay exit 2.


def register(subparsers):
    parser = subparsers.add_parser('why', help='Explain from records why an item or refusal happened')
    parser.add_argument('target', nargs='+', help='an item, owner/repo#n, a target key, an event id or "last refusal"')
    parser.add_argument('--full', action='store_true', help='add event ids and evidence paths')
    parser.add_argument('--json', action='store_true',
                        help="print an item's live docs, ticket and spec values and its steps as JSON")
    parser.set_defaults(func=run)


def level(root, full):
    return 'full' if full else workspace.verbosity(workspace.load_config(root), 'report')


def run(args):
    root = workspace.find_workspace()
    target = ' '.join(args.target)
    if args.json and (target == 'last refusal' or any(re.fullmatch(pattern, target) for pattern in (
            EVENT_ID, DRAFT))):
        print('wuwei why: --json reads an item; pass an item id', file=sys.stderr)
        return UNRUN
    try:
        if args.json:
            print(json.dumps(live(root, target, level(root, args.full))))
            return CLEAN
        if target == 'last refusal' or re.fullmatch(EVENT_ID, target):
            steps = refusal(root, target)
        elif re.fullmatch(DRAFT, target):  # #552
            steps = [(line, None, []) for line in held(root, target)]
        elif target == 'adhoc':  # #676
            steps = adhoc(root)
        else:
            steps = item(root, target)
    except Missing as exc:
        print(f'wuwei why: {exc}', file=sys.stderr)
        return FINDINGS
    print('\n'.join(render(steps, level(root, args.full), root)))
    return CLEAN


def adhoc(root):
    """#676: today's adhoc seats, the agents launched outside the WUWEI seat types."""
    path = workspace.day_dir(root) / 'state.json'
    steps = [(f"adhoc seat {name}: {seat.get('type', NOT)} as {seat.get('label', NOT)}, "
              f"launched by {seat.get('launcher', NOT)}, {seat['status']}; prompt: {seat.get('prompt', NOT)}; "
              f"traces: {', '.join(seat.get('trace_sessions', [])) or 'none yet'}",
              None, [str(path.relative_to(root))])
             for name, seat in state.read_state(root)['seats'].items() if seat.get('role') == 'adhoc']
    if not steps:
        raise Missing('no adhoc seat today; an Agent launch of a type outside the WUWEI seats registers one, then run wuwei why adhoc')
    return steps


def render(steps, level, root):
    """One line per step; at full, each line names its event id and evidence paths.

    Record text is redacted as refusal targets are: a credential never reaches stdout."""
    markers = security.load(root)
    return [security.redact(redact(text if level != 'full' else f'{text} (event {event or NOT}'
                                   + ''.join(f'; {path}' for path in paths) + ')'), markers)
            for text, event, paths in steps]


def scored(score):
    return 'score ' + (', '.join(f'{key} {value}' for key, value in score.items())
                       if isinstance(score, dict) else NOT)


def proposed(day, name):
    path = day / 'proposal.json'
    if not path.is_file():
        return None
    return next((row.get('score') for row in json.loads(path.read_text(encoding='utf-8')).get('candidates', [])
                 if row.get('id') == name), None)


def live(root, name, level):
    """#667: the item's values as recorded now (docs, ticket, spec) and its steps."""
    from pathlib import Path
    from wuwei import docs, specmode
    name, days = _days(root, name)
    day, data = days[-1]
    row = data['items'][name]
    config = workspace.load_config(root)
    markers = security.load(root)
    clean = lambda text: text if text is None else security.redact(redact(text), markers)
    shown = docs.shown(config, row)
    spec = specmode.brief_line(config, name, row, Path(row['worktree']) if row.get('worktree') else None, True)
    return {'item': name, 'day': day.name,
            'docs': {'value': clean(shown), 'reason': clean((row.get('docs') or {}).get('reason', '')),
                     'command': None if shown == 'n/a' else docs.command(config, name)},
            'ticket': clean(((data.get('tickets') or {}).get(name) or {}).get('id')),
            'spec': clean(spec and spec.removeprefix('Spec: ')),
            'steps': render(item(root, name), level, root)}


def _days(root, name):
    """(item name, [(day, state)] oldest first); a PR ref resolves to its item."""
    if '#' in name:
        ref = references.pull_request(name)
        name = next((key for day in watch.days(root)
                     for key, row in state.read_state(directory=day)['items'].items()
                     if row.get('pr') == ref), None)
        if name is None:
            raise Missing(f'no item links {ref}; run bin/wuwei pr state for the PRs owned today')
    days = [(day, data) for day in reversed(watch.days(root))
            if name in (data := state.read_state(directory=day))['items']]
    if not days:
        raise Missing(f'no recorded item {name}; run bin/wuwei status for today\'s items')
    return name, days


def item(root, name):
    """The recorded chain of one item, oldest day first, as (text, event id, paths) steps."""
    name, days = _days(root, name)
    rel = lambda path: str(path.relative_to(root))
    groups = {group: [] for group in GROUPS}
    for day, data in days:
        row = data['items'][name]
        for number, event in enumerate(watch.records(day / 'events.jsonl'), 1):
            at, kind, payload = f'{day.name}:{number}', event['kind'], event['payload']
            add = lambda group, text, *paths: groups[group].append((text, at, list(paths)))
            if kind in ('plan.approved', 'state.import') and name in payload.get('approved_items', []):
                add('queued', f'queued: goal {row.get("goal", NOT)}, {scored(proposed(day, name))}',
                    rel(day / 'proposal.json'))
            elif kind == 'state.import' and name in payload.get('items', []):
                add('queued', f'queued: carried over from an earlier day, goal {row.get("goal", NOT)}')
            if kind == 'plan.added' and payload.get('item') == name:
                score = data.get('discovery_candidates', {}).get(name, {}).get('score')
                add('queued', f'queued: goal {row.get("goal", NOT)}, {scored(score)}', rel(day / 'state.json'))
            if kind == 'worktree.created' and payload.get('item') == name:
                add('worktree', f'worktree: branch {payload.get("branch", NOT)} from {payload.get("base", NOT)} '
                    f'at {str(payload.get("start", NOT))[:12]}')
            if kind == 'seat launched' and payload.get('item') == name:
                seat = data.get('seats', {}).get(payload.get('name'), {})
                if seat.get('planner_note'):  # #660: the planner's note around WUWEI's launch prompt
                    add('seat', f'seat {payload["name"]} ({seat.get("role")}): planner note: {seat["planner_note"]}',
                        rel(day / 'state.json'))
                elif seat.get('role') == 'adhoc':
                    add('seat', f'seat {payload["name"]} ({seat.get("type")}, unbriefed): prompt: '
                        f'{seat.get("prompt", NOT)}', rel(day / 'state.json'))
            if kind == 'gate.tiered' and payload.get('item') == name:
                reasons = payload.get('reasons') or []
                add('tier', f'tier: {payload.get("tier", NOT)}' + (f' ({"; ".join(reasons)})' if reasons else ''))
            if kind == 'gate.received' and payload.get('item') == name:
                text = f'gate {payload.get("role")} {payload.get("round")}: {payload.get("verdict")}'
                record = data['gate_verdicts'].get(f'{name}:{payload.get("role")}:{payload.get("round")}', {})
                path = root / record['file'] if record.get('file') else None
                if path is not None and path.is_file():
                    blocking = [block.strip().splitlines()[0] for block in verdict.finding_blocks(
                        verdict.active_text(path.read_text(encoding='utf-8')))
                        if re.search(verdict.BLOCKS_YES, block, re.I)]
                    add('gate', text + (', blocking: ' + '; '.join(blocking) if blocking else ''), rel(path))
                else:
                    add('gate', text + f', blocking findings {NOT}')
            if name in payload.get('phase_changes', {}):
                add('phase', f'phase {payload["phase_changes"][name]} by {EVENT_PRODUCERS.get(kind, kind)}')
            if kind == 'merge.auto' and row.get('pr') and payload.get('pr') == row['pr']:
                evidence = payload.get('evidence', {})
                checks = ', '.join(f'{check.get("name")} {check.get("conclusion")}'
                                   for check in evidence.get('checks', [])) or 'none'
                add('merge', f'merge {row["pr"]}: cleared by the merge policy at head '
                    f'{str(evidence.get("head", NOT))[:12]}, checks {checks}, '
                    f'approvals {", ".join(evidence.get("approvals", [])) or "none"}',
                    *(entry['path'] for entry in evidence.get('verdicts', [])))
    day, data = days[-1]
    row = data['items'][name]
    if row.get('approved_as'):  # #731: the owner's recorded approval, once, from the latest day
        groups['approved'].append((f'approved as: {row["approved_as"]}', None, [rel(day / 'state.json')]))
    steps = [step for group in GROUPS for step in groups[group] or (
        [(f'{REQUIRED[group]}: {NOT}', None, [])]
        if group in REQUIRED and (group != 'merge' or row['phase'] == 'merged') else [])]
    now = f'now: {row["phase"]} ({row["status"]})'
    action = data.get('watch', {}).get('actions', {}).get(row.get('pr'), {}).get('action')
    if row['phase'] in ('parked', 'escalated'):  # a park in code shows its reason; the owner resumes it
        reason = (row.get('disposition') or {}).get('reason')
        now += (f', {reason}' if reason else '') + f'; waiting on: wuwei plan resume {name}'
    elif action:
        now += f', waiting on {action}'
    return steps + [(now, None, [rel(day / 'state.json')])]


def refusal(root, target):
    """The guard, rule, command and fix of one recorded hook refusal or shadowed refusal."""
    if target == 'last refusal':
        found = next(((day, number, event) for day in watch.days(root)
                      for number, event in reversed(list(enumerate(watch.records(day / 'events.jsonl'), 1)))
                      if event['kind'] in REFUSALS), None)
        if found is None:
            raise Missing('no recorded refusal; nothing was refused today, so run bin/wuwei status for the day')
    else:
        name, _, line = target.partition(':')
        day = next((day for day in watch.days(root) if day.name == name), None)
        rows = watch.records(day / 'events.jsonl') if day else []
        if int(line) > len(rows) or rows[int(line) - 1]['kind'] not in REFUSALS:
            raise Missing(f'no recorded refusal {target}; run bin/wuwei why last refusal for the latest one')
        found = day, int(line), rows[int(line) - 1]
    day, number, event = found
    payload = event['payload']
    shadowed = event['kind'] == 'guard.would_refuse'
    lines = [f'{"would have refused (shadow)" if shadowed else "refusal"} at {event["ts"]}',
             f'command: {payload.get("target") or NOT}']
    refusals = ([{'guard': payload.get('guard'), 'reason': payload.get('reason', '')}] if shadowed
                else payload.get('refusals') or [{'guard': None, 'reason': payload.get('reason', '')}])
    for entry in refusals:
        # Messages carry no structured rule or fix; the first "; " splits them (Assumption A3).
        rule, _, fix = entry['reason'].partition('; ')
        lines += [f'guard: {entry.get("guard") or NOT}', f'rule: {rule}', f'fix: {fix or NOT}']
        draft = re.search(DRAFT, rule) if rule.startswith('outward:') else None
        if draft:  # #552: the register edge behind the hold
            try:
                tool = _draft(root, draft[0]).get('tool')
            except ValueError:  # a damaged queue still shows the refusal
                tool = None
            lines += edges(root, rule, tool)
    return [(text, f'{day.name}:{number}', []) for text in lines]


def _draft(root, draft_id):
    from wuwei import drafts
    return drafts.read(state.read_state(root)).get(draft_id) or {}


def edges(root, reason, tool=None):
    """#552: the edge lines of the register edges a hold's reason names."""
    from wuwei import graph
    try:
        register = graph.load(root)
    except ValueError:
        register = None
    found = graph.cite(register, reason, tool) if register else []
    return [f'edge: {graph.line(edge)}' for edge in found] or [f'edge: {NOT}']


def held(root, draft_id):
    """#552: the rule that held a draft and the register edge behind it."""
    from wuwei import outward
    row = _draft(root, draft_id)
    if not row:
        raise Missing(f'no draft {draft_id} today; run bin/wuwei drafts for the queued ids')
    rule = row['tier_reason'].removeprefix(outward.APPROVAL_REQUIRED + ': ')
    return [f'held: {rule}', *edges(root, rule, row.get('tool'))]
