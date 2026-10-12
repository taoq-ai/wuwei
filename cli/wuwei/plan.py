"""Morning proposal and dedicated gate approval producer."""

import json
import os
from pathlib import Path
import re

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

    return state._write_state(update, root, kind='plan.session',
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
    for role, policy in data['seat_policy'].items():  # #845: an optional alternate runtime
        if 'alternate' in policy and (policy['alternate'] not in workspace.SCHEMA['budget']
                                      or policy['alternate'] == policy['runtime']):
            raise ValueError(f'seat_policy {role} alternate must be another known runtime; {PLAN_JSON}')
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
        for key in ('ticket', 'tier'):  # #640: empty means absent; in place, callers reuse item
            if key in item and isinstance(item[key], str) and not item[key].strip():
                item.pop(key)  # a null ticket stays: it is the owner's none (#636)
            elif key != 'ticket' and key in item and item[key] is None:
                item.pop(key)
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
        _admitted(name, item)
        if 'tier' in item and item['tier'] not in dispatch.TIERS:
            raise ValueError(f'{name}: tier must be light, standard or full; {PLAN_JSON}')
        if item.get('ticket') is not None and not (isinstance(item['ticket'], str) and re.fullmatch(
                TICKET, item['ticket'])):  # #636: null is the owner's none; #640: empty is absent
            raise ValueError(f'{name}: invalid ticket {item["ticket"]!r}; ticket must match {TICKET}, an id '
                             f'such as ENG-12, PROJ-12 or owner/repo#12, or be left out; {PLAN_JSON}')
        # #478, #518: owner-only steps the gate pre-approves. An entry the CLI does not
        # understand is a warning on the plan, never a refusal before the gate.
        if not isinstance(item.get('owner_actions', []), list):
            raise ValueError(f'{name}: owner_actions must be a list; {PLAN_JSON}')
        paths = item.get('paths', [])  # #579: the files it touches; guard paths advise careful
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ValueError(f'{name}: paths must be a list of strings; {PLAN_JSON}')
    json.dumps(data, allow_nan=False)
    return data


def _admitted(name, item, tree=None):
    """#868: the track, flags and governed_by checks plan propose and plan add share."""
    if item.get('track') not in ('SLICE', 'FULL'):
        raise ValueError(f'{name}: track must be SLICE or FULL; {PLAN_JSON}')
    flags = item.get('flags')
    if not isinstance(flags, dict) or set(flags) != set(FLAGS) or any(type(v) is not bool for v in flags.values()):
        raise ValueError(f'{name}: flags must contain boolean trust_surface, boundary_relevant, agent_surface; {PLAN_JSON}')
    if 'governed_by' in item:
        governed(name, item['governed_by'], tree)


def governed(name, reference, tree=None):
    """#664, #864: the one governed_by check: a path or path#heading that, in the item's
    checkout when it is known, resolves as the brief resolves it (specmode.governing)."""
    from wuwei import specmode
    if not (isinstance(reference, str) and reference.strip()):
        raise ValueError(f'{name}: governed_by must be a path or path#heading; {PLAN_JSON}')
    if tree is None:
        return
    try:
        specmode.governing(tree, {'governed_by': reference})
    except ValueError as exc:
        raise ValueError(f'{name}: governed_by {reference}: {str(exc).split(";")[0]}; set governed_by '
                         'to a repository-relative file, or a directory with a spec.md, with an optional '
                         '#heading') from None


def checkout(root, repos, repo=None, worktree=None):
    """#864: the tree an item's governed_by resolves in: its worktree once it exists, else the
    configured repository it names (or the only one), else None while that is unknown."""
    if worktree and (root / worktree).is_dir():
        return root / worktree
    found = [row for row in repos if row['name'] == repo] or (repos if len(repos) == 1 else [])
    return root / Path(found[0]['path']).expanduser() if found else None


REPO = r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
# #518: every owner-only step a lead may list, with its target shape.
OWNER_ACTIONS = {'deploy': 'repo:' + REPO, 'release': 'repo:' + REPO, 'publish': 'repo:' + REPO,
                 'merge': f'(?:repo:{REPO}|pr:{REPO}#[0-9]+)',
                 'message': r'(?:channel|dm):[A-Za-z0-9_-]+',
                 'secret-set': f'secret:{REPO}/[A-Za-z0-9_]+'}


def understood(entry):
    """'' for a known action with a well-formed target, else why not (never an exception)."""
    if (not isinstance(entry, dict) or set(entry) != {'action', 'target'}
            or not all(isinstance(value, str) for value in entry.values())):
        return 'needs exactly action and target as strings'
    shape = OWNER_ACTIONS.get(entry['action'])
    if shape is None:
        return f'action {entry["action"]} not understood; known: {", ".join(OWNER_ACTIONS)}'
    if not re.fullmatch(shape, entry['target']):
        return f'target {entry["target"]} is not in the shape for {entry["action"]}'
    return ''


def owner_steps(item):
    """#518, #816: plan lines for the owner actions the lead lists; an entry the CLI does not
    understand is asked at the gate as written."""
    lines = []
    for entry in item.get('owner_actions', []):
        reason = understood(entry)
        if reason:
            lines.append(f'Owner-only: {json.dumps(entry, sort_keys=True)} (not understood: {reason}; '
                         'the gate asks for it as written)')
        else:
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


def _tickets(config, data):
    """#636: {item: '<id> (existing)' | 'none'} for the plan and the gate card; #842: an item
    with no ticket shows none and gets none."""
    if config['adapters']['tracker'] == 'none':
        return {}
    found, texts = tracked(data), {}
    for row in data['candidates']:
        if record := proposed(row, found):
            texts[row['id']] = 'none' if record['id'] is None else f'{record["id"]} (existing)'
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
    own = config['outbound']['owner']['code_host']
    # #867 F1: GitHub search answers 422 for a user it does not know, so only handles that can be
    # GitHub logins are searched (never a chat ID, checked before casefold); the code host login always.
    logins = {login.casefold() for login in config['owner']['handles']
              if not re.fullmatch(r'[UW][A-Z0-9]+', login) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', login)}
    logins |= {own.casefold()} if own else set()
    if not config['repos'] or not logins:
        return [], 'unmeasured: no configured repository or owner.handles'
    host = registry.load('code_host', config)
    taken, rows = {item['id'] for item in candidates}, []
    for repo in config['repos']:
        for login in sorted(logins):  # #867: GitHub filters by author; never every open PR
            result = host.open_prs(repo['name'], login, root=root)
            if result.exit:
                return [], f'unmeasured: {result.reason}'
            # #603: with several repositories the id names the repository, so one number gives two ids.
            prefix = f'PR-{repo["name"].rsplit("/", 1)[-1]}-' if len(config['repos']) > 1 else 'PR-'
            for pr in result.data:
                ident = f'{prefix}{pr["number"]}'
                if (pr['author'] or '').casefold() in logins and ident not in taken:
                    taken.add(ident)
                    rows.append({'id': ident, 'pr': f'{repo["name"]}#{pr["number"]}', 'title': pr['title']})
    return rows, f'measured: {len(rows)} open PR{"" if len(rows) == 1 else "s"} by the owner'


def propose(data, root=None):
    root = workspace.find_workspace() if root is None else Path(root)
    from wuwei import steward
    steward_finding = steward.previous_day_finding(root)
    recorded = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
    goals_text, provisional = goals.proposed(recorded, data.get('goals') if isinstance(data, dict) else None)
    goal_list = goals.parse(goals_text)
    if provisional:  # #848: blocks over recorded goals replace them; name the ids they replace
        data = {**data, 'goals': list(goal_list),
                'replaces': list(goals.parse(recorded)) if goals.defined(recorded) else []}
    found = discovery.discover(root)
    data = {**data, 'sweep': {**data.get('sweep', {}),
            **{f'discovery.{key}': value for key, value in found['sources'].items()}},
            'discovered': found['candidates']}
    config = workspace.load_config(root)
    from wuwei.dispatch import host
    # #528: CAP derives; the lead's cap is not used. #658: the proposal's seat policy picks the rule
    limits = host(root, config, policy=data.get('seat_policy'))
    data = {**data, 'cap': limits['cap'],
            'capacity': {key: limits[key] for key in ('bound', 'text', 'seats')}}
    framework = config['prioritisation']['framework']
    data = _proposal(data, goals_text, framework)
    if config['gates']['second_opinion'].partition(':')[0] == data['seat_policy'].get('builder', {}).get('alternate'):
        raise ValueError(f'seat_policy builder alternate must differ from the second opinion runtime; {PLAN_JSON}')
    from wuwei import tracker
    for row in data['candidates']:  # #741: the lead's tickets, in the one id format
        if row.get('ticket'):
            row['ticket'] = tracker.full_id(config, row['ticket'])
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
    for item in data['candidates']:  # #864: refused here, never at the brief after the gate
        if 'governed_by' in item:
            governed(item['id'], item['governed_by'], checkout(root, config['repos'], item.get('repo')))
    data['seats'] = _seats(data)
    data['adopt'], data['sweep']['open-prs'] = _owner_prs(config, root, data['candidates'])
    directory = workspace.day_dir(root)
    if state.day_started(directory) and state.read_state(root).get('gate_approved'):
        raise state.StateError('morning gate already approved; run bin/wuwei plan add <item> to admit a new item, or bin/wuwei next for the approved plan')
    lines = ['# Morning plan', '', 'Status: PROPOSED', '',
             *(['Finding: ' + steward_finding, ''] if steward_finding else []),
             '## Goals to confirm',
             *([f'Replaces the recorded goals {", ".join(data["replaces"])}; plan approve records '
                f'days/{directory.name}/goals.md.' if data.get('replaces') else
                f'Provisional: proposed by the lead; plan approve records days/{directory.name}/'
                'goals.md.'] if provisional else []),
             *[line for goal in data['goals'] for line in (
                 [f'- {goal}' + ('' if data.get('replaces') else ' (provisional)'),
                  *(f'  {key}: {goal_list[goal][key]}' for key in goals.FIELDS)]
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
                  *owner_steps(item), '']
    lines += ['## Discovered',
              *[f'- {item["id"]}: {item.get("evidence", "evidence pending")}' for item in data['discovered']], '',
              *(['## Open PRs to claim', *(f'- {row["id"]}: {row["pr"]} {row["title"]} (claimed under '
                                           f'{data["goals"][0]})' for row in data['adopt']), '']
                if data['adopt'] else []),
              '## Gate proposal', f'CAP: {data["capacity"]["text"]}; host.seats {data["capacity"]["seats"]}',
              'Seats per goal: ' + seats_text(data['seats'], data['cap']),
              'Seat policy: ' + _policy(config, data),
              'Envelope: ' + json.dumps(data['envelope'], sort_keys=True), '']
    directory.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(directory / 'proposal.json', json.dumps(data, allow_nan=False, indent=2) + '\n')
    if provisional:
        workspace.atomic_write(directory / 'goals.md', goals_text)
    else:
        (directory / 'goals.md').unlink(missing_ok=True)
    path = directory / 'plan.md'
    workspace.atomic_write(path, '\n'.join(lines))
    return path


def _policy(config, data):
    """The seat policy as the gate shows it; #860: with why an empty codex.command matters."""
    from wuwei.commands.doctor import codex_gap
    gap = codex_gap(config, data['seat_policy'].values())
    return json.dumps(data['seat_policy'], sort_keys=True) + (f' ({gap})' if gap else '')


def gate_widget(root=None, *, import_yesterday=False):
    """The one morning gate question for today's proposal and the command that approves it."""
    from wuwei import decision
    root = workspace.find_workspace() if root is None else Path(root)
    directory = workspace.day_dir(root)
    data = json.loads((directory / 'proposal.json').read_text(encoding='utf-8'))
    draft = directory / 'goals.md'  # propose writes it only for proposed goal blocks
    provisional = goals.parse(draft.read_text(encoding='utf-8')) if draft.is_file() else None
    adopt = data.get('adopt', [])
    ids = [item['id'] for item in data['candidates']] + [row['id'] for row in adopt]
    config = workspace.load_config(root)
    shown = _tickets(config, data)
    approves = '. '.join(part[:1].upper() + part[1:] for part in [
        'Goals ' + ', '.join(f'{goal} ({provisional[goal]["outcome"]})' if provisional else goal
                             for goal in data['goals'])
        + (f' (replaces {", ".join(data["replaces"])})' if provisional and data.get('replaces') else ''),
        'queue ' + (', '.join(item['id'] for item in data['candidates']) or 'empty'),
        *(['tickets ' + ', '.join(f'{name} {text}' for name, text in shown.items())] if shown else []),
        *(['claims ' + ', '.join(f'{row["id"]} ({row["pr"]})' for row in adopt)] if adopt else []),
        seats_text(_seats(data), data['cap']),
        *([data['capacity']['text']] if 'capacity' in data else []),
        'seat policy ' + _policy(config, data),
        'envelope ' + json.dumps(data['envelope'], sort_keys=True),
        *(['carry-over of unfinished prior-day items'] if import_yesterday else [])])
    return decision.widget(
        decision.gate(root) + "Approve today's plan as proposed?",
        'Goals' if provisional else 'Plan',
        [('Approve', approves + '.'),
         ('Change something', 'Ask the separate questions on goals, queue, tickets, seat policy, '
                              'CAP and seats per goal, envelope and carry-over. CAP is derived. '
                              'A changed CAP is recorded as config cap. Name any item you merge '
                              'yourself; the planner records it with wuwei plan set <item> owner_merge=true.')],
        ' '.join(['wuwei plan approve --items', *ids, '--goals-confirmed',
                  *(['--import-yesterday'] if import_yesterday else [])]))


def _approval(scope, note):
    """#731: the item's recorded approval: the plan scope the owner approved, then the owner's words, on one line."""
    note = ' '.join((note or '').split())
    return '; '.join(part for part in (' '.join(scope.split()), note and f'owner: "{note}"') if part)


def approve(items, root=None, *, goals_confirmed=False, import_yesterday=False, note=None):
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
    if (directory / 'goals.md').is_file():  # #603, #848: the proposed goals the gate card showed
        text = (directory / 'goals.md').read_text(encoding='utf-8')
    data = _proposal(json.loads(proposal_path.read_text(encoding='utf-8')), text, framework)
    if not isinstance(items, list) or len(items) != len(set(items)):
        raise ValueError(f'approved items must be a unique list; {PLAN_JSON}')
    adopted = {row['id']: row for row in data.get('adopt', [])}  # #510: claimed after the gate
    claims, items = [name for name in items if name in adopted], [name for name in items if name not in adopted]
    candidates = {item['id']: item for item in data['candidates']}
    if any(name not in candidates for name in items):
        raise state.StateError('approved item is absent from proposal; approve only ids from the proposal (bin/wuwei next lists them), or run bin/wuwei plan propose again')
    from wuwei import tracker
    imported, carried = {}, {}
    found = tracked(data)
    if import_yesterday:
        days = root / '.wuwei/days'
        prior = sorted((path for path in days.iterdir() if path.is_dir() and
                        path.name < directory.name and re.fullmatch(r'\d{4}-\d{2}-\d{2}', path.name)),
                       reverse=True)
        if not prior or not state.day_started(prior[0]):
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
    current = state.read_state(root)
    if not current.get('gate_approved'):  # #833: the gate answer records the goals it approved
        from wuwei import promotion
        try:
            promotion.save_goals(root, text)
        except OSError as exc:
            raise OSError(f'{exc}; the goals are not recorded and the day stays unapproved; '
                          'run bin/wuwei doctor, then plan approve again') from exc

    def update(current):
        if current.get('gate_approved'):
            raise state.StateError('morning gate already approved; run bin/wuwei plan add <item> to admit a new item')
        if set(current['items']) & (set(imported) | set(items)):
            raise state.StateError('day item already exists; remove the existing ids from --items (bin/wuwei next lists them)')
        tickets = {**current.get('tickets', {}), **carried}
        for name in items:
            if name not in tickets and (record := proposed(candidates[name], found)):
                tickets[name] = record
        if tickets:
            current['tickets'] = tickets
        current['items'].update(imported)
        current['items'].update({name: {'goal': candidates[name].get('goal', 'unplanned'),
                                       'track': candidates[name]['track'],
                                       'flags': candidates[name]['flags'],
                                       'budget_size': candidates[name]['score'][
                                           'job_size' if framework == 'wsjf' else 'effort'],
                                       **{key: candidates[name][key] for key in ('tier', 'governed_by')
                                          if key in candidates[name]},
                                       'approved_as': _approval(candidates[name]['scope'], note)}
                                 for name in items})
        current.update(cap=data['cap'], cap_bound=data.get('capacity', {}).get('bound', ''),
                       seat_policy=data['seat_policy'], goal_seats=_seats(data),
                       envelope=data['envelope'], goals=data['goals'],
                       approved_items=items, gate_approved=True)

    kind = 'state.import' if import_yesterday else 'plan.approved'
    written = state._write_state(update, root, kind=kind,
                                 payload={'items': sorted(imported) if import_yesterday else items,
                                          'approved_items': items,
                                          'flags': {name: candidates[name]['flags'] for name in items}})
    if config['adapters']['tracker'] != 'none':  # #842: a new item's ticket opens as a duty
        from wuwei import dispatch
        for name in items:
            if proposed(candidates[name], found) is None:
                dispatch.tracker_call(name, 'create', root)
    from wuwei import shepherd
    for name in claims:  # claim_pr prints the claim or its refusal; the gate stays approved.
        shepherd.claim_pr(root, adopted[name]['pr'], name, data['goals'][0])
    return written


def add(item, root=None, goal=None, size=None, title=None, ticket=None, source=None, note=None,
        repo=None, track='SLICE', governed_by=None, flags=()):
    """Admit one item after the gate: an item the owner names under a goal (the owner naming it
    is the decision) or a seat's finding. #868: the owner's repo, track, governed_by and flags
    pass the checks plan propose applies."""
    root = workspace.find_workspace(root)
    day = state.read_state(root)
    if not day['gate_approved']:
        raise state.StateError('morning gate has not been approved; run the morning gate first (/wuwei:wuwei-plan)')
    if item in day['items'] and _approval('', note):  # #731: the approval is recorded once, at admission
        raise state.StateError(f"item {item} is already in the plan and its approval is recorded; write the "
                               "owner's new words into the item's spec as a scope change")
    if item in day['items']:  # #615: an item admitted without risk evidence records it once
        from wuwei.merge import risk_evidence
        if risk_evidence(root, item):
            raise state.StateError(f'item {item} is already in the plan; run bin/wuwei build next {item}')
        state.append_event('plan.added', {'item': item, 'source': 'replan',
                                          'flags': {item: day['items'][item]['flags']}}, root)
        return {'action': 'risk recorded', 'item': item}
    if source == 'finding':  # #646: a seat's finding joins as a small item
        finding = day.get('seat_findings', {}).get(item)
        if finding is None:
            raise state.StateError(f'{item} is not a seat finding; wuwei next lists the findings to add')
        goal, title = goal or day['goals'][0], finding['scope']
    config = workspace.load_config(root)
    size_key = 'job_size' if config['prioritisation']['framework'] == 'wsjf' else 'effort'
    if goal is None:
        raise state.StateError(f"{item} is not in the plan; to add it as the owner's item "
                               f'run bin/wuwei plan add {item} --goal G-n')
    if goal not in day['goals']:
        raise state.StateError(f"{goal} is not one of today's goals ({', '.join(day['goals'])}); "
                               f'run bin/wuwei plan add {item} --goal <one of them>')
    candidate = {'id': item, 'goal': goal, 'track': track, 'source': source or 'owner',
                 'flags': {key: key in flags for key in FLAGS},
                 'title': title or item, 'score': {size_key: 1 if size is None else size},
                 **({'ticket': ticket} if ticket else {}),
                 **({'tier': 'light'} if source == 'finding' else {}),
                 **({'repo': repo} if repo else {}),
                 **({'governed_by': governed_by} if governed_by is not None else {})}
    names = [row['name'] for row in config['repos']]
    if repo is not None and repo not in names or source is None and repo is None and len(names) > 1:
        raise ValueError(f'{item}: name its repository: run bin/wuwei plan add {item} --goal {goal} '
                         f'--repo <one of {", ".join(names) or "none configured"}>')
    _admitted(item, candidate, checkout(root, config['repos'], repo, f'worktrees/{item}'))
    from wuwei import tracker
    if candidate.get('ticket'):  # #741: one id format, before anything is written
        candidate = {**candidate, 'ticket': tracker.full_id(config, candidate['ticket'])}
    chosen = proposed(candidate)
    size = candidate['score'][size_key]

    def admit(current):
        if item in current['items']:
            raise state.StateError(f'item {item} is already in the plan; run bin/wuwei build next {item}')
        current['items'][item] = {'goal': candidate['goal'], 'track': candidate['track'],
                                  'flags': candidate['flags'], 'budget_size': size,
                                  **{key: candidate[key] for key in ('tier', 'governed_by', 'repo') if key in candidate},
                                  **({'source': source, 'title': candidate['title']} if source else {}),
                                  **({'approved_as': text} if (text := _approval('', note)) else {})}
        current['approved_items'].append(item)
        if chosen and not tracker.ticket(current, item):
            current.setdefault('tickets', {})[item] = chosen
    state._write_state(admit, root, kind='plan.added',
                       payload={'item': item, 'source': candidate['source'],
                                'flags': {item: candidate['flags']}})
    if not chosen and config['adapters']['tracker'] != 'none':  # #842: best effort, never a wall
        from wuwei import dispatch
        dispatch.tracker_call(item, 'create', root, row={
            'scope': candidate['title'], 'goal': candidate['goal'], 'track': candidate['track'],
            'evidence': 'named by the owner'})
    return {'action': 'build next', 'item': item}


def _owner_confirm(root, argv, detail, token=''):
    """#800, #831: only the owner's Yes on this step's Owner step card lets it run."""
    import shlex
    if reason := sessions.needs_owner(root, shlex.join(['bin/wuwei', 'plan', 'set', *argv]), detail, token):
        raise state.StateError(reason)


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
    if value == 'skipped':  # #800: spec before gates; only the owner skips it
        _owner_confirm(root, [item, 'spec=skipped', '--reason', reason], f'Skip the spec for {item}: {reason}')

    def update(data):
        if item not in data['items']:
            raise state.StateError(f"no item {item} today; today's items: "
                                   f"{', '.join(sorted(data['items'])) or 'none'}; use one of those ids")
        data['items'][item]['spec'] = {'value': value, 'reason': reason}
    state._write_state(update, root, kind='spec.override',
                       payload={'item': item, 'value': value, 'reason': reason})
    return f'{item}: spec {value}'


def set_governed_by(item, value, root=None):
    """#864: plan set <item> governed_by=<path>: after the gate, only the owner's Yes changes
    what governs an item; the value resolves in its checkout first."""
    root = workspace.find_workspace(root)
    row = state.read_state(root)['items'].get(item)
    if row is None:
        raise state.StateError(f"no item {item} today; use an id from today's plan (bin/wuwei next lists them)")
    repo = row.get('repo') or (dispatch.candidate(root, item) or {}).get('repo')
    governed(item, value, checkout(root, workspace.load_config(root)['repos'], repo,
                                   row.get('worktree') or f'worktrees/{item}'))
    _owner_confirm(root, [item, f'governed_by={value}'], f'Govern {item} by {value}')
    state._write_state(lambda data: data['items'][item].update(governed_by=value), root,
                       kind='plan.set', payload={'item': item, 'governed_by': value})
    return f'{item}: governed_by {value}'


def set_owner_merge(item, value, root=None):
    """#678: plan set <item> owner_merge=true|false: the owner keeps (or releases) this merge."""
    root = workspace.find_workspace(root)
    if value not in ('true', 'false'):
        raise ValueError(f'expected owner_merge=true or owner_merge=false; run bin/wuwei plan set {item} '
                         'owner_merge=true|false')
    on = value == 'true'
    by = os.environ.get('WUWEI_SEAT_ROLE') or ('planner' if sessions.current() else 'owner')
    if not on:  # #800: releasing the hold lets WUWEI merge it; only the owner does
        from wuwei.watch import records  # #831: the answer is bound to this hold, the item's nth hold today
        held = sum(row['kind'] == 'plan.set' and row['payload'].get('item') == item
                   and row['payload'].get('owner_merge') is True
                   for row in records(workspace.day_dir(root) / 'events.jsonl'))
        _owner_confirm(root, [item, 'owner_merge=false'], f'Release the owner merge hold on {item}', f'hold {held}')
    linked = []

    def update(data):
        if item not in data['items']:
            raise state.StateError(f"no item {item} today; today's items: "
                                   f"{', '.join(sorted(data['items'])) or 'none'}; use one of those ids")
        data['items'][item]['owner_merge'] = {'value': on, 'by': by, 'at': workspace.now().isoformat()}
        linked.append(data['items'][item].get('pr'))
    state._write_state(update, root, kind='plan.set',
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
                               '(bin/wuwei next lists them)')
    from wuwei import tracker
    config = workspace.load_config(root)
    ticket = tracker.full_id(config, ticket)  # #741: one id format, confirmed and stored
    result = registry.load('tracker', config).created(ticket, root=root)
    if result.exit:
        raise (state.StateError if result.exit == 1 else OSError)(
            result.reason or f'tracker could not confirm {ticket}; check the id in the tracker, then '
                             f'run bin/wuwei plan set {item} ticket=<id> again')
    state._write_state(lambda data: data.setdefault('tickets', {}).update(
        {item: {'id': ticket, 'source': 'set'}}), root, kind='plan.set',
        payload={'item': item, 'ticket': ticket})
    return ticket


def dispose(item, outcome, reason=None, root=None):
    """plan carry|park: record on the item that it carries or parks at day close, with one
    plan.disposed event. Park pauses an active item; carry changes no phase."""
    root = workspace.find_workspace(root)
    reason = ' '.join((reason or '').split())  # one line, as plan set reasons

    def update(data):
        if item not in data['items']:
            raise state.StateError((f"no item {item} today; today's items: "
                                   f"{', '.join(sorted(data['items'])) or 'none'}; use one of those ids"))
        record = data['items'][item]
        record['disposition'] = {'kind': outcome, 'reason': reason}
        if outcome == 'parked' and record['phase'] not in ('parked', 'escalated', 'merged'):
            record.update(phase='parked', status='blocked')
    state._write_state(update, root, kind='plan.disposed',
                       payload={'item': item, 'outcome': outcome, 'reason': reason})


def park(item, reason, root=None):
    """Park one item in code (the round cap, a PARK verdict, the owner's No)."""
    dispose(item, 'parked', reason, root)


def resume_token(root, item, data=None):
    """The token of plan resume's Owner step card: each resume takes a fresh Yes."""
    import hashlib
    from wuwei.watch import records
    data = state.read_state(root) if data is None else data
    row = data['items'][item]
    why = (row.get('disposition') or {}).get('reason') or row['phase']
    resumed = sum(event['kind'] == 'plan.resumed' and event['payload'].get('item') == item
                  for event in records(workspace.day_dir(root) / 'events.jsonl'))
    return hashlib.sha256(f'{why}\n{resumed}'.encode()).hexdigest()[:12]


def resume(item, root=None):
    """plan resume <item>: only the owner's Yes on its Owner step card returns a parked or
    escalated item to the phase it paused in, queued."""
    import shlex
    root = workspace.find_workspace(root)
    data = state.read_state(root)
    row = data['items'].get(item)
    if row is None or row['phase'] not in ('parked', 'escalated') or row['status'] != 'blocked':
        raise state.StateError(f'{item} is not parked; plan resume returns a parked item to its phase '
                               "(bin/wuwei next lists today's items)")
    why = (row.get('disposition') or {}).get('reason') or row['phase']
    if reason := sessions.needs_owner(root, shlex.join(['bin/wuwei', 'plan', 'resume', item]),
                                      f'Resume {item}: {why}', resume_token(root, item, data)):
        raise state.StateError(reason)
    from wuwei import derive
    from wuwei.commands import build
    record = data.get('builds', {}).get(item) or {}
    end = derive.head(record['worktree']) if record.get('worktree') else None

    def update(fresh):
        current = fresh['items'][item]
        if current['phase'] != row['phase']:
            raise state.StateError(f'{item} changed during plan resume; run bin/wuwei plan resume {item} again')
        after = build.AFTER.get(current['resume_phase'])
        current.update(phase=current['resume_phase'], status='queued')
        if after and (fresh.get('builds', {}).get(item) or {}).get('status') == 'done':
            build.built(fresh, item, after, end)  # #872: its checks passed while it was paused
        current.pop('disposition', None)
        current.pop('decision', None)
    state._write_state(update, root, kind='plan.resumed', payload={'item': item})
    return f'{item}: resumed'

