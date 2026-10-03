"""Morning proposal and dedicated gate approval producer."""

import json
from pathlib import Path
import re

from wuwei import discovery, dispatch, goals, rank, sessions, state, workspace


FLAGS = ('trust_surface', 'boundary_relevant', 'agent_surface')


def session(session_id, root=None, *, take_over=False):
    """Register the plan skill's session as today's single planner wake recipient."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError('planner session id must be a nonempty string')
    current = state.read_state(root).get('planner_session_id')
    previous = current if current not in (None, session_id) else None
    if previous and not take_over:
        raise ValueError(f'planner session {previous} is registered; to hand over, run from '
                         f'this session: wuwei plan session {session_id} --take-over')

    def update(data):
        if data.get('planner_session_id') != current:
            raise ValueError('planner changed during registration; retry')
        data['planner_session_id'] = session_id
        sessions.record(data, session_id, hook='plan session', cwd=str(Path.cwd()))

    return state._write_state(update, root, reserved=False, kind='plan.session',
                              payload={'session_id': session_id,
                                       **({'previous': previous} if previous else {})})


def _proposal(data, goals_text, framework="wsjf"):
    goal_list = goals.parse(goals_text)
    if not isinstance(data, dict):
        raise ValueError('proposal must be an object')
    for key in ('goals', 'candidates', 'seat_policy', 'envelope', 'sweep', 'cap'):
        if key not in data:
            raise ValueError(f'missing {key}')
    if (not isinstance(data['goals'], list) or not data['goals'] or
            any(not isinstance(goal, str) or not re.fullmatch(r'G-[1-9][0-9]*', goal)
                or goal not in goal_list for goal in data['goals'])):
        raise ValueError('goals must cite identifiers in memory/goals.md')
    if type(data['cap']) is not int or data['cap'] < 1:
        raise ValueError('cap must be a positive integer')
    if (not isinstance(data['seat_policy'], dict) or not data['seat_policy'] or
            any(not isinstance(role, str) or not isinstance(policy, dict) or
                not all(isinstance(policy.get(key), str) and policy[key].strip()
                        for key in ('runtime', 'model'))
                for role, policy in data['seat_policy'].items())):
        raise ValueError('seat_policy requires runtime and model per role')
    if (not isinstance(data['envelope'], dict) or
            not all(key in data['envelope'] for key in ('start', 'end', 'net_build_hours')) or
            type(data['envelope']['net_build_hours']) not in (int, float) or
            data['envelope']['net_build_hours'] < 0):
        raise ValueError('envelope requires start, end and net_build_hours')
    if (not isinstance(data['sweep'], dict) or not data['sweep'] or
            any(not isinstance(value, str) or not value.strip()
                for value in data['sweep'].values())):
        raise ValueError('sweep must report measured or unmeasured sources')
    if not isinstance(data['candidates'], list):
        raise ValueError('candidates must be a list')
    seen = set()
    for item in data['candidates']:
        if not isinstance(item, dict):
            raise ValueError('candidate must be an object')
        name = item.get('id')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in seen:
            raise ValueError('candidate id must be unique and safe')
        seen.add(name)
        for key in ('evidence', 'scope', 'overlap'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'{name}: {key} required')
        if item.get('goal', 'unplanned' if item.get('unplanned') is True else None) not in (*data['goals'], 'unplanned'):
            raise ValueError(f'{name}: goal must be confirmed or unplanned')
        rank.validate(item, framework, goal_list)
        if item.get('track') not in ('SLICE', 'FULL'):
            raise ValueError(f'{name}: track must be SLICE or FULL')
        if 'tier' in item and item['tier'] not in dispatch.TIERS:
            raise ValueError(f'{name}: tier must be light, standard or full')
        flags = item.get('flags')
        if not isinstance(flags, dict) or set(flags) != set(FLAGS) or any(type(v) is not bool for v in flags.values()):
            raise ValueError(f'{name}: flags must contain boolean trust_surface, boundary_relevant, agent_surface')
    json.dumps(data, allow_nan=False)
    return data


def propose(data, root=None):
    root = workspace.find_workspace() if root is None else Path(root)
    from wuwei import steward
    steward_finding = steward.previous_day_finding(root)
    goals_text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
    goal_list = goals.parse(goals_text)
    found = discovery.discover(root)
    day = workspace.day_dir(root)
    prior = sorted((path for path in (root / '.wuwei/days').glob('*')
                    if path.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.name)
                    and path.name < day.name), reverse=True)
    carried = []
    if prior:
        earlier = state.read_state(directory=prior[0])
        carried = [proposal['candidate'] for proposal in
                   earlier.get('intraday_proposals', {}).values()
                   if proposal.get('decision') == 'tomorrow']
    discovered_ids = {row['id'] for row in found['candidates']}
    found['candidates'].extend(row for row in carried if row['id'] not in discovered_ids)
    data = {**data, 'sweep': {**data.get('sweep', {}),
            **{f'discovery.{key}': value for key, value in found['sources'].items()}},
            'discovered': found['candidates']}
    framework = workspace.load_config(root)['prioritisation']['framework']
    data = _proposal(data, goals_text, framework)
    from wuwei import mcp
    measured = mcp.check(root)
    gate = mcp.cached(root)  # The posture decides refusal; the sweep shows the measurement.
    if gate.exit:
        raise (state.StateError if gate.exit == 1 else OSError)(gate.reason)
    data['sweep']['mcp'] = measured.reason or 'MCP registry: no attached servers'
    data['candidates'] = rank.rank(data['candidates'], framework, goal_list)
    directory = workspace.day_dir(root)
    if (directory / 'state.json').exists() and state.read_state(root).get('gate_approved'):
        raise state.StateError('morning gate already approved')
    lines = ['# Morning plan', '', 'Status: PROPOSED', '',
             *(['Finding: ' + steward_finding, ''] if steward_finding else []),
             '## Goals to confirm', *[f'- {goal}' for goal in data['goals']], '',
             '## Measured sweep', *[f'- {key}: {value}' for key, value in data['sweep'].items()], '',
             '## Proposed queue']
    for number, item in enumerate(data['candidates'], 1):
        lines += [f'### {number}. {item["id"]} ({item["track"]})',
                  f'Goal: {item.get("goal", "unplanned")}', f'Evidence: {item["evidence"]}',
                  f'Scope: {item["scope"]}', f'Overlap: {item["overlap"]}',
                  'Flags: ' + ', '.join(key for key in FLAGS if item['flags'][key]) if any(item['flags'].values()) else 'Flags: none', '']
    lines += ['## Discovery intake',
              *[f'- {item["id"]}: {item.get("evidence", "evidence pending")}' for item in data['discovered']], '',
              '## Gate proposal', f'CAP: {data["cap"]}',
              'Seat policy: ' + json.dumps(data['seat_policy'], sort_keys=True),
              'Envelope: ' + json.dumps(data['envelope'], sort_keys=True), '']
    directory.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(directory / 'proposal.json', json.dumps(data, allow_nan=False, indent=2) + '\n')
    path = directory / 'plan.md'
    workspace.atomic_write(path, '\n'.join(lines))
    return path


def approve(items, root=None, *, goals_confirmed=False, import_yesterday=False):
    root = workspace.find_workspace() if root is None else Path(root)
    directory = workspace.day_dir(root)
    if not goals_confirmed:
        raise state.StateError('goals must be confirmed at the morning gate')
    if not (directory / 'plan.md').is_file():
        raise state.StateError('today\'s plan.md is missing')
    proposal_path = directory / 'proposal.json'
    if proposal_path.is_symlink() or (directory / 'plan.md').is_symlink():
        raise ValueError('plan files must not be symlinks')
    framework = workspace.load_config(root)['prioritisation']['framework']
    data = _proposal(json.loads(proposal_path.read_text(encoding='utf-8')),
                     (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'),
                     framework)
    if not isinstance(items, list) or len(items) != len(set(items)):
        raise ValueError('approved items must be a unique list')
    candidates = {item['id']: item for item in data['candidates']}
    if any(name not in candidates for name in items):
        raise state.StateError('approved item is absent from proposal')
    imported = {}
    if import_yesterday:
        days = root / '.wuwei/days'
        prior = sorted((path for path in days.iterdir() if path.is_dir() and
                        path.name < directory.name and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.name)),
                       reverse=True)
        if not prior or not (prior[0] / 'state.json').is_file():
            raise ValueError('no prior day state to import')
        imported = {name: {**item, 'phase': 'planned', 'status': 'queued', 'gates': {}}
                    for name, item in state.read_state(directory=prior[0])['items'].items()
                    if item['phase'] != 'merged' and item['status'] != 'done'}
        for item in imported.values():
            item.pop('resume_phase', None)
        if set(imported) & set(items):
            raise state.StateError('imported and approved item ids overlap')

    def update(current):
        if current.get('gate_approved'):
            raise state.StateError('morning gate already approved')
        if set(current['items']) & (set(imported) | set(items)):
            raise state.StateError('day item already exists')
        current['items'].update(imported)
        current['items'].update({name: {'goal': candidates[name].get('goal', 'unplanned'),
                                       'track': candidates[name]['track'],
                                       'flags': candidates[name]['flags'],
                                       'budget_size': candidates[name]['score'][
                                           'job_size' if framework == 'wsjf' else 'effort'],
                                       **{key: candidates[name][key] for key in ('tier',)
                                          if key in candidates[name]}}
                                 for name in items})
        current.update(cap=data['cap'], seat_policy=data['seat_policy'],
                       envelope=data['envelope'], goals=data['goals'],
                       approved_items=items, gate_approved=True)

    kind = 'state.import' if import_yesterday else 'plan.approved'
    return state._write_state(update, root, reserved=False, kind=kind,
                              payload={'items': sorted(imported) if import_yesterday else items,
                                       'approved_items': items,
                                       'flags': {name: candidates[name]['flags'] for name in items}})


def add(item, root=None):
    """Apply the intraday policy to one discovered candidate after the gate."""
    root = workspace.find_workspace(root)
    day = state.read_state(root)
    if not day['gate_approved']:
        raise state.StateError('morning gate has not been approved')
    candidate = day.get('discovery_candidates', {}).get(item)
    if candidate is None:
        raise state.StateError(f'unknown discovery candidate {item}')
    config = workspace.load_config(root)
    goals_text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
    _proposal({'goals': day['goals'], 'cap': day['cap'],
               'seat_policy': day['seat_policy'], 'envelope': day['envelope'],
               'sweep': {'discovery': 'measured: candidate'},
               'candidates': [candidate]}, goals_text,
              config['prioritisation']['framework'])
    size_key = 'job_size' if config['prioritisation']['framework'] == 'wsjf' else 'effort'
    size = candidate['score'][size_key]
    committed = sum(row.get('budget_size', float('inf')) for row in day['items'].values())
    within_budget = committed + size <= day['envelope']['net_build_hours']
    running = sum(seat.get('status') == 'running' and seat.get('role') == 'builder'
                  for seat in day['seats'].values())
    within_cap = running < day['cap']
    above_cut = True
    if config['discovery']['autostart'] == 'strict' and day['approved_items']:
        proposal_path = workspace.day_dir(root) / 'proposal.json'
        if proposal_path.is_symlink():
            raise ValueError('proposal.json must not be a symlink')
        proposal = json.loads(proposal_path.read_text(encoding='utf-8'))
        approved = [row for row in proposal['candidates']
                    if row['id'] in day['approved_items']]
        if approved:
            ordered = rank.rank([*approved, candidate], config['prioritisation']['framework'],
                                goals.parse(goals_text))
            above_cut = [row['id'] for row in ordered].index(item) < len(approved)
    decision = discovery.start_decision(candidate, config, set(day['goals']),
                                        within_budget=within_budget and within_cap,
                                        above_cut=above_cut)
    if decision != 'start':
        def propose(current):
            if item in current['items']:
                raise state.StateError(f'item {item} is already in the plan')
            current.setdefault('intraday_proposals', {})[item] = {
                'decision': decision, 'candidate': candidate}
        state._write_state(propose, root, reserved=False, kind='plan.proposed',
                           payload={'item': item, 'decision': decision})
        return {'action': decision, 'item': item}

    def admit(current):
        if item in current['items']:
            raise state.StateError(f'item {item} is already in the plan')
        current['items'][item] = {'goal': candidate['goal'], 'track': candidate['track'],
                                  'flags': candidate['flags'], 'budget_size': size,
                                  **{key: candidate[key] for key in ('tier',) if key in candidate}}
        current['approved_items'].append(item)
    state._write_state(admit, root, reserved=False, kind='plan.added',
                       payload={'item': item})
    return {'action': 'build next', 'item': item}
