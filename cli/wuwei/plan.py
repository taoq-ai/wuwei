"""Morning proposal and dedicated gate approval producer."""

import json
import os
from pathlib import Path
import re
import sys

from wuwei import discovery, dispatch, goals, rank, sessions, state, workspace
from wuwei.exits import PAYLOAD, PLAN_JSON, SYMLINK


FLAGS = ('trust_surface', 'boundary_relevant', 'agent_surface')
TICKET = r'[A-Za-z0-9][A-Za-z0-9._/#-]{0,99}'  # ENG-1, PROJ-12, owner/repo#12


def session(session_id, root=None, *, take_over=False):
    """Register the plan skill's session as today's single planner wake recipient."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError(f'planner session id must be a nonempty string; {PAYLOAD}')
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
        raise ValueError(f'proposal must be an object; {PLAN_JSON}')
    for key in ('goals', 'candidates', 'seat_policy', 'envelope', 'sweep', 'cap'):
        if key not in data:
            raise ValueError(f'missing {key}; {PLAN_JSON}')
    if (not isinstance(data['goals'], list) or not data['goals'] or
            any(not isinstance(goal, str) or not re.fullmatch(r'G-[1-9][0-9]*', goal)
                or goal not in goal_list for goal in data['goals'])):
        raise ValueError(f'goals must cite identifiers in memory/goals.md; {PLAN_JSON}')
    if type(data['cap']) is not int or data['cap'] < 1:
        raise ValueError(f'cap must be a positive integer; {PLAN_JSON}')
    if (not isinstance(data['seat_policy'], dict) or not data['seat_policy'] or
            any(not isinstance(role, str) or not isinstance(policy, dict) or
                not all(isinstance(policy.get(key), str) and policy[key].strip()
                        for key in ('runtime', 'model'))
                for role, policy in data['seat_policy'].items())):
        raise ValueError(f'seat_policy requires runtime and model per role; {PLAN_JSON}')
    if (not isinstance(data['envelope'], dict) or
            not all(key in data['envelope'] for key in ('start', 'end', 'net_build_hours')) or
            type(data['envelope']['net_build_hours']) not in (int, float) or
            data['envelope']['net_build_hours'] < 0):
        raise ValueError(f'envelope requires start, end and net_build_hours; {PLAN_JSON}')
    if (not isinstance(data['sweep'], dict) or not data['sweep'] or
            any(not isinstance(value, str) or not value.strip()
                for value in data['sweep'].values())):
        raise ValueError(f'sweep must report measured or unmeasured sources; {PLAN_JSON}')
    if not isinstance(data['candidates'], list):
        raise ValueError(f'candidates must be a list; {PLAN_JSON}')
    seats = data.get('seats', {})
    if (not isinstance(seats, dict)
            or any(goal not in (*data['goals'], 'unplanned') or type(count) is not int or count < 1
                   for goal, count in seats.items())
            or sum(seats.values()) > data['cap']):
        raise ValueError(f'seats must map confirmed goals to seat counts within cap; {PLAN_JSON}')
    seen = set()
    for item in data['candidates']:
        if not isinstance(item, dict):
            raise ValueError(f'candidate must be an object; {PLAN_JSON}')
        name = item.get('id')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in seen:
            raise ValueError(f'candidate id must be unique and safe; {PLAN_JSON}')
        seen.add(name)
        for key in ('evidence', 'scope', 'overlap'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'{name}: {key} required; {PLAN_JSON}')
        if item.get('goal', 'unplanned' if item.get('unplanned') is True else None) not in (*data['goals'], 'unplanned'):
            raise ValueError(f'{name}: goal must be confirmed or unplanned; {PLAN_JSON}')
        rank.validate(item, framework, goal_list)
        if item.get('track') not in ('SLICE', 'FULL'):
            raise ValueError(f'{name}: track must be SLICE or FULL; {PLAN_JSON}')
        if 'tier' in item and item['tier'] not in dispatch.TIERS:
            raise ValueError(f'{name}: tier must be light, standard or full; {PLAN_JSON}')
        if item.get('ticket') is not None and not (isinstance(item['ticket'], str) and re.fullmatch(
                TICKET, item['ticket'])):  # #636: null is the owner's none
            raise ValueError(f'{name}: invalid ticket; {PLAN_JSON}')
        flags = item.get('flags')
        if not isinstance(flags, dict) or set(flags) != set(FLAGS) or any(type(v) is not bool for v in flags.values()):
            raise ValueError(f'{name}: flags must contain boolean trust_surface, boundary_relevant, agent_surface; {PLAN_JSON}')
        # #478, #518: owner-only steps the gate pre-approves. An entry the CLI does not
        # understand is a warning on the plan, never a refusal before the gate.
        if not isinstance(item.get('owner_actions', []), list):
            raise ValueError(f'{name}: owner_actions must be a list; {PLAN_JSON}')
        paths = item.get('paths', [])  # #579: the files it touches; guard paths advise careful
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ValueError(f'{name}: paths must be a list of strings; {PLAN_JSON}')
    json.dumps(data, allow_nan=False)
    return data


def owner_steps(item):
    """#518: plan lines for owner actions that are not grant cards: known owner steps (message,
    secret-set) and entries the CLI does not understand, which the gate asks as written."""
    from wuwei import grants
    lines = []
    for entry in item.get('owner_actions', []):
        reason = grants.understood(entry)
        if reason:
            lines.append(f'Owner-only: {json.dumps(entry, sort_keys=True)} (not understood: {reason}; '
                         'the gate asks for it as written)')
        elif entry['action'] not in grants.ACTIONS:
            lines.append(f'Owner-only: {entry["action"]} {entry["target"]} (owner step)')
    return lines


def tracked(data):
    """The ids discovery found in the tracker: each is its own ticket."""
    return {row.get('id') for row in data.get('discovered', []) if isinstance(row, dict)
            and row.get('source') == 'tracker'}


def proposed(row, found=()):
    """#636: the ticket record a candidate carries: its ticket field (None is the owner's
    none), its own id when discovered from the tracker, or None for a new ticket."""
    if 'ticket' in row:
        return {'id': row['ticket'], 'source': 'candidate' if row['ticket'] else 'none'}
    if row['id'] in found or row.get('source') == 'tracker':
        return {'id': row['id'], 'source': 'tracker'}
    return None


def _skipped(name, row):
    """The tracker.skipped payload: the owner's none, else the skipped tier."""
    return ({'item': name, 'ticket': 'none'} if 'ticket' in row and row['ticket'] is None
            else {'item': name, 'tier': row['tier']})


def _tickets(config, data):
    """#636: {item: '<id> (existing)' | 'new <title>' | 'none'} for the plan and the gate card."""
    from wuwei import tracker
    if not tracker.in_force(config):
        return {}
    found, texts = tracked(data), {}
    for row in data['candidates']:
        if row.get('tier') in config['tracker']['skip_tiers']:
            continue
        record = proposed(row, found)
        texts[row['id']] = ('new ' + ' '.join(row['scope'].split()) if record is None else
                            'none' if record['id'] is None else f'{record["id"]} (existing)')
    return texts


def goal_seats(candidates, cap):
    """{goal: seats}: the first cap ranked candidates counted per goal, in queue order."""
    from collections import Counter
    return dict(Counter(item.get('goal', 'unplanned') for item in candidates[:cap]))


def seats_text(seats, cap):
    total = sum(seats.values())
    return (f'{total} seats: ' + ', '.join(f'{goal} {count}' for goal, count in seats.items())
            if seats else '0 seats') + f' (CAP {cap})'


def _seats(data):
    return data.get('seats') or goal_seats(data['candidates'], data['cap'])


def _owner_prs(config, root, candidates):
    """#510: the owner's open PRs in the configured repositories, as rows the gate claims."""
    from wuwei import registry
    logins = {login.casefold() for login in (*config['owner']['handles'],
                                             config['outbound']['owner']['code_host']) if login}
    if not config['repos'] or not logins:
        return [], 'unmeasured: no configured repository or owner.handles'
    host = registry.load('code_host', config)
    taken, rows = {item['id'] for item in candidates}, []
    for repo in config['repos']:
        result = host.open_prs(repo['name'], root=root)
        if result.exit:
            return [], f'unmeasured: {result.reason}'
        # #603: with several repositories the id names the repository, so one number gives two ids.
        prefix = f'PR-{repo["name"].rsplit("/", 1)[-1]}-' if len(config['repos']) > 1 else 'PR-'
        for pr in result.data:
            ident = f'{prefix}{pr["number"]}'
            if (pr['author'] or '').casefold() in logins and ident not in taken:
                rows.append({'id': ident, 'pr': f'{repo["name"]}#{pr["number"]}', 'title': pr['title']})
    return rows, f'measured: {len(rows)} open PR{"" if len(rows) == 1 else "s"} by the owner'


def propose(data, root=None):
    root = workspace.find_workspace() if root is None else Path(root)
    from wuwei import steward
    steward_finding = steward.previous_day_finding(root)
    goals_text, provisional = goals.proposed(
        (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'),
        data.get('goals') if isinstance(data, dict) else None)
    goal_list = goals.parse(goals_text)
    if provisional:
        data = {**data, 'goals': list(goal_list)}
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
    config = workspace.load_config(root)
    from wuwei import calibrate
    limits = calibrate.host(root, config)  # #528: CAP derives; the lead's cap is not used
    data = {**data, 'cap': limits['cap'],
            'capacity': {key: limits[key] for key in ('bound', 'text', 'seats')}}
    framework = config['prioritisation']['framework']
    data = _proposal(data, goals_text, framework)
    from wuwei import mcp
    measured = mcp.check(root)
    gate = mcp.cached(root)  # The posture decides refusal; the sweep shows the measurement.
    if gate.exit:
        raise (state.StateError if gate.exit == 1 else OSError)(gate.reason)
    if measured.exit or measured.reason == mcp.NO_SCANNER:  # #351, #424: printed, not only filed.
        print(measured.reason, file=sys.stderr)
    data['sweep']['mcp'] = measured.reason or gate.reason or 'MCP registry: no attached servers'
    from wuwei.commands.doctor import pr_flow
    warned = [row['name'] for row in pr_flow(workspace.load_config(root)) if row['status'] != 'ok']
    data['sweep']['pr-flow'] = (f"measured: {len(warned)} warn ({', '.join(warned)}); "
                                'wuwei doctor --section pr-flow' if warned else 'measured: ok')
    data['candidates'] = rank.rank(data['candidates'], framework, goal_list)
    names = [repo['name'] for repo in config['repos']] if len(config['repos']) > 1 else []
    for item in data['candidates'] if names else ():  # #603: worktree add needs --repo here
        if item.get('repo') not in names:
            item.pop('repo', None)
            found = [repo['name'] for repo in config['repos'] if any(
                (root / Path(repo['path']).expanduser() / path).exists() for path in item.get('paths', []))]
            if len(found) == 1:
                item['repo'] = found[0]
    data['seats'] = _seats(data)
    data['adopt'], data['sweep']['open-prs'] = _owner_prs(config, root, data['candidates'])
    from wuwei import pace  # #579: the recommended pace, its reasoning and the binding input
    advice = pace.advise(root, config, data, goal_list, limits, workspace.now())
    data.update(pace=advice['pace'], pace_reasoning=advice['lines'], pace_advice=advice)
    directory = workspace.day_dir(root)
    if (directory / 'state.json').exists() and state.read_state(root).get('gate_approved'):
        raise state.StateError('morning gate already approved; run bin/wuwei plan add <item> to admit a new item, or bin/wuwei status for the approved plan')
    from wuwei import grants, shepherd
    planned = grants.plan(root, workspace.load_config(root), data['candidates'])
    from wuwei import cruise
    cruise.propose(root, workspace.load_config(root))  # #283: raise and weekly sample cards
    pace.propose_default(root, workspace.load_config(root))  # #579: once ten days ran two paces
    lines = ['# Morning plan', '', 'Status: PROPOSED', '',
             *(['Finding: ' + steward_finding, ''] if steward_finding else []),
             *(shepherd.overnight_lines(swept) if (swept := shepherd.owning_day(root, day.name)) else []),  # #511
             '## Goals to confirm',
             *([f'Provisional: proposed by the lead; the planner records days/{directory.name}/'
                'goals.md on approval.'] if provisional else []),
             *[line for goal in data['goals'] for line in (
                 [f'- {goal} (provisional)', *(f'  {key}: {goal_list[goal][key]}'
                                               for key in goals.FIELDS)]
                 if provisional else [f'- {goal}'])], '',
             '## Measured sweep', *[f'- {key}: {value}' for key, value in data['sweep'].items()], '',
             '## Proposed queue']
    shown = _tickets(config, data)
    for number, item in enumerate(data['candidates'], 1):
        lines += [f'### {number}. {item["id"]} ({item["track"]})',
                  f'Goal: {item.get("goal", "unplanned")}', f'Evidence: {item["evidence"]}',
                  f'Scope: {item["scope"]}', f'Overlap: {item["overlap"]}',
                  *([f'Repository: {item["repo"]}' if 'repo' in item else
                     f'Repository: not named; the lead adds "repo": one of {", ".join(names)} (the paths '
                     'match none or several), then the planner runs wuwei plan propose again'] if names else []),
                  'Flags: ' + ', '.join(key for key in FLAGS if item['flags'][key]) if any(item['flags'].values()) else 'Flags: none',
                  *([f'Ticket: {shown[item["id"]]}'] if item['id'] in shown else []),
                  *(f'Owner-only: {name} {target} ({key})' for name, target, key in planned.get(item['id'], [])),
                  *owner_steps(item), '']
    lines += ['## Discovery intake',
              *[f'- {item["id"]}: {item.get("evidence", "evidence pending")}' for item in data['discovered']], '',
              *(['## Open PRs to claim', *(f'- {row["id"]}: {row["pr"]} {row["title"]} (claimed under '
                                           f'{data["goals"][0]})' for row in data['adopt']), '']
                if data['adopt'] else []),
              '## Gate proposal', f'CAP: {data["capacity"]["text"]}; host.seats {data["capacity"]["seats"]}',
              'Seats per goal: ' + seats_text(data['seats'], data['cap']),
              'Seat policy: ' + json.dumps(data['seat_policy'], sort_keys=True),
              'Envelope: ' + json.dumps(data['envelope'], sort_keys=True),
              f'Pace: {data["pace"]} (recommended)', *data['pace_reasoning'], '']
    directory.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(directory / 'proposal.json', json.dumps(data, allow_nan=False, indent=2) + '\n')
    if provisional:
        workspace.atomic_write(directory / 'goals.md', goals_text)
    else:
        (directory / 'goals.md').unlink(missing_ok=True)
    path = directory / 'plan.md'
    workspace.atomic_write(path, '\n'.join(lines))
    return path


def gate_widget(root=None, *, import_yesterday=False):
    """The one morning gate question for today's proposal and the command that approves it."""
    from wuwei import decision
    root = workspace.find_workspace() if root is None else Path(root)
    directory = workspace.day_dir(root)
    data = json.loads((directory / 'proposal.json').read_text(encoding='utf-8'))
    draft = directory / 'goals.md'  # propose writes it only for provisional goals
    provisional = goals.parse(draft.read_text(encoding='utf-8')) if draft.is_file() else None
    adopt = data.get('adopt', [])
    ids = [item['id'] for item in data['candidates']] + [row['id'] for row in adopt]
    shown = _tickets(workspace.load_config(root), data)  # #636: Approve opens the new ones
    approves = '. '.join(part[:1].upper() + part[1:] for part in [
        'Goals ' + ', '.join(f'{goal} ({provisional[goal]["outcome"]})' if provisional else goal
                             for goal in data['goals']),
        'queue ' + (', '.join(item['id'] for item in data['candidates']) or 'empty'),
        *(['tickets ' + ', '.join(f'{name} {text}' for name, text in shown.items())] if shown else []),
        *(['claims ' + ', '.join(f'{row["id"]} ({row["pr"]})' for row in adopt)] if adopt else []),
        seats_text(_seats(data), data['cap']),
        *([data['capacity']['text']] if 'capacity' in data else []),
        'seat policy ' + json.dumps(data['seat_policy'], sort_keys=True),
        'envelope ' + json.dumps(data['envelope'], sort_keys=True),
        *(['carry-over of unfinished prior-day items'] if import_yesterday else [])])
    from wuwei import pace
    advised = data.get('pace')  # #579: the pace is option rows on the one card, advice first
    paces = [('Approve', f'{approves}. Pace {advised}. ' + ' '.join(data.get('pace_reasoning', [])))] + [
        (f'Approve at {other}', f'{approves}. Pace {other}.') for other in pace.PACES if other != advised]
    return decision.widget(
        decision.gate(root) + "Approve today's plan as proposed?",
        'Goals' if provisional else 'Plan',
        [*(paces if advised else [('Approve', approves + '.')]),
         ('Change something', 'Ask the separate questions on goals, queue, tickets, seat policy, '
                              'CAP and seats per goal, envelope and carry-over. CAP is derived. '
                              'A changed CAP is recorded as config cap. Name any item you merge '
                              'yourself; the planner records it with wuwei plan set <item> owner_merge=true.')],
        ' '.join(['wuwei plan approve --items', *ids, '--goals-confirmed',
                  *(['--import-yesterday'] if import_yesterday else []),
                  *(['--pace "<label>"'] if advised else [])]))


def approve(items, root=None, *, goals_confirmed=False, import_yesterday=False, pace_label=None):
    root = workspace.find_workspace() if root is None else Path(root)
    directory = workspace.day_dir(root)
    if not goals_confirmed:
        raise state.StateError('goals must be confirmed at the morning gate; confirm the goals at the morning gate (/wuwei:wuwei-plan), then pass --goals-confirmed')
    if not (directory / 'plan.md').is_file():
        raise state.StateError('No plan for today yet, so there is nothing to approve; run '
                               '/wuwei:wuwei-plan (or bin/wuwei plan propose) first.')
    proposal_path = directory / 'proposal.json'
    if proposal_path.is_symlink() or (directory / 'plan.md').is_symlink():
        raise ValueError(f'plan files must not be symlinks; {SYMLINK}')
    config = workspace.load_config(root)
    framework = config['prioritisation']['framework']
    text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
    if not goals.defined(text) and (directory / 'goals.md').is_file():
        text = (directory / 'goals.md').read_text(encoding='utf-8')  # #603: the provisional goals the gate card showed
    data = _proposal(json.loads(proposal_path.read_text(encoding='utf-8')), text, framework)
    if not isinstance(items, list) or len(items) != len(set(items)):
        raise ValueError(f'approved items must be a unique list; {PLAN_JSON}')
    from wuwei import pace  # #579: the owner's pick on the gate card, recorded as given
    wish = config['pace']['default']
    recommended = data.get('pace') or wish
    chosen = recommended if pace_label is None else pace.label(pace_label, recommended)
    adopted = {row['id']: row for row in data.get('adopt', [])}  # #510: claimed after the gate
    claims, items = [name for name in items if name in adopted], [name for name in items if name not in adopted]
    candidates = {item['id']: item for item in data['candidates']}
    if any(name not in candidates for name in items):
        raise state.StateError('approved item is absent from proposal; approve only ids from the proposal (bin/wuwei status lists them), or run bin/wuwei plan propose again')
    from wuwei import tracker
    imported, carried = {}, {}
    found, skipped = tracked(data), []
    if import_yesterday:
        days = root / '.wuwei/days'
        prior = sorted((path for path in days.iterdir() if path.is_dir() and
                        path.name < directory.name and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.name)),
                       reverse=True)
        if not prior or not (prior[0] / 'state.json').is_file():
            raise ValueError('no prior day state to import; run bin/wuwei plan approve without --import-yesterday')
        earlier = state.read_state(directory=prior[0])
        imported = {name: {**item, 'phase': 'planned', 'status': 'queued', 'gates': {}}
                    for name, item in earlier['items'].items()
                    if item['phase'] != 'merged' and item['status'] != 'done'}
        carried = {name: {'id': tracker.ticket(earlier, name), 'source': 'yesterday'}
                   for name in imported if tracker.ticket(earlier, name)}
        for item in imported.values():
            item.pop('resume_phase', None)
        if set(imported) & set(items):
            raise state.StateError('imported and approved item ids overlap; remove the overlapping ids from --items, or run without --import-yesterday')
    current, reasons = state.read_state(root), []
    if (tracker.in_force(config) and workspace.posture(config)[0] != 'strict'
            and not current.get('gate_approved')):
        from wuwei import drafts
        for name in items:  # #636: the Approve answer listed these new tickets; it is their Send
            if (proposed(candidates[name], found) is not None
                    or tracker.check(current, config, name, candidates[name])[0] != 'missing'):
                continue
            result = tracker.create(root, name)
            if result.exit == 1 and isinstance(result.data, dict) and result.data.get('draft'):
                result = drafts.approve(root, result.data['draft'])
            if result.exit:
                reasons.append(f'{name}: {result.reason}')
    if reasons:
        raise state.StateError('\n'.join(reasons))

    def update(current):
        if current.get('gate_approved'):
            raise state.StateError('morning gate already approved; run bin/wuwei plan add <item> to admit a new item')
        if set(current['items']) & (set(imported) | set(items)):
            raise state.StateError('day item already exists; remove the existing ids from --items (bin/wuwei status lists them)')
        tickets = {**current.get('tickets', {}), **carried}
        for name in items:
            if name not in tickets and (record := proposed(candidates[name], found)):
                tickets[name] = record
        if tickets:
            current['tickets'] = tickets
        reasons = []
        for name in items:
            status, reason = tracker.check(current, config, name, candidates[name])
            if status == 'missing':
                reasons.append(reason)
            elif status == 'skipped':
                skipped.append(name)
        if reasons:
            raise state.StateError('\n'.join(reasons))
        current['items'].update(imported)
        current['items'].update({name: {'goal': candidates[name].get('goal', 'unplanned'),
                                       'track': candidates[name]['track'],
                                       'flags': candidates[name]['flags'],
                                       'budget_size': candidates[name]['score'][
                                           'job_size' if framework == 'wsjf' else 'effort'],
                                       **{key: candidates[name][key] for key in ('tier',)
                                          if key in candidates[name]}}
                                 for name in items})
        current.update(cap=data['cap'], cap_bound=data.get('capacity', {}).get('bound', ''),
                       seat_policy=data['seat_policy'], goal_seats=_seats(data),
                       envelope=data['envelope'], goals=data['goals'],
                       approved_items=items, gate_approved=True, pace=chosen)

    kind = 'state.import' if import_yesterday else 'plan.approved'
    written = state._write_state(update, root, reserved=False, kind=kind,
                                 payload={'items': sorted(imported) if import_yesterday else items,
                                          'approved_items': items,
                                          'flags': {name: candidates[name]['flags'] for name in items},
                                          'pace': chosen, 'recommended': recommended, 'wish': wish})
    for name in skipped:
        state.append_event('tracker.skipped', _skipped(name, candidates[name]), root)
    from wuwei import shepherd
    for name in claims:  # claim_pr prints the claim or its refusal; the gate stays approved.
        shepherd.claim_pr(root, adopted[name]['pr'], name, data['goals'][0])
    return written


def add(item, root=None, goal=None, size=None, title=None, ticket=None, source=None):
    """Admit one item after the gate: a discovered candidate through the intraday
    policy, or an item the owner names under a goal (the owner naming it is the decision)."""
    root = workspace.find_workspace(root)
    day = state.read_state(root)
    if not day['gate_approved']:
        raise state.StateError('morning gate has not been approved; run the morning gate first (/wuwei:wuwei-plan)')
    if item in day['items']:  # #615: an item admitted without risk evidence records it once
        from wuwei.merge import risk_evidence
        if risk_evidence(root, item):
            raise state.StateError(f'item {item} is already in the plan; run bin/wuwei build next {item}')
        state.append_event('plan.added', {'item': item, 'source': 'replan',
                                          'flags': {item: day['items'][item]['flags']}}, root)
        return {'action': 'risk recorded', 'item': item}
    config = workspace.load_config(root)
    size_key = 'job_size' if config['prioritisation']['framework'] == 'wsjf' else 'effort'
    candidate = day.get('discovery_candidates', {}).get(item)
    owner_item = candidate is None
    if owner_item:
        if goal is None:
            raise state.StateError(f"{item} is not a discovery candidate; to add it as the owner's item "
                                   f'run bin/wuwei plan add {item} --goal G-n')
        if goal not in day['goals']:
            raise state.StateError(f"{goal} is not one of today's goals ({', '.join(day['goals'])}); "
                                   f'run bin/wuwei plan add {item} --goal <one of them>')
        candidate = {'id': item, 'goal': goal, 'track': 'SLICE', 'source': source or 'owner',
                     'flags': {key: False for key in FLAGS},
                     'title': title or item, 'score': {size_key: 1 if size is None else size},
                     **({'ticket': ticket} if ticket else {})}
    else:
        goals_text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
        _proposal({'goals': day['goals'], 'cap': day['cap'],
                   'seat_policy': day['seat_policy'], 'envelope': day['envelope'],
                   'sweep': {'discovery': 'measured: candidate'},
                   'candidates': [candidate]}, goals_text,
                  config['prioritisation']['framework'])
    from wuwei import tracker
    chosen = proposed(candidate)
    status, reason = tracker.check({'tickets': {item: chosen}} if chosen else day,
                                   config, item, candidate)
    if status == 'missing' and owner_item and workspace.posture(config)[0] != 'strict':
        # #636: draft the owner item's ticket for its Send card; a seat can reach plan add, so never send here.
        opened = tracker.create(root, item, row={'scope': candidate['title'], 'goal': goal,
                                                 'track': candidate['track'],
                                                 'evidence': 'named by the owner'})
        if opened.exit == 0:
            status = 'ticket'
        elif isinstance(opened.data, dict):
            reason = tracker.check(state.read_state(root), config, item, candidate)[1]
        else:
            reason = opened.reason
    if status == 'missing':
        raise state.StateError(reason)
    size = candidate['score'][size_key]
    decision = 'start'
    if not owner_item:
        committed = sum(row.get('budget_size', float('inf')) for row in day['items'].values())
        within_budget = committed + size <= day['envelope']['net_build_hours']
        running = sum(seat.get('status') == 'running' and seat.get('role') == 'builder'
                      for seat in day['seats'].values())
        within_cap = running < day['cap']
        above_cut = True
        if config['discovery']['autostart'] == 'strict' and day['approved_items']:
            proposal_path = workspace.day_dir(root) / 'proposal.json'
            if proposal_path.is_symlink():
                raise ValueError(f'proposal.json must not be a symlink; {SYMLINK}')
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
                raise state.StateError(f'item {item} is already in the plan; run bin/wuwei build next {item}')
            current.setdefault('intraday_proposals', {})[item] = {
                'decision': decision, 'candidate': candidate}
        state._write_state(propose, root, reserved=False, kind='plan.proposed',
                           payload={'item': item, 'decision': decision})
        return {'action': decision, 'item': item}

    def admit(current):
        if item in current['items']:
            raise state.StateError(f'item {item} is already in the plan; run bin/wuwei build next {item}')
        current['items'][item] = {'goal': candidate['goal'], 'track': candidate['track'],
                                  'flags': candidate['flags'], 'budget_size': size,
                                  **{key: candidate[key] for key in ('tier',) if key in candidate},
                                  **({'source': source, 'title': candidate['title']} if source else {})}
        current['approved_items'].append(item)
        if chosen and not tracker.ticket(current, item):
            current.setdefault('tickets', {})[item] = chosen
    state._write_state(admit, root, reserved=False, kind='plan.added',
                       payload={'item': item, 'source': candidate.get('source', 'discovery'),
                                'flags': {item: candidate['flags']}})
    if status == 'skipped':
        state.append_event('tracker.skipped', _skipped(item, candidate), root)
    return {'action': 'build next', 'item': item}


def set_spec(item, assignment, reason=None, root=None):
    """plan set <item> spec=required|skipped: the owner's per-item spec override (5.10)."""
    root = workspace.find_workspace(root)
    key, _, value = assignment.partition('=')
    if key != 'spec' or value not in ('required', 'skipped'):
        raise ValueError(f'expected spec=required or spec=skipped; run bin/wuwei plan set {item} spec=required, '
                         f'or spec=skipped --reason <why>')
    reason = ' '.join((reason or '').split())  # one line, as plan carry and park
    if value == 'skipped' and not reason:
        raise ValueError(f'spec=skipped needs a reason; run bin/wuwei plan set {item} spec=skipped --reason <why>')

    def update(data):
        if item not in data['items']:
            raise state.StateError(f"no item {item} today; today's items: "
                                   f"{', '.join(sorted(data['items'])) or 'none'}; use one of those ids")
        data['items'][item]['spec'] = {'value': value, 'reason': reason}
    state._write_state(update, root, reserved=False, kind='spec.override',
                       payload={'item': item, 'value': value, 'reason': reason})
    return f'{item}: spec {value}'


def set_owner_merge(item, value, root=None):
    """#678: plan set <item> owner_merge=true|false: the owner keeps (or releases) this merge."""
    root = workspace.find_workspace(root)
    if value not in ('true', 'false'):
        raise ValueError(f'expected owner_merge=true or owner_merge=false; run bin/wuwei plan set {item} '
                         'owner_merge=true|false')
    on = value == 'true'
    by = os.environ.get('WUWEI_SEAT_ROLE') or ('planner' if sessions.current() else 'owner')
    linked = []

    def update(data):
        if item not in data['items']:
            raise state.StateError(f"no item {item} today; today's items: "
                                   f"{', '.join(sorted(data['items'])) or 'none'}; use one of those ids")
        data['items'][item]['owner_merge'] = {'value': on, 'by': by, 'at': workspace.now().isoformat()}
        linked.append(data['items'][item].get('pr'))
    state._write_state(update, root, reserved=False, kind='plan.set',
                       payload={'item': item, 'owner_merge': on, 'by': by})
    config = workspace.load_config(root)
    if linked[-1] and config['adapters']['code_host'] != 'none':
        from wuwei import merge, registry
        try:
            labels = merge.read(registry.load('code_host', config).label, linked[-1], merge.LABEL, on, root=root)
            if (merge.LABEL in labels['labels']) != on:
                raise ValueError('the PR labels did not change; if it repeats, run bin/wuwei doctor, '
                                 'which tests the code host adapter')
        except merge.ERRORS as exc:
            raise OSError(f'{item}: owner_merge {value} recorded; PR label not updated: {exc}; '
                          f'rerun bin/wuwei plan set {item} owner_merge={value}') from exc
    return f'{item}: owner_merge {value}'


def set_pace(value, root=None):
    """#579: plan set pace=<p>: the day's pace from now on; items tiered already keep theirs."""
    from wuwei import pace
    root = workspace.find_workspace(root)
    if value not in pace.PACES:
        raise ValueError(f'unknown pace {value!r}; run bin/wuwei plan set pace=<p> with one of careful, steady or fast')
    payload = {'pace': value}

    def update(data):
        payload['previous'] = pace.current(data, workspace.load_config(root))
        data['pace'] = value
    state._write_state(update, root, reserved=False, kind='pace.set', payload=payload)
    return f"pace {value} (was {payload['previous']})"


def set_ticket(item, ticket, root=None):
    """plan set <item> ticket=<id>: record an existing ticket once the tracker confirms it."""
    from wuwei import registry
    root = workspace.find_workspace(root)
    if not isinstance(ticket, str) or not re.fullmatch(TICKET, ticket):
        raise ValueError(f'invalid ticket {ticket!r}; pass an id such as ENG-12, PROJ-12 or owner/repo#12')
    proposal = workspace.day_dir(root) / 'proposal.json'
    names = set(state.read_state(root)['items'])
    if proposal.is_file() and not proposal.is_symlink():
        names |= {row.get('id') for row in
                  json.loads(proposal.read_text(encoding='utf-8')).get('candidates', [])}
    if item not in names:
        raise state.StateError(f"unknown item {item}; use an id from today's plan or proposal "
                               '(bin/wuwei status lists them)')
    result = registry.load('tracker', workspace.load_config(root)).created(ticket, root=root)
    if result.exit:
        raise (state.StateError if result.exit == 1 else OSError)(
            result.reason or f'tracker could not confirm {ticket}; check the id in the tracker, then '
                             f'run bin/wuwei plan set {item} ticket=<id> again')
    state._write_state(lambda data: data.setdefault('tickets', {}).update(
        {item: {'id': ticket, 'source': 'set'}}), root, reserved=False, kind='plan.set',
        payload={'item': item, 'ticket': ticket})


def dispose(item, outcome, reason=None, root=None):
    """plan carry|park: write and route a two-way record that carries or parks one item at
    day close; return its D-n. Park pauses an active item, carry changes no phase."""
    from wuwei import decision
    root = workspace.find_workspace(root)
    verb = {'carried': 'carry', 'parked': 'park'}[outcome]
    reason = ' '.join((reason or '').split())  # one line, so a reason cannot start a field

    def known(data):
        if item not in data['items']:
            raise state.StateError((f"no item {item} today; today's items: "
                                   f"{', '.join(sorted(data['items'])) or 'none'}; use one of those ids"))
        return data['items'][item]

    current = known(state.read_state(root))
    action = {'carry': 'Carry to tomorrow', 'park': 'Park the item'}[verb]
    consequence = {'carry': "It joins tomorrow's plan and its phase does not change.",
                   'park': 'It pauses until someone resumes it.'}[verb]
    text = (
        f'Question: {verb.title()} {item} at day close?\n'
        f'Class: {"defer" if verb == "carry" else "park"}\n'
        f'Context: {item} is {current["status"]}/{current["phase"]} at day close.'
        f'{" Reason: " + reason if reason else ""}\n'
        'Options:\n| Option | Title | Rationale | Consequence |\n| --- | --- | --- | --- |\n'
        f'| {verb} | {action} | Reversible and lets the day close. | {consequence} |\n'
        '| keep | Do nothing, keep working | Reversible but the day cannot close. | The item stays open today. |\n'
        f'Musts:\n| Criterion | {verb} | keep |\n| --- | --- | --- |\n'
        '| Reversible | pass | pass |\n'
        f'Wants:\n| Criterion | Weight | {verb} | keep |\n| --- | --- | --- | --- |\n'
        '| Day can close | 10 | 10 | 0 |\n'
        f'Recommendation: {verb}\nReasoning: Closing the day decided it; urgent work on the item would flip it.\n'
        'Confidence: high\nReversibility: two-way\n'
        'Blast radius: own branch\nPre-mortem: The item needed attention today and waits a day.\n'
        "Revisit: At tomorrow's morning gate.\n"
        f'Decided-by: seat\nOutcome: {outcome} {item}\n')
    payload = {'item': item}

    def update(data):
        record = known(data)
        path = decision.write(text, root)
        outcome_record = decision.seat_outcome(*decision.evaluate(text))
        data.setdefault('decision_outcomes', {})[path.stem] = outcome_record
        if outcome == 'parked' and record['phase'] not in ('parked', 'escalated', 'merged'):
            record.update(phase='parked', status='blocked')
        payload.update(id=path.stem, **outcome_record)
    state._write_state(update, root, reserved=False, kind='decision.decided', payload=payload)
    return payload['id']
