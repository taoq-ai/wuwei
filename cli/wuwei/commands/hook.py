"""Translate Claude Code lifecycle hooks into registered guard calls."""

import json
import os
from pathlib import Path
import re
import shlex
import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.guards import EVENTS, SELECTION, discover, profile_result
from wuwei.workspace import ConfigError

# The watch heartbeat's probe calls; their refusals are measurements, not seat refusals.
HEARTBEAT_SESSION = 'wuwei-heartbeat'
# #326: events whose answer to a config.toml that does not load is config_failure.
CONFIG_EVENTS = ('PreToolUse', 'Stop')
# #326: with a broken config these reads still pass, so the session can show the line.
REPAIR_READS = {'Read': 'file_path', 'Grep': 'path', 'Glob': 'path'}


def register(subparsers):
    parser = subparsers.add_parser('hook', help='Run guards for a Claude Code hook')
    parser.add_argument('event', choices=EVENTS)
    parser.set_defaults(func=run)


def run(args):
    try:
        payload = json.load(sys.stdin, parse_constant=invalid_constant)
    except BaseException as exc:
        reason = (f'wuwei hook: {type(exc).__name__}: could not read PostToolUse payload'
                  if args.event == 'PostToolUse' else f'wuwei hook: {type(exc).__name__}: {exc}')
        return refuse(args.event, reason, malformed=True)
    try:
        validate(payload, args.event)
    except BaseException as exc:
        return refuse(args.event, f'wuwei hook: {type(exc).__name__}: {exc}',
                      malformed=True)
    try:
        from wuwei import env, workspace
        cwd = Path(payload['cwd']).resolve()
        try:
            root = workspace.find_workspace(cwd)
        except FileNotFoundError:
            root = None
        if root is None or not cwd.is_relative_to(root):
            root = workspace.guard_scope(payload)
        if not reaches_workspace(payload, root):
            return CLEAN
        if root is not None:
            env.load(root)
            if args.event in CONFIG_EVENTS:
                try:
                    workspace.load_config(root)
                except OSError:
                    pass  # A missing or unreadable file stays the guards' to measure, as before.
        token = SELECTION.set((args.event, payload.get('tool_name', '')))
        try:
            guards = discover()
        finally:
            SELECTION.reset(token)
    except BaseException as exc:
        if isinstance(exc, ConfigError) and args.event in CONFIG_EVENTS:
            return config_failure(args.event, payload, str(exc))
        reason = (f'{type(exc).__name__}: could not discover guards' if args.event == 'PostToolUse'
                  else f'wuwei hook: {type(exc).__name__}: {exc}')
        return refuse(args.event, reason, malformed=True)
    refusals, context = [], []
    for guard in guards:
        if guard.event != args.event:
            continue
        try:
            if guard.matcher is not None and not re.fullmatch(guard.matcher, payload.get('tool_name', '')):
                continue
            result = guard.check(payload)
            if (not isinstance(result, tuple) or len(result) != 2
                    or type(result[0]) is not int or result[0] not in (CLEAN, FINDINGS, UNRUN)
                    or not isinstance(result[1], str) or (result[0] and not result[1].strip())):
                raise ValueError('invalid guard result; expected (0|1|2, message)')
            code, message = result
            if code == FINDINGS and guard.profile_relaxable:
                from wuwei import workspace
                scope = workspace.guard_scope(payload)
                profile = workspace.load_config(scope)['profile'] if scope is not None else 'strict'
                code, message = profile_result(result, profile, scope, payload.get('tool_name'))
        except BaseException as exc:
            code = UNRUN
            message = (f'{type(exc).__name__}: could not run PostToolUse guard'
                       if args.event == 'PostToolUse' else f'{type(exc).__name__}: {exc}')
        if code:
            refusals.append((guard.check, message))
        elif message:
            context.append(message)
    enforced = [(module(check), message, '') for check, message in refusals]
    if (refusals and args.event != 'SessionStart'
            and payload.get('session_id') != HEARTBEAT_SESSION):
        enforced = posture(payload, refusals, root)
    reasons = [f'{message}\n{line}' if line else message for _, message, line in enforced]
    if args.event == 'SessionStart' and (context or reasons):
        from wuwei.commands.next import HEADER  # Not guards: hook tests replace their __path__.
        parts = sorted(context + reasons, key=lambda text: not text.startswith(HEADER))
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': args.event, 'additionalContext': '\n'.join(parts)}}))
        if reasons:
            print('\n'.join(reasons), file=sys.stderr)
        return CLEAN
    if reasons:
        return refuse(args.event, '\n'.join(reasons), cwd=payload.get('cwd'),
                      record=payload.get('session_id') != HEARTBEAT_SESSION,
                      refusals=[(guard, message) for guard, message, _ in enforced],
                      payload=payload)
    if args.event == 'Stop' and context:
        print('\n'.join(context), file=sys.stderr)
    return CLEAN


def config_failure(event, payload, reason):
    """A config.toml that does not load (#326): Stop prints it and lets the turn end;
    PreToolUse lets ToolSearch and reads of the config and charters through so the session
    can show the line, and refuses everything else with the error."""
    if event == 'Stop':
        print(reason, file=sys.stderr)
        return CLEAN
    if repair_read(payload):
        return CLEAN
    return refuse(event, reason, cwd=payload.get('cwd'),
                  record=payload.get('session_id') != HEARTBEAT_SESSION, payload=payload)


def repair_read(payload):
    """ToolSearch, or a Read, Grep or Glob whose path is a workspace's .wuwei/config.toml,
    its .wuwei/charters directory or a file in it."""
    tool = payload.get('tool_name')
    if tool == 'ToolSearch':
        return True
    inputs = payload.get('tool_input')
    if not isinstance(tool, str) or tool not in REPAIR_READS or not isinstance(inputs, dict):
        return False
    value = inputs.get(REPAIR_READS[tool])
    if not isinstance(value, str) or not value:
        return False
    from wuwei import workspace
    try:
        target = (Path(payload['cwd']) / Path(value).expanduser()).resolve()
        base = workspace.find_workspace(target, use_environment=False) / '.wuwei'
    except (OSError, ValueError, RuntimeError):
        return False
    return target == base / 'config.toml' or target.is_relative_to(base / 'charters')


def reaches_workspace(payload, root):
    """Design 9.1 before any guard parses: the cwd or a file target (root), a
    WUWEI_WORKSPACE selection, or a path word of the call (literal, tilde or the hook's
    own environment variables expanded) lies in, is, or
    directly contains a workspace or managed worktree."""
    if root is not None or 'WUWEI_WORKSPACE' in os.environ:
        return True
    from wuwei import workspace
    cwd = Path(payload['cwd']).resolve()
    inputs = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
    words = {inputs.get('notebook_path'), os.environ.get('GIT_DIR'), os.environ.get('GIT_WORK_TREE')}
    if isinstance(inputs.get('command'), str):
        words.update(re.sub(r'^-\w(?=[~./])', '', word)
                     for word in re.split(r'''[\s;&|()<>'"`=\\]+''', inputs['command']))
    # ponytail: each word walks its own parents through workspace.scope; dedupe the walk if
    # a large heredoc shows in the latency figures. Nonliteral targets (cd $P, bare cd,
    # cd -, CDPATH) are not resolved; the code host and the pre-push hook are the anchors.
    for word in words:
        if not isinstance(word, str) or not word:
            continue
        try:
            path = (cwd / Path(os.path.expandvars(word)).expanduser()).resolve()
            if '/' not in word and not path.exists():
                continue
        except (OSError, ValueError, RuntimeError):
            continue
        try:
            if workspace.scope(path) is not None or path.is_dir() and workspace.contains_workspace(path):
                return True
        except Exception:
            return True  # A broken marker or anchor is WUWEI-shaped; the guards report it.
    return False


def module(check):
    return check.__module__.rsplit('.', 1)[-1]


def posture(payload, refusals, root):
    """#331, at the point #308 shadow mode used: per refusal, off drops it, warn records
    guard.would_refuse and lets the call through, block enforces it with its posture line.
    Returns (guard, reason, line); the config is read only because a guard refused."""
    from wuwei import state, workspace
    from wuwei.guards import level
    try:
        if root is None:
            raise LookupError('no workspace')
        name, levels = workspace.posture(workspace.load_config(root))
    except BaseException:  # No workspace or an unreadable config enforces, as before #331.
        return [(module(check), reason, '') for check, reason in refusals]
    enforced, shown = [], None
    for check, reason in refusals:
        guard, area, decided, line = level(check, levels)
        if decided == 'off':
            continue
        if decided == 'block':
            enforced.append((guard, reason, line))
            continue
        try:
            if shown is None:
                shown = redacted_target(payload, root)
            state.append_event('guard.would_refuse', {
                'guard': guard, 'area': area, 'level': decided, 'posture': name,
                'reason': reason, 'target': shown, 'session': payload['session_id'],
                'item': claimed(root, payload['session_id'])}, root)
        except BaseException as exc:
            print(f'wuwei hook: could not record shadow refusal: {exc}', file=sys.stderr)
            enforced.append((guard, reason, line))
    return enforced


def redacted_target(payload, root):
    """The normalised target as refusal records store it, credentials and canaries redacted."""
    from wuwei import security
    from wuwei.redact import redact
    return security.redact(redact(target(payload)), security.load(root))


def target(payload):
    """The normalised Bash command, else the file path, else the tool or event name."""
    inputs = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
    command = inputs.get('command')
    if isinstance(command, str):
        from wuwei import shell
        try:
            return '; '.join(shlex.join(found.argv) for found in shell.normalize(command))
        except Exception:
            return command
    return next((inputs[key] for key in ('file_path', 'notebook_path', 'path')
                 if isinstance(inputs.get(key), str)),
                payload.get('tool_name') or payload['hook_event_name'])


def claimed(root, session):
    """The first item this session claims, or None; never blocks a shadowed refusal."""
    from wuwei import state
    try:
        claims = state.read_state(root).get('claims', {})
        return next((item for item, holder in sorted(claims.items()) if holder == session), None)
    except Exception:
        return None


def invalid_constant(value):
    raise ValueError('invalid JSON constant')


def validate(payload, event):
    if not isinstance(payload, dict):
        raise ValueError('hook payload must be a JSON object')
    for field in ('session_id', 'transcript_path', 'cwd', 'hook_event_name'):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f'missing or invalid {field}')
    if payload['hook_event_name'] != event:
        raise ValueError('hook_event_name does not match command event')


def refuse(event, reason, *, malformed=False, cwd=None, record=True, refusals=(), payload=None):
    print(reason, file=sys.stderr)
    if event == 'SessionStart':
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': event, 'additionalContext': f'session unmeasured: {reason}'}}))
        return CLEAN
    if event == 'PreToolUse' and not malformed and record:
        from wuwei import state, workspace
        try:
            root = workspace.find_workspace(cwd)
        except FileNotFoundError:
            root = None
        if root is not None:
            details = {'reason': reason}
            if refusals:
                details['refusals'] = [{'guard': guard, 'reason': message} for guard, message in refusals]
                try:
                    details['target'] = redacted_target(payload, root)
                except Exception:
                    pass  # wuwei why prints "not recorded"; never lose the refusal over its target.
            try:
                state.append_event('hook.refusal', details, root)
            except BaseException as exc:
                print(f'wuwei hook: could not record refusal: {exc}', file=sys.stderr)
    if event == 'PreToolUse':
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': event, 'permissionDecision': 'deny',
            'permissionDecisionReason': reason}}))
    elif event in ('Stop', 'SubagentStop'):
        print(json.dumps({'decision': 'block', 'reason': reason}))
    # Ordinary PreCompact findings must not prevent compaction (design 4.1).
    return FINDINGS if event == 'PreCompact' and not malformed else UNRUN
