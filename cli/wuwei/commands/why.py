"""Explain from recorded events why an item or a refusal is where it is."""

import json
import re
import sys

from wuwei import references, security, state, verdict, watch, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.redact import redact

NOT = 'not recorded'
EVENT_ID = r'\d{4}-\d{2}-\d{2}:[1-9][0-9]*'
REFUSALS = ('hook.refusal', 'guard.would_refuse')
GROUPS = ('queued', 'approved', 'worktree', 'seat', 'tier', 'gate', 'phase', 'merge')
REQUIRED = {'queued': 'queued', 'tier': 'tier', 'gate': 'gate verdicts', 'merge': 'merge policy check'}


# The command that writes each event kind, named in a phase line.
EVENT_PRODUCERS = {
    'outward.ai_tells': 'the outward port and hook (wuwei.outward.humanize_lint)',
    'outward.lint': 'the outward port and hook (wuwei.outward.check_lint)',
    'outward.to_owner': 'the outward port and hook (wuwei.outward.to_owner)',
    'worktree.adopted': 'wuwei worktree adopt, wuwei worktree add --branch or wuwei pr claim',
    'worktree.created': 'wuwei worktree add',
    'build.started': 'wuwei build next', 'gate.tiered': 'wuwei dispatch next', 'gate.delta_head': 'wuwei dispatch next', 'build.launched': 'wuwei build',
    'build.fix_opened': 'wuwei pr act or wuwei dispatch next',
    'polish.skipped': 'wuwei dispatch skip-polish',
    'build.checked': 'wuwei build check', 'build.check_started': 'wuwei build check',
    **{f'spec.{kind}': 'wuwei hook, wuwei build or wuwei dispatch next' for kind in ('step', 'skipped', 'warned')},
    'spec.override': 'owner host wuwei plan set',
    'guard.would_refuse': 'wuwei hook (guards.enforce = false) or wuwei pr raise',
    'traces.noted': 'wuwei dispatch receive or wuwei close', 'traces.unmatched': 'wuwei dispatch receive or wuwei close',
    'seat.usage': 'wuwei build, wuwei dispatch opinion or SubagentStop',
    'integrity': 'wuwei integrity check', 'integrity_failed': 'wuwei integrity check',
    'integrity_confirmation': 'owner host re-confirmation',
    'state.transition': 'wuwei build next',
    'state.import': 'wuwei plan approve', 'plan.approved': 'wuwei plan approve',
    'cap.derived': 'wuwei dispatch next --all',
    'plan.added': 'wuwei plan add',
    'finding.noted': 'wuwei note --fix',
    'plan.session': 'wuwei plan session', 'gate.asked': 'wuwei hook PostToolUse', 'brief written': 'wuwei brief',
    'seat launched': 'wuwei hook PreToolUse or wuwei dispatch opinion',
    'seat stopped': 'wuwei hook SubagentStop, wuwei dispatch opinion or owner wuwei seat stop',
    'traces.gap': 'wuwei hook PostToolUse',
    'traces.slow': 'wuwei hook PostToolUse',
    'seat stood down': 'wuwei hook SubagentStop',
    'seat adhoc': 'wuwei seat start', 'subagent.untraced': 'wuwei hook SubagentStop',
    'fast_checks.record': 'wuwei build check', 'reply: acknowledged': 'wuwei pr act',
    'reply: thread_posted': 'wuwei pr act', 'pr.disposition': 'wuwei pr disposition',
    'scanner.finding': 'wuwei scanner or security recorder',
    'pr.action': 'wuwei pr state', 'pr.action.done': 'wuwei pr act',
    'pr.review_posted': 'wuwei pr ping', 'pr.raised': 'wuwei pr raise',
    'pr.claimed': 'wuwei pr claim',
    'pr.reviewers_selected': 'wuwei pr ping',
    'reviewer.unresolved': 'wuwei pr raise, ping or reviewers',
    'day.close_requested': 'wuwei close', 'day.closed': 'wuwei close', 'next.action': 'wuwei next',
    'build.parked': 'wuwei build', 'build.held': 'wuwei build', 'build.released': 'wuwei build',
    'gate.received': 'wuwei dispatch receive',
    'tracker.call': 'wuwei tracker lifecycle',
    **{f'duty.{step}': 'wuwei tracker lifecycle' for step in ('due', 'done', 'skipped')},
    'tracker.created': 'wuwei tracker create or wuwei plan approve',
    'tracker.folded': 'wuwei tracker log',
    'tracker.logged': 'wuwei tracker log', 'plan.set': 'wuwei plan set or wuwei init --upgrade',
    'steward.run': 'wuwei steward run',
    'calibration.drift': 'wuwei steward run',
    'plan.disposed': 'wuwei plan carry or park, wuwei dispatch next or wuwei build',
    'plan.resumed': 'wuwei plan resume',
    'doctor.fixed': 'owner host wuwei doctor --fix',
    'config.newer_template': 'wuwei hook PreToolUse',
    **{f'telemetry.{action}': 'wuwei telemetry or wuwei report'
       for action in ('skipped', 'unsent', 'shared', 'ready', 'off')},
}


class Missing(Exception):
    """The target has no record (exit 1)."""  # Not LookupError: a KeyError must stay exit 2.


def register(subparsers):
    parser = subparsers.add_parser('why', help='Explain from records why an item or refusal happened')
    parser.add_argument('target', nargs='+', help='an item, owner/repo#n, a target key, an event id or "last refusal"')
    parser.add_argument('--full', action='store_true', help='add event ids and evidence paths')
    parser.add_argument('--json', action='store_true',
                        help="print an item's live ticket and spec values and its steps as JSON")
    parser.set_defaults(func=run)


def level(root, full):
    return 'full' if full else workspace.verbosity(workspace.load_config(root), 'report')


def run(args):
    root = workspace.find_workspace()
    target = ' '.join(args.target)
    if args.json and (target == 'last refusal' or re.fullmatch(EVENT_ID, target)):
        print('wuwei why: --json reads an item; pass an item id', file=sys.stderr)
        return UNRUN
    try:
        if args.json:
            print(json.dumps(live(root, target, level(root, args.full))))
            return CLEAN
        if target == 'last refusal' or re.fullmatch(EVENT_ID, target):
            steps = refusal(root, target)
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
    path = workspace.day_dir(root) / 'events.jsonl'
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
    """#667: the item's values as recorded now (ticket, spec) and its steps."""
    from pathlib import Path
    from wuwei import specmode
    name, days = _days(root, name)
    day, data = days[-1]
    row = data['items'][name]
    config = workspace.load_config(root)
    markers = security.load(root)
    clean = lambda text: text if text is None else security.redact(redact(text), markers)
    spec = specmode.brief_line(config, name, row, Path(row['worktree']) if row.get('worktree') else None, True)
    return {'item': name, 'day': day.name,
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
                add('queued', f'queued: goal {row.get("goal", NOT)}, added by {payload.get("source", NOT)}',
                    rel(day / 'events.jsonl'))
            if kind == 'worktree.created' and payload.get('item') == name:
                add('worktree', f'worktree: branch {payload.get("branch", NOT)} from {payload.get("base", NOT)} '
                    f'at {str(payload.get("start", NOT))[:12]}')
            if kind == 'seat launched' and payload.get('item') == name:
                seat = data.get('seats', {}).get(payload.get('name'), {})
                if seat.get('planner_note'):  # #660: the planner's note around WUWEI's launch prompt
                    add('seat', f'seat {payload["name"]} ({seat.get("role")}): planner note: {seat["planner_note"]}',
                        rel(day / 'events.jsonl'))
                elif seat.get('role') == 'adhoc':
                    add('seat', f'seat {payload["name"]} ({seat.get("type")}, unbriefed): prompt: '
                        f'{seat.get("prompt", NOT)}', rel(day / 'events.jsonl'))
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
        groups['approved'].append((f'approved as: {row["approved_as"]}', None, [rel(day / 'events.jsonl')]))
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
    return steps + [(now, None, [rel(day / 'events.jsonl')])]


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
    return [(text, f'{day.name}:{number}', []) for text in lines]
