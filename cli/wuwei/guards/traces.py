"""Record completed tool calls in the OTLP JSONL shape consumed by ZIRAN."""

from wuwei.guards import Guard
from wuwei.exits import PAYLOAD


def _record(payload, root, findings=(), transcript_path=None):
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
            return 2, f'wuwei traces: missing or invalid {field}; {PAYLOAD}'
    if not isinstance(payload.get('tool_input'), dict):
        return 2, f'wuwei traces: missing or invalid tool_input; {PAYLOAD}'
    duration = payload.get('duration_ms', 0)
    if (type(duration) not in (int, float) or duration < 0
            or isinstance(duration, float) and not math.isfinite(duration)):
        return 2, f'wuwei traces: invalid duration_ms; {PAYLOAD}'
    directory = workspace.day_dir(root)
    now = workspace.now()
    end = int(now.timestamp()) * 1_000_000_000 + now.microsecond * 1000
    if duration > end / 1_000_000:
        return 2, f'wuwei traces: invalid duration_ms; {PAYLOAD}'
    start = end - int(duration * 1_000_000)
    if start < 0:
        return 2, f'wuwei traces: invalid duration_ms; {PAYLOAD}'
    role = redact(payload.get('agent_type', 'unknown'))
    tool = redact(payload['tool_name'])
    attributes = {
        'session.id': payload['session_id'],
        'gen_ai.tool.name': tool,
        'gen_ai.tool.arguments': json.dumps(redact(payload['tool_input']), allow_nan=False),
        'gen_ai.agent.name': role,
    }
    if findings:
        attributes['security.findings'] = json.dumps(['security.' + key for key in sorted(findings)])
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
    # The reservation is the item link; role and tool arguments are not links.
    from wuwei import brief
    if transcript_path:
        try:
            reference = brief.transcript_reference(transcript_path)
        except (OSError, ValueError, KeyError, TypeError):
            reference = None
        if reference is not None:
            def bind(data):
                for seat in brief.seats(data).values():
                    if seat.get('brief') == reference:
                        sessions = seat.setdefault('trace_sessions', [])
                        if payload['session_id'] not in sessions:
                            sessions.append(payload['session_id'])
            state._write_state(bind, root, reserved=False)
    try:
        from wuwei import steward
        with (directory / 'traces.jsonl').open(encoding='utf-8') as stream:
            steward.maybe_run_for_tool_calls(sum(1 for _ in stream), root)
    except Exception:
        pass  # The due signal must never turn a recorded tool span into a hook refusal.
    return 0, ''


def check(payload):
    import sys
    from wuwei import security, state, workspace

    security_data = None
    try:
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
    except (OSError, ValueError, TypeError, RuntimeError):
        return 2, 'wuwei traces: cannot determine workspace scope; run bin/wuwei doctor, which names the workspace problem'
    try:
        try:
            security_data = security.load(root)
            findings = security.trace_findings(payload, root, security_data)
            security.record(findings, root, 'tool_trace')
            payload = dict(payload)
            transcript_path = payload.get('transcript_path')
            if 'agent_id' in payload:
                from pathlib import Path
                agent_id = payload['agent_id']
                if not isinstance(agent_id, str) or not agent_id.strip():
                    raise ValueError(f'invalid agent_id; {PAYLOAD}')
                if transcript_path:
                    transcript_path = (Path(transcript_path).parent / payload['session_id']
                                       / 'subagents' / f'agent-{agent_id}.jsonl')
                payload['session_id'] = payload['session_id'] + ':' + agent_id
            original_session = payload.get('session_id')
            payload = security.redact(payload, security_data)
            if isinstance(original_session, str):
                import hashlib
                from wuwei.redact import redact
                if redact(payload['session_id']) != original_session:
                    payload['session_id'] = hashlib.sha256(original_session.encode()).hexdigest()

        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            return 2, 'wuwei traces: cannot inspect or record workspace security evidence; run bin/wuwei doctor, then retry'
        code, reason = _record(payload, root, findings, transcript_path)
        if not code:
            return 0, ''
    except BaseException as exc:
        reason = f'wuwei traces: {type(exc).__name__}: could not record tool span'
    print(reason, file=sys.stderr)
    try:
        state.append_event('hook.post_tool_use_error', {'reason': reason}, root)
    except BaseException as exc:
        print(f'wuwei traces: {type(exc).__name__}: could not log PostToolUse error; run bin/wuwei doctor',
              file=sys.stderr)
    return (2, reason) if security_data is not None else (0, '')


GUARDS = [Guard('PostToolUse', None, check)]
