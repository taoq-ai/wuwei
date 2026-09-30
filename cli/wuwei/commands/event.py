"""Append an event through the shared writer."""

import json
import sys

from wuwei.exits import CLEAN, FINDINGS
from wuwei.state import append_event


FREE_KINDS = frozenset({'note'})
EVENT_PRODUCERS = {
    **{f'draft.{action}': 'wuwei drafts and outward adapters'
       for action in ('created', 'sending', 'sent', 'failed', 'dropped')},
    'build.started': 'wuwei build next', 'build.launched': 'wuwei build',
    'build.fix_opened': 'wuwei pr act or wuwei dispatch next',
    'build.checked': 'wuwei build check',
    'build.requested': 'wuwei dispatch discovery',
    'seat.usage': 'wuwei build or SubagentStop',
    'mcp.finding': 'wuwei mcp check', 'mcp.checked': 'wuwei mcp check',
    'mcp.decided': 'owner host MCP decision',
    'integrity': 'wuwei integrity check', 'integrity_failed': 'wuwei integrity check',
    'integrity_confirmation': 'owner host re-confirmation',
    'state.set': 'wuwei state set', 'state.transition': 'wuwei state transition',
    'state.recovered': 'owner host wuwei state recover',
    'state.import': 'wuwei plan approve', 'plan.approved': 'wuwei plan approve',
    'plan.added': 'wuwei plan add', 'plan.proposed': 'wuwei plan add',
    'plan.session': 'wuwei plan session', 'brief written': 'wuwei brief',
    'session.seen': 'wuwei hook SessionStart, Stop and SubagentStop',
    'item.claimed': 'wuwei worktree add',
    'seat launched': 'wuwei hook PreToolUse',
    'seat stopped': 'wuwei hook SubagentStop',
    'seat stood down': 'wuwei hook SubagentStop',
    'fast_checks.record': 'wuwei fast-checks', 'reply: acknowledged': 'wuwei reply',
    'reply: thread_posted': 'wuwei reply',
    'decision.decided': 'wuwei decision outcome', 'watch: sweep': 'wuwei sweep',
    'decision.routed': 'wuwei decision route',
    'decision.reversed': 'wuwei decision outcome',
    'decision.digest': 'wuwei sweep',
    'scanner.finding': 'wuwei scanner or security recorder',
    'watch: clock': 'wuwei watch', 'pr.disposition': 'wuwei pr disposition',
    'pr.action': 'wuwei pr state', 'pr.action.done': 'wuwei pr act',
    'pr.reply.drafted': 'wuwei pr act', 'pr.action.decision': 'wuwei pr act',
    'pr.review_posted': 'wuwei pr ping', 'pr.raised': 'wuwei pr raise',
    'pr.claimed': 'wuwei pr claim',
    'pr.reviewers_selected': 'wuwei pr ping',
    'day.close_requested': 'wuwei close', 'build.parked': 'wuwei build',
    'gate.received': 'wuwei dispatch receive', 'discovery.requested': 'wuwei dispatch discovery',
    'discovery.intake': 'wuwei dispatch discovery',
    'tracker.call': 'wuwei tracker lifecycle',
    'brief.pack': 'wuwei brief pack', 'brief.answer': 'wuwei brief answer',
    'steward.notes': 'wuwei steward run', 'steward.run': 'wuwei steward run',
    'steward.due': 'wuwei hook PostToolUse',
    'steward.acknowledged': 'wuwei steward ack',
}


def register(subparsers):
    parser = subparsers.add_parser('event', help='Append a timestamped day event')
    parser.add_argument('kind')
    parser.add_argument('payload', nargs='?', default='{}')
    parser.set_defaults(func=run)


def run(args):
    if not args.kind.strip():
        raise ValueError('event kind must be a nonempty string')
    if args.kind not in FREE_KINDS:
        producer = EVENT_PRODUCERS.get(args.kind, 'its dedicated command')
        print(f'wuwei event: {args.kind}: reserved; written by {producer}', file=sys.stderr)
        return FINDINGS
    payload = json.loads(args.payload)
    append_event(args.kind, payload)
    return CLEAN
