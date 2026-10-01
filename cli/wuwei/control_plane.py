"""Control-plane interface: escalate, notify and poll_replies, plus the shared reply parser.

The default is no transport: Claude Code Remote Control with "Push when actions required"
delivers the planner's question widget to the phone, so WUWEI renders text and sends nothing.
"""

import functools
import re

from wuwei import decision, state, workspace
from wuwei.registry import Result


# Fixed outward lines avoid words the outward lint refuses; a transport dm is an outward operation.
HELP = 'Not recorded. Reply approve D-n, option X on D-n, or drop it.'

# ponytail: transport is duck-typed (dm, poll); promote to an adapter kind when a second
# messaging transport lands.


def _fail_closed(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            return Result(2, None, f'control plane: {exc}')
    return wrapper


def pending(root):
    """Return {id: fields} for owner-routed decisions without an owner outcome, in route order."""
    data = state.read_state(root)
    routes = data.get('decision_routes', {})
    if not isinstance(routes, dict):
        raise ValueError('invalid decision ledger')
    found = {}
    for identifier in routes:
        if decision.answered(data, identifier) is None:
            path = decision.today_path(identifier, root)
            if path.is_symlink() or path.parent.is_symlink():
                raise ValueError(f'decision {identifier}: record must be a regular file')
            found[identifier], _ = decision.evaluate(path.read_text(encoding='utf-8'))
    return found


def options(fields):
    return decision.table(fields['Options'], ['Option', 'Description'], 'Options')


def parse(text, decisions):
    """Return (id, option) for a reply that names one pending decision's option, else None."""
    reply = re.sub(r'[.!]$', '', ' '.join(text.split())).casefold()
    if match := re.fullmatch(r'approve (d-[1-9][0-9]*)', reply):
        identifier = match[1].upper()
        return (identifier, decisions[identifier]['Recommendation']) if identifier in decisions else None
    if match := re.fullmatch(r'option ([a-z][a-z0-9_-]*) on (d-[1-9][0-9]*)', reply):
        identifier = match[2].upper()
        found = [row[0] for row in (options(decisions[identifier]) if identifier in decisions else [])
                 if row[0].casefold() == match[1]]
        return (identifier, found[0]) if len(found) == 1 else None
    if reply == 'drop it' and len(decisions) == 1:
        [(identifier, fields)] = decisions.items()
        found = [row[0] for row in options(fields)
                 if re.match(r'(?i)(?:Do nothing|Defer)\b', row[1])]
        return (identifier, found[0]) if len(found) == 1 else None
    return None


def render(identifier, fields, content, level, root):
    if content == 'none':
        return f'{identifier} options: ' + ', '.join(row[0] for row in options(fields))
    if level == 'full':  # pending() has checked the record is a regular file of today.
        return decision.today_path(identifier, root).read_text(encoding='utf-8').rstrip()
    return decision.present(identifier, fields, level)


def _content(root):
    return workspace.load_config(root)['control_plane']['content']


def _level(root):
    return workspace.verbosity(workspace.load_config(root), 'dm')


@_fail_closed
def escalate(decision_id, *, root=None, transport=None):
    root = workspace.find_workspace(root)
    decisions = pending(root)
    if decision_id not in decisions:
        return Result(1, None, f'control plane: {decision_id} is not pending')
    if transport is None:
        return Result(0, render(decision_id, decisions[decision_id], 'summary', _level(root), root),
                      'ask as a question widget; Remote Control pushes it')
    content, level = _content(root), _level(root)
    text = render(decision_id, decisions[decision_id], content, level, root)
    if content != 'none' and level != 'full':
        text += f'\nReply more {decision_id} for the full record.'
    return transport.dm(text + '\n' + HELP, root=root)


@_fail_closed
def notify(summary, *, root=None, transport=None):
    if transport is None:
        return Result(0, summary, 'shown in the session; Claude Code decides whether to push')
    root = workspace.find_workspace(root)
    text = summary if _content(root) == 'summary' else 'An update is waiting in the workspace.'
    return transport.dm(text, root=root)


@_fail_closed
def poll_replies(since, *, root=None, transport=None):
    """Record parsed replies as decision.replied evidence; echo the options for anything else."""
    if transport is None:
        return Result(0, [], 'replies arrive in the planner session')
    root = workspace.find_workspace(root)
    polled = transport.poll(since, root=root)
    if polled.exit != 0:
        return Result(2, None, polled.reason or 'control plane: poll failed')
    if not isinstance(polled.data, list) or not all(
            isinstance(reply, dict) and isinstance(reply.get('text'), str) for reply in polled.data):
        return Result(2, None, 'control plane: invalid poll result')
    decisions, content, level = pending(root), _content(root), _level(root)
    lines = [render(identifier, fields, content, level, root) for identifier, fields in decisions.items()]
    echo = '\n'.join([HELP, *(lines or ['No pending decisions.'])])
    answers, echoed = [], False
    for reply in polled.data:
        answer = parse(reply['text'], decisions)
        if answer:
            answers.append({'id': answer[0], 'option': answer[1]})
            state.append_event('decision.replied', answers[-1], root=root)
            continue
        echoed = True
        sent = transport.dm(echo, root=root)
        if sent.exit != 0:
            return Result(2, answers, sent.reason or 'control plane: echo failed')
    return Result(1 if echoed else 0, answers, 'replies not recorded were echoed' if echoed else '')
