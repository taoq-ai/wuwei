"""Planner turn-end PR anchor and explicit day-close guard."""

from pathlib import Path

from wuwei import closing, pr_actions, state, watch, workspace
from wuwei.guards import Guard
from wuwei.exits import DAMAGED, PAYLOAD


def check(payload):
    if payload.get('stop_hook_active') is True:
        return 0, ''
    try:
        if not isinstance(payload.get('cwd'), str) or not Path(payload['cwd']).is_absolute():
            raise ValueError(f'cwd must be absolute; {PAYLOAD}')
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
        data = state.read_state(root)
        requested = data.get('close_requested', False)
        if type(requested) is not bool:
            raise ValueError(f'invalid day-close request; {DAMAGED}')
        planners = [row['payload'].get('session_id') for row in
                    watch.records(workspace.day_dir(root) / 'events.jsonl')
                    if row['kind'] == 'plan.session']
        if data.get('planner_session_id') is not None:
            planners.append(data['planner_session_id'])
        if any(not isinstance(value, str) or not value.strip() for value in planners):
            raise ValueError(f'invalid planner session record; {DAMAGED}')
        if not planners and requested:
            raise ValueError('day close needs a registered planner session; register the planner with bin/wuwei plan session first')
        if payload.get('session_id') not in planners:
            return 0, ''
        if not (workspace.day_dir(root) / 'state.json').is_file():
            raise ValueError('day state missing for registered planner; run bin/wuwei state recover in a host terminal (the owner), or start the day with /wuwei:wuwei-plan')
        if type(payload.get('stop_hook_active', False)) is not bool:
            raise ValueError(f'stop_hook_active must be boolean; {PAYLOAD}')
        return closing.check(root) if requested else pr_actions.check(root)
    except watch.ERRORS as exc:
        return 2, f'Stop unmeasured: {exc}'


GUARDS = [Guard('Stop', None, check)]
