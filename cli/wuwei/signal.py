"""Pure attention classification for day events."""

from datetime import datetime


SILENT = ('item.progress', 'state.write', 'state.set', 'state.transition',
          'seat started', 'seat stopped', 'seat launched', 'brief written',
          'brief.pack', 'brief.answer', 'session.seen', 'item.claimed',
          'draft.sending', 'draft.sent', 'draft.dropped',
          'fast_checks.record', 'retro.captured', 'decision.two_way', 'merge.auto',
          'merge.observation', 'merge.metric', 'merge.intent', 'merge.completed', 'merge.red', 'merge.revert',
          'reply: acknowledged', 'reply: thread_posted', 'pr.raised', 'pr.claimed',
          'pr.reviewers_selected', 'pr.review_posted', 'hook.refusal', 'decision.decided',
          'decision.routed', 'decision.digest', 'decision.replied', 'mcp.decided',
          'seat.usage', 'build.iteration', 'build.fix_opened', 'pr.action.done',
          'pr.reply.drafted', 'pr.action.decision',
          'watch: clock', 'watch: heartbeat', 'watch: observation', 'session: compact',
          'session: wake-seen', 'plan.session', 'pr.disposition', 'day.close_requested',
          'gate.received', 'discovery.requested', 'discovery.intake',
          'plan.added', 'steward.run', 'steward.acknowledged', 'plan.approved', 'state.import',
          'build.started', 'build.launched', 'build.checked', 'verdict.rejected',
          'inbox.redacted')


def classify(event, state):
    """Return one (tier, lane) pair; malformed events demand a nudge."""
    if not isinstance(event, dict) or not isinstance(event.get('kind'), str):
        return 'nudge', 'Work'
    kind = event['kind']
    payload = event.get('payload', {})
    if not isinstance(payload, dict):
        return 'nudge', 'Work'
    if kind == 'state.transition' and payload.get('phase') == 'escalated':
        kind = 'item.escalated'
    lane = 'People' if kind.startswith('person.') else (
        'Decisions' if kind.startswith(('decision.', 'draft.')) or kind in (
            'item.escalated', 'merge.policy_blocked', 'work.outside_goals') else 'Work')
    if kind == 'mcp.finding':
        return ('page' if payload.get('severity') in ('high', 'critical') else 'nudge'), lane
    if kind == 'mcp.checked':
        return ('silent' if type(payload.get('exit')) is int and payload['exit'] == 0 else 'nudge'), lane
    if kind == 'tracker.call':
        return ('silent' if payload.get('exit') == 0
                or payload.get('reason') == 'tracker adapter is none' else 'nudge'), lane
    if kind == 'pr.action':
        tier = payload.get('tier')
        return (tier if tier in ('silent', 'nudge', 'page') else 'nudge'), lane
    if kind == 'item.escalated':
        seats = state.get('seats', {}) if isinstance(state, dict) else {}
        if not isinstance(seats, dict):
            return 'nudge', lane
        blocking = any(isinstance(seat, dict) and seat.get('item') == payload.get('item')
                       and seat.get('status') == 'running' for seat in seats.values())
        return ('page' if blocking else 'nudge'), lane
    if kind in ('day.blocked', 'security.finding', 'security.canary', 'security.honeytoken', 'scanner.finding', 'base.red', 'merge.breaker', 'dead_man.hit', 'budget.cap'):
        return 'page', lane
    if kind == 'decision.one_way':
        return ('page' if payload.get('blocking') is True else 'nudge'), lane
    if kind == 'person.ask':
        due = payload.get('due')
        try:
            deadline = datetime.fromisoformat(due)
            now = datetime.fromisoformat(state["now"])
            if deadline.tzinfo is None:
                return 'nudge', lane
            return ('page' if deadline <= now else 'nudge'), lane
        except (TypeError, ValueError, KeyError):
            return 'nudge', lane
    if kind == 'budget.usage':
        fraction = payload.get('fraction')
        if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and fraction >= 1:
            return 'page', lane
        if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and fraction < .8:
            return 'silent', lane
        return 'nudge', lane
    if kind == 'watch: sweep':
        counts = (payload.get('owed'), payload.get('unreadable'))
        return ('silent' if all(type(count) is int and count == 0 for count in counts)
                else 'nudge'), lane
    if kind in ('hook.warning', 'merge.policy_blocked', 'work.outside_goals',
                'build.parked', 'steward.due'):
        return 'nudge', lane
    if kind in SILENT:
        return 'silent', lane
    return 'nudge', lane
