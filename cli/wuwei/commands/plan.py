"""CLI for morning proposal and approval."""

import json
from pathlib import Path
import sys

from wuwei import goals, plan, state, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('plan', help='Propose or approve the morning plan')
    actions = parser.add_subparsers(dest='action', required=True)
    session = actions.add_parser('session', help='Register the planner session for wake delivery')
    actions.add_parser('template', help='Print valid lead JSON for this workspace')
    session.add_argument('session_id')
    session.add_argument('--take-over', action='store_true',
                         help='Hand the planner role over from the registered session')
    propose = actions.add_parser('propose')
    propose.add_argument('input', type=Path, help='Lead discovery JSON')
    propose.add_argument('--refill', type=int, help='Number of the exhausted-queue lead pass')
    gate = actions.add_parser('gate', help="Print the morning gate question as an AskUserQuestion widget; writes nothing")
    gate.add_argument('--import-yesterday', action='store_true',
                      help='The plan proposes carrying over unfinished prior-day items')
    approve = actions.add_parser('approve')
    approve.add_argument('--items', nargs='*', required=True)
    approve.add_argument('--goals-confirmed', action='store_true')
    approve.add_argument('--import-yesterday', action='store_true')
    approve.add_argument('--note', help="The owner's own words on the gate card; recorded on each approved "
                                        'item and quoted in its briefs as Approved as:')
    add = actions.add_parser('add', help='Admit an item after the morning gate: an item the owner names '
                                         "with --goal, or a seat's finding")
    add.add_argument('item')
    add.add_argument('--goal', help='Goal id for an item the owner names')
    add.add_argument('--size', type=float, help="Its size in the framework's unit (default 1)")
    add.add_argument('--title', help='Short title for the record (default: the item id)')
    add.add_argument('--ticket', help='Existing tracker ticket id when a tracker is set')
    add.add_argument('--from-finding', action='store_true',
                     help="Admit a seat's finding (wuwei next lists them) as a small item; its ticket comes later")
    add.add_argument('--note', help="The owner's own words naming the item; recorded once and quoted in "
                                    'its briefs as Approved as:')
    add.add_argument('--repo', help='Configured repository name; required when several are configured')
    add.add_argument('--track', default='SLICE', help='SLICE (default) or FULL')
    add.add_argument('--kind', default='build', choices=('build', 'review', 'measure'))
    add.add_argument('--pr', help='Existing PR for a review item')
    add.add_argument('--review-role', choices=('arch', 'quality', 'security', 'goal'))
    add.add_argument('--governed-by', help='The governing document: <path> or <path>#<heading>, relative to '
                                           'the repository; a directory names its spec.md')
    for flag in plan.FLAGS:
        add.add_argument('--' + flag.replace('_', '-'), action='store_true', help=f'Set the {flag} flag')
    for verb, text in (('carry', 'Carry an open item to tomorrow'), ('park', 'Park an open item')):
        command = actions.add_parser(verb, help=text)
        command.add_argument('item')
        command.add_argument('--reason', help='Why; recorded on the item on one line')
    done = actions.add_parser('done', help='Record work completed by the owner on an Owner step card')
    done.add_argument('item')
    done.add_argument('--reason', required=True, help='What the owner completed')
    actions.add_parser('resume', help="Resume a parked item on the owner's Yes on its Owner step card"
                       ).add_argument('item')
    assign = actions.add_parser('set', help="Record an item's value: spec=required|skipped, "
                                            'ticket=<id>, owner_merge=true|false or governed_by=<path>')
    assign.add_argument('item', help='The item id')
    assign.add_argument('assignment', help='spec=required|skipped, ticket=<id>, owner_merge=true|false or '
                                           'governed_by=<path>[#heading]')
    assign.add_argument('--reason', help='Why; required for spec=skipped')
    assign.add_argument('--pr', help='Existing PR when setting kind=review')
    assign.add_argument('--review-role', choices=('arch', 'quality', 'security', 'goal'))
    parser.set_defaults(func=run)


def candidate_template(goal, framework):
    components = ('value', 'time_criticality', 'risk_reduction', 'job_size') if framework == 'wsjf' else ('reach', 'impact', 'confidence', 'effort')
    score = ({'value': 5, 'time_criticality': 3, 'risk_reduction': 2, 'job_size': 2}
             if framework == 'wsjf' else
             {'reach': 10, 'impact': 1, 'confidence': 0.8, 'effort': 2})
    return {'id': 'EXAMPLE-1', 'goal': goal, 'evidence': 'Replace with source path',
            'scope': 'Replace with scope', 'overlap': 'none', 'track': 'SLICE',
            'flags': {'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False},
            'score': score, 'evidence_lines': {key: 'Replace with evidence' for key in components}}


def run(args):
    try:
        if args.action == 'template':
            root = workspace.find_workspace()
            text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
            goal = (next(iter(goals.parse(text))) if goals.defined(text) else
                    {'id': 'G-1', 'outcome': 'Replace with the outcome',
                     'measure': 'Replace with the measure', 'target': 'Replace with the target',
                     'date': workspace.now().date().isoformat(), 'priority': 1})
            framework = workspace.load_config(root)['prioritisation']['framework']
            from wuwei.dispatch import host
            print(json.dumps({'goals': [goal], 'cap': host(root, workspace.load_config(root))['cap'],
                'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 6},
                'sweep': {'manual': 'unmeasured: replace with discovery evidence'},
                'candidates': [candidate_template(goal if isinstance(goal, str) else goal['id'],
                                                  framework)]}, indent=2))
        elif args.action == 'session':
            plan.session(args.session_id, take_over=args.take_over)
        elif args.action == 'propose':
            source = sys.stdin.read() if str(args.input) == '-' else args.input.read_text(encoding='utf-8')
            print(plan.propose(json.loads(source), refill=getattr(args, 'refill', None)))
        elif args.action == 'gate':
            root = workspace.find_workspace()
            print(json.dumps([plan.gate_widget(root, import_yesterday=args.import_yesterday)], indent=2))
        elif args.action == 'add':
            print(json.dumps(plan.add(args.item, goal=args.goal, size=args.size,
                                      title=args.title, ticket=args.ticket, note=args.note,
                                      source='finding' if args.from_finding else None,
                                      repo=args.repo, track=args.track, governed_by=args.governed_by,
                                      kind=args.kind, pr=args.pr, review_role=args.review_role,
                                      flags=[flag for flag in plan.FLAGS if getattr(args, flag)])))
        elif args.action == 'set':
            key, _, value = args.assignment.partition('=')
            if key == 'spec':
                print(plan.set_spec(args.item, args.assignment, args.reason))
            elif key == 'owner_merge':
                print(plan.set_owner_merge(args.item, value))
            elif key == 'ticket':
                print(f'{args.item}: ticket {plan.set_ticket(args.item, value)}')
            elif key == 'governed_by':
                print(plan.set_governed_by(args.item, value))
            elif key == 'kind':
                print(plan.set_kind(args.item, value, pr=args.pr, review_role=args.review_role))
            else:
                raise ValueError(f'plan set: {args.assignment} is not a spec, ticket, owner_merge or governed_by '
                                 f'value; run bin/wuwei plan set {args.item} spec=required|skipped, '
                                 'ticket=<id>, owner_merge=true|false or governed_by=<path>. '
                                 'Pass --reason "<why>" with spec=skipped')
        elif args.action in ('carry', 'park'):
            outcome = {'carry': 'carried', 'park': 'parked'}[args.action]
            plan.dispose(args.item, outcome, args.reason)
            print(f'{outcome} {args.item}')
        elif args.action == 'resume':
            print(plan.resume(args.item))
        elif args.action == 'done':
            print(plan.done(args.item, args.reason))
        else:
            plan.approve(args.items, goals_confirmed=args.goals_confirmed,
                         import_yesterday=args.import_yesterday, note=args.note)
        return CLEAN
    except state.StateError as exc:
        print(f'wuwei plan: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei plan: {exc}', file=sys.stderr)
        return UNRUN
