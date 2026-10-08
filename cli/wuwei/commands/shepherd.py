"""Run the headless PR sweep, or schedule it as a user service (#511)."""

from argparse import Namespace
import json

from wuwei import decision, sessions, shepherd, workspace
from wuwei.commands import watch as service

QUESTION = ('Schedule the overnight shepherd on this machine? Every 15 minutes while no planner '
            'is live it checks approved PRs against the merge policy, sends due review pings '
            'under the outbound tiers and queues the rest for your morning plan. No model runs.')
RECORD = 'bin/wuwei shepherd schedule --yes'


def register(subparsers):
    parser = subparsers.add_parser('shepherd', help='Run the headless PR sweep; schedule installs it')
    actions = parser.add_subparsers(dest='shepherd_action')
    schedule = actions.add_parser('schedule', help='Install and start the user shepherd service')
    schedule.add_argument('--dry-run', action='store_true',
                          help='Print the unit path, unit and service commands without changing anything')
    schedule.add_argument('--yes', action='store_true',
                          help="Install now; a session runs this after the owner's answer on the Shepherd card")
    actions.add_parser('unschedule', help='Stop and remove the user shepherd service')
    parser.set_defaults(func=run)


def run(args):
    verb = args.shepherd_action
    dry_run = getattr(args, 'dry_run', False)
    if verb and not dry_run and sessions.current():
        root = workspace.find_workspace()
        if workspace.posture(workspace.load_config(root))[0] == 'strict':
            # #551: under strict a scheduled shepherd is the owner's to start or stop.
            print(json.dumps({'action': 'owner_terminal', 'command': f'bin/wuwei shepherd {verb}',
                              'why': 'a scheduled shepherd posts as you while no session runs; under strict you start or stop it',
                              'then': 'bin/wuwei doctor shows the shepherd row'}))
            return 1
        if verb == 'schedule' and not args.yes:
            # #548: the answer on the card is the confirmation; its record command installs.
            action = {'action': 'ask', 'command': RECORD, 'then': 'bin/wuwei doctor shows the shepherd row'}
            if (workspace.day_dir(root) / 'plan.md').is_file():
                action['widget'] = decision.widget(decision.gate(root) + QUESTION, 'Shepherd', [
                    ('Schedule (Recommended)', f'Claude runs {RECORD} and installs the user service.'),
                    ('Not now', 'The shepherd runs only while a planner is live.')], RECORD)
            print(json.dumps(action))
            return 0
    action = {'schedule': 'install', 'unschedule': 'uninstall'}.get(verb)
    return service.service(Namespace(shepherd_action=action, once=False, dry_run=dry_run), 'shepherd',
                           lambda once: shepherd.loop(once=once))
