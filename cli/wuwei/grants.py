"""#478: an owner-only action asks the owner on a decision card; the recorded answer is the grant."""

from fnmatch import fnmatchcase
from pathlib import PurePosixPath
import re


ACTIONS = {'deploy': ('deploy', 'deploys'), 'release': ('release', 'releases'),
           'publish': ('publish action', 'publishes'),
           'evidence': ('publish without evidence', 'publishes without evidence'),  # #530
           'merge': ('merge', 'merges')}  # #524
REPO = r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
RELEASES = ('release create', 'tag push', 'release API', 'tag or branch ref API')
# #518: every owner-only step a lead may list, with its target shape. Those in ACTIONS (deploy,
# release, publish and, #524, merge) become grant cards; message and secret-set are owner steps.
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


def action(rule):
    """The action class a deploy guard rule refuses; #530: an evidence miss of a push or PR raise."""
    if rule.startswith('evidence: '):
        return 'evidence'
    if rule.startswith('merge: '):  # #524: wuwei merge; merge_deploys and environment rules stay deploy
        return 'merge'
    return 'release' if rule in RELEASES else 'publish' if rule.startswith('deploy.deny: ') else 'deploy'


def target(root, config, cwd, repo):
    """repo:<org>/<name> from the repository the command names, else the one configured
    repository holding cwd; None when neither is a plain org/name."""
    if repo is None:
        from wuwei import merge
        try:
            found = merge.configured(root, config, cwd)
        except (OSError, ValueError, KeyError, TypeError):  # vcs unreadable: no target, no card
            found = []
        repo = found[0] if len(found) == 1 else None
    return f'repo:{repo}' if isinstance(repo, str) and re.fullmatch(REPO, repo) else None


def _record(question, context, rows, criterion, recommendation, reasoning, blast, premortem,
            revisit='Revoke a standing grant with bin/wuwei grants revoke.'):
    """A decision record from (id, title, rationale, consequence, score) rows."""
    ids, cells = ' | '.join(row[0] for row in rows), ' --- |' * len(rows)
    return f'''Question: {question}
Class: other
Context: {context}
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
{''.join(f'| {row[0]} | {row[1]} | {row[2]} | {row[3]} |{chr(10)}' for row in rows)}Musts:
| Criterion | {ids} |
| --- |{cells}
| Owner decides |{' pass |' * len(rows)}
Wants:
| Criterion | Weight | {ids} |
| --- | --- |{cells}
| {criterion} | 10 | {' | '.join(str(row[4]) for row in rows)} |
Recommendation: {recommendation}
Reasoning: {reasoning}
Confidence: medium
Reversibility: one-way
Blast radius: {blast}
Pre-mortem: {premortem}
Revisit: {revisit}
Decided-by: owner
Outcome: pending
'''


def ask(root, row, text):
    """Write the card, route it to the owner and store its grant row; returns D-n."""
    from wuwei import decision, state
    identifier = decision.write(text, root).stem
    fields, _ = decision.evaluate(text)
    decision.route_owner(identifier, fields, root)
    state._write_state(lambda data: data.setdefault('grants', {}).__setitem__(
        identifier, {**row, 'answered': None, 'spent': False}), root, reserved=False, kind='grant.asked',
        payload={'id': identifier, 'action': row['action'], 'target': row['target'], 'planned': row['planned']})
    return identifier


def active(config, data, name, found, standing=True):
    """(scope, D-n) of the grant that lets this action on this target through, else None;
    standing=False leaves the [grants] lines out (#556: a novel target)."""
    from wuwei import workspace
    if standing and workspace.posture(config)[0] != 'strict':
        for line in config['grants']['standing']:
            if line['action'] == name and fnmatchcase(found, line['target']):
                return 'always', line['decision']
    hits = [(row['answered'], key) for key, row in data.get('grants', {}).items()
            if (row['action'], row['target']) == (name, found) and (
                row['answered'] == 'today' and not data.get('close_requested')
                or row['answered'] == 'once' and not row['spent'])]
    return min(hits, key=lambda hit: hit[0] != 'today', default=None)


def merge_tier(config):
    """#524: with no grant, ask (a card) or owner_only (the host-terminal command); unset follows the posture."""
    from wuwei import workspace
    return config['merge']['default_tier'] or (
        'owner_only' if workspace.posture(config)[0] == 'strict' else 'ask')


def gate(payload, root, config, argv, rule, repo, moved=False, pr=None):
    """The deploy guard's owner-only result: (0, use) on a matching grant, where the caller
    calls use() to record or spend it once the whole call passes, else exit 1 with the reason
    naming the action, the target and the card the owner answers. A moved command (cd, git -C,
    GIT_*) gets no cwd target. #524: pr (org/name#n) also matches a planned pr: card."""
    from wuwei import state, workspace
    from wuwei.commands import hook
    from wuwei.exits import RACE
    from wuwei.guards.deploy import PERMISSIONS_DENY
    name = action(rule)
    noun = ACTIONS[name][0]
    command = ' '.join(hook.redacted_target(payload, root).split())
    tail = f'is a {noun} ({rule}), owner-only under {workspace.posture(config)[0]}'
    missing = rule.removeprefix('evidence: ')
    if name == 'evidence':  # #530: never a host-terminal step; the seat runs the check
        tail = f'has no recorded evidence ({missing})'
    elif payload.get('session_id') == hook.HEARTBEAT_SESSION:
        return 1, f'publish: {command} {tail}; ask the owner to run it in a host terminal'
    text = ' '.join([PurePosixPath(argv[0]).name, *argv[1:]])
    if name != 'evidence' and any(fnmatchcase(text, pattern[5:-1]) for pattern in PERMISSIONS_DENY):
        return 1, (f'publish: {command} {tail}; the workspace permissions deny it, so no grant lifts it: '
                   'ask the owner to run it in a host terminal')
    found = None if moved and repo is None else target(root, config, payload['cwd'], repo)
    if found is None and name == 'evidence':
        return 1, missing
    if found is None:
        return 1, (f'publish: {command} {tail}; name the repository with -R <org>/<repo> or run it from '
                   'a configured repository so the owner can decide on a card')
    head = f'publish: {command} on {found[5:]} {tail}'
    from wuwei import novelty
    novel = (novelty.novel(root, config, [found])
             if name != 'evidence' and config['autonomy']['mode'] == 'autonomous' else [])
    if novel:  # #556: a standing line never covers a target the workspace never touched
        head += f'; {novelty.line(novel)}'
    data = state.read_state(root)
    hit, where = active(config, data, name, found, standing=not novel), found
    if not hit and pr:
        hit, where = active(config, data, name, f'pr:{pr}', standing=False), f'pr:{pr}'
    if hit:
        scope, identifier = hit
        used = {'decision': identifier, 'action': name, 'target': where, 'scope': scope,
                'session': payload.get('session_id'), 'item': hook.claimed(root, payload.get('session_id'))}
        if scope != 'once':
            return 0, lambda: state.append_event('grant.used', used, root)

        def spend(current):
            row = current.get('grants', {}).get(identifier, {})
            if row.get('answered') != 'once' or row.get('spent') is not False:
                raise ValueError(f'grants: {identifier} changed; {RACE}')
            row['spent'] = True

        return 0, lambda: state._write_state(spend, root, reserved=False, kind='grant.used', payload=used)
    rows = {key: row for key, row in data.get('grants', {}).items()
            if (row['action'], row['target']) == (name, found)}
    kept = next((key for key, row in rows.items() if row['answered'] == 'keep'), None)
    if kept and name == 'evidence':
        return 1, f'{head}; the owner asked for the check first ({kept}): run it, then retry'
    if kept:
        return 1, f'{head}; the owner kept it owner-only ({kept}): ask the owner to run it in a host terminal'
    identifier = next((key for key, row in rows.items() if row['answered'] is None), None)
    if identifier is None:
        strict = workspace.posture(config)[0] == 'strict'
        repo_name, item = found[5:], hook.claimed(root, payload.get('session_id'))
        seat = payload.get('agent_type') or 'main session'
        options = [('keep', 'Keep owner-only', 'Nothing runs from the session.',
                    'You run the command in a host terminal.', 9),
                   ('once', 'Allow once', f'The seat runs this {noun} on {repo_name} once.',
                    'The next run asks again.', 7),
                   ('today', 'Allow today', f'Every {noun} on {repo_name} runs until wuwei close.',
                    'Each run is recorded as grant.used.', 5),
                   ('always', 'Always allow', 'A standing grant in config.toml [grants].',
                    'Later days too, until bin/wuwei grants revoke.', 3)][:3 if strict else 4]
        texts = (f'Allow {name} on {repo_name}?',
                 f'{command} is a {noun} ({rule}). Target: {found}. Item: {item or "none"}. Seat: {seat}.',
                 'A grant lets a seat run an action that cannot be undone; keep it unless this run is expected.',
                 f'{noun} on {repo_name}.', f'A seat runs the {noun} at the wrong time or on the wrong branch.')
        if name == 'evidence':  # #530: no Always allow, so the standing-grant schema is unchanged
            options = [('keep', 'Defer until the check passes', 'The seat runs the named check, then retries.',
                        'Nothing publishes without its evidence.', 9), *options[1:3]]
            texts = (f'Publish on {repo_name} without its evidence?',
                     f'{command} has no recorded evidence: {missing}. Target: {found}. Item: '
                     f'{item or "none"}. Seat: {seat}.',
                     'The check is cheap and the seat can run it; allow only when the check cannot run.',
                     f'publish without evidence on {repo_name}.', 'The change publishes with a failing check.')
        identifier = ask(root, {
            'action': name, 'target': found, 'rule': rule, 'command': command, 'item': item,
            'seat': seat, 'planned': False}, _record(
            *texts[:2], options, 'Least standing access', 'keep', *texts[2:]))
    return 1, f'{head}; the owner decides: bin/wuwei decision show {identifier} --widget'


def evidence(payload, root, config, argv, reason, repo, record=False):
    """#530: a push or PR raise without its recorded evidence. Where publish warns, (1, reason)
    for the hook to record and let through, or with record (a CLI command, no hook) the
    guard.would_refuse event, the warning on stderr and (0, None); under strict (1, reason);
    otherwise the owner's card (run the check first, once, today)."""
    import sys
    from wuwei import state, workspace
    from wuwei.commands import hook
    name, levels = workspace.posture(config)
    if levels['publish'] == 'off':
        return 0, None
    if name == 'strict' or levels['publish'] == 'warn' and not record:
        return 1, reason
    if levels['publish'] == 'warn':
        state.append_event('guard.would_refuse', {
            'guard': 'pr', 'area': 'publish', 'level': 'warn', 'posture': name, 'reason': reason,
            'exit': 1, 'target': hook.redacted_target(payload, root), 'session': payload.get('session_id'),
            'item': hook.claimed(root, payload.get('session_id'))}, root)
        print(f'warning: {reason}', file=sys.stderr)
        return 0, None
    return gate(payload, root, config, argv, 'evidence: ' + reason, repo)


def standing(root, row, identifier):
    """Write the [grants] line an Always allow answer creates; the answer is the confirmation."""
    import sys
    from wuwei import workspace
    from wuwei.commands import setup
    from wuwei.exits import FINDINGS
    if workspace.posture(workspace.load_config(root))[0] == 'strict':
        print('decide: Always allow is not offered under strict; answer Allow today or Allow once',
              file=sys.stderr)
        return FINDINGS
    line = {'action': row['action'], 'target': row['target'], 'scope': 'always', 'decision': identifier,
            'date': workspace.now().date().isoformat()}
    return setup._edit('decide', 'standing grant', lambda *args, **kwargs: True,
                       lambda _, raw: setup.write_value(raw, 'grants.standing', [line], mode='append'), root)


def plan(root, config, candidates):
    """One planned card per owner-only action the lead lists; {item: [(action, target, D-n)]}.
    A planned card already written today for the same item, action and target is reused."""
    from wuwei import state, workspace
    strict = workspace.posture(config)[0] == 'strict'
    rows = state.read_state(root).get('grants', {})
    found = {}
    for item in candidates:
        for entry in item.get('owner_actions', []):
            if understood(entry) or entry['action'] not in ACTIONS:
                continue  # #518: an owner step the plan lists, not a grant card
            name, repo_target = entry['action'], entry['target']
            identifier = next((key for key, row in rows.items() if row['planned'] and (
                row['item'], row['action'], row['target']) == (item['id'], name, repo_target)), None)
            if identifier is None:
                noun, verb = ACTIONS[name]
                repo_name, goal = repo_target.split(':', 1)[1], item.get('goal', 'unplanned')  # #524: pr: too
                score = (3, 5, 9) if strict else (9, 5, 1)
                identifier = ask(root, {
                    'action': name, 'target': repo_target, 'rule': 'planned', 'command': None,
                    'item': item['id'], 'goal': goal, 'seat': None, 'planned': True}, _record(
                    f'{goal} {item["id"]} {verb} {repo_name}: allow today, ask when it happens, or keep owner-only?',
                    f'Planned in days/{workspace.day_dir(root).name}/plan.md for {item["id"]}. Target: {repo_target}.',
                    [('today', 'Allow today', f'The {noun} runs without asking today.',
                      'Each run is recorded as grant.used.', score[0]),
                     ('ask', 'Ask when it happens', 'The first run asks on a card.',
                      'The day stops once for it.', score[1]),
                     ('keep', 'Keep owner-only', 'Nothing runs from the session.',
                      'You run it in a host terminal.', score[2])],
                    'Least standing access' if strict else 'Day runs without interruption',
                    'keep' if strict else 'today',
                    'The plan names this step; allow it today so the day runs without stopping, unless the '
                    'timing is not settled.', f'{noun} on {repo_name}.',
                    f'A seat runs the {noun} before the change is ready.'))
                rows = state.read_state(root).get('grants', {})
            found.setdefault(item['id'], []).append((name, repo_target, identifier))
    return found


def gate_widgets(root, config):
    """The open planned cards as widgets, after the gate question, in id order."""
    from wuwei import decision, state, workspace
    rows = state.read_state(root).get('grants', {})
    level = workspace.verbosity(config, 'decisions')
    widgets = []
    for key in sorted((key for key, row in rows.items() if row['planned'] and row['answered'] is None),
                      key=lambda key: int(key[2:])):
        fields, _ = decision.evaluate(decision.today_path(key, root).read_text(encoding='utf-8'))
        widgets.append(decision.record_widget(key, fields, level=level))
    return widgets
