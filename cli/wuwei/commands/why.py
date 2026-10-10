"""Explain from recorded events why an item, a decision or a refusal is where it is."""

import json
import re
import sys

from wuwei import decision, novelty, references, security, state, verdict, watch, workspace
from wuwei.commands.event import EVENT_PRODUCERS
from wuwei.exits import CLEAN, FINDINGS
from wuwei.redact import redact

NOT = 'not recorded'
EVENT_ID = r'\d{4}-\d{2}-\d{2}:[1-9][0-9]*'
REFUSALS = ('hook.refusal', 'guard.would_refuse')
DRAFT = r'draft-[0-9a-f]{32}'
GROUPS = ('queued', 'tier', 'gate', 'decision', 'phase', 'merge')
REQUIRED = {'queued': 'queued', 'tier': 'tier', 'gate': 'gate verdicts', 'merge': 'merge policy check'}


class Missing(Exception):
    """The target has no record (exit 1)."""  # Not LookupError: a KeyError must stay exit 2.


def register(subparsers):
    parser = subparsers.add_parser('why', help='Explain from records why an item, decision or refusal happened')
    parser.add_argument('target', nargs='+', help='an item, owner/repo#n, D-n, a target key, an event id or "last refusal"')
    parser.add_argument('--full', action='store_true', help='add event ids and evidence paths')
    parser.set_defaults(func=run)


def level(root, full):
    return 'full' if full else workspace.verbosity(workspace.load_config(root), 'report')


def run(args):
    root = workspace.find_workspace()
    target = ' '.join(args.target)
    try:
        if target == 'last refusal' or re.fullmatch(EVENT_ID, target):
            steps = refusal(root, target)
        elif re.fullmatch(decision.DECISION_ID, target):
            steps = decided(root, target)
        elif re.fullmatch(DRAFT, target):  # #552
            steps = [(line, None, []) for line in held(root, target)]
        elif target == 'adhoc':  # #676
            steps = adhoc(root)
        elif re.fullmatch(novelty.KEY, target):  # #556
            steps = [(line, None, []) for line in novelty.explain(root, workspace.load_config(root), target)]
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

    Record text is redacted as refusal targets are: a credential never reaches stdout or the board."""
    markers = security.load(root)
    return [security.redact(redact(text if level != 'full' else f'{text} (event {event or NOT}'
                                   + ''.join(f'; {path}' for path in paths) + ')'), markers)
            for text, event, paths in steps]


def question(day, ident):
    path = day / 'decisions' / f'{ident}.md'
    if not path.is_file():
        return NOT
    return (verdict.rows(verdict.active_text(path.read_text(encoding='utf-8')), 'Question') or [NOT])[0].strip()


def scored(score):
    return 'score ' + (', '.join(f'{key} {value}' for key, value in score.items())
                       if isinstance(score, dict) else NOT)


def proposed(day, name):
    path = day / 'proposal.json'
    if not path.is_file():
        return None
    return next((row.get('score') for row in json.loads(path.read_text(encoding='utf-8')).get('candidates', [])
                 if row.get('id') == name), None)


def item(root, name):
    """The recorded chain of one item, oldest day first, as (text, event id, paths) steps."""
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
    rel = lambda path: str(path.relative_to(root))
    groups = {group: [] for group in GROUPS}
    for day, data in days:
        row = data['items'][name]
        ids = {ident for ident, names in decision.naming(day, [name]).items()
               if names and ident.startswith('D-')}
        ids |= {value for value in (row.get('decision'), row.get('assumption', {}).get('decision'))
                if isinstance(value, str)}
        named = set()
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
            if kind.startswith('decision.') and (payload.get('id') in ids or payload.get('item') == name):
                ident, by = payload.get('id'), payload.get('decided_by') or NOT
                outcome = {'decision.decided': f'{payload.get("option")} by {by}',
                           'decision.reversed': f'reversed to {payload.get("option")} by {by}',
                           'decision.routed': 'routed to the owner',
                           'decision.waited': f'{payload.get("outcome")} by {EVENT_PRODUCERS["decision.waited"]}'
                                              ' after decisions.wait_hours'}.get(kind)
                if outcome:
                    named.add(ident)
                    add('decision', f'decision {ident}: {question(day, ident)}: {outcome}',
                        rel(day / 'decisions' / f'{ident}.md'))
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
        for ident in sorted(ids - named):
            groups['decision'].append((f'decision {ident}: {question(day, ident)}: decided {NOT}', None,
                                       [rel(day / 'decisions' / f'{ident}.md')]))
    day, data = days[-1]
    row = data['items'][name]
    steps = [step for group in GROUPS for step in groups[group] or (
        [(f'{REQUIRED[group]}: {NOT}', None, [])]
        if group in REQUIRED and (group != 'merge' or row['phase'] == 'merged') else [])]
    now, wait = f'now: {row["phase"]} ({row["status"]})', row.get('assumption', {})
    action = data.get('watch', {}).get('actions', {}).get(row.get('pr'), {}).get('action')
    if row['phase'] in ('parked', 'escalated'):
        now += f', waiting on decision {row["decision"]}' if row.get('decision') else f', waiting on: {NOT}'
    elif wait.get('status') == 'waiting':
        now += f', waiting on external confirmation {wait.get("decision", NOT)}'
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
    if shadowed and payload.get('area'):  # #331
        lines.append(f'posture: {payload["area"]} = {payload.get("level")} ({payload.get("posture")})')
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


def decided(root, ident):
    """Today's D-n: options and scores, weights, margin, class, level and who decided."""
    path = decision.today_path(ident, root)
    if not path.is_file():
        raise Missing(f'no decision record {ident} today; run bin/wuwei nudges for open decisions')
    text = path.read_text(encoding='utf-8')
    fields, scores = decision.evaluate(text)
    _, _, wants, _ = decision._scored(fields)
    margin = decision.margin(fields, scores)
    kind = (verdict.rows(verdict.active_text(text), 'Class') or [''])[0].strip() or NOT
    lines = [*decision.present(ident, fields, 'brief').splitlines(),
             'weights: ' + ', '.join(f'{row[0]} {row[1]}' for row in wants),
             f'margin: {margin:.2f}', f'class: {kind}']
    steps = [(line, None, [str(path.relative_to(root))]) for line in lines]
    novel = novelty.routed(state.read_state(root), ident)
    if novel:  # #556
        steps.append((f'novel: first time for {", ".join(novel)}', None, []))
    rows = list(enumerate(watch.records(workspace.day_dir(root) / 'events.jsonl'), 1))
    last = next(((number, event['payload']) for number, event in reversed(rows)
                 if event['kind'] in ('decision.decided', 'decision.reversed')
                 and event['payload'].get('id') == ident), None)
    if last is None:
        return steps + [(f'level: {NOT}', None, []), (f'decided: {NOT}', None, [])]
    number, payload = last
    by = str(payload.get('decided_by') or NOT)
    cruise = re.search(r'@L(\d)', by)
    at = f'{workspace.day_dir(root).name}:{number}'
    return steps + [(f'level: L{cruise[1]}' if cruise else f'level: {NOT}', at if cruise else None, []),
                    (f'decided: {payload.get("option")} by {by}', at, [])]
