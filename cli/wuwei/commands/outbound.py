"""Report outbound tiers without sending or creating drafts; learn unknown connectors (#492)."""

import json
import os
from pathlib import Path
import re
import sys

from wuwei import outward, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED


def register(subparsers):
    parser = subparsers.add_parser('outbound', help='inspect outbound approval policy')
    actions = parser.add_subparsers(dest='action', required=True)
    tier = actions.add_parser('tier', help='classify one JSON message from stdin')
    tier.set_defaults(func=run)
    learn_parser = actions.add_parser(
        'learn', help='propose an unknown connector, its work channels and people on one card (planner)')
    learn_parser.add_argument('--tool', required=True, help='the MCP tool the refusal named')
    learn_parser.add_argument('--as', dest='channel', choices=CHANNELS,
                              help='the channel when the tool name does not give one')
    learn_parser.add_argument('--channels', metavar='FILE', help='JSON channel listing (slack only)')
    learn_parser.add_argument('--people', metavar='FILE', help='JSON people listing (slack only)')
    learn_parser.add_argument('--owner', metavar='FILE',
                              help="JSON {user, dm} from the connector's identity call (slack only)")
    learn_parser.add_argument('--thread', metavar='FILE',
                              help="JSON {channel, thread_ts, participants} from the connector's replies tool (slack only)")
    learn_parser.set_defaults(func=learn)
    actions.add_parser('tiers', help='print the effective outbound tier table').set_defaults(func=tiers)
    explain_parser = actions.add_parser('explain', help='print the rows a draft passed and the row that held it')
    explain_parser.add_argument('draft', help='the draft id')
    explain_parser.set_defaults(func=explain)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field; {DAMAGED}')
        result[key] = value
    return result


def run(args):
    code, decision, why = UNRUN, 'draft', []
    try:
        inputs = json.load(sys.stdin, object_pairs_hook=_unique)
        kind = inputs.pop('kind', 'chat')
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        texts, _ = outward._text(inputs)
        code, decision = outward.classify('\n'.join(texts), root, config, inputs, kind=kind, why=why)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    print(json.dumps({'tier': decision, 'exit': code}))
    if decision == 'block':  # #496: refused with the row named; no draft.
        print(outward.blocked(why[0]), file=sys.stderr)
    elif code:
        reason = 'cannot classify policy, audience or message evidence; ' if code == UNRUN else ''
        print(f'outbound: {reason}deliver as a draft for the owner to send; save it as a draft (bin/wuwei drafts lists it)', file=sys.stderr)
    return code


KIND_RULES = ('no row: the kind rules decide (direct messages draft, tracker.auto, docs.auto, chat threads, '
              'a measured team pull request, routine replies in a team channel)')


def tiers(args):
    """#496: the effective table, owner rows tagged; strict marks the send rows it ignores."""
    try:
        config = workspace.load_config(workspace.find_workspace())
    except (OSError, ValueError) as exc:
        print(f'outbound tiers: {exc}', file=sys.stderr)
        return UNRUN
    strict = workspace.posture(config)[0] == 'strict'
    print(f"{'rule':<6}{'source':<9}row")
    for number, (row, source, note) in enumerate(outward.table(config), 1):
        ignored = strict and source == 'owner' and row['tier'] == 'send' and outward.reaches_client(row, config)
        print(f"{number:<6}{source:<9}{outward.render(row)}{note}{' (ignored under strict)' if ignored else ''}")
    umbrella = config['outbound']['default_tier']
    if umbrella == 'ask':
        print(f"{'-':<6}{'default':<9}{KIND_RULES}")
    print(f"{'-':<6}{'default':<9}{{ tier = \"{umbrella}\" }} (outbound.default_tier: what no row narrows, "
          "for chat, code host, mail and other)")
    return CLEAN


def explain(args):
    """#496: the stored rule of a draft and the table walked again with today's config."""
    # ponytail: recomputed with today's config; store the trace on the draft row if the owner
    # needs the table as it was.
    from wuwei import drafts, state
    from wuwei.guards.outward import DM_TOOL
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        row = drafts.read(state.read_state(root)).get(args.draft)
        if row is None:
            print(f'outbound explain: unknown draft {args.draft}; run bin/wuwei drafts for the queued ids',
                  file=sys.stderr)
            return FINDINGS
        inputs = dict(row['inputs'])
        if row['operation'] == 'dm' or re.search(DM_TOOL, row.get('tool') or '', re.IGNORECASE):
            inputs['is_dm'] = True
        why, trace = [], []
        code, decision = outward.classify(row['text'], root, config, inputs, kind=row['channel'],
                                          port=row['adapter'] != 'mcp', why=why, tool=row.get('tool'),
                                          trace=trace)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'outbound explain: {exc}; run bin/wuwei doctor', file=sys.stderr)
        return UNRUN
    print(f"{args.draft}: {row['tier_reason'].removeprefix(outward.APPROVAL_REQUIRED + ': ')}")
    print('\n'.join(trace))
    if why and why[0].startswith(('ask by rule', 'block by rule')):
        print(f'now: {why[0]}')
    elif trace and decision == 'send' and sum(line.endswith(': matched') for line in trace) == sum(
            line.startswith('party ') for line in trace):
        print('now: send by the table')
    else:
        print(f"now: no row decides; the {'kind rules' if trace else 'floors'} decide: "
              f"{why[0] if why else decision if code != UNRUN else 'cannot classify'}")
    return CLEAN


CHANNELS = workspace.SCHEMA['outward']['servers']['*'][2]
SHAPES = {'channels': {'id': str, 'name': str, 'members': int, 'shared': bool},
          'people': {'id': str, 'name': str, 'email': str}}
DRAFT = 'write the message as a draft for the owner to send'


def _problem(path, kind):
    return ValueError(f'{path}: expected a JSON list of {{{", ".join(SHAPES[kind])}}} objects with unique '
                      'ids of capitals and digits and names of 1 to 80 characters without a '
                      'control character, |, backtick, $ or backslash; write the file again')


def _rows(path, kind):
    """One listing file, validated: names reach a decision record and a card."""
    text = Path(path).read_text(encoding='utf-8')  # OSError: unreadable, the caller's exit 2
    try:
        rows = json.loads(text)
    except ValueError:
        raise _problem(path, kind) from None
    return _listing(rows, kind, _problem(path, kind))


def _listing(rows, kind, problem):
    shape = SHAPES[kind]
    if not isinstance(rows, list):
        raise problem
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != set(shape)
                or any(type(row[key]) is not kind_ for key, kind_ in shape.items())
                or not re.fullmatch(r'[A-Z0-9]+', row['id']) or row['id'] in seen
                or not re.fullmatch(r'[^\x00-\x1f\x7f|`$\\]{1,80}', row['name'])
                or row.get('members', 0) < 0
                or row.get('email') and not re.fullmatch(r'[^@\s]+@[^@\s]+', row['email'])):
            raise problem
        seen.add(row['id'])
    return rows


def _thread(path):
    """#526: the thread file the planner wrote from the connector's replies tool."""
    text = Path(path).read_text(encoding='utf-8')  # OSError: unreadable, the caller's exit 2
    problem = ValueError(f'{path}: expected a JSON object {{"channel", "thread_ts", "participants"}} with a '
                         'channel id of capitals and digits, a thread ts of digits dot digits and at least one participant '
                         f'as {{{", ".join(SHAPES["people"])}}} objects; write the file again')
    try:
        found = json.loads(text)
    except ValueError:
        raise problem from None
    if (not isinstance(found, dict) or set(found) != {'channel', 'thread_ts', 'participants'}
            or not isinstance(found['channel'], str) or not re.fullmatch(r'[A-Z0-9]+', found['channel'])
            or not isinstance(found['thread_ts'], str) or not re.fullmatch(r'\d+\.\d+', found['thread_ts'])
            or not found['participants']):  # a thread has at least its parent author; empty is fail-open
        raise problem
    return found['channel'], found['thread_ts'], _listing(found['participants'], 'people', problem)


def _owner(path):
    """#495: the owner's Slack identity file, validated; never the WUWEI app DM, which the
    listener reads as owner input."""
    text = Path(path).read_text(encoding='utf-8')  # OSError: unreadable, the caller's exit 2
    try:
        found = json.loads(text)
    except ValueError:
        found = None
    if (not isinstance(found, dict) or set(found) != {'user', 'dm'}
            or not all(isinstance(value, str) for value in found.values())
            or not re.fullmatch(outward.SLACK_SHAPE['user'], found['user'])
            or found['dm'] and not re.fullmatch(outward.SLACK_SHAPE['dm'], found['dm'])
            or found['dm'] and found['dm'] == os.environ.get('SLACK_OWNER_DM_CHANNEL')):
        raise ValueError(f'{path}: expected a JSON object {{"user", "dm"}} with the owner\'s Slack user id (U or W) '
                         "and the owner's own DM id (D, or empty), not the WUWEI app DM; write the file again")
    return found


def _record_text(root, data):
    """Today's plan.md and decision records, symlinks skipped; learn's own cards left out."""
    day = workspace.day_dir(root)
    own = set(data.get('outbound_learn', {}))
    paths = [day / 'plan.md', *sorted((day / 'decisions').glob('D-*.md'))]
    return '\n'.join(path.read_text(encoding='utf-8') for path in paths
                     if path.is_file() and not path.is_symlink() and path.stem not in own)


def propose(root, config, data, server, channel, tool, channels, people, *, card, owner=None,
            participants=(), thread=None):
    """The proposal for one connector from today's state, or None when nothing is new."""
    rules = config['outbound']
    new_owner = {key: value for key, value in (owner or {}).items()
                 if value and not rules['owner']['slack'][key]}  # #495: never replaces one
    alias = server.casefold() not in {name.casefold() for name in config['outward']['servers']}
    # #496: a channel shared with an external org is client, the rest team.
    new_channels = [{'id': row['id'], 'name': row['name'], 'members': row['members'],
                     'class': 'client' if row['shared'] else 'team'}
                    for row in channels if not row['id'].startswith('D')
                    and row['id'] not in rules['external_channels']
                    and row['id'] not in rules['work_channels']]
    reviewers = {}  # login -> the organisation of a pull request it reviews
    for ref, logins in data.get('pr_reviewers', {}).items():
        for login in logins:
            reviewers.setdefault(login.casefold(), ref.split('/')[0])
    authors = config['shepherd']['authors']
    by_mention = {row['mention']: row['login'].casefold() for row in authors.values() if row['mention']}
    by_email = {email.casefold(): login.casefold()
                for email, login in data.get('author_logins', {}).items() if login}
    by_email.update({email.casefold(): row['login'].casefold() for email, row in authors.items()})
    known = {key.casefold() for key in rules['people']}
    domains = {domain.casefold() for domain in rules['company_domains']}
    orgs = {org.casefold() for org in rules['code_host_orgs']}
    text = _record_text(root, data) if card else ''
    new_people, skipped = [], 0
    for row in people:
        if f'slack:{row["id"]}'.casefold() in known:
            continue
        email = row['email'].casefold()
        login = next((login for login in (by_mention.get(row['id']), by_email.get(email))
                      if login in reviewers), None)
        named = card and (re.search(r'(?<!\w)' + re.escape(row['id']) + r'(?!\w)', text)
                          or email and email in text.casefold())
        if not (login or named):
            continue
        if email and email.rpartition('@')[2] in domains:
            entry = {'email': row['email'], 'class': 'team'}
        elif login and reviewers[login].casefold() in orgs:
            entry = {'org': reviewers[login], 'class': 'team'}
        else:
            skipped += 1
            continue
        new_people.append({'id': row['id'], 'name': row['name'], 'entry': entry,
                           'why': 'reviewer' if login else "named in today's records"})
    # #526: a thread's unknown participants are proposed; the email classes them.
    for row in participants:
        if row['id'] in {item['id'] for item in new_people}:
            continue
        domain = row['email'].rpartition('@')[2].casefold()
        found = 'team' if domain and domain in domains else 'client' if domain and domains else 'company'
        new_people.append({'id': row['id'], 'name': row['name'],
                           'entry': {**({'email': row['email']} if row['email'] else {}), 'class': found},
                           'why': f'in thread {thread}'})
    if skipped:
        print(f'not proposed: {skipped} people not internal by outbound.company_domains or '
              'outbound.code_host_orgs')
    if not (alias or new_channels or new_people or new_owner):
        return None
    return {'server': server, 'channel': channel, 'tool': tool, 'alias': alias,
            'channels': new_channels, 'people': new_people, 'owner': new_owner}


# #492 scope addition: the default mode of a class and what each mode does, for the card.
CLASS_MODES = {'slack': 'draft', 'mail': 'draft'}
MODE_TEXT = {
    'slack': 'routine sends to known work channels that mention known people go out; the rest draft.',
    'mail': 'every write drafts.',
    'tracker': 'writes follow the tracker tier as today.',
    'code_host': 'writes follow the code host tier as today.',
    'docs': 'writes follow the docs tier as today.',
    'other': 'writes go out after the lint and the sensitive, commitment and disagreement rows.',
    'send': 'Every write through this connector goes out after the lint (its row in bin/wuwei outbound tiers).',
    'draft': 'Every write through this connector is a draft.',
    'refuse': 'Every write through this connector is refused.'}


def _count(n, one, many):
    return f'{n} {one if n == 1 else many}'


CLASS_TEXT = {'team': 'Its routine sends go out after the lint.',
              'client': 'Its sends ask; its commitments and disagreements are blocked.',
              'company': 'Sends that reach this person ask.'}


def _other_class(row):
    """#496: the class the learn card offers instead of the proposed one."""
    if 'entry' in row:
        return 'company' if row['entry'].get('class', 'team') == 'team' else 'team'
    return 'team' if row.get('class') == 'client' else 'client'


def record(proposal):
    """The decision record text (contracts/outbound-learn.md)."""
    server, n, m = proposal['server'], len(proposal['channels']), len(proposal['people'])
    client = sum(row.get('class') == 'client' for row in proposal['channels'])
    label = 'Slack' if proposal['channel'] == 'slack' else proposal['channel']
    owner = proposal.get('owner') or {}
    me = ', '.join(filter(None, [owner.get('user'), owner.get('dm') and f"DM {owner['dm']}"]))
    mine = ' and your identity' if owner else ''
    parts = ([_count(n - client, 'work channel', 'work channels')] if n - client else []) + (
        [_count(client, 'client channel', 'client channels')] if client else []) + (
        [_count(m, 'person', 'people')] if m else []) + ([f'your identity {me}'] if owner else [])
    default = CLASS_MODES.get(proposal['channel'], 'send')
    question = (f'Connector {server} is {label}, mode {default}'
                + (f'; add {", ".join(parts[:-1]) + " and " * (len(parts) > 1) + parts[-1]}?' if parts else '?'))
    lines = ''.join([f"- channel #{row['name']} ({row['id']}, {row['members']} members): {row.get('class', 'team')}"
                     f"{', shared with an external org' if row.get('class') == 'client' else ''}\n"
                     for row in proposal['channels']]
                    + [f"- person {row['name']} ({row['id']}, {row['why']}): {row['entry'].get('class', 'team')}\n"
                       for row in proposal['people']]
                    + [f"- owner {me} from the connector's identity call\n"] * bool(owner))
    # Scope addition: one option per other mode, so the owner changes the mode on this card.
    rows = [('approve', 'Approve', f'Records the alias, {n} channels and {m} people{mine}.',
             f'Mode {default}: {MODE_TEXT[proposal["channel"]]}', 9)]
    if n:
        rows.append(('channels', 'Approve channels only', f'Records the alias and {n} channels.',
                     'Mentions of these people still draft.', 5))
    rows.append(('keep', 'Defer: keep as drafts', 'Records nothing.',
                 'Every send through this connector stays a draft today.', 1))
    rows += [(other, f'Approve, mode {other}', f'Records the alias, {n} channels and {m} people{mine} with mode {other}.',
              MODE_TEXT[other], 3) for other in ('send', 'draft', 'refuse') if other != default]
    # #496: the card asks each entry's class; one option per entry approves with the other class.
    rows += [(f"{row['id']}-{found}", f"Approve, {prefix}{row['name']} ({row['id']}) as {found}",
              f"Records the same as Approve with {row['id']} as {found}.", CLASS_TEXT[found], 2)
             for prefix, entries in (('#', proposal['channels']), ('', proposal['people']))
             for row in entries for found in [_other_class(row)]]
    ids = ' | '.join(row[0] for row in rows)
    return f'''Question: {question}
Class: other
Context: Proposed by bin/wuwei outbound learn from the planner's listing of connector {server} for tool {proposal['tool']}.
{lines}Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
{''.join(f'| {row[0]} | {row[1]} | {row[2]} | {row[3]} |{chr(10)}' for row in rows)}Musts:
| Criterion | {ids} |
| --- |{' --- |' * len(rows)}
| Only listed channels and reviewed or recorded people |{' pass |' * len(rows)}
Wants:
| Criterion | Weight | {ids} |
| --- | --- |{' --- |' * len(rows)}
| Sends without typing config | 10 | {' | '.join(str(row[4]) for row in rows)} |
Recommendation: approve
Reasoning: The listing names these channels and the people are the day's reviewers or named in its records; a channel shared with another organisation is client, so its sends ask and its commitments are blocked.
Confidence: medium
Reversibility: two-way
Blast radius: Outbound policy for connector {server}.
Pre-mortem: A listed channel is shared with another company and a routine send reaches it.
Revisit: Reopen if a send reaches the wrong audience.
Decided-by: owner
Outcome: pending
'''


def _widget(root, config, identifier):
    from wuwei import decision
    fields, _ = decision.evaluate(decision.today_path(identifier, root).read_text(encoding='utf-8'))
    print(json.dumps([decision.record_widget(identifier, fields,
                                             level=workspace.verbosity(config, 'decisions'))], indent=2))


def ask(root, config, proposal):
    """Write the record, route it to the owner, store the proposal and print the widget."""
    from wuwei import decision, state
    text = record(proposal)
    identifier = decision.write(text, root).stem
    fields, _ = decision.evaluate(text)
    decision.route_owner(identifier, fields, root)
    state._write_state(lambda data: data.setdefault('outbound_learn', {}).__setitem__(
        identifier, {**proposal, 'answered': None}), root, reserved=False, kind='outbound.proposed',
        payload={'id': identifier, 'server': proposal['server'], 'channel': proposal['channel']})
    _widget(root, config, identifier)
    return CLEAN


def apply(root, proposal, option, decision_id=None):
    """Write what the answer approved through the owner edit frame; the answer is the
    confirmation. One outbound.learned event (ids only) after a write."""
    from wuwei import state
    from wuwei.commands import setup
    choice = option
    for row in [*proposal['channels'], *proposal['people']]:
        if option == f"{row['id']}-{_other_class(row)}":  # #496: approve with this entry's other class
            found, choice = _other_class(row), 'approve'
            proposal = {**proposal,
                        'channels': [{**item, 'class': found} if item is row else item
                                     for item in proposal['channels']],
                        'people': [{**item, 'entry': {**item['entry'], 'class': found}} if item is row else item
                                   for item in proposal['people']]}
            break
    mode = choice if choice in ('send', 'draft', 'refuse') else None
    rows = proposal['channels'] if choice in ('approve', 'channels') or mode else []
    channels = [row['id'] for row in rows]
    client = [row['id'] for row in rows if row.get('class') == 'client']
    team = [key for key in channels if key not in client]
    people = [row for row in proposal['people']] if choice == 'approve' or mode else []
    alias = proposal['alias'] and (choice in ('approve', 'channels') or bool(mode))
    owner = (proposal.get('owner') or {}) if choice == 'approve' or mode else {}  # #495
    if not (alias or channels or people or mode or owner):
        return CLEAN

    def change(_, raw):
        config = workspace.load_config(root, raw=raw)
        settings = [(('outward', 'servers'), proposal['server'], proposal['channel'])] if alias else []
        settings += [(('outward', 'modes'), proposal['server'], mode)] if mode else []
        for key, ids in (('work_channels', team), ('external_channels', client)):  # #496: by class.
            if ids:
                settings += setup.merged(config, ['outbound', key], ids)
        settings += [(('outbound', 'people'), f"slack:{row['id']}", row['entry']) for row in people]
        settings += [(('outbound', 'owner', 'slack'), key, value) for key, value in owner.items()]
        return setup._settle(raw, settings)

    code = setup._edit('outbound learn', 'learned connector', lambda *args, **kwargs: True, change, root)
    if code == CLEAN:
        state.append_event('outbound.learned', {
            'decision': decision_id, 'option': option, 'mode': 'card' if decision_id else 'auto',
            'server': proposal['server'], 'channel': proposal['channel'], 'alias': alias,
            'connector_mode': mode, 'channels': channels, 'people': [row['id'] for row in people],
            'owner': bool(owner)}, root)
        from wuwei import graph  # #552: names and a thread's members, which no config key holds
        names = {**{f"channel:{row['id']}": row['name'] for row in rows},
                 **{f"person:slack:{row['id']}": row['name'] for row in people}}
        where = proposal.get('thread_channel')
        members = [{'from': f"person:slack:{row['id']}", 'type': 'member_of', 'to': f'channel:{where}',
                    **({'card': decision_id} if decision_id else {})}
                   for row in people if where and row['why'].startswith('in thread')]
        try:
            graph.sync(root, workspace.load_config(root), members, names)
        except (OSError, ValueError) as exc:  # A13: the config write stands
            graph.warn('outbound learn', exc)
    return code


def learn(args):
    """Planner command: the contract flow, top to bottom; the first exit wins."""
    def fail(text, code=FINDINGS):
        print(f'outbound learn: {text}', file=sys.stderr)
        return code

    from wuwei import state
    from wuwei.guards.outward import resolve
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        data = state.read_state(root)
    except (OSError, ValueError) as exc:
        return fail(f'{exc}; run bin/wuwei doctor', UNRUN)
    if config['outbound']['learn'] == 'off':
        return fail(f'outbound.learn is off; {DRAFT}')
    tool = args.tool
    server = tool[5:].rpartition('__')[0]
    if not re.fullmatch(r'mcp__[A-Za-z0-9_-]+', tool) or not server:
        return fail('--tool: expected mcp__<server>__<tool>; pass the tool the refusal named')
    found = resolve(tool, config)
    if args.channel and found and args.channel not in found:
        # Verify #492: --as names a channel for a connector that has none; it never lowers one.
        return fail(f'connector {server} already resolves to {", ".join(sorted(found))}; --as cannot change it; '
                    'the owner changes outward.servers in a host terminal')
    channel = args.channel or (next(iter(found)) if len(found) == 1 else None)
    if channel is None:
        return fail(f'connector {server} has no channel; pass --as slack, tracker, code_host, docs, mail or other')
    unknown, thread = [], None
    if args.thread:  # #526: record the participants before any card; known ones need none.
        if channel != 'slack':
            return fail('listings apply to a slack connector; run it without --channels, --people, --owner and --thread')
        try:
            target, thread, participants = _thread(args.thread)
        except OSError as exc:
            return fail(f'cannot read a listing: {exc}; write the file under today\'s day directory', UNRUN)
        except ValueError as exc:
            return fail(str(exc))
        name = f'{target}/{thread}'
        try:
            state._write_state(lambda data: data.setdefault('outbound_threads', {}).__setitem__(
                name, [row['id'] for row in participants]), root, reserved=False, kind='outbound.thread',
                payload={'thread': name, 'participants': len(participants)})
        except (OSError, ValueError) as exc:
            return fail(f'{exc}; run bin/wuwei doctor', UNRUN)
        known = {key.casefold() for key in config['outbound']['people']}
        mine = config['outbound']['owner']['slack']['user'].casefold()
        unknown = [row for row in participants
                   if f"slack:{row['id']}".casefold() not in known and row['id'].casefold() != mine]
        if not (unknown or args.channels or args.people or args.owner):
            print(f'outbound learn: recorded {len(participants)} participants of thread {name}; send the reply again')
            return CLEAN
    learned = data.get('outbound_learn', {})
    open_card = next((key for key, row in learned.items() if row.get('answered') is None), None)
    if open_card:
        _widget(root, config, open_card)
        return CLEAN
    kept = next((key for key, row in learned.items() if row.get('answered') == 'keep'
                 and row['server'].casefold() == server.casefold()), None)
    if kept:
        return fail(f'connector {server} was kept as drafts today ({kept}); {DRAFT}')
    if (args.channels or args.people or args.owner) and channel != 'slack':
        return fail('listings apply to a slack connector; run it without --channels, --people and --owner')
    if channel == 'slack' and not (args.channels or args.people or args.owner or args.thread):
        # #495: while the owner's identity is missing, the same step asks for it.
        identity = ('' if all(config['outbound']['owner']['slack'].values()) else
                    ", and its identity tool (auth_test, users_me, whoami, or the tool whose name says "
                    'identity or profile); write the owner\'s user id and own DM channel id as {"user", '
                    '"dm"} in a JSON file and add --owner <file>')
        return fail(f'connector {server} needs its listings; call its channel listing tool (channels_list, '
                    'conversations_list or slack_search_channels) and its user listing tool (users_list '
                    'or slack_search_users), write the channels the message goes to as [{"id", "name", '
                    '"members", "shared"}] and the people it mentions as [{"id", "name", "email"}] in JSON '
                    f'files under today\'s day directory, then run bin/wuwei outbound learn --tool {tool} '
                    f'--channels <file> --people <file>{identity}')
    try:
        channels = _rows(args.channels, 'channels') if args.channels else []
        people = _rows(args.people, 'people') if args.people else []
        owner = _owner(args.owner) if args.owner else {}
    except OSError as exc:
        return fail(f'cannot read a listing: {exc}; write the file under today\'s day directory', UNRUN)
    except ValueError as exc:
        return fail(str(exc))
    # `other` carries mode send with no audience rules, so it is never learned without the card.
    strict = workspace.posture(config)[0] == 'strict'
    card = config['outbound']['learn'] == 'card' or strict or channel == 'other'
    if owner and not channels and not people and not strict:
        card = False  # #537: the owner's own identity, from the connector's identity call, needs no card.
    proposal = propose(root, config, data, server, channel, tool, channels, people, card=card, owner=owner,
                       participants=unknown, thread=thread)
    if proposal is None:
        return fail(f'nothing new to learn for connector {server}; {DRAFT}')
    if args.thread:
        proposal['thread_channel'] = target  # #552: apply records the members of this channel
    try:
        return ask(root, config, proposal) if card else apply(root, proposal, 'approve')
    except (OSError, ValueError) as exc:
        return fail(f'{exc}; run bin/wuwei doctor', UNRUN)
