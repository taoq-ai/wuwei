"""Session identity, the planner and seat registry rows, and the Owner step cards."""

import json
import os
from pathlib import Path
import shlex

from wuwei import workspace
from wuwei.exits import PAYLOAD, DAMAGED


ROLES = ('adhoc', 'seat-host')


def current():
    """The calling session id that SessionStart exported, or None (host terminal)."""
    value = os.environ.get('WUWEI_SESSION_ID', '').strip()
    return value or None


def card_topic(card, answer):
    """#529: the gate topic of the owner's answer to a card, hashed."""
    from hashlib import sha256
    text = answer.strip().removesuffix(' (Recommended)').strip()
    return f'{card}={sha256(text.encode()).hexdigest()}'


OWNER_STEP = 'Owner step'


def owner_card(command, detail, token='', no='Nothing changes.'):
    """#831: the Owner step card of one command; record is the command to run again on Yes."""
    return {'question': f'{OWNER_STEP}: {command}' + (f' ({token})' if token else ''), 'header': OWNER_STEP,
            'multiSelect': False, 'options': [{'label': 'Yes', 'description': detail},
                                              {'label': 'No', 'description': no}],
            'record': command}


def owner_topic(question, options, reply):
    """The hashed answer to an Owner step question: the question, every option as asked, the
    reply. An empty reply is the asked topic every answer carries, so the latest one decides."""
    text = '\n'.join([question, *(f"{option['label']}: {option['description']}" for option in options), reply])
    return card_topic(OWNER_STEP, text if reply else question)


def owner_answer(root, command, detail, token='', no='Nothing changes.'):
    """'Yes', 'No' or None: the owner's latest answer on this step's Owner step card today,
    recorded by the hook; any other reply, or none, is None."""
    card = owner_card(command, detail, token, no)
    asked, *replies = (owner_topic(card['question'], card['options'], reply) for reply in ('', 'Yes', 'No'))
    path = workspace.day_dir(root) / 'events.jsonl'
    answer = None
    for line in path.read_text(encoding='utf-8').splitlines() if path.is_file() else ():
        try:
            row = json.loads(line)
            topics = row['payload']['topics'] if row['kind'] == 'gate.asked' else None
        except (ValueError, TypeError, KeyError):
            continue  # a damaged row is no answer
        if isinstance(topics, list) and asked in topics:
            answer = next((label for label, topic in zip(('Yes', 'No'), replies) if topic in topics), None)
    return answer


def needs_owner(root, command, detail, token='', no='Nothing changes.'):
    """#831: None when the owner's latest answer on this step's card today (recorded by the
    hook) is Yes, else the refusal naming the card to ask."""
    if owner_answer(root, command, detail, token, no) == 'Yes':
        return None
    card = owner_card(command, detail, token, no)
    return (f'{command}: waits for the owner; ask this Owner step card with AskUserQuestion, '
            f'then run the command again on Yes: {json.dumps(card)}')


def owner_step_call(payload, root, *actions):
    """#831: an AskUserQuestion of only Owner step cards for these actions (wuwei argv
    prefixes), or a Bash call whose one command is one of them run by the workspace launcher
    (.wuwei/executable, or this plugin's bin/wuwei) with no redirect and no environment
    prefix; the gates that refuse every tool call let these through so the owner can still
    answer in the session."""
    tool, inputs = payload.get('tool_name'), payload.get('tool_input')
    if not isinstance(inputs, dict):
        return False
    if tool == 'AskUserQuestion':
        prefixes = [f"{OWNER_STEP}: bin/wuwei {' '.join(action)}" for action in actions]
        questions = inputs.get('questions')
        return isinstance(questions, list) and bool(questions) and all(
            isinstance(question, dict) and question.get('header') == OWNER_STEP
            and isinstance(text := question.get('question'), str)
            and any(text == prefix or text.startswith(prefix + ' ') for prefix in prefixes)
            for question in questions)
    if tool != 'Bash' or not isinstance(inputs.get('command'), str):
        return False
    from wuwei import integrity
    from wuwei.shell import ParseError, normalize
    try:
        commands = normalize(inputs['command'])
    except ParseError:
        return False
    if len(commands) != 1 or commands[0].writes or commands[0].reads or commands[0].env or not commands[0].argv:
        return False
    program, *argv = commands[0].argv
    plugin = (integrity.PLUGIN / 'bin/wuwei').resolve()
    launcher = program == integrity.recorded(root) or (Path(payload.get('cwd', '.')) / program).resolve() == plugin
    return launcher and any(argv[:len(action)] == list(action) for action in actions)


def record(data, session_id, *, hook, cwd, role=None):
    """Upsert one registry row inside the caller's state write."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError(f'session id must be a nonempty string; {PAYLOAD}')
    if role is not None and role not in ROLES:
        raise ValueError(f'session role must be one of {", ".join(ROLES)}; pass one of those roles')
    registry = data.setdefault('sessions', {})
    if not isinstance(registry, dict):
        raise ValueError(f'sessions: expected object; {DAMAGED}')
    now = workspace.now().isoformat()
    row = registry.setdefault(session_id, {'role': 'adhoc', 'started': now, 'cwd': cwd})
    row.update(last_seen=now, last_hook=hook)
    if role is not None:
        row['role'] = role


def registered(data, session_id):
    """The non-seat role the registry gives a trace session, or None (#352). A subagent's
    trace id is <session>:<agent>; an adhoc row (any SessionStart) is not a registration."""
    parent = session_id.split(':', 1)[0]
    if parent == data.get('planner_session_id'):
        return 'planner'
    row = data.get('sessions', {}).get(parent)
    role = row.get('role') if isinstance(row, dict) else None
    return role if role in ROLES and role != 'adhoc' else None


def export(session_id):
    """Hand the session id to later Bash calls through Claude Code's env file; False without one."""
    path = os.environ.get('CLAUDE_ENV_FILE')
    if path:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(f'export WUWEI_SESSION_ID={shlex.quote(session_id)}\n')
    return bool(path)
