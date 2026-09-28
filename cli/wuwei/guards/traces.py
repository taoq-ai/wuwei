"""Record completed tool calls in the OTLP JSONL shape consumed by ZIRAN."""

from wuwei.guards import Guard


def _record(payload, root):
    # Discovery runs on every hook; load recorder dependencies only for PostToolUse.
    import hashlib
    import json
    import math
    from uuid import uuid4

    from wuwei import state, workspace
    from wuwei.redact import redact

    for field in ('session_id', 'cwd', 'tool_name', 'agent_type'):
        if field == 'agent_type' and field not in payload:
            continue
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return 2, f'wuwei traces: missing or invalid {field}'
    if not isinstance(payload.get('tool_input'), dict):
        return 2, 'wuwei traces: missing or invalid tool_input'
    duration = payload.get('duration_ms', 0)
    if (type(duration) not in (int, float) or duration < 0
            or isinstance(duration, float) and not math.isfinite(duration)):
        return 2, 'wuwei traces: invalid duration_ms'
    directory = workspace.day_dir(root)
    now = workspace.now()
    end = int(now.timestamp()) * 1_000_000_000 + now.microsecond * 1000
    if duration > end / 1_000_000:
        return 2, 'wuwei traces: invalid duration_ms'
    start = end - int(duration * 1_000_000)
    if start < 0:
        return 2, 'wuwei traces: invalid duration_ms'
    role = redact(payload.get('agent_type', 'unknown'))
    tool = redact(payload['tool_name'])
    attributes = {
        'session.id': redact(payload['session_id']),
        'gen_ai.tool.name': tool,
        'gen_ai.tool.arguments': json.dumps(redact(payload['tool_input']), allow_nan=False),
        'gen_ai.agent.name': role,
    }
    span = {
        'traceId': hashlib.sha256(payload['session_id'].encode()).hexdigest()[:32],
        'spanId': uuid4().hex[:16], 'parentSpanId': '',
        'name': tool,
        'startTimeUnixNano': str(start),
        'endTimeUnixNano': str(end),
        'attributes': [{'key': key, 'value': {'stringValue': value}}
                       for key, value in attributes.items()],
    }
    state.append_jsonl(directory / 'traces.jsonl', {'resourceSpans': [{
        'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': role}}]},
        'scopeSpans': [{'scope': {'name': 'wuwei'}, 'spans': [span]}],
    }]})
    return 0, ''


def check(payload):
    import os
    import sys
    from wuwei import state, workspace

    root = None
    try:
        try:
            root = workspace.find_workspace(payload.get('cwd'))
        except FileNotFoundError:
            if 'WUWEI_WORKSPACE' not in os.environ:
                return 0, ''
            raise
        code, reason = _record(payload, root)
        if not code:
            return 0, ''
    except BaseException as exc:
        reason = f'wuwei traces: {type(exc).__name__}: could not record tool span'
    print(reason, file=sys.stderr)
    try:
        state.append_event('hook.post_tool_use_error', {'reason': reason}, root)
    except BaseException as exc:
        print(f'wuwei traces: {type(exc).__name__}: could not log PostToolUse error',
              file=sys.stderr)
    return 0, ''


GUARDS = [Guard('PostToolUse', None, check)]
