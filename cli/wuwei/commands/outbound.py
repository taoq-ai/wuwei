"""Report outbound tiers without sending or creating drafts; learn unknown connectors (#492)."""

import json
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
    learn_parser.set_defaults(func=learn)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field; {DAMAGED}')
        result[key] = value
    return result


def run(args):
    code, decision = UNRUN, 'draft'
    try:
        inputs = json.load(sys.stdin, object_pairs_hook=_unique)
        kind = inputs.pop('kind', 'chat')
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        texts, _ = outward._text(inputs)
        code, decision = outward.classify('\n'.join(texts), root, config, inputs, kind=kind)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    print(json.dumps({'tier': decision, 'exit': code}))
    if code:
        reason = 'cannot classify policy, audience or message evidence; ' if code == UNRUN else ''
        print(f'outbound: {reason}deliver as a draft for the owner to send; save it as a draft (bin/wuwei drafts lists it)', file=sys.stderr)
    return code


CHANNELS = workspace.SCHEMA['outward']['servers']['*'][2]
SHAPES = {'channels': {'id': str, 'name': str, 'members': int, 'shared': bool},
          'people': {'id': str, 'name': str, 'email': str}}
DRAFT = 'write the message as a draft for the owner to send'


def _rows(path, kind):
    """One listing file, validated: names reach a decision record and a card."""
    shape = SHAPES[kind]
    text = Path(path).read_text(encoding='utf-8')  # OSError: unreadable, the caller's exit 2
    problem = ValueError(f'{path}: expected a JSON list of {{{", ".join(shape)}}} objects with unique '
                         'ids of capitals and digits and names of 1 to 80 characters without a '
                         'control character, |, backtick, $ or backslash; write the file again')
    try:
        rows = json.loads(text)
    except ValueError:
        raise problem from None
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


def _record_text(root, data):
    """Today's plan.md and decision records, symlinks skipped; learn's own cards left out."""
    day = workspace.day_dir(root)
    own = set(data.get('outbound_learn', {}))
    paths = [day / 'plan.md', *sorted((day / 'decisions').glob('D-*.md'))]
    return '\n'.join(path.read_text(encoding='utf-8') for path in paths
                     if path.is_file() and not path.is_symlink() and path.stem not in own)


def propose(root, config, data, server, channel, tool, channels, people, *, card):
    """The proposal for one connector from today's state, or None when nothing is new."""
    rules = config['outbound']
    alias = server.casefold() not in {name.casefold() for name in config['outward']['servers']}
    new_channels = [{'id': row['id'], 'name': row['name'], 'members': row['members']}
                    for row in channels if not row['shared'] and not row['id'].startswith('D')
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
            entry = {'email': row['email']}
        elif login and reviewers[login].casefold() in orgs:
            entry = {'org': reviewers[login]}
        else:
            skipped += 1
            continue
        new_people.append({'id': row['id'], 'name': row['name'], 'entry': entry,
                           'why': 'reviewer' if login else "named in today's records"})
    if skipped:
        print(f'not proposed: {skipped} people not internal by outbound.company_domains or '
              'outbound.code_host_orgs')
    if not (alias or new_channels or new_people):
        return None
    return {'server': server, 'channel': channel, 'tool': tool, 'alias': alias,
            'channels': new_channels, 'people': new_people}


# #492 scope addition: the default mode of a class and what each mode does, for the card.
CLASS_MODES = {'slack': 'draft', 'mail': 'draft'}
MODE_TEXT = {
    'slack': 'routine sends to known work channels that mention known people go out; the rest draft.',
    'mail': 'every write drafts.',
    'tracker': 'writes follow the tracker tier as today.',
    'code_host': 'writes follow the code host tier as today.',
    'docs': 'writes follow the docs tier as today.',
    'other': 'writes go out after the lint and the sensitive, commitment and disagreement patterns.',
    'send': 'Writes go out after the lint and the sensitive, commitment and disagreement patterns; audience rules do not apply.',
    'draft': 'Every write through this connector is a draft.',
    'refuse': 'Every write through this connector is refused.'}


def _count(n, one, many):
    return f'{n} {one if n == 1 else many}'


def record(proposal):
    """The decision record text (contracts/outbound-learn.md)."""
    server, n, m = proposal['server'], len(proposal['channels']), len(proposal['people'])
    label = 'Slack' if proposal['channel'] == 'slack' else proposal['channel']
    parts = ([_count(n, 'work channel', 'work channels')] if n else []) + (
        [_count(m, 'person', 'people')] if m else [])
    default = CLASS_MODES.get(proposal['channel'], 'send')
    question = (f'Connector {server} is {label}, mode {default}'
                + (f'; add {" and ".join(parts)}?' if parts else '?'))
    lines = ''.join([f"- channel #{row['name']} ({row['id']}, {row['members']} members)\n"
                     for row in proposal['channels']]
                    + [f"- person {row['name']} ({row['id']}, {row['why']})\n" for row in proposal['people']])
    # Scope addition: one option per other mode, so the owner changes the mode on this card.
    rows = [('approve', 'Approve', f'Records the alias, {n} work channels and {m} people.',
             f'Mode {default}: {MODE_TEXT[proposal["channel"]]}', 9)]
    if n:
        rows.append(('channels', 'Approve channels only', f'Records the alias and {n} work channels.',
                     'Mentions of these people still draft.', 5))
    rows.append(('keep', 'Defer: keep as drafts', 'Records nothing.',
                 'Every send through this connector stays a draft today.', 1))
    rows += [(other, f'Approve, mode {other}', f'Records the alias, {n} work channels and {m} people with mode {other}.',
              MODE_TEXT[other], 3) for other in ('send', 'draft', 'refuse') if other != default]
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
Reasoning: The listing names these channels and the people are the day's reviewers or named in its records; keep drafts if a channel is shared outside the company.
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
    mode = option if option in ('send', 'draft', 'refuse') else None
    channels = [row['id'] for row in proposal['channels']] if option in ('approve', 'channels') or mode else []
    people = [row for row in proposal['people']] if option == 'approve' or mode else []
    alias = proposal['alias'] and (option in ('approve', 'channels') or bool(mode))
    if not (alias or channels or people or mode):
        return CLEAN

    def change(_, raw):
        config = workspace.load_config(root, raw=raw)
        settings = [(('outward', 'servers'), proposal['server'], proposal['channel'])] if alias else []
        settings += [(('outward', 'modes'), proposal['server'], mode)] if mode else []
        if channels:
            settings += setup.merged(config, ['outbound', 'work_channels'], channels)
        settings += [(('outbound', 'people'), f"slack:{row['id']}", row['entry']) for row in people]
        return setup._settle(raw, settings)

    code = setup._edit('outbound learn', 'learned connector', lambda *args, **kwargs: True, change, root)
    if code == CLEAN:
        state.append_event('outbound.learned', {
            'decision': decision_id, 'option': option, 'mode': 'card' if decision_id else 'auto',
            'server': proposal['server'], 'channel': proposal['channel'], 'alias': alias,
            'connector_mode': mode, 'channels': channels, 'people': [row['id'] for row in people]}, root)
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
    learned = data.get('outbound_learn', {})
    open_card = next((key for key, row in learned.items() if row.get('answered') is None), None)
    if open_card:
        _widget(root, config, open_card)
        return CLEAN
    kept = next((key for key, row in learned.items() if row.get('answered') == 'keep'
                 and row['server'].casefold() == server.casefold()), None)
    if kept:
        return fail(f'connector {server} was kept as drafts today ({kept}); {DRAFT}')
    if (args.channels or args.people) and channel != 'slack':
        return fail('listings apply to a slack connector; run it without --channels and --people')
    if channel == 'slack' and not (args.channels or args.people):
        return fail(f'connector {server} needs its listings; call its channel listing tool (channels_list, '
                    'conversations_list or slack_search_channels) and its user listing tool (users_list '
                    'or slack_search_users), write the channels the message goes to as [{"id", "name", '
                    '"members", "shared"}] and the people it mentions as [{"id", "name", "email"}] in JSON '
                    f'files under today\'s day directory, then run bin/wuwei outbound learn --tool {tool} '
                    '--channels <file> --people <file>')
    try:
        channels = _rows(args.channels, 'channels') if args.channels else []
        people = _rows(args.people, 'people') if args.people else []
    except OSError as exc:
        return fail(f'cannot read a listing: {exc}; write the file under today\'s day directory', UNRUN)
    except ValueError as exc:
        return fail(str(exc))
    # `other` carries mode send with no audience rules, so it is never learned without the card.
    card = (config['outbound']['learn'] == 'card' or workspace.posture(config)[0] == 'strict'
            or channel == 'other')
    proposal = propose(root, config, data, server, channel, tool, channels, people, card=card)
    if proposal is None:
        return fail(f'nothing new to learn for connector {server}; {DRAFT}')
    try:
        return ask(root, config, proposal) if card else apply(root, proposal, 'approve')
    except (OSError, ValueError) as exc:
        return fail(f'{exc}; run bin/wuwei doctor', UNRUN)
