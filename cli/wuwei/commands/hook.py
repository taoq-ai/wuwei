"""Translate Claude Code lifecycle hooks into registered guard calls."""

import json
from pathlib import Path
import re
import shlex
import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.guards import EVENTS, NEVER_SHADOWED, SELECTION, discover, profile_result

# The watch heartbeat's probe calls; their refusals are measurements, not seat refusals.
HEARTBEAT_SESSION = 'wuwei-heartbeat'


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
        if root is not None:
            env.load(root)
        token = SELECTION.set((args.event, payload.get('tool_name', '')))
        try:
            guards = discover()
        finally:
            SELECTION.reset(token)
    except BaseException as exc:
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
            refusals.append((guard.check.__module__.rsplit('.', 1)[-1], message))
        elif message:
            context.append(message)
    reasons = [message for _, message in refusals]
    if (refusals and args.event != 'SessionStart'
            and payload.get('session_id') != HEARTBEAT_SESSION):
        reasons = shadow(payload, refusals, root)
    if args.event == 'SessionStart' and (context or reasons):
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': args.event, 'additionalContext': '\n'.join(context + reasons)}}))
        if reasons:
            print('\n'.join(reasons), file=sys.stderr)
        return CLEAN
    if reasons:
        return refuse(args.event, '\n'.join(reasons), cwd=payload.get('cwd'),
                      record=payload.get('session_id') != HEARTBEAT_SESSION)
    if args.event == 'Stop' and context:
        print('\n'.join(context), file=sys.stderr)
    return CLEAN


def shadow(payload, refusals, root):
    """Shadow mode (#308): record refusals outside NEVER_SHADOWED; return the enforced reasons."""
    from wuwei import state, workspace
    try:
        shadowing = root is not None and workspace.load_config(root)['guards']['mode'] == 'shadow'
    except BaseException:
        shadowing = False  # An unreadable config enforces, exactly as before shadow mode.
    reasons, shown = [], None
    for guard, reason in refusals:
        if not shadowing or guard in NEVER_SHADOWED:
            reasons.append(reason)
            continue
        try:
            if shown is None:
                from wuwei import security
                from wuwei.redact import redact
                shown = security.redact(redact(target(payload)), security.load(root))
            state.append_event('guard.would_refuse', {
                'guard': guard, 'reason': reason, 'target': shown,
                'session': payload['session_id'], 'item': claimed(root, payload['session_id'])}, root)
        except BaseException as exc:
            print(f'wuwei hook: could not record shadow refusal: {exc}', file=sys.stderr)
            reasons.append(reason)
    return reasons


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


def refuse(event, reason, *, malformed=False, cwd=None, record=True):
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
            try:
                state.append_event('hook.refusal', {'reason': reason}, root)
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
