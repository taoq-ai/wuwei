"""Append an event through the shared writer."""

import json
import sys

from wuwei.exits import CLEAN, FINDINGS, DAMAGED
from wuwei.state import append_event


FREE_KINDS = frozenset({'note'})
EVENT_PRODUCERS = {
    **{f'draft.{action}': 'wuwei drafts and outward adapters'
       for action in ('created', 'sending', 'sent', 'failed', 'dropped')},
    'outward.ai_tells': 'the outward port and hook (wuwei.outward.humanize_lint)',
    'build.started': 'wuwei build next', 'gate.tiered': 'wuwei dispatch next', 'build.launched': 'wuwei build',
    'build.fix_opened': 'wuwei pr act or wuwei dispatch next',
    'build.checked': 'wuwei build check',
    'guard.would_refuse': 'wuwei hook (shadow mode)',
    'traces.noted': 'wuwei sweep', 'traces.unmatched': 'wuwei sweep',
    'inbox.redacted': 'the inbox store',
    'build.requested': 'wuwei dispatch discovery',
    'seat.usage': 'wuwei build, wuwei dispatch opinion or SubagentStop',
    'mcp.finding': 'wuwei mcp check', 'mcp.checked': 'wuwei mcp check',
    'mcp.decided': 'owner host MCP decision',
    'decision.replied': 'wuwei control plane poll_replies or wuwei listen',
    'decision.escalated': 'wuwei listen',
    'pr.changed': 'wuwei watch or wuwei listen', 'pr.notified': 'wuwei listen',
    'shepherd.dispatched': 'wuwei listen', 'shepherd.finished': 'wuwei listen',
    **{f'remote.{action}': 'wuwei listen' for action in ('pending', 'started', 'resumed', 'stopped', 'ignored', 'refused', 'confirmed')},
    'remote.acknowledged': 'owner host wuwei remote ack',
    'integrity': 'wuwei integrity check', 'integrity_failed': 'wuwei integrity check',
    'integrity_confirmation': 'owner host re-confirmation',
    'state.set': 'wuwei state set', 'state.transition': 'wuwei state transition',
    'state.recovered': 'owner host wuwei state recover',
    'state.import': 'wuwei plan approve', 'plan.approved': 'wuwei plan approve',
    'plan.added': 'wuwei plan add', 'plan.proposed': 'wuwei plan add',
    'plan.session': 'wuwei plan session', 'gate.asked': 'wuwei hook PostToolUse', 'brief written': 'wuwei brief',
    'session.seen': 'wuwei hook SessionStart, Stop and SubagentStop',
    'session.rotated': 'wuwei hook Stop',
    'item.claimed': 'wuwei worktree add',
    'seat launched': 'wuwei hook PreToolUse or wuwei dispatch opinion',
    'seat stopped': 'wuwei hook SubagentStop or wuwei dispatch opinion',
    'seat stood down': 'wuwei hook SubagentStop',
    'fast_checks.record': 'wuwei fast-checks', 'reply: acknowledged': 'wuwei reply',
    'reply: thread_posted': 'wuwei reply',
    'decision.decided': 'wuwei decision outcome or wuwei listen (two-way DM answer)', 'watch: sweep': 'wuwei sweep',
    'heartbeat: clock': 'wuwei watch',
    'decision.routed': 'wuwei decision route',
    'decision.reversed': 'wuwei decision outcome or wuwei listen (two-way DM answer)',
    'decision.digest': 'wuwei sweep',
    'scanner.finding': 'wuwei scanner or security recorder',
    'watch: clock': 'wuwei watch', 'listen: clock': 'wuwei listen', 'listen: wake': 'wuwei listen', 'pr.disposition': 'wuwei pr disposition',
    'pr.action': 'wuwei pr state', 'pr.action.done': 'wuwei pr act',
    'pr.reply.drafted': 'wuwei pr act', 'pr.action.decision': 'wuwei pr act',
    'pr.review_posted': 'wuwei pr ping', 'pr.raised': 'wuwei pr raise',
    'pr.claimed': 'wuwei pr claim',
    'pr.reviewers_selected': 'wuwei pr ping',
    'reviewer.unresolved': 'wuwei pr raise, ping or reviewers',
    'day.close_requested': 'wuwei close', 'build.parked': 'wuwei build',
    'gate.received': 'wuwei dispatch receive', 'discovery.requested': 'wuwei dispatch discovery',
    'discovery.intake': 'wuwei dispatch discovery',
    'tracker.call': 'wuwei tracker lifecycle',
    'brief.pack': 'wuwei brief pack', 'brief.answer': 'wuwei brief answer',
    'steward.notes': 'wuwei steward run', 'steward.run': 'wuwei steward run',
    'steward.due': 'wuwei hook PostToolUse',
    'steward.acknowledged': 'wuwei steward ack',
    'calibration.drift': 'wuwei steward run',
    'negotiation.loop': 'wuwei steward run or wuwei dispatch next',
    'negotiation.notified': 'wuwei listen', 'decision.waited': 'wuwei sweep',
    'doctor.fixed': 'owner host wuwei doctor --fix',
    'config.newer_template': 'wuwei hook PreToolUse',
    'memory.folded': 'owner host wuwei memory forget', 'memory.consolidated': 'wuwei consolidate',
    'docs.set': 'wuwei plan set or wuwei docs page',
    'docs.written': 'wuwei docs or wuwei drafts approve', 'docs.exempt': 'wuwei dispatch next',
}


def register(subparsers):
    parser = subparsers.add_parser('event', help='Append a timestamped day event')
    parser.add_argument('kind')
    parser.add_argument('payload', nargs='?', default='{}')
    parser.set_defaults(func=run)


def run(args):
    if not args.kind.strip():
        raise ValueError(f'event kind must be a nonempty string; {DAMAGED}')
    if args.kind not in FREE_KINDS:
        producer = EVENT_PRODUCERS.get(args.kind, 'its dedicated command')
        print(f'wuwei event: {args.kind}: reserved; written by {producer}; use another event kind; that producer writes this one', file=sys.stderr)
        return FINDINGS
    payload = json.loads(args.payload)
    append_event(args.kind, payload)
    return CLEAN
