"""The owner interview: one question table mapped to config keys, charter overrides and voice rules."""

from datetime import date, datetime
import json
import re
import zoneinfo

from wuwei import calibrate, workspace
from wuwei.merge import quiet
from wuwei.promotion import safe_path


BLOCK = '## Owner preferences (interview)\n'
ROLES = ('planner', 'shepherd', 'lead')
EXECUTABLE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*')
SOAK = 'only where the repository declares merge_deploys = false'
# The retro offers the merge question again after this many owner merges within this many days.
REASK_AFTER, REASK_DAYS = 3, 7
BACKLOG = 'https://github.com/taoq-ai/wuwei/issues/370'
LATER = f'Not supported yet, so WUWEI sets the adapter to none. Integrations backlog: {BACKLOG}'
MERGE_QUESTION = re.compile(r'Merge (?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#[0-9]+\?')


def _items(text):
    """Comma-separated free text: 1 to 20 items, each in the calibrate charset and not instruction-like."""
    items = [item.strip() for item in text.split(',') if item.strip()]
    if not 1 <= len(items) <= 20 or any(
            not calibrate.SAFE.fullmatch(item) or calibrate.instruction_like(item) for item in items):
        raise ValueError('expected 1 to 20 comma-separated items of letters, digits, spaces and ._/()*@+-')
    return items


def _windows(text):
    windows = [item.strip() for item in text.split(',') if item.strip()]
    if not 1 <= len(windows) <= 20:
        raise ValueError('expected 1 to 20 comma-separated HH:MM-HH:MM windows')
    for window in windows:
        quiet({'quiet_hours': [window]}, datetime(2000, 1, 1))
    return windows


def _hours(text):
    window, _, zone = text.strip().partition(' ')
    if len(_windows(window)) != 1:
        raise ValueError('expected one HH:MM-HH:MM window and a time zone')
    if zone.strip() not in zoneinfo.available_timezones():
        raise ValueError(f'unknown time zone {zone.strip()!r}')
    return {'planner': f'The owner works {window} in {zone.strip()}; '
                       'outside those hours only pages interrupt.'}


def _signature(text):
    items = _items(text)
    if len(items) != 1:
        raise ValueError('expected one signature without commas')
    return {'shepherd': f'Sign messages sent as the owner with: {items[0]}.'}


def _commands(text):
    items = _items(text)
    if any(not EXECUTABLE.fullmatch(item.split()[0]) for item in items):
        raise ValueError('start each command with a literal executable name')
    return {'deploy.deny': [item if item.endswith('*') else item + '*' for item in items]}


def _chat(text):
    """A Slack review channel ID, or the name of another tool, which is not supported yet."""
    text = text.strip()
    if re.fullmatch(r'[CG][A-Z0-9]*[0-9][A-Z0-9]*', text):
        return {'adapters.chat': 'slack', 'shepherd.review_channel': text}
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9 .+-]{0,39}', text) and not calibrate.instruction_like(text):
        return {'adapters.chat': 'none'}
    raise ValueError('expected a Slack channel ID such as C0123ABCD, or the name of another tool such as Email')


def _login(text):
    text = text.strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', text):
        raise ValueError('expected a code-host login such as pat-dev')
    return {'shepherd.lead_login': text, 'shepherd.min_reviewers': 1}


# The only definition of the interview. Effects: a dotted config key (`repos.` means each
# answered repository), a charter override role with one fixed sentence, or voice never phrases.
QUESTIONS = (
    {'id': 'merge', 'scope': 'repo', 'header': 'Merges', 'question': 'Who merges pull requests in {repo}?',
     'choices': (
         ('Owner merges', 'You merge every pull request yourself.', {'repos.merge.auto': False}),
         ('Auto, 30 min soak', (f'WUWEI merges once checks and reviews pass, 30 minutes after the last push or approval '
           f'(soak); {SOAK}.'),
          {'repos.merge.auto': True, 'repos.merge.soak_minutes': 30}),
         ('Auto, 2 hour soak', (f'WUWEI merges once checks and reviews pass, 2 hours after the last push or approval '
           f'(soak); {SOAK}.'),
          {'repos.merge.auto': True, 'repos.merge.soak_minutes': 120})),
     'free': None},
    {'id': 'gates', 'scope': 'repo', 'header': 'Reviewers',
     'question': 'How many reviewer agents check each change in {repo}? (gate floor)',
     'choices': (
         ('Standard', 'Every change gets three reviewer agents: architecture, quality and security '
                      '(standard floor).', {'repos.gates.floor': 'standard'}),
         ('Full', 'Every change gets three reviewer agents and is recorded at the highest level (full floor).', {'repos.gates.floor': 'full'}),
         ('Light', 'Small low-risk changes get one reviewer agent, the rest three (light floor).', {'repos.gates.floor': 'light'})),
     'free': None},
    {'id': 'quiet', 'scope': 'repo', 'header': 'Quiet hours', 'question': 'When must {repo} never auto-merge?',
     'choices': (
         ('No quiet hours', 'Auto-merge may run at any hour.', {'repos.merge.quiet_hours': []}),
         ('Nights', 'No auto-merge from 20:00 to 08:00.', {'repos.merge.quiet_hours': ['20:00-08:00']})),
     'free': (lambda text: {'repos.merge.quiet_hours': _windows(text)}, 'HH:MM-HH:MM, comma-separated')},
    {'id': 'interrupt', 'scope': 'workspace', 'header': 'Interrupts',
     'question': 'When should a pending decision interrupt you?',
     'choices': (
         ('Batch', 'Collect decisions that can wait and send them every two hours (digest).', {'planner': (
             'Batch pending owner decisions into the two-hourly digest; '
             'ask at once only when a decision blocks a running item.')}),
         ('At once', 'Ask each decision that cannot be undone as soon as it is ready (one-way door).', {'planner': (
             'Ask each one-way-door decision as soon as its record passes the lint.')}),
         ('Morning only', 'Hold decisions that block nothing until the next morning plan (morning gate).', {'planner': (
             'Hold decisions that block nothing for the next morning gate; pages still interrupt.')})),
     'free': None},
    {'id': 'decisions', 'scope': 'workspace', 'header': 'Decisions',
     'question': 'How should decisions be presented to you?',
     'choices': (
         ('Recommended first', 'Two or three options, the recommendation first.', {'planner': (
             'Present two or three options with the recommended option first.')}),
         ('Options only', 'The options without the recommendation marked.', {'planner': (
             'Present the options without marking the recommendation; the record keeps it.')}),
         ('Yes or no', 'Only the recommendation, as a yes or no question.', {'planner': (
             'Ask the recommendation as a yes or no question; the other options stay in the record.')})),
     'free': None},
    {'id': 'phone', 'scope': 'workspace', 'header': 'Phone',
     'question': 'What may messages to your phone say about a decision? (control plane)',
     'choices': (
         ('Summary', 'A one-line summary of each decision.', {'control_plane.content': 'summary'}),
         ('Nothing', 'Only that a decision is waiting.', {'control_plane.content': 'none'})),
     'free': None},
    {'id': 'hours', 'scope': 'workspace', 'header': 'Hours',
     'question': 'When do you work, and in which time zone?',
     'choices': (
         ('Office hours', '09:00 to 17:00 in this host time zone.', {'planner': (
             "The owner works 09:00-17:00 in this host's time zone; outside those hours only pages interrupt.")}),
         ('Any time', 'No working-hours rule.', {})),
     'free': (_hours, 'HH:MM-HH:MM Area/City')},
    {'id': 'avoid', 'scope': 'workspace', 'header': 'Avoid words',
     'question': 'Which words should messages sent as you never use?',
     'choices': (
         ('Defaults only', 'Only the built-in list of words to avoid (voice profile).', {}),
         ('Corporate filler', 'Never: synergy, circle back, touch base, leverage.',
          {'voice': ['synergy', 'circle back', 'touch base', 'leverage']})),
     'free': (lambda text: {'voice': _items(text)}, 'comma-separated phrases')},
    {'id': 'formality', 'scope': 'workspace', 'header': 'Formality', 'question': 'How formal is your writing?',
     'choices': (
         ('Plain', 'First names, no pleasantries.', {'shepherd': (
             'Write plainly and directly: first names, no pleasantries.')}),
         ('Neutral', 'A neutral professional register.', {'shepherd': (
             'Write in a neutral professional register.')}),
         ('Formal', 'Full sentences, a greeting and a sign-off.', {'shepherd': (
             'Write formally: full sentences, a greeting and a sign-off.')})),
     'free': None},
    {'id': 'signature', 'scope': 'workspace', 'header': 'Signature',
     'question': 'How do you sign messages sent as you?',
     'choices': (
         ('No signature', 'Messages end without a signature.', {'shepherd': (
             'Add no signature to messages sent as the owner.')}),
         ('First name', 'Messages end with your first name (owner.name).', {'shepherd': (
             'Sign messages sent as the owner with the first name in owner.name.')})),
     'free': (_signature, 'the signature, without commas')},
    {'id': 'risk', 'scope': 'workspace', 'header': 'Risk words',
     'question': 'Which other areas need extra care: three reviewers and your merge? (trust surface)',
     'choices': (
         ('Lead defaults', ('Only the built-in areas: auth, credentials, input parsing, scoping and permissions '
                           '(lead charter).'), {}),
         ('Money and data', 'Billing, payments and exports of personal data.', {'lead': (
             'Also set trust_surface for changes touching billing, payments or exports of personal data.')})),
     'free': (lambda text: {'lead': f"Also set trust_surface for changes touching: {', '.join(_items(text))}."},
              'comma-separated areas')},
    {'id': 'manual', 'scope': 'workspace', 'header': 'By hand',
     'question': 'Which commands do you always run yourself?',
     'choices': (
         ('Deployment ban only', 'Only deploy commands, which agents never run (deploy.deny).', {}),
         ('Package publishing', ('Agents also never run npm publish, twine upload, cargo publish or gem push '
                                '(deploy.deny).'),
          {'deploy.deny': ['npm publish*', 'twine upload*', 'cargo publish*', 'gem push*']})),
     'free': (_commands, 'comma-separated commands, each starting with an executable')},
    {'id': 'verbosity', 'scope': 'workspace', 'header': 'Verbosity',
     'question': 'How much should decisions and messages to you say?',
     'choices': (
         ('Brief', 'The question, scored options and the recommendation; the rest on request.',
          {'owner.verbosity.default': 'brief'}),
         ('Standard', 'Also the context, reversibility, blast radius and pre-mortem.',
          {'owner.verbosity.default': 'standard'}),
         ('Full', 'Every field of each record.', {'owner.verbosity.default': 'full'})),
     'free': None},
    {'id': 'posture', 'scope': 'workspace', 'header': 'Posture',
     'question': 'Where does WUWEI run here, and how hard should the guards stop it?',
     'choices': (
         ('Observe', 'Records what it would refuse and lets the call through; records and owner-only actions '
          'still refuse. For a first week or a sandbox (observe posture).', {'security.posture': 'observe'}),
         ('Guarded', 'Refuses changes to records, publishing and a changed plugin; warns on agents, outgoing '
          'text and MCP tools. For a real project (guarded posture).', {'security.posture': 'guarded'}),
         ('Strict', ('Refuses everything a guard would refuse. For a repository that deploys or shares '
                     'credentials (strict posture).'),
          {'security.posture': 'strict'})),
     'free': None},
    {'id': 'tracker', 'scope': 'workspace', 'header': 'Tracker', 'question': 'Where does your backlog live?',
     'choices': (
         ('None', 'Discovery reads no tracker backlog.', {'adapters.tracker': 'none'}),
         ('Linear', 'Discovery reads the Linear backlog; set LINEAR_API_KEY in .wuwei/env.',
          {'adapters.tracker': 'linear'}),
         ('GitHub Issues', LATER, {'adapters.tracker': 'none'}),
         ('Jira', LATER, {'adapters.tracker': 'none'})),
     'free': None},
    {'id': 'chat', 'scope': 'workspace', 'header': 'Chat',
     'question': 'Which tool does your team use for messages? Your DM and review pings go there.',
     'choices': (
         ('Slack', 'Setup connects your DM next (bin/wuwei setup slack); type the review channel ID '
          'to set it too.', {'adapters.chat': 'slack'}),
         ('Microsoft Teams', LATER, {'adapters.chat': 'none'}),
         ('Discord', LATER, {'adapters.chat': 'none'}),
         ('None', 'Reviewers are requested on the code host only.', {'adapters.chat': 'none'})),
     'free': (_chat, 'a Slack review channel ID such as C0123ABCD, or another tool such as Email '
                     '(not supported yet: ' + BACKLOG + ')')},
    {'id': 'review_bot', 'scope': 'workspace', 'header': 'Review bot',
     'question': 'Which review bot reads your pull requests?',
     'choices': (
         ('None', 'Discovery reads no review-bot findings.', {'adapters.review_bot': 'none'}),
         ('Greptile', 'Read Greptile scores and findings; set GREPTILE_API_KEY in .wuwei/env.',
          {'adapters.review_bot': 'greptile'})),
     'free': None},
    # Claude asks these: labels name people in the third person, never I or me.
    {'id': 'reviewers', 'scope': 'workspace', 'header': 'Reviewers', 'question': 'Who reviews your pull requests?',
     'choices': (
         ('Owner only', 'No second reviewer: you merge your own pull requests.', {'shepherd.min_reviewers': 0}),
         ('Code authors', 'Whoever touched the changed code is asked; at least one review before merge.',
          {'shepherd.min_reviewers': 1})),
     'free': (_login, "a teammate's code-host login, for example pat-dev")},
)


def question(qid):
    row = next((row for row in QUESTIONS if row['id'] == qid), None)
    if row is None:
        raise ValueError(f"unknown interview question {qid!r}; use one of: "
                         + ', '.join(row['id'] for row in QUESTIONS))
    return row


def effects(qid, answer):
    """The effects of one answer: a choice label (any case), else valid free text."""
    row = question(qid)
    if not isinstance(answer, str):
        raise ValueError(f'{qid}: expected text')
    for label, _, result in row['choices']:
        if label.casefold() == answer.strip().casefold():
            return result
    labels = ', '.join(label for label, _, _ in row['choices'])
    if row['free']:
        try:
            return row['free'][0](answer)
        except ValueError as exc:
            raise ValueError(f"{qid}: answer one of: {labels}, or {row['free'][1]} ({exc})") from None
    raise ValueError(f'{qid}: answer one of: {labels}')


def _answered(answers):
    """(row, repository or None, answer, effects) for each recorded answer, in table order."""
    for row in QUESTIONS:
        if row['id'] in answers:
            picked = answers[row['id']]
            for repo, answer in (sorted(picked.items()) if row['scope'] == 'repo' else [(None, picked)]):
                yield row, repo, answer, effects(row['id'], answer)


def _path(name, repo, config):
    parts = name.split('.')
    if parts[0] == 'repos':
        index = [r['name'] for r in config['repos']].index(repo)
        return ('repos', index, *parts[1:-1]), parts[-1]
    return tuple(parts[:-1]), parts[-1]


def settings(answers, config):
    """Config effects as calibrate (path, key, value) settings."""
    rows = [(*_path(name, repo, config), value) for _, repo, _, result in _answered(answers)
            for name, value in result.items() if '.' in name]
    if (('security',), 'posture', 'observe') in rows and not config.get('guards', {}).get('shadow_since'):
        rows.append((('guards',), 'shadow_since', workspace.now().date().isoformat()))
    return rows


def _role(row):
    """The charter override a workspace question writes to, if any."""
    return next((key for _, _, result in row['choices'] for key in result if key in ROLES), None)


def describe(answers, config):
    """One line per answer naming the config keys or the override it maps to."""
    lines = []
    for row, repo, answer, result in _answered(answers):
        parts = []
        for name, value in result.items():
            if '.' in name:
                path, key = _path(name, repo, config)
                parts.append(f"{'.'.join(map(str, (*path, key)))} = {json.dumps(value)}")
            elif name == 'voice':
                parts.append('.wuwei/memory/voice.md never: ' + ', '.join(value))
            else:
                parts.append(f'.wuwei/charters/{name}.md')
        if not parts and _role(row):
            parts.append(f'.wuwei/charters/{_role(row)}.md (no rule)')
        lines.append(f"- {row['id']}{f' ({repo})' if repo else ''}: {answer} -> "
                     + (', '.join(parts) or 'no change'))
    return lines


def load(root, config):
    """Today's answers, re-validated against the table and the configured repositories."""
    path = workspace.day_dir(root) / 'interview.json'
    if path.is_symlink():
        raise ValueError('interview.json must not be a symlink')
    if not path.exists():
        return {}
    try:
        answers = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(answers, dict):
            raise ValueError('expected an object')
        names = {repo['name'] for repo in config['repos']}
        for qid, value in answers.items():
            if question(qid)['scope'] == 'repo':
                if not isinstance(value, dict) or not value or not set(value) <= names:
                    raise ValueError(f'{qid}: expected answers keyed by configured repositories')
            elif not isinstance(value, str):
                raise ValueError(f'{qid}: expected one answer')
        list(_answered(answers))
    except ValueError as exc:
        raise ValueError(f'interview.json: {exc}') from None
    return answers


def _read(root, relative):
    path = safe_path(root, relative, label='interview target')
    return path.read_text(encoding='utf-8') if path.exists() else ''


def _proposals(root, answers):
    """Charter and voice proposals from today's answers: {target name: proposal}."""
    evidence = f'.wuwei/days/{workspace.day_dir(root).name}/interview.json'
    ids = '|'.join(row['id'] for row in QUESTIONS)
    proposals = {}
    for role in ROLES:
        today = {row['id']: result.get(role) for row, _, _, result in _answered(answers) if _role(row) == role}
        if not today:
            continue
        target = f'.wuwei/charters/{role}.md'
        found = re.search(rf'^{re.escape(BLOCK)}(?:- (?:{ids}): .*\n)*', _read(root, target), re.M)
        lines = dict(re.findall(r'^- (\w+): (.*)$', found[0], re.M)) if found else {}
        lines.update(today)
        text = BLOCK + ''.join(f"- {row['id']}: {lines[row['id']]}\n" for row in QUESTIONS
                               if lines.get(row['id']))
        if found and found[0] != text:
            proposals[role] = {'target': target, 'action': 'patch', 'old_text': found[0], 'text': text}
        elif not found and text != BLOCK:
            proposals[role] = {'target': target, 'action': 'add', 'text': text}
        else:
            continue
        proposals[role].update(reason='owner interview: ' + ', '.join(today), evidence=evidence)
    phrases = [phrase for _, _, _, result in _answered(answers) for phrase in result.get('voice', [])]
    if phrases:
        from wuwei.voice import parse_profile
        voice = _read(root, '.wuwei/memory/voice.md')
        known = {phrase.casefold() for phrase in parse_profile(voice).get('shared', {}).get('never', [])}
        lines = ''.join(f'- never: {p}\n' for p in dict.fromkeys(phrases) if p.casefold() not in known)
        if lines:
            heading = '## shared\n'
            proposals['voice'] = {'target': '.wuwei/memory/voice.md', **(
                {'action': 'patch', 'old_text': heading, 'text': heading + lines}
                if voice.count(heading) == 1 else {'action': 'add', 'text': heading + lines}),
                'reason': 'owner interview: avoid', 'evidence': evidence}
    return proposals


def record(root, config, picked):
    """Merge validated answers into today's interview.json and rewrite the interview proposals."""
    answers = load(root, config)
    for qid, value in picked.items():
        if question(qid)['scope'] == 'repo':
            answers.setdefault(qid, {}).update(value)
        else:
            answers[qid] = value
    names = {repo['name'] for repo in config['repos']}
    if any(not set(answers[row['id']]) <= names for row in QUESTIONS
           if row['scope'] == 'repo' and row['id'] in answers):
        raise ValueError('answers must name configured repositories')
    proposals = _proposals(root, answers)
    day = workspace.day_dir(root)
    (day / 'proposals').mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(day / 'interview.json', json.dumps(answers, indent=2, sort_keys=True) + '\n')
    for target in (*ROLES, 'voice'):
        path = day / 'proposals' / f'interview-{target}.json'
        if target in proposals:
            workspace.atomic_write(path, json.dumps(proposals[target], indent=2) + '\n')
        elif path.exists() or path.is_symlink():
            path.unlink()
    return answers


def _selected(ids, repos):
    """Rows for the given ids (all when empty) in table order, each with its repositories."""
    wanted = {question(qid)['id'] for qid in ids}
    rows = [row for row in QUESTIONS if not wanted or row['id'] in wanted]
    if any(row['scope'] == 'repo' for row in rows) and not repos:
        raise ValueError(calibrate.NO_REPOS)
    return [(row, repo) for row in rows for repo in (repos if row['scope'] == 'repo' else [None])]


def _put(picked, row, repo, answer):
    if repo:
        picked.setdefault(row['id'], {})[repo] = answer
    else:
        picked[row['id']] = answer


def ask(ids, repos):
    """Ask on this terminal until each answer is valid; a number picks a choice. EOFError propagates."""
    picked = {}
    for row, repo in _selected(ids, repos):
        print(f"\n{row['header']}: {row['question'].format(repo=repo)}")
        for number, (label, description, _) in enumerate(row['choices'], 1):
            print(f'  {number}. {label}: {description}')
        if row['free']:
            print(f"  or type your own: {row['free'][1]}")
        while True:
            reply = input('> ').strip()
            if reply.isdecimal() and 1 <= int(reply) <= len(row['choices']):
                reply = row['choices'][int(reply) - 1][0]
            try:
                effects(row['id'], reply)
                break
            except ValueError as exc:
                print(str(exc))
        _put(picked, row, repo, reply)
    return picked


def parse(pairs, repos):
    """ID=VALUE answers relayed from the widget path; a repository answer applies to each selected one."""
    picked = {}
    for pair in pairs:
        qid, separator, answer = pair.partition('=')
        if not separator:
            raise ValueError(f'expected ID=VALUE, got {pair!r}')
        answer = answer.strip()
        effects(qid.strip(), answer)
        for row, repo in _selected([qid.strip()], repos):
            _put(picked, row, repo, answer)
    return picked


def _recorded(root):
    """(question id, repository or None) for every answer a day's or archived day's interview.json
    records; membership only, so an answer from an older table still counts."""
    from wuwei.consolidation import day_records
    found = set()
    sources = []
    for base in ('days', 'archive'):
        for path in sorted((root / '.wuwei' / base).glob('*/interview.json')):
            name = path.relative_to(root / '.wuwei').as_posix()
            if path.is_symlink():
                raise ValueError(f'{name} must not be a symlink')
            sources.append((name, path.read_bytes))
    # ponytail: opens every archived day; index answers in a digest if calibrate gets slow.
    for path in sorted((root / '.wuwei/archive').glob('*/*.tar.gz')):
        day = path.name.removesuffix('.tar.gz')
        sources.append((path.relative_to(root / '.wuwei').as_posix(),
                        lambda day=day: (day_records(root, day) or {}).get('interview.json', '{}')))
    for name, read in sources:
        try:
            answers = json.loads(read())
        except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
            raise ValueError(f'{name}: {exc}') from None
        if not isinstance(answers, dict):
            raise ValueError(f'{name}: expected an object')
        for qid, value in answers.items():
            found |= {(qid, repo) for repo in value} if isinstance(value, dict) else {(qid, None)}
    return found


def widgets(root, repos):
    """The unanswered questions as AskUserQuestion widgets for the morning gate."""
    from wuwei import decision
    done = _recorded(root)
    return [{'id': row['id'], **({'repo': repo} if repo else {}), **decision.widget(
                decision.gate(root) + row['question'].format(repo=repo), row['header'],
                [(label, description) for label, description, _ in row['choices']],
                f'wuwei calibrate --answer "{row["id"]}=<label>"' + (f' --repo {repo}' if repo else ''))}
            for row, repo in _selected([], repos) if (row['id'], repo) not in done]


def reask(root):
    """Retro lines proposing merge.auto where the owner merged what the policy routed to them."""
    from wuwei import decision, state, watch

    found = {}
    try:
        config = workspace.load_config(root)
        today = workspace.now().date()
        for day in watch.days(root):
            if (today - date.fromisoformat(day.name)).days >= REASK_DAYS:
                break
            data = state.read_state(directory=day)
            for identifier in sorted(data.get('decision_outcomes', {})):
                option = decision.answered(data, identifier)
                path = day / 'decisions' / f'{identifier}.md'
                if option is None or path.is_symlink() or not path.is_file():
                    continue
                try:
                    fields, _ = decision.evaluate(path.read_text(encoding='utf-8'))
                    options = dict(decision.table(fields['Options'], ['Option', 'Description'], 'Options'))
                except ValueError:
                    continue
                match = MERGE_QUESTION.fullmatch(fields['Question'].strip())
                if match and options.get(option, '').casefold().startswith('merge'):
                    found.setdefault(match['repo'], []).append(f'{day.name} {identifier}')
    except (OSError, ValueError) as exc:
        return [f'- unmeasured: {exc}']
    lines = []
    for repo in config['repos']:
        evidence = found.get(repo['name'], [])
        if repo['merge']['auto'] or len(evidence) < REASK_AFTER:
            continue
        note = '' if repo['merge_deploys'] is False else ' (it applies only with merge_deploys = false)'
        lines.append(f"- {repo['name']}: you merged {len(evidence)} pull requests the merge policy routed "
                     f"to you in the last {REASK_DAYS} days ({', '.join(evidence)}). Proposed: "
                     f"repos.merge.auto = true{note}. "
                     f"Re-ask: bin/wuwei calibrate --interview merge --repo {repo['name']}")
    return lines
