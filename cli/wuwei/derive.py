"""The derived next (#844): the world readers and the one decision table.

Everything here only reads: the worktree HEAD from git's files, the verdict files, the cached PR
listing (prs.json) and the day's records. No write, no subprocess, so `next` stays hook-safe;
`refresh` is the one call out, made by `wuwei next` and WUWEI's own PR commands.
"""

import json
import re
from pathlib import Path

from wuwei import state, workspace

SHA = re.compile(r'[0-9a-f]{40}|[0-9a-f]{64}')
DUTIES = ('ping', 'shepherd', 'tracker', 'summary')
# parks the owner decides on plan resume's card: the round cap, a stuck build loop
ASK_PARKS = ('round cap', 'fix round already used', 'same fast-check failure repeated',
             'maximum build iterations reached', 'environment:')


def head(path):
    """The worktree's HEAD sha read from git's files (the .git pointer, the per-worktree HEAD,
    loose or packed refs), or None when a link is missing (the worktree is gone).
    ponytail: a reftable repository reads as no HEAD; the vcs adapter's head off the hook path
    is the upgrade."""
    try:
        path = Path(path)
        pointer = path / '.git'
        if pointer.is_dir():
            gitdir = pointer
        else:
            text = pointer.read_text(encoding='utf-8').strip()
            if not text.startswith('gitdir:'):
                return None
            gitdir = Path(text[7:].strip())
            gitdir = gitdir if gitdir.is_absolute() else path / gitdir
        common = gitdir
        if (gitdir / 'commondir').is_file():
            common = gitdir / (gitdir / 'commondir').read_text(encoding='utf-8').strip()
        value = (gitdir / 'HEAD').read_text(encoding='utf-8').strip()
        if value.startswith('ref: '):
            ref = value[5:].strip()
            loose = next((base / ref for base in (gitdir, common) if (base / ref).is_file()), None)
            if loose is not None:
                value = loose.read_text(encoding='utf-8').strip()
            else:
                packed = common / 'packed-refs'
                lines = packed.read_text(encoding='utf-8').splitlines() if packed.is_file() else ()
                value = next((line.split()[0] for line in lines if line.endswith(' ' + ref)), '')
        value = value.lower()
        return value if SHA.fullmatch(value) else None
    except (OSError, UnicodeError):
        return None


def at_head(row, recorded, current):
    """True when a verdict recorded at head `recorded` counts at the worktree's `current` HEAD:
    the same commit, or a commit the item's recorded fix rounds produced from it (design 5.3:
    a gate that did not ask for the fix keeps its PASS for the head that round produced). A head
    moved any other way makes it stale (#669). An unread current HEAD judges nothing."""
    if not current or not isinstance(recorded, str) or not recorded:
        return True
    current, at = current.lower(), recorded.lower()
    for start, end in (row.get('fix_heads') or ()):
        if start and end and start.lower().startswith(at):
            at = end.lower()
    return current.startswith(at)


def listing(directory):
    """The cached PR listing: {'fetched_at': iso or None, 'pulls': {ref: row}}."""
    path = Path(directory) / 'prs.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'fetched_at': None, 'pulls': {}}
    if not isinstance(value, dict) or not isinstance(value.get('pulls'), list):
        raise ValueError(f'{path}: invalid PR listing; delete it and run wuwei next to refresh it')
    return {'fetched_at': value.get('fetched_at'),
            'pulls': {row['ref']: row for row in value['pulls'] if isinstance(row, dict) and row.get('ref')}}


# WUWEI's own PR steps: the listing is refreshed on the next call after one of them
LISTING_EVENTS = (b'"pr.raised"', b'"pr.claimed"', b'"merge.auto"', b'"merge.completed"', b'"merge.revert"')


def stale(root, config, data):
    """True when an item has a PR and the listing is older than pr.poll_seconds, or older than
    WUWEI's own last raise, claim or merge."""
    if not any(row.get('pr') for row in data['items'].values()):
        return False
    directory = workspace.day_dir(root)
    fetched = listing(directory)['fetched_at']
    if not fetched:
        return True
    from datetime import datetime
    at = datetime.fromisoformat(fetched)
    if (workspace.now() - at).total_seconds() >= config['pr']['poll_seconds']:
        return True
    log = directory / 'events.jsonl'
    acted = [json.loads(line)['ts'] for line in (log.read_bytes().splitlines() if log.is_file() else ())
             if any(kind in line for kind in LISTING_EVENTS)]
    return bool(acted) and datetime.fromisoformat(acted[-1]) >= at


def refresh(root, config):
    """One code-host list call per repository; writes prs.json. On a failed call the old
    listing stays and the reason is returned (None on success)."""
    from wuwei import registry
    port = registry.load('code_host', config)
    pulls = []
    for repo in config['repos']:
        result = port.pulls(repo['name'], root=root)
        if result.exit or not isinstance(result.data, list):
            return result.reason or f'PR listing for {repo["name"]} unmeasured'
        pulls += [{**row, 'ref': f"{repo['name']}#{row['number']}"} for row in result.data]
    workspace.day_dir(root).mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(workspace.day_dir(root) / 'prs.json',
                           json.dumps({'fetched_at': workspace.now().isoformat(), 'pulls': pulls}) + '\n')
    return None


def counted(root, row, record, current):
    """The received verdict when it counts at the current HEAD, else None (missing or stale: its
    head moved). The receipt is the record: a file edited after it changes nothing (#844 F3)."""
    if record is None:
        return None
    return record if at_head(row, record['head'], current) else None


def when(text):
    """An ISO time as an instant (G2: offsets compare as times, never as strings), else None."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None


def gone(root, row):
    """The recorded worktree whose HEAD cannot be read (removed, or an unborn or chained ref),
    else None: no verdict counts there and nothing raises (#844 F5)."""
    tree = row.get('worktree')
    if not tree:
        return None
    path = Path(root) / tree
    # a checkout with no .git at all is not a git worktree (a fixture's stand-in): not judged
    return tree if not path.is_dir() or ((path / '.git').exists() and head(path) is None) else None


def moved(root, data, name, pull_head):
    """The PR head when a rebase or a push moved it past the item's verdicts (none of its
    recorded fix rounds made it), else None (#844 F1)."""
    from wuwei import dispatch
    row = data['items'][name]
    if not pull_head:
        return None
    for role in dispatch.gate_set(row):
        record = dispatch._record(data, name, role, 'delta') or dispatch._record(data, name, role, 'initial')
        if record and not at_head(row, record['head'], pull_head):
            return pull_head
    return None


def _gate(root, data, config, name):
    """The gate offer of an item at gate or delta: ('gates' | 'fix' | 'raise' | 'park' |
    'owner', reason). Precedence follows dispatch.next_step: a missing or stale gate, the round
    cap, PARK, ESCALATE, FIX."""
    from wuwei import dispatch
    row = data['items'][name]
    if tree := gone(root, row):
        return 'gone', f'its worktree {tree} is gone or its HEAD unreadable'
    if row['phase'] == 'gate' and not dispatch._resumed(root, name):
        blocked = dispatch._blocked_card(root, data, name)
        if blocked and blocked[1] == 'No':
            return 'park', blocked[0]
        if blocked and blocked[1] != 'Yes':
            return 'owner', blocked[0]
    gates = dispatch.gate_set(row)
    round_name = 'initial' if row['phase'] == 'gate' else 'delta'
    if round_name == 'delta' and any(dispatch._record(data, name, role, 'initial') is None for role in gates):
        return 'gates', 'an initial verdict is missing'  # dispatch next names it
    roles = list(gates) if round_name == 'initial' else [
        role for role in gates if dispatch.rechecks(data, name, role, root)]
    current = head(root / row['worktree']) if row.get('worktree') else None
    results = {role: counted(root, row, dispatch._record(data, name, role, round_name), current)
               for role in roles}
    if missing := [role for role, record in results.items() if record is None]:
        return 'gates', f"{', '.join(missing)} to run at the current head"
    asked = [role for role in roles if results[role]['verdict'] in ('PARK', 'ESCALATE')]
    blocking = [role for role in roles if role in asked or (
        results[role]['verdict'] == 'FIX' if round_name == 'initial' else results[role]['blocks'])]
    if not blocking:
        return 'raise', 'every gate passed at the current head'
    if dispatch.rounds_used(data, name) >= dispatch.max_rounds(config, row):
        return 'owner', f'round cap reached: {blocking[0]} still blocks'
    resumed = dispatch._resumed(root, name)
    if any(results[role]['verdict'] == 'PARK' for role in asked) and not resumed:
        return 'park', f'gate {asked[0]} PARK'
    if asked and not resumed:
        answer = dispatch._asked(root, data, name, results, asked, round_name)[0]
        if answer == 'No':
            return 'park', f"gate {asked[0]} {results[asked[0]]['verdict']}"
        if answer != 'Yes':
            return 'owner', f"gate {asked[0]} {results[asked[0]]['verdict']}"
    return 'fix', f"gate {blocking[0]} asks for a fix"


def waits_on(root, data, name, pulls=None):
    """#637: the items name's proposal says it depends on that have not merged."""
    from wuwei import dispatch
    try:
        needs = (dispatch.candidate(root, name) or {}).get('depends_on') or ()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []  # a damaged proposal refuses the item's start, never the whole set
    if not needs:
        return []
    pulls = listing(workspace.day_dir(root))['pulls'] if pulls is None else pulls
    items = data['items']
    return [dep for dep in needs if (items.get(dep) or {}).get('phase') != 'merged'
            and (pulls.get((items.get(dep) or {}).get('pr')) or {}).get('state') != 'merged']


def offers(data, root, config, merges=None):
    """The decision table (#844), pure: {launches, decision, parks, rows} over the approved
    items in plan order. A launch is {kind, item, command, why}; the decision the first owner
    decision in plan order; parks the items a PARK verdict or the owner's No parks in code
    (wuwei next records them); rows one status row per open item, runnable first, PRs last."""
    from wuwei import dispatch
    from wuwei.commands.next import TERMINAL, approved
    merges = merges or {}
    found = listing(workspace.day_dir(root))
    pulls, listing_at = found['pulls'], found['fetched_at']
    items = data['items']
    names = approved(data)
    running = {item for _, _, item in state.in_flight(data)}
    merged = {name for name, row in items.items() if row['phase'] == 'merged'
              or (pulls.get(row.get('pr')) or {}).get('state') == 'merged'}
    free = data['cap'] - sum(items[name]['phase'] in state.BUILD_PHASES and not state.held(data, name)
                             for name in names)
    launches, parks, rows, waiting = [], [], [], []
    decision = None

    def launch(kind, name, command, why):
        ticket = (data.get('tickets', {}).get(name) or {}).get('id')
        why = why.replace(name, f'{name} ({ticket})', 1) if ticket else why
        launches.append({'kind': kind, 'item': name, 'command': command, 'why': why})

    def ask(name, why, command, card=False):
        """card: the decision is the owner's Yes on this command's card (a park); after a No
        the item stays as it is and is not asked again."""
        nonlocal decision
        if decision is None and card:
            from wuwei import sessions
            detail = f'{name}: {why}. Yes parks it; No keeps it as it is.'
            if sessions.owner_answer(root, command, detail) == 'No':
                return
            decision = {'item': name, 'why': f'{name}: {why}', 'command': command,
                        'card': sessions.owner_card(command, detail)}
        decision = decision or {'item': name, 'why': f'{name}: {why}', 'command': command}

    def park(name, reason):
        ask(name, reason, f'wuwei plan park {name} --reason "{reason}"', card=True)

    for name in data['approved_items']:  # the round cap or a stuck build parked it: the owner decides
        row = items.get(name) or {}
        reason = (row.get('disposition') or {}).get('reason') or ''
        if row.get('phase') == 'parked' and reason.startswith(ASK_PARKS):
            from wuwei import plan, sessions
            if sessions.owner_answer(root, f'bin/wuwei plan resume {name}', f'Resume {name}: {reason}',
                                     plan.resume_token(root, name, data)) is None:
                ask(name, reason, f'wuwei plan resume {name}')
    for name in names:
        row = items[name]
        phase, pr = row['phase'], row.get('pr')
        pull = pulls.get(pr) if pr else None
        if phase in TERMINAL or name in merged:
            continue  # merged, parked or carried
        if (pull or {}).get('state') == 'closed':  # F9, G8: the owner parks it, re-opens or carries
            park(name, 'PR closed unmerged on the code host')
            continue
        if phase in state.BUILD_PHASES:
            rows.append({'state': 'build', 'item': name, 'command': f'wuwei build next {name}'})
            build = data.get('builds', {}).get(name) or {}
            if name not in running and not state.held(data, name) and build.get('status') != 'running':
                launch('fix' if phase == 'fix' else 'build', name, f'wuwei build next {name}',
                       f'{name} is in {phase}; this is its build loop step.')
        elif phase == 'planned':
            if needs := waits_on(root, data, name, pulls):  # #637: an item waiting on another takes no seat
                rows.append({'state': 'wait', 'item': name, 'command': f"waits on {', '.join(needs)}"})
            elif free > 0:
                free -= 1
                launch('build', name, 'wuwei dispatch next --all', f'{name} is planned and a seat is free.')
        elif phase in ('gate', 'delta'):
            rows.append({'state': 'verdicts', 'item': name, 'command': f'wuwei dispatch next {name}'})
            if name in running:
                continue  # never a gate before the builder (or a gate seat) stops
            kind, why = _gate(root, data, config, name)
            if kind == 'gone':
                park(name, why)
            elif kind == 'owner':
                ask(name, why, f'wuwei dispatch next {name}')
            elif kind == 'park':
                parks.append(name)
            else:
                launch(kind, name, f'wuwei dispatch next {name}', f'{name}: {why}.')
        elif phase == 'raised':
            waiting.append({'state': 'pr', 'item': name, 'command': f'wuwei pr act {pr}'})
            checks = (pull or {}).get('checks')
            checks = 'green' if checks == 'none' else checks  # G3: no CI; merge.check holds the policy
            owner = row.get('owner_merge') or 'owner-merge' in ((pull or {}).get('labels') or ())
            blocked, held = merges.get(pr) or (None, None)
            fetched = when(listing_at) if listing_at else None
            if pull is not None and moved(root, data, name, pull.get('head')):  # F1: re-read first
                if (dispatch.rounds_used(data, name) >= dispatch.max_rounds(config, row)
                        and not dispatch._resumed(root, name)):  # D3: the owner's resume grants one round
                    ask(name, f'PR {pr} head moved past its verdicts at the round cap.', f'wuwei dispatch next {name}')
                else:
                    launch('fix', name, f'wuwei dispatch next {name}',
                           f'{name}: PR {pr} head moved past its verdicts; the gates re-read it.')
            elif blocked or (checks == 'green' and owner):
                ask(name, f'the merge of {pr} is yours to decide.', f'wuwei merge {pr}')
            elif pull is None:
                launch('pr', name, f'wuwei pr act {pr}', f'{name}: PR {pr} is not in the listing yet.')
            elif checks == 'red' and dispatch.rounds_used(data, name) >= dispatch.max_rounds(config, row):
                ask(name, f'PR {pr} checks are red at the round cap.', f'wuwei pr act {pr}')
            elif checks == 'red':
                launch('fix', name, f'wuwei pr act {pr}', f'{name}: PR {pr} checks are red.')
            elif pull.get('mergeable') == 'conflicting':
                launch('pr', name, f'wuwei pr act {pr}', f'{name}: PR {pr} conflicts with its base.')
            elif checks == 'green' and held and (fetched is None or when(held) >= fetched):
                pass  # G1: the merge policy holds it (approvals, threads, soak); it waits on people
            elif checks == 'green':
                launch('merge', name, f'wuwei merge {pr}', f'{name}: PR {pr} is green.')
    return {'launches': launches, 'decision': decision, 'parks': parks, 'rows': rows + waiting}


def _days(root, directory):
    """Today and, while it was not closed, the latest earlier day: a day carried without close
    keeps its open duties in next and close.
    ponytail: one day back; a chain of unclosed days carries only the latest."""
    days = [Path(directory)]
    prior = sorted(path for path in (root / '.wuwei/days').glob('????-??-??')
                   if path.is_dir() and path.name < Path(directory).name)
    if prior and state.day_started(prior[-1]):
        log = prior[-1] / 'events.jsonl'
        if not (log.is_file() and b'"day.closed"' in log.read_bytes()):
            days.append(prior[-1])
    return days


def _rows(directory):
    path = Path(directory) / 'events.jsonl'
    found = []
    for text in path.read_text(encoding='utf-8').splitlines() if path.is_file() else ():
        if '"duty.' in text or '"pr.review_posted"' in text:
            try:
                found.append(json.loads(text))
            except ValueError:
                continue  # a torn line recorded nothing (F4)
    return found


def duties(root, config, directory=None, data=None):
    """Every due duty (#844, #842): [{duty, item, prompt, record}], today's and those of the
    latest earlier day carried without close. A tracker duty (#842) is open while its last
    event is duty.due; the configured duties (duties.on) are due from the world: ping once the
    item has a PR, shepherd on outside review activity newer than its last record, tracker once
    merged, summary once the report is written. duty.done or duty.skipped records each."""
    from wuwei import tracker
    directory = workspace.day_dir(root) if directory is None else Path(directory)
    days = _days(root, directory)
    rows = [row for day in days for row in _rows(day)]
    found, seen = [], set()

    def add(duty, item, prompt, record):
        if (item, duty) not in seen:
            seen.add((item, duty))
            found.append({'duty': duty, 'item': item, 'prompt': prompt, 'record': record})

    if config['adapters']['tracker'] != 'none':
        for item, duty, command in tracker.open_duties(rows):
            add(duty, item, f'Run the {duty} update for {item}.', command)
    done = {}  # (item or PR, duty): the latest record time
    for row in rows:
        payload = row.get('payload') or {}
        at = when(row.get('ts'))
        if row.get('kind') in ('duty.done', 'duty.skipped', 'duty.due'):
            key = (payload.get('item'), {'tracker.done': 'tracker'}.get(payload.get('duty'), payload.get('duty')))
            done[key] = max(filter(None, (done.get(key), at)), default=None)
        elif row.get('kind') == 'pr.review_posted':
            done[(payload.get('pr'), 'ping')] = at
    # G7: a duty is due while its channel is configured; duties.on only turns one off
    channels = {'ping': bool(config['shepherd']['review_channel']),
                'shepherd': config['adapters']['code_host'] != 'none',
                'tracker': config['adapters']['tracker'] != 'none' or bool(config['outbound']['owner']['pages']),
                'summary': config['outbound']['owner_channel'] != 'session'}
    on = {name for name in config['duties']['on'] if channels.get(name)}
    channel = config['shepherd']['review_channel']
    for index, day in enumerate(days):
        values = data if index == 0 and data is not None else state.read_state(directory=day)
        pulls = listing(day)['pulls']
        from wuwei.commands.next import approved
        for name in approved(values):
            row = values['items'][name]
            pr = row.get('pr')
            pull = pulls.get(pr) or {}
            merged = row['phase'] == 'merged' or pull.get('state') == 'merged'
            if 'ping' in on and pr and (name, 'ping') not in done and (pr, 'ping') not in done:
                add('ping', name, f'Post the review request for {pr}'
                    + (f' to the review channel {channel}.' if channel else '.'),
                    f'wuwei pr ping {pr}' if channel else f'wuwei duty {name} ping --evidence <link>')
            activity, answered = when(pull.get('activity_at')), done.get((name, 'shepherd'))
            if 'shepherd' in on and pr and not merged and activity and (answered is None or activity > answered):
                add('shepherd', name, f'Launch the shepherd seat to answer every open review thread on {pr} '
                    '(wuwei pr act --reply).', f'wuwei duty {name} shepherd --evidence <link>')
            ticket = (values.get('tickets', {}).get(name) or {}).get('id')
            page = bool(config['outbound']['owner']['pages'])  # an item with no ticket has a page or no duty
            if 'tracker' in on and merged and (ticket or page) and (name, 'tracker') not in done:
                add('tracker', name, f'Update the ticket or page of {name}: merged in {pr}.',
                    f'wuwei tracker move {name} done' if ticket and config['adapters']['tracker'] != 'none'
                    else f'wuwei duty {name} tracker --evidence <link>')
        if 'summary' in on and (day / 'report.md').is_file() and ('day', 'summary') not in done:
            add('summary', 'day', "Post the day's summary to the owner's channel.",
                'wuwei duty day summary --evidence <link>')
    return found
