"""Producer-owned outward drafts and host decisions."""

from copy import deepcopy
import os
import re
from uuid import uuid4

from wuwei import outward, state, voice, workspace
from wuwei.exits import RACE, DAMAGED


OPERATIONS = {'chat': {'post', 'dm'}, 'code_host': {'comment'},
              'tracker': {'create', 'comment'}, 'docs': {'write'}}
# A tool row (#493): a call the MCP outward guard held; any name outward.tool_patterns matches.
TOOL = r'[A-Za-z0-9_.-]+'
ANSWERS = ('Send now', 'Send with an edit')


def _tool_row(row):
    return (row.get('operation') == 'tool' and row.get('adapter') == 'mcp'
            and isinstance(row.get('tool'), str) and re.fullmatch(TOOL, row['tool']) is not None)


def read(data):
    rows = data.get('drafts', {})
    if not isinstance(rows, dict):
        raise ValueError(f'drafts: invalid queue; {DAMAGED}')
    for key, row in rows.items():
        if (not isinstance(row, dict) or row.get('id') != key
                or row.get('status') not in ('pending', 'approved', 'sending', 'sent', 'failed', 'dropped')
                or not (_tool_row(row) or 'tool' not in row
                        and row.get('operation') in OPERATIONS.get(row.get('channel'), set()))
                or not isinstance(row.get('inputs'), dict)
                or not isinstance(row.get('text'), str)
                or any(not isinstance(row.get(field), str) or not row[field]
                       for field in ('id', 'adapter', 'destination', 'created',
                                     'tier_reason', 'audience'))):
            raise ValueError(f'drafts: invalid record; {DAMAGED}')
        texts, _ = outward._text(row['inputs'])
        if '\n'.join(texts) != row['text']:
            raise ValueError(f'drafts: text differs from operation inputs; {DAMAGED}')
        if row['status'] == 'approved':
            from datetime import datetime
            if (row.get('answer') not in ANSWERS or not isinstance(row.get('text_sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', row['text_sha256'])
                    or not isinstance(row.get('expires'), str)):
                raise ValueError(f'drafts: invalid allowance; {DAMAGED}')
            datetime.fromisoformat(row['expires'])
        if row['status'] in ('approved', 'sending', 'sent', 'failed'):
            if (not isinstance(row.get('final_inputs'), dict)
                    or not isinstance(row.get('final_text'), str)
                    or type(row.get('edit_size')) is not int or row['edit_size'] < 0
                    or type(row.get('sent_unedited')) is not bool
                    or row['sent_unedited'] != (row['inputs'] == row['final_inputs'])):
                raise ValueError(f'drafts: invalid send record; {DAMAGED}')
            if '\n'.join(outward._text(row['final_inputs'])[0]) != row['final_text']:
                raise ValueError(f'drafts: final text differs from operation inputs; {DAMAGED}')
    return rows


def destination(inputs, channel, operation):
    """Where a draft goes, from inputs without is_dm."""
    _, destinations = outward._text(inputs)
    nested = inputs.get('draft', {})
    return (destinations[0] if destinations else inputs.get('ref')
            or nested.get('ref') or nested.get('parent') or nested.get('teamId') or nested.get('team') or
            (os.environ.get('SLACK_OWNER_DM_CHANNEL', 'owner DM')
             if operation == 'dm' else channel))


def create(root, config, channel, operation, adapter, inputs, reason, tool=None):
    if (not _tool_row({'operation': operation, 'adapter': adapter, 'tool': tool}) if tool
            else operation not in OPERATIONS.get(channel, set())):
        raise ValueError('drafts: unsupported operation; use approve or drop')
    inputs = deepcopy(inputs)
    inputs.pop('is_dm', None)
    texts, destinations = outward._text(inputs)
    nested = inputs.get('draft', {})
    target = destination(inputs, channel, operation)
    audience = voice.audience(target if destinations or operation == 'dm' else channel, config)
    draft_id = 'draft-' + uuid4().hex
    row = {'id': draft_id, 'channel': channel, 'operation': operation,
           'adapter': adapter, 'destination': target, 'inputs': inputs,
           'text': '\n'.join(texts), 'created': workspace.now().isoformat(),
           'tier_reason': reason, 'audience': audience, 'status': 'pending',
           'item': inputs.get('item') or nested.get('item'), 'style': outward.tells('\n'.join(texts))}

    def update(data):
        read(data)
        if row['item'] is None:
            row['item'] = next((name for name, item in data['items'].items()
                                if item.get('pr') == target), None)
        data.setdefault('drafts', {})[draft_id] = row
    if tool:
        row['tool'] = tool
    state._write_state(update, root, reserved=False, kind='draft.created',
                       payload={'id': draft_id, 'channel': channel})
    return draft_id


def reason(draft_id, tier_reason):
    """The refusal for a held call (#493): the id, the rule and the card command."""
    rule = tier_reason.removeprefix(outward.APPROVAL_REQUIRED + ': ')
    return (f'outward: draft {draft_id}: {rule}; the owner decides: '
            f'bin/wuwei drafts show {draft_id} --widget')


def hold(root, config, channel, operation, adapter, inputs, tier_reason, tool=None):
    """Store a held call as a pending draft and return its refusal; a tool call identical
    to a pending one reuses that draft."""
    draft_id = None
    if tool:
        stored = {key: value for key, value in inputs.items() if key != 'is_dm'}
        draft_id = next((key for key, row in read(state.read_state(root)).items()
                         if row['status'] == 'pending' and row.get('tool') == tool
                         and row['inputs'] == stored), None)
    return reason(draft_id or create(root, config, channel, operation, adapter, inputs,
                                     tier_reason, tool=tool), tier_reason)


def spend(root, tool, channel, inputs):
    """Pass one held tool call an approved draft allows (#493): same tool (any for an
    adapter none draft), destination and text, before expires. Returns the id or None."""
    from datetime import datetime
    stored = {key: value for key, value in inputs.items() if key != 'is_dm'}
    target, now = destination(stored, channel, 'tool'), workspace.now()
    rows = [row for row in read(state.read_state(root)).values()
            if row['status'] == 'approved' and row.get('tool', tool) == tool
            and row['destination'] == target and datetime.fromisoformat(row['expires']) > now]
    if not rows:
        return None
    from hashlib import sha256
    digest = sha256('\n'.join(outward._text(stored)[0]).encode()).hexdigest()
    row = next((row for row in rows if row['text_sha256'] == digest), None)
    if row is None:
        return None

    def update(data):
        current = read(data).get(row['id'])
        if current is None or current['status'] != 'approved':
            raise ValueError(f'drafts: allowance changed; {RACE}')
        current.update(status='sent', closed=workspace.now().isoformat())
    state._write_state(update, root, reserved=False, kind='draft.sent',
                       payload={'id': row['id'], 'tool': tool})
    return row['id']


def _pending(data, draft_id):
    row = read(data).get(draft_id)
    if row is None:
        raise state.StateError('drafts: unknown draft ID; run bin/wuwei drafts for the queued ids')
    if row['status'] != 'pending':
        raise state.StateError(f"drafts: draft is {row['status']}; cannot decide again; run bin/wuwei drafts for what is still queued")
    return row


def widget(row, config):
    """The draft card (#493): one #359 widget whose record is the Send now command."""
    from wuwei import decision
    draft_id, rule = row['id'], row['tier_reason'].removeprefix(outward.APPROVAL_REQUIRED + ': ')
    allowance = row['adapter'] in ('mcp', 'none')
    send = 'Send the text as it is. ' + ('The seat repeats its call and it goes out once.' if allowance
                                         else f"It goes out through the {row['adapter']} adapter.")
    tool = f" --tool {row['tool']}" if row.get('tool') else ''
    learning = config['outbound'].get('learn', 'off') != 'off'
    if learning and rule.startswith(('unknown destination', 'unknown mention')):
        send += (f" Then run bin/wuwei outbound learn{tool} to record {rule.split(':')[0].split()[-1]} "
                 'for later sends.')
    elif (learning and rule.startswith('unknown DM recipient')
          and not all(config['outbound']['owner']['slack'].values())):
        # #495: the DM may be the owner's own; the card learns the identity from the connector.
        send += (f" If it is your own DM, run bin/wuwei outbound learn{tool} --owner <file> with your user "
                 "and DM ids from the connector's identity tool, so later messages to you go out.")
    options = [('Send now', send),
               ('Send with an edit', f'I ask you for the new text in a Draft card citing {draft_id}, '
                f'write it to a file and run bin/wuwei drafts approve {draft_id} --file <file>.'),
               ('Keep as draft', 'Nothing is sent; it stays in bin/wuwei drafts.'),
               ('Drop', f'Nothing is sent: bin/wuwei drafts drop {draft_id}.')]
    if rule.startswith('approval tier') and workspace.posture(config)[0] == 'strict':
        options.insert(0, options.pop(2))
    options[0] = (options[0][0] + ' (Recommended)', options[0][1])
    return decision.widget(f"{draft_id}: send this to {row['destination']} through "
                           f"{row.get('tool') or row['adapter']}? Rule: {rule}.\n\n{row['text']}",
                           'Draft', options, f'bin/wuwei drafts approve {draft_id}')


def _edit(inputs, root, source=None):
    """Replace the text fields from the editor, or from the source file (#493)."""
    import json
    from pathlib import Path
    import tempfile
    from wuwei import registry

    fields = {key: value for key, value in inputs.items() if key in outward.TEXT_FIELDS}
    fields.update({'draft.' + key: value for key, value in inputs.get('draft', {}).items()
                   if key in outward.TEXT_FIELDS})
    single = len(fields) == 1
    text = next(iter(fields.values())) if single else json.dumps(fields, indent=2)
    if source is not None:
        text = Path(source).read_text(encoding='utf-8')
    else:
        with tempfile.TemporaryDirectory(prefix='wuwei-draft-') as directory:
            path = Path(directory) / ('reply.txt' if single else 'reply.json')
            workspace.atomic_write(path, text, mode=0o600)
            editor = registry.load('editor', {'adapters': {'editor': 'local'}})
            result = outward._result(editor.edit(path, os.environ.get('EDITOR') or 'vi', root=root))
            if result.exit:
                raise OSError('drafts: editor could not complete; set EDITOR to a working editor, or run bin/wuwei drafts approve without --edit')
            text = path.read_text(encoding='utf-8')
    if single and not next(iter(fields.values())).endswith('\n'):
        text = text.removesuffix('\n')
    edited = {next(iter(fields)): text} if single else json.loads(text)
    if (not isinstance(edited, dict) or edited.keys() != fields.keys()
            or any(not isinstance(value, str) or not value.strip() for value in edited.values())):
        raise ValueError('drafts: edit must preserve text field names and nonempty strings; write the same text fields, each with nonempty text, then save again')
    for key, value in edited.items():
        if key.startswith('draft.'):
            inputs['draft'][key[6:]] = value
        else:
            inputs[key] = value


def approve(root, draft_id, *, edit=False, source=None):
    """Host action: claim once, then send through the original adapter implementation."""
    from datetime import timedelta
    from difflib import SequenceMatcher
    from hashlib import sha256
    from wuwei import integrity, registry, security

    try:
        # Pin the day before editing or transport can cross midnight.
        directory = workspace.day_dir(root)
        data = state.read_state(directory=directory)
        row = _pending(data, draft_id)
        config = workspace.load_config(root)
        # #493: a tool draft or an adapter none draft records an allowance the seat's same
        # call spends once (spend); a configured adapter sends here.
        allowance = row['adapter'] in ('mcp', 'none')
        if row['adapter'] != 'mcp' and config['adapters'][row['channel']] != row['adapter']:
            raise ValueError('drafts: adapter configuration changed; cannot replay destination; drop the draft with bin/wuwei drafts drop and send it again')
        if (row['operation'] == 'dm' and row['destination'] !=
                os.environ.get('SLACK_OWNER_DM_CHANNEL', 'owner DM')):
            raise ValueError('drafts: DM destination changed; cannot replay destination; drop the draft with bin/wuwei drafts drop and send it again')
        if not allowance:
            operation = getattr(registry.load(row['channel'], config), row['operation']).__wrapped__
        inputs = deepcopy(row['inputs'])
        if edit or source:
            _edit(inputs, root, source)
        code, reason = security.outbound(inputs, root)
        if not code:
            lint_inputs = ({**inputs, 'channel': row['destination']}
                           if row['operation'] == 'dm' else inputs)
            code, reason = outward.check_lint(lint_inputs, root, config, {row['channel']})
        style = ''
        if not code:
            code, style = outward.humanize_lint({**inputs, 'is_dm': row['operation'] == 'dm'}, root,
                                                config, {row['channel']}, draft=True)
            reason = style
        if code:
            return registry.Result(code, reason=reason)
        text = '\n'.join(outward._text(inputs)[0])
        size = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in
                   SequenceMatcher(None, row['text'], text, autojunk=False).get_opcodes()
                   if tag != 'equal')
        # #493: outside strict only the owner or the planner after a card answer reaches this
        # (protect_state), so the recorded answer is the confirmation. A --file text is the
        # owner's only when they typed it into a Draft card citing this id (record_gate).
        planner = data.get('sessions', {}).get(data.get('planner_session_id'), {})
        typed = f'{draft_id}:text:{sha256(text.strip().encode()).hexdigest()}' in planner.get('gate_asked', ())
        # An --edit text comes from an editor, never from a card, so it is confirmed like a --file text.
        if workspace.posture(config)[0] == 'strict' or (edit or source) and not typed:
            try:
                confirmed = integrity._host_confirm(
                    sha256((draft_id + '\n' + text).encode()).hexdigest(),
                    prompt=f"Send this draft to {row['destination']}:\n{text}" + (f'\n{style}' if style else ''))
            except OSError as exc:
                return registry.Result(2, reason=str(exc))
            if not confirmed:
                return registry.Result(1, reason='drafts: owner confirmation declined; rerun it in a host terminal and answer y')

        now = workspace.now()
        ttl = config['outward']['draft_ttl']

        def claim(data):
            current = _pending(data, draft_id)
            if current != row:
                raise ValueError(f'drafts: draft changed during approval; {RACE}')
            current.update(status='approved' if allowance else 'sending', final_inputs=inputs,
                           final_text=text, edit_size=size, sent_unedited=(inputs == row['inputs']),
                           decided=now.isoformat(),
                           answer='Send with an edit' if edit or source else 'Send now',
                           text_sha256=sha256(text.encode()).hexdigest())
            if allowance:
                current['expires'] = (now + timedelta(seconds=ttl)).isoformat()
        state._write_state(claim, reserved=False, directory=directory,
                           kind='draft.approved' if allowance else 'draft.sending',
                           payload={'id': draft_id, 'tool': row.get('tool')} if allowance
                           else {'id': draft_id})
        if allowance:
            return registry.Result(0, reason=(
                f"drafts: {draft_id} approved; repeat the same call to {row['destination']} "
                f'within {ttl} seconds; it passes once'))
        try:
            result = outward._result(operation(**inputs, root=root))
        except Exception:
            result = registry.Result(2, reason='drafts: adapter outcome unknown; do not retry')
        status = 'sent' if result.exit == 0 else 'failed'

        def finish(data):
            current = read(data)[draft_id]
            if current['status'] != 'sending':
                raise ValueError(f'drafts: send state changed; {RACE}')
            current.update(status=status, closed=workspace.now().isoformat())
        state._write_state(finish, reserved=False, directory=directory, kind='draft.' + status,
                           payload={'id': draft_id, 'exit': result.exit})
        if row['channel'] == 'docs' and result.exit == 0:
            from wuwei import docs
            docs.record(root, inputs['draft'], row['adapter'], result.data['link'], draft_id=draft_id)
        if row['channel'] == 'tracker' and row['operation'] == 'create' and result.exit == 0:
            from wuwei import tracker
            try:
                tracker.record(inputs['draft'], result.data, directory=directory)
            except (OSError, ValueError, TypeError, KeyError):
                created = inputs['draft']
                return registry.Result(2, reason=(
                    f'drafts: {draft_id} sent; could not record ticket; run bin/wuwei plan set '
                    f'{created["item"]} ticket=<id> with the id the tracker shows'
                    if created.get('category') == 'items' else
                    f'drafts: {draft_id} sent; could not record ticket; do not retry, the ticket '
                    'is in the tracker'))
        return registry.Result(result.exit, reason=(f'drafts: {draft_id} sent' if not result.exit
                               else 'drafts: adapter did not confirm send; do not retry'))
    except state.StateError as exc:
        return registry.Result(1, reason=str(exc))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return registry.Result(2, reason='drafts: cannot read, edit, validate or record approval; run bin/wuwei doctor, then retry')


def drop(root, draft_id):
    from wuwei import registry

    try:
        def update(data):
            _pending(data, draft_id).update(status='dropped', decided=workspace.now().isoformat())
        state._write_state(update, root, reserved=False, kind='draft.dropped',
                           payload={'id': draft_id})
        return registry.Result(0, reason=f'drafts: {draft_id} dropped')
    except state.StateError as exc:
        return registry.Result(1, reason=str(exc))
    except (OSError, ValueError, TypeError, KeyError):
        return registry.Result(2, reason='drafts: cannot read or record drop; run bin/wuwei doctor, then retry')
