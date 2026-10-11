"""Append an event through the shared writer."""

import json
import sys

from wuwei.exits import CLEAN, FINDINGS, DAMAGED
from wuwei.state import append_event


FREE_KINDS = frozenset({'note'})
EVENT_PRODUCERS = {
    'outward.ai_tells': 'the outward port and hook (wuwei.outward.humanize_lint)',
    'outward.lint': 'the outward port and hook (wuwei.outward.check_lint)',
    'outward.to_owner': 'the outward port and hook (wuwei.outward.to_owner)',
    'worktree.hooks_skipped': 'wuwei worktree add, wuwei worktree adopt or wuwei init --upgrade',
    'worktree.adopted': 'wuwei worktree adopt, wuwei worktree add --branch or wuwei pr claim',
    'worktree.created': 'wuwei worktree add',
    'build.started': 'wuwei build next', 'gate.tiered': 'wuwei dispatch next', 'gate.delta_head': 'wuwei dispatch next', 'build.launched': 'wuwei build',
    'build.fix_opened': 'wuwei pr act or wuwei dispatch next',
    'polish.skipped': 'wuwei dispatch skip-polish',
    'build.checked': 'wuwei build check', 'build.check_started': 'wuwei build check',
    **{f'spec.{kind}': 'wuwei hook, wuwei build or wuwei dispatch next' for kind in ('step', 'skipped', 'warned')},
    'spec.override': 'owner host wuwei plan set',
    'guard.would_refuse': 'wuwei hook (guards.enforce = false) or wuwei pr raise',
    'traces.noted': 'wuwei sweep', 'traces.unmatched': 'wuwei sweep',
    'build.requested': 'wuwei dispatch discovery',
    'seat.usage': 'wuwei build, wuwei dispatch opinion or SubagentStop',
    'pr.changed': 'wuwei watch',
    **{f'shepherd.{kind}': 'wuwei sweep obligations --headless or wuwei shepherd'
       for kind in ('overnight', 'swept')},
    'integrity': 'wuwei integrity check', 'integrity_failed': 'wuwei integrity check',
    'integrity_confirmation': 'owner host re-confirmation',
    'state.set': 'wuwei state set', 'state.transition': 'wuwei state transition',
    'state.recovered': 'owner host wuwei state recover',
    'state.import': 'wuwei plan approve', 'plan.approved': 'wuwei plan approve',
    'cap.derived': 'wuwei dispatch next --all',
    'plan.added': 'wuwei plan add', 'plan.proposed': 'wuwei plan add',
    'finding.noted': 'wuwei note --fix',
    'plan.session': 'wuwei plan session', 'gate.asked': 'wuwei hook PostToolUse', 'brief written': 'wuwei brief',
    'session.seen': 'wuwei hook SessionStart, Stop and SubagentStop',
    'session.rotated': 'wuwei hook Stop',
    'item.claimed': 'wuwei worktree add or wuwei worktree adopt',
    'seat launched': 'wuwei hook PreToolUse or wuwei dispatch opinion',
    'seat stopped': 'wuwei hook SubagentStop, wuwei dispatch opinion or owner wuwei seat stop',
    'traces.gap': 'wuwei hook PostToolUse',
    'traces.slow': 'wuwei hook PostToolUse',
    'seat stood down': 'wuwei hook SubagentStop',
    'seat adhoc': 'wuwei seat start', 'subagent.untraced': 'wuwei hook SubagentStop',
    'fast_checks.record': 'wuwei fast-checks', 'reply: acknowledged': 'wuwei pr act',
    'reply: thread_posted': 'wuwei pr act', 'watch: sweep': 'wuwei sweep',
    'heartbeat: clock': 'wuwei watch',
    'scanner.finding': 'wuwei scanner or security recorder',
    'watch: clock': 'wuwei watch', 'pr.disposition': 'wuwei pr disposition',
    'pr.action': 'wuwei pr state', 'pr.action.done': 'wuwei pr act',
    'pr.review_posted': 'wuwei pr ping', 'pr.raised': 'wuwei pr raise',
    'pr.claimed': 'wuwei pr claim',
    'pr.reviewers_selected': 'wuwei pr ping',
    'reviewer.unresolved': 'wuwei pr raise, ping or reviewers',
    'day.close_requested': 'wuwei close', 'day.closed': 'wuwei close', 'next.action': 'wuwei next',
    'build.parked': 'wuwei build', 'build.held': 'wuwei build', 'build.released': 'wuwei build',
    'gate.received': 'wuwei dispatch receive', 'discovery.requested': 'wuwei dispatch discovery',
    'discovery.intake': 'wuwei dispatch discovery',
    'tracker.call': 'wuwei tracker lifecycle',
    'tracker.created': 'wuwei tracker create or wuwei plan approve',
    'tracker.skipped': 'wuwei plan approve or add', 'tracker.folded': 'wuwei tracker log',
    'tracker.logged': 'wuwei tracker log', 'plan.set': 'wuwei plan set or wuwei init --upgrade',
    'steward.run': 'wuwei steward run',
    'calibration.drift': 'wuwei steward run',
    'plan.disposed': 'wuwei plan carry or park, wuwei dispatch next or wuwei build',
    'plan.resumed': 'wuwei plan resume',
    'doctor.fixed': 'owner host wuwei doctor --fix',
    'config.newer_template': 'wuwei hook PreToolUse',
    **{f'telemetry.{action}': 'wuwei telemetry or wuwei sweep'
       for action in ('skipped', 'unsent', 'shared', 'ready', 'off')},
    'docs.set': 'wuwei plan set or wuwei docs page',
    'docs.written': 'wuwei docs', 'docs.exempt': 'wuwei dispatch next',
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
