"""Translate Claude Code lifecycle hooks into registered guard calls."""

import json
import re
import sys

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.guards import EVENTS, discover


def register(subparsers):
    parser = subparsers.add_parser('hook', help='Run guards for a Claude Code hook')
    parser.add_argument('event', choices=EVENTS)
    parser.set_defaults(func=run)


def run(args):
    try:
        payload = json.load(sys.stdin, parse_constant=invalid_constant)
        validate(payload, args.event)
        guards = discover()
    except BaseException as exc:
        return refuse(args.event, f'wuwei hook: {type(exc).__name__}: {exc}', malformed=True)
    reasons, context = [], []
    for guard in guards:
        if guard.event != args.event:
            continue
        if guard.matcher is not None and not re.fullmatch(guard.matcher, payload.get('tool_name', '')):
            continue
        try:
            result = guard.check(payload)
            if (not isinstance(result, tuple) or len(result) != 2
                    or type(result[0]) is not int or result[0] not in (CLEAN, FINDINGS, UNRUN)
                    or not isinstance(result[1], str) or (result[0] and not result[1].strip())):
                raise ValueError('invalid guard result; expected (0|1|2, message)')
            code, message = result
        except BaseException as exc:
            code, message = UNRUN, f'{type(exc).__name__}: {exc}'
        if code:
            reasons.append(message)
        elif message:
            context.append(message)
    if reasons:
        return refuse(args.event, '\n'.join(reasons))
    if args.event == 'SessionStart' and context:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': args.event, 'additionalContext': '\n'.join(context)}}))
    return CLEAN


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


def refuse(event, reason, *, malformed=False):
    print(reason, file=sys.stderr)
    if event == 'PreToolUse':
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': event, 'permissionDecision': 'deny',
            'permissionDecisionReason': reason}}))
    elif event in ('Stop', 'SubagentStop'):
        print(json.dumps({'decision': 'block', 'reason': reason}))
    # Ordinary PreCompact findings must not prevent compaction (design 4.1).
    return FINDINGS if event == 'PreCompact' and not malformed else UNRUN
