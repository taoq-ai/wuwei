"""Producer-owned outward drafts and host decisions."""

from copy import deepcopy
import os
from uuid import uuid4

from wuwei import outward, state, voice, workspace
from wuwei.exits import RACE, DAMAGED


OPERATIONS = {'chat': {'post', 'dm'}, 'code_host': {'comment'},
              'tracker': {'create', 'comment'}, 'docs': {'write'}}


def read(data):
    rows = data.get('drafts', {})
    if not isinstance(rows, dict):
        raise ValueError(f'drafts: invalid queue; {DAMAGED}')
    for key, row in rows.items():
        if (not isinstance(row, dict) or row.get('id') != key
                or row.get('status') not in ('pending', 'sending', 'sent', 'failed', 'dropped')
                or row.get('operation') not in OPERATIONS.get(row.get('channel'), set())
                or not isinstance(row.get('inputs'), dict)
                or any(not isinstance(row.get(field), str) or not row[field]
                       for field in ('id', 'adapter', 'destination', 'text', 'created',
                                     'tier_reason', 'audience'))):
            raise ValueError(f'drafts: invalid record; {DAMAGED}')
        texts, _ = outward._text(row['inputs'])
        if '\n'.join(texts) != row['text']:
            raise ValueError(f'drafts: text differs from operation inputs; {DAMAGED}')
        if row['status'] in ('sending', 'sent', 'failed'):
            if (not isinstance(row.get('final_inputs'), dict)
                    or not isinstance(row.get('final_text'), str)
                    or type(row.get('edit_size')) is not int or row['edit_size'] < 0
                    or type(row.get('sent_unedited')) is not bool
                    or row['sent_unedited'] != (row['inputs'] == row['final_inputs'])):
                raise ValueError(f'drafts: invalid send record; {DAMAGED}')
            if '\n'.join(outward._text(row['final_inputs'])[0]) != row['final_text']:
                raise ValueError(f'drafts: final text differs from operation inputs; {DAMAGED}')
    return rows


def create(root, config, channel, operation, adapter, inputs, reason):
    if operation not in OPERATIONS.get(channel, set()):
        raise ValueError('drafts: unsupported operation; use approve or drop')
    inputs = deepcopy(inputs)
    inputs.pop('is_dm', None)
    texts, destinations = outward._text(inputs)
    nested = inputs.get('draft', {})
    destination = (destinations[0] if destinations else inputs.get('ref')
                   or nested.get('ref') or nested.get('parent') or nested.get('teamId') or nested.get('team') or
                   (os.environ.get('SLACK_OWNER_DM_CHANNEL', 'owner DM')
                    if operation == 'dm' else channel))
    audience = voice.audience(destination if destinations or operation == 'dm' else channel, config)
    draft_id = 'draft-' + uuid4().hex
    row = {'id': draft_id, 'channel': channel, 'operation': operation,
           'adapter': adapter, 'destination': destination, 'inputs': inputs,
           'text': '\n'.join(texts), 'created': workspace.now().isoformat(),
           'tier_reason': reason, 'audience': audience, 'status': 'pending',
           'item': inputs.get('item') or nested.get('item'), 'style': outward.tells('\n'.join(texts))}

    def update(data):
        read(data)
        if row['item'] is None:
            row['item'] = next((name for name, item in data['items'].items()
                                if item.get('pr') == destination), None)
        data.setdefault('drafts', {})[draft_id] = row
    state._write_state(update, root, reserved=False, kind='draft.created',
                       payload={'id': draft_id, 'channel': channel})
    return draft_id


def _pending(data, draft_id):
    row = read(data).get(draft_id)
    if row is None:
        raise state.StateError('drafts: unknown draft ID; run bin/wuwei drafts for the queued ids')
    if row['status'] != 'pending':
        raise state.StateError(f"drafts: draft is {row['status']}; cannot decide again; run bin/wuwei drafts for what is still queued")
    return row


def _edit(inputs, root):
    import json
    from pathlib import Path
    import tempfile
    from wuwei import registry

    fields = {key: value for key, value in inputs.items() if key in outward.TEXT_FIELDS}
    fields.update({'draft.' + key: value for key, value in inputs.get('draft', {}).items()
                   if key in outward.TEXT_FIELDS})
    single = len(fields) == 1
    text = next(iter(fields.values())) if single else json.dumps(fields, indent=2)
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


def approve(root, draft_id, *, edit=False):
    """Host action: claim once, then send through the original adapter implementation."""
    from difflib import SequenceMatcher
    from hashlib import sha256
    from wuwei import integrity, registry, security

    try:
        # Pin the day before editing or transport can cross midnight.
        directory = workspace.day_dir(root)
        row = _pending(state.read_state(directory=directory), draft_id)
        config = workspace.load_config(root)
        if config['adapters'][row['channel']] != row['adapter']:
            raise ValueError('drafts: adapter configuration changed; cannot replay destination; drop the draft with bin/wuwei drafts drop and send it again')
        if (row['operation'] == 'dm' and row['destination'] !=
                os.environ.get('SLACK_OWNER_DM_CHANNEL', 'owner DM')):
            raise ValueError('drafts: DM destination changed; cannot replay destination; drop the draft with bin/wuwei drafts drop and send it again')
        adapter = registry.load(row['channel'], config)
        operation = getattr(adapter, row['operation']).__wrapped__
        inputs = deepcopy(row['inputs'])
        if edit:
            _edit(inputs, root)
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
        try:
            confirmed = integrity._host_confirm(
                sha256((draft_id + '\n' + text).encode()).hexdigest(),
                prompt=f"Send this draft to {row['destination']}:\n{text}" + (f'\n{style}' if style else ''))
        except OSError as exc:
            return registry.Result(2, reason=str(exc))
        if not confirmed:
            return registry.Result(1, reason='drafts: owner confirmation declined; rerun it in a host terminal and answer y')

        def claim(data):
            current = _pending(data, draft_id)
            if current != row:
                raise ValueError(f'drafts: draft changed during approval; {RACE}')
            current.update(status='sending', final_inputs=inputs, final_text=text,
                           edit_size=size, sent_unedited=(inputs == row['inputs']),
                           decided=workspace.now().isoformat())
        state._write_state(claim, reserved=False, directory=directory, kind='draft.sending',
                           payload={'id': draft_id})
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
