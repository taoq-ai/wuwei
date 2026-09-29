"""Append an event through the shared writer."""

import json
import sys

from wuwei.exits import CLEAN, FINDINGS
from wuwei.state import append_event


def register(subparsers):
    parser = subparsers.add_parser('event', help='Append a timestamped day event')
    parser.add_argument('kind')
    parser.add_argument('payload', nargs='?', default='{}')
    parser.set_defaults(func=run)


def run(args):
    if args.kind.startswith(('state.', 'decision.', 'watch:', 'session:',
                                   'security.', 'scanner.', 'pr.disposition',
                                   'day.close')) or args.kind in (
            'brief written', 'seat stood down', 'watch: sweep', 'reply: acknowledged',
            'hook.refusal', 'seat.usage', 'build.iteration', 'build.parked',
            'retro.captured', 'retro.gap', 'verdict.rejected', 'fast_checks.record',
            'plan.approved', 'plan.session', 'pr.changed'):
        print('wuwei event: event kind reserved for its dedicated writer', file=sys.stderr)
        return FINDINGS
    payload = json.loads(args.payload)
    append_event(args.kind, payload)
    return CLEAN
