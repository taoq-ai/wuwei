"""Pure attention classification for day events."""

from datetime import datetime


SILENT = ('item.progress', 'state.write', 'state.set', 'state.transition',
          'seat started', 'seat stopped', 'seat launched', 'brief written',
          'fast_checks.record', 'retro.captured', 'decision.two_way', 'merge.auto',
          'reply: acknowledged', 'hook.refusal')


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
        'Decisions' if kind.startswith('decision.') or kind in (
            'item.escalated', 'merge.policy_blocked', 'work.outside_goals') else 'Work')
    if kind == 'item.escalated':
        seats = state.get('seats', {}) if isinstance(state, dict) else {}
        if not isinstance(seats, dict):
            return 'nudge', lane
        blocking = any(isinstance(seat, dict) and seat.get('item') == payload.get('item')
                       and seat.get('status') == 'running' for seat in seats.values())
        return ('page' if blocking else 'nudge'), lane
    if kind in ('day.blocked', 'security.finding', 'base.red', 'dead_man.hit', 'budget.cap'):
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
    if kind in ('merge.policy_blocked', 'work.outside_goals'):
        return 'nudge', lane
    if kind in SILENT:
        return 'silent', lane
    return 'nudge', lane
