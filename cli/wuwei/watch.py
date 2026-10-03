"""Continuous supervision through ports and the shared synchronous writer."""

from collections import Counter
from datetime import timedelta
import json
import re

from wuwei import brief, discovery, obligations, registry, state, workspace
from wuwei.references import pull_request
from wuwei.exits import DAMAGED


ACTIVITY_SECONDS = 60
MAX_READ_FAILURES = 5
DIGEST_SECONDS = 7200

ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)


def records(path):
    """Read complete event records; missing streams are empty, corrupt ones fail."""
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    return _rows(text)


def _rows(text):
    if text and not text.endswith('\n'):
        raise ValueError(f'incomplete event line; {DAMAGED}')
    rows = []
    for line in text.splitlines():
        # The decoder refuses what json.dumps(allow_nan=False) would (NaN, Infinity and
        # floats that overflow): half the cost of encoding every row again.
        row = json.loads(line, parse_constant=_not_json, parse_float=_finite)
        if (not isinstance(row, dict) or not isinstance(row.get('kind'), str)
                or not isinstance(row.get('payload'), dict)):
            raise ValueError(f'invalid event record; {DAMAGED}')
        obligations._time(row['ts'])
        rows.append(row)
    return rows


def _not_json(value):
    raise ValueError(f'Out of range float values are not JSON compliant: {value}')


def _finite(text):
    value = float(text)
    if value in (float('inf'), float('-inf')):
        _not_json(text)
    return value


def days(root):
    today = workspace.now().date().isoformat()
    return sorted((p for p in (root / '.wuwei/days').glob('*')
                   if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name)
                   and p.name <= today), reverse=True)


def health(root, clocks=None, name='watch'):
    """Dead when today's clock went stale, or when the installed service wrote none today.

    No clock line today and no installed unit means off, not a finding.
    """
    try:
        if clocks is None:
            clocks = [row['ts'] for row in _day_rows(workspace.day_dir(root) / 'events.jsonl')
                      if row['kind'] == f'{name}: clock']
        if clocks:
            age = (workspace.now() - max(map(obligations._time, clocks))).total_seconds()
            if age < 0:
                raise ValueError(f'clock line is in the future; {DAMAGED}')
            if age < workspace.load_config(root)[name]['dead_seconds']:
                return 0, ''
            return 1, f'{name} dead: no clock line within deadline; the owner restarts it with bin/wuwei {name} install in a host terminal'
        if workspace.unit_installed(root, name=name):
            return 1, f'{name} dead: installed but no clock line today; the owner restarts it with bin/wuwei {name} install in a host terminal'
        return 0, f'{name} off: no clock line today'
    except ERRORS as exc:
        return 2, f'{name} health unmeasured: {exc}'


# The last events text health decoded and its rows: SessionStart asks for watch and listen
# in turn, and an unchanged day decodes once. Only health reads it (kinds and stamps).
_SEEN = {}


def _day_rows(path):
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    if _SEEN.get('text') != text:
        rows = _rows(text)
        _SEEN.clear()
        _SEEN.update(text=text, rows=rows)
    return _SEEN['rows']


def saved(root):
    value = state.read_state(root).get('watch', {})
    if not isinstance(value, dict):
        raise ValueError(f'invalid watch state; {DAMAGED}')
    return value


def save(root, changes, kind='watch: observation', payload=None):
    def update(data):
        data.setdefault('watch', {}).update(changes)
    return state._write_state(update, root, reserved=False, kind=kind, payload=payload)


def digest(root, config):
    """Batch undigested seat choices through the owner chat port."""
    try:
        data = state.read_state(root)
        prior = data.get('watch', {})
        last = prior.get('digest_at')
        if last is None:
            prior_days = [directory for directory in days(root)
                          if directory != workspace.day_dir(root)]
            if prior_days:
                last = state.read_state(directory=prior_days[0]).get('watch', {}).get('digest_at')
        if last is not None:
            age = (workspace.now() - obligations._time(last)).total_seconds()
            if age < 0:
                raise ValueError(f'digest timestamp is in the future; {DAMAGED}')
            if age < DIGEST_SECONDS:
                return 0
        sent = set(prior.get('digest_ids', []))
        pending = sorted((ident, value['option']) for ident, value in
                         data.get('decision_outcomes', {}).items()
                         if ident not in sent and value.get('decided_by') == 'seat'
                         and value.get('reversibility') == 'two-way')
        if not pending:
            return 0
        from wuwei import decision
        for ident, option in pending:
            if not re.fullmatch(decision.DECISION_ID, ident) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', option):
                raise ValueError(f'invalid two-way decision evidence; {DAMAGED}')
        path = ' (decisions/{}.md)' if workspace.verbosity(config, 'digest') == 'full' else ''
        text = 'Two-way decisions taken:\n' + '\n'.join(
            f'- {ident}: {option}' + path.format(ident) for ident, option in pending) + '\n'
        result = registry.load('chat', config).dm(text, root=root)
        draft = (result.exit == 1 and result.reason.startswith('outward: deliver as a draft')
                 or result.reason == 'no adapter configured')
        if draft:
            path = workspace.day_dir(root) / 'decisions' / ('two-way-digest-' + workspace.now().strftime('%H%M%S') + '.md')
            path.parent.mkdir(parents=True, exist_ok=True)
            workspace.atomic_write(path, text, replace=False)
        elif result.exit != 0:
            raise ValueError(f'chat digest unavailable: {result.reason or "unknown error"}')
        save(root, {'digest_at': workspace.now().isoformat(),
                    'digest_ids': sorted(sent | {ident for ident, _ in pending})},
             kind='decision.digest', payload={'ids': [ident for ident, _ in pending],
                                              'draft': draft})
        return 0
    except ERRORS as exc:
        print(f'watch digest unmeasured: {exc}', flush=True)
        return 2


def owned(root, config):
    data = state.read_state(root)
    host = registry.load('code_host', config)
    refs = sorted({pull_request(ref) for ref in data['raised_prs'] + data['claimed_prs']})
    return host, refs


def activity(root):
    """Observe running worktrees; return stale count and read failures."""
    stale, unreadable = [], 0
    try:
        config = workspace.load_config(root)
        data = state.read_state(root)
        active = {name: item for name, item in data['items'].items()
                  if item['status'] == 'running' and item.get('worktree')}
        running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
        if running:
            logged = records(workspace.day_dir(root) / 'events.jsonl')
            for seat in running:
                matches = [row['payload'] for row in logged if row['kind'] == 'brief written'
                           and row['payload'].get('path') == seat.get('brief')]
                if len(matches) != 1:
                    raise ValueError(f'running seat needs one logged brief; {DAMAGED}')
                tree = matches[0].get('worktree')
                if tree:
                    name = seat['item']
                    if name in active and active[name]['worktree'] != tree:
                        if (root / active[name]['worktree']).resolve() != (root / tree).resolve():
                            raise ValueError(f'running seat and item disagree on worktree; {DAMAGED}')
                    active[name] = {**data['items'][name], 'worktree': tree}
        old_trees = saved(root).get('trees')
        if old_trees is None:
            old_trees = previous(root).get('trees', {})
        trees = {}
        vcs = registry.load('vcs', config)
        for name, item in active.items():
            try:
                path = str((root / item['worktree']).resolve())
                head = obligations._read(vcs.head, path, root=root)['sha']
                if not isinstance(head, str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', head):
                    raise ValueError(f'invalid HEAD; {DAMAGED}')
                old = old_trees.get(name)
                changed = old is not None and old['path'] == path and old['head'] != head
                at = workspace.now().isoformat()
                if old and old['path'] == path and not changed:
                    at = old['at']
                if changed:
                    state.append_event('watch: heartbeat', {'item': name, 'head': head}, root)
                trees[name] = {'path': path, 'head': head, 'at': at}
                last = obligations._time(at)
                if item.get('report_at'):
                    last = max(last, obligations._time(item['report_at']))
                age = (workspace.now() - last).total_seconds()
                if age < 0:
                    raise ValueError(f'activity timestamp is in the future; {DAMAGED}')
                if age >= config['watch']['stale_seconds']:
                    stale.append(name)
            except ERRORS as exc:
                unreadable += 1
                if name in old_trees:
                    trees[name] = old_trees[name]
                print(f'watch activity unmeasured: {name}: {exc}', flush=True)
        save(root, {'trees': trees})
    except ERRORS as exc:
        unreadable += 1
        print(f'watch activity unmeasured: {exc}', flush=True)
    for name in stale:
        print(f'watch stale: {name}', flush=True)
    return (2 if unreadable else int(bool(stale))), {'stale': stale, 'unreadable': unreadable}


def sweep(root=None, *, watch_health=None):
    root = workspace.find_workspace(root)
    from wuwei import integrity
    measured = integrity.check(root)
    if measured.reason:
        print(measured.reason, flush=True)
    config = workspace.load_config(root)
    counts = dict(sweep='obligations', prs=0, reply_owed=0, visibility_owed=0, unreadable=0)
    try:
        counts.update(obligations.evaluate(root))
    except ERRORS as exc:
        counts['unreadable'] += 1
        print(f'watch sweep unmeasured: {exc}', flush=True)
    code, message = health(root) if watch_health is None else watch_health
    counts['watch_dead'] = int(code == 1)
    counts['unreadable'] += int(code == 2)
    if message:
        print(message, flush=True)
    _, activity_counts = activity(root)
    counts['stale_owed'] = len(activity_counts['stale'])
    counts['unreadable'] += activity_counts['unreadable']
    found = {'sources': {}, 'candidates': []}
    try:
        found = discovery.discover(root)
        counts.update({f'discovery.{key}': value for key, value in found['sources'].items()})
        counts['discovery_candidates'] = len(found['candidates'])
        counts['unreadable'] += int(any(value.startswith('unmeasured') for value in found['sources'].values()))
    except ERRORS as exc:
        counts['discovery'] = f'unmeasured: {exc}'
        counts['unreadable'] += 1
    from wuwei import scanner
    scan = scanner.trace_sweep(root, config)
    counts['scanner'] = scan['scanner']
    counts['scanner_owed'] = scan['scanner_owed']
    counts['unreadable'] += scan['unreadable']
    counts['integrity_owed'] = int(measured.exit == 1)
    counts['unreadable'] += int(measured.exit == 2)
    counts['unreadable'] += int(digest(root, config) == 2)
    from wuwei import decision
    try:
        counts['external_waits'] = decision.waits(root)
    except ERRORS as exc:
        counts['unreadable'] += 1
        print(f'watch external waits unmeasured: {exc}', flush=True)
    counts['owed'] = sum(counts[key] for key in (
        'reply_owed', 'visibility_owed', 'stale_owed', 'watch_dead', 'scanner_owed', 'unreadable', 'integrity_owed'))
    counts['exit'] = 2 if counts['unreadable'] else int(counts['owed'] > 0)
    from wuwei import dispatch
    try:
        dispatch.discovery('sweep', root, found)
    except ERRORS as exc:
        counts['unreadable'] += 1
        counts['owed'] += 1
        counts['exit'] = 2
        print(f'watch discovery intake unmeasured: {exc}', flush=True)
    from wuwei import steward
    try:
        prior = saved(root).get('steward_at')
        if prior is None or (workspace.now() - obligations._time(prior)).total_seconds() >= config['watch']['sweep_seconds']:
            steward.run(root, trigger='sweep')
            save(root, {'steward_at': workspace.now().isoformat()})
    except ERRORS as exc:
        counts['unreadable'] += 1
        counts['owed'] += 1
        counts['exit'] = 2
        print(f'watch steward unmeasured: {exc}', flush=True)
    from wuwei import telemetry
    try:
        counts['telemetry'] = telemetry.step(root, config)
    except ERRORS as exc:  # Design 5.13: never the sweep's exit, never owed work.
        counts['telemetry'] = f'unmeasured: {exc}'
        print(f'watch telemetry unmeasured: {exc}', flush=True)
    state.append_event('watch: sweep', counts, root)
    print('watch: sweep ' + json.dumps(counts, sort_keys=True), flush=True)
    return counts['exit']


def previous(root):
    for directory in days(root):
        if directory != workspace.day_dir(root):
            value = state.read_state(directory=directory).get('watch', {})
            if not isinstance(value, dict):
                raise ValueError(f'invalid prior watch state; {DAMAGED}')
            return value
    return {}


def fingerprint(value):
    # Array order from providers is not activity. Bodies are hashed, never logged.
    if isinstance(value, list):
        value = sorted(fingerprint(entry) for entry in value)
    elif isinstance(value, dict):
        value = {key: fingerprint(entry) for key, entry in value.items()}
    return obligations._fingerprint(value)


def evidence(host, ref, root):
    pr = obligations._read(host.pr, ref, root=root)
    if (pr['state'] not in ('open', 'closed') or
            f'{pr["repo"]}#{pr["number"]}' != ref or
            not isinstance(pr['head'], str) or
            not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', pr['head']) or
            (pr['mergeable'] is not None and type(pr['mergeable']) is not bool)):
        raise ValueError(f'invalid PR evidence; {DAMAGED}')
    obligations._time(pr['updated_at'])
    reviews, threads = obligations._evidence(host, ref, root)
    checks = obligations._list(obligations._read(host.checks, ref, pr['head'], root=root))
    for check in checks:
        if (not isinstance(check, dict) or check.get('sha') != pr['head']
                or not isinstance(check.get('name'), str) or not check['name']
                or not isinstance(check.get('state'), str) or not check['state']
                or 'conclusion' not in check):
            raise ValueError(f'invalid checks evidence; {DAMAGED}')
    return dict(pr=pr, reviews=reviews, threads=threads, checks=checks)


def snapshot(host, ref, root, *, measured=None):
    measured = evidence(host, ref, root) if measured is None else measured
    pr = measured['pr']
    fields = {key: pr[key] for key in ('state', 'head', 'mergeable', 'merge_state',
                                      'updated_at', 'requested_reviewers', 'requested_teams')}
    fields.update({key: measured[key] for key in ('reviews', 'threads', 'checks')})
    return {key: fingerprint(value) for key, value in fields.items()}


def facts(measured):
    """Body-free PR facts a summary can name: ids, authors, thread paths, check results."""
    pr = measured['pr']
    seen = {f'comment:{row["id"]}': [row.get('author') or '', '']
            for row in measured['threads']['comments']}
    for item in measured['threads']['threads']:
        seen.update({f'thread:{row["id"]}': [row.get('author') or '', item.get('path') or '']
                     for row in item['comments']})
    seen.update({f'review:{row["id"]}': [row.get('author') or '', row['state']]
                 for row in measured['reviews']})
    return {'head': pr['head'], 'mergeable': pr['mergeable'], 'state': pr['state'],
            'merged': pr.get('merged') is True,
            'requested': sorted(pr['requested_reviewers'] + pr['requested_teams']),
            'seen': seen,
            'checks': {row['name']: row['conclusion'] if row['state'] == 'completed' else row['state']
                       for row in measured['checks']}}


PASSING = ('success', 'neutral', 'skipped', 'queued', 'in_progress', 'pending', 'waiting', 'requested')


def summary(ref, before, after, fields):
    """One line naming what changed; never a bare 'changed'."""
    if fields == ['new'] or fields == ['gone']:
        return f'PR {ref}: ' + ('now watched' if fields == ['new'] else 'no longer owned')
    parts = []
    if before is not None and after is not None:
        if after['merged'] and not before['merged']:
            parts.append('merged')
        elif after['state'] == 'closed' and before['state'] != 'closed':
            parts.append('closed')
        if after['head'] != before['head']:
            parts.append(f'new commits pushed (head {after["head"][:7]})')
        if after['mergeable'] is False and before['mergeable'] is not False:
            parts.append('conflicts with its base')
        elif after['mergeable'] is True and before['mergeable'] is False:
            parts.append('conflicts resolved')
        new = [(key.split(':')[0], *value) for key, value in after['seen'].items()
               if key not in before['seen']]
        groups = Counter(row for row in new if row[0] != 'review')
        for (surface, author, path), count in sorted(groups.items(), key=lambda pair: pair[0][0] != 'thread'):
            noun = 'review comment' if surface == 'thread' else 'comment'
            parts.append(f'{count} new {noun}{"s" if count > 1 else ""} by {author}'
                         + (f' on {path}' if path else ''))
        reviews = {'approved': 'approved by', 'changes_requested': 'changes requested by',
                   'commented': 'review by'}
        parts += [f'{reviews[state]} {author}' for surface, author, state in new
                  if surface == 'review' and state in reviews]
        for name, value in after['checks'].items():
            old = before['checks'].get(name)
            if value != old and value not in PASSING and value is not None:
                parts.append(f'check {name} failed')
            elif value == 'success' and old is not None and old not in PASSING:
                parts.append(f'check {name} passed')
        added = [login for login in after['requested'] if login not in before['requested']]
        if added:
            parts.append(f'review requested from {", ".join(added)}')
    return f'PR {ref}: ' + ('; '.join(parts) or f'updated ({", ".join(fields)})')


def poll(root):
    """Preserve the baseline on failure and persist changes before announcing wake."""
    started = workspace.now()
    try:
        config = workspace.load_config(root)
        old = saved(root).get('prs')
        if old is None:
            old = previous(root).get('prs')
        if old is not None and not isinstance(old, dict):
            raise ValueError(f'invalid PR baseline; {DAMAGED}')
        old_facts = saved(root).get('facts')
        if old_facts is None:
            old_facts = previous(root).get('facts', {})
        if not isinstance(old_facts, dict):
            raise ValueError(f'invalid PR facts; {DAMAGED}')
        host, refs = owned(root, config)
    except ERRORS as exc:
        failures = saved(root).get('failures', 0) + 1
        save(root, {'failures': failures, 'measured_at': None}, kind='watch: read-failed',
             payload={'failures': failures, 'reason': str(exc)})
        print(f'watch PR read failed ({failures}): {exc}', flush=True)
        return 2

    current, new_facts, unreadable = {}, {}, False
    for ref in refs:
        try:
            from wuwei import pr_actions
            measured = evidence(host, ref, root)
            current[ref] = snapshot(host, ref, root, measured=measured)
            new_facts[ref] = facts(measured)
            pr_actions.observe(root, host, ref, config, measured)
        except ERRORS as exc:
            unreadable = True
            if ref not in current and old is not None and ref in old:
                current[ref] = old[ref]
            if ref not in new_facts and ref in old_facts:
                new_facts[ref] = old_facts[ref]
            state.append_event('watch: read-failed', {'pr': ref, 'reason': str(exc)}, root)
            print(f'watch PR read failed: {ref}: {exc}', flush=True)
    changes = {}
    if old is not None:
        for ref in sorted(old.keys() | current.keys()):
            if ref not in old:
                changes[ref] = ['new']
            elif ref not in current:
                changes[ref] = ['gone']
            elif old[ref] != current[ref]:
                changes[ref] = sorted(key for key in current[ref]
                                      if old[ref].get(key) != current[ref][key])
    # Save the wake before the baseline so interruption cannot lose a change.
    if changes:
        summaries = {ref: summary(ref, old_facts.get(ref), new_facts.get(ref), fields)
                     for ref, fields in changes.items()}
        (ref, fields), *rest = changes.items()
        mark_wake(root, prs=changes, summaries=list(summaries.values()), kind='pr.changed',
                  payload={'pr': ref, 'fields': fields, 'summary': summaries[ref]})
        for ref, fields in rest:
            state.append_event('pr.changed', {'pr': ref, 'fields': fields, 'summary': summaries[ref]}, root)
        for text in summaries.values():
            print(f'planner wake: {text}', flush=True)
    save(root, {'prs': current, 'facts': new_facts, 'failures': 0,
                'measured_at': None if unreadable else started.isoformat()})
    return 2 if unreadable else int(bool(changes))


def mark_wake(root, *, prs=(), inbox=0, summaries=(), kind, payload):
    """Merge into the planner wake; an unseen marker keeps its PRs, inbox count and summaries."""
    def mark(data):
        value = data.setdefault('watch', {})
        prior = previous(root) if 'wake' not in value else {}
        pending = value.get('wake', prior.get('wake'))
        seen = value.get('wake_seen_at', prior.get('wake_seen_at'))
        if pending and not prs and not summaries and inbox <= pending.get('inbox', 0):
            return  # already covered: a listener restart must not wake twice
        at, refs, count, lines = workspace.now(), set(prs), inbox, list(summaries)
        if pending:
            at = max(at, obligations._time(pending['at']) + timedelta(microseconds=1))
            if seen != pending['at']:
                refs.update(pending['prs'])
                count = max(count, pending.get('inbox', 0))
                lines = pending.get('summaries', []) + lines
        # ponytail: last 20 summaries while unseen; a day-long idle planner reads the rest in nudges.
        value['wake'] = {'at': at.isoformat(), 'prs': sorted(refs),
                         **({'inbox': count} if count else {}),
                         **({'summaries': lines[-20:]} if lines else {})}
    state._write_state(mark, root, reserved=False, kind=kind, payload=payload)


def poll_prs(root):
    """One full PR read and merge reconcile: the shared step of the watch and the listener."""
    from wuwei import merge
    result = max(poll(root), merge.poll(root))
    save(root, {'poll_at': workspace.now().isoformat()})
    return result


def listening(root):
    """A live listener owns PR polling; the watch polls only without one."""
    return health(root, name='listen') == (0, '')


def tick(root):
    """Run due work once; persisted scheduler marks survive watch restarts."""
    config = workspace.load_config(root)
    now = workspace.now()
    before = saved(root)
    result = 0
    due = lambda key, seconds: (key not in before or
        (now - obligations._time(before[key])).total_seconds() >= seconds)
    old_health = health(root)
    if due('clock_at', config['watch']['clock_seconds']):
        save(root, {'clock_at': now.isoformat()}, kind='watch: clock')
        if 'clock_at' not in before:
            old_health = health(root)
    from wuwei import heartbeat
    result = max(result, heartbeat.beat(root))
    if due('poll_at', config['pr']['poll_seconds']) and not listening(root):
        result = max(result, poll_prs(root))
    if old_health[0] == 1 or due('sweep_at', config['watch']['sweep_seconds']):
        result = max(result, sweep(root, watch_health=old_health))
        save(root, {'sweep_at': now.isoformat(), 'activity_at': now.isoformat()})
    elif due('activity_at', ACTIVITY_SECONDS):
        code, _ = activity(root)
        result = max(result, code)
        save(root, {'activity_at': now.isoformat()})
    return max(result, pending_discovery(root))


def pending_discovery(root):
    """Run a seat-free discovery request recorded by a hook; a failure is recorded once."""
    try:
        rows = [row for row in records(workspace.day_dir(root) / 'events.jsonl')
                if row['kind'] in ('discovery.requested', 'discovery.intake', 'discovery.unmeasured')]
    except ERRORS as exc:
        print(f'watch discovery unmeasured: {exc}', flush=True)
        return 2
    if not rows or rows[-1]['kind'] != 'discovery.requested' or rows[-1]['payload'].get('trigger') != 'seat-free':
        return 0
    try:
        discovery.intake(root, trigger='seat-free')
        return 0
    except (*ERRORS, RuntimeError) as exc:
        state.append_event('discovery.unmeasured', {'reason': str(exc)}, root)
        print(f'watch discovery unmeasured: {exc}', flush=True)
        return 2


def serve(root, name, tick, delay, *, once=False, sleep=None, blind=lambda: False):
    """One named loop per workspace; stop cleanly on SIGTERM, SIGINT or interruption."""
    import fcntl
    import signal
    import threading

    stopping = threading.Event()
    sleep = stopping.wait if sleep is None else sleep
    with (root / f'.wuwei/{name}.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f'{name} could not run: another {name} holds the workspace lock', flush=True)
            return 2
        handlers = {}
        def stop(signum, frame):
            stopping.set()
        try:
            for signum in (signal.SIGTERM, signal.SIGINT):
                handlers[signum] = signal.signal(signum, stop)
            while not stopping.is_set():
                code = tick(root)
                if once:
                    return code
                if stopping.is_set():
                    break
                if blind():
                    return 2
                sleep(delay)
            return 0
        except KeyboardInterrupt:
            return 0
        finally:
            for signum, handler in handlers.items():
                signal.signal(signum, handler)


def run(root=None, *, once=False, sleep=None):
    """One watch per workspace; stop cleanly on SIGTERM, SIGINT or interruption."""
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    def blind():
        value = saved(root)
        if value.get('failures', 0) and ('prs' not in value or value['failures'] >= MAX_READ_FAILURES):
            print('watch blind: PR read failure limit reached', flush=True)
            return True
        return False
    return serve(root, 'watch', lambda root: tick(root),
                 min(60, config['pr']['poll_seconds'], config['watch']['clock_seconds'],
                     ACTIVITY_SECONDS, config['watch']['sweep_seconds']),
                 once=once, sleep=sleep, blind=blind)


def wake(root, *, consume=False):
    current = saved(root)
    prior = previous(root) if 'wake' not in current else {}
    value = current.get('wake', prior.get('wake'))
    seen = current.get('wake_seen_at', prior.get('wake_seen_at'))
    if value is None or value['at'] == seen:
        return ''
    obligations._time(value['at'])
    refs = [pull_request(ref) for ref in obligations._list(value['prs'])]
    count = value.get('inbox', 0)
    if type(count) is not int or count < 0:
        raise ValueError(f'invalid inbox wake; {DAMAGED}')
    lines = obligations._list(value.get('summaries', []))
    if not all(isinstance(line, str) and line for line in lines):
        raise ValueError(f'invalid wake summaries; {DAMAGED}')
    if not refs and not count and not lines:
        raise ValueError('empty planner wake marker; pass at least one PR ref, count or summary')
    message = '\n'.join([*lines, f'planner wake ({value["at"]}): ' + ', '.join(
        refs + ([f'inbox to line {count}'] if count else []))])
    if consume:
        def acknowledge(data):
            nonlocal message
            target = data.setdefault('watch', {})
            if (target.get('wake_seen_at') == value['at'] or
                    target.get('wake', value)['at'] != value['at']):
                message = ''
            else:
                # A newer marker racing this read remains unseen.
                target['wake_seen_at'] = value['at']
        state._write_state(acknowledge, root, reserved=False, kind='session: wake-seen',
                           payload={'at': value['at']})
    return message


def flush(root):
    """Check and sync the synchronous writer under its existing shared lock."""
    import os

    directory = workspace.day_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'state.lock').open('a') as lock:
        state.lock_ex(lock, 'state.lock')
        state.read_state(root)
        rows = records(directory / 'events.jsonl')
        if (directory / 'state.json').exists() and not rows:
            raise ValueError(f'state has no event history; {DAMAGED}')
        state._append_event('session: compact', {'events_checked': len(rows)}, directory)
        for name in ('state.json', 'events.jsonl'):
            path = directory / name
            if path.exists():
                with path.open('rb') as stream:
                    os.fsync(stream.fileno())
