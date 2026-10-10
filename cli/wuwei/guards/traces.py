"""Record completed tool calls in the OTLP JSONL shape consumed by ZIRAN."""

import time

from wuwei.guards import Guard
from wuwei.exits import PAYLOAD

# A warm call takes 5 to 20 ms; one that has already run a second is under load.
# ponytail: sustained load above it defers the advisory steward nudge until a call fits.
BUDGET_MS = 1000


def _digest(directory, calls=0, steward=None):
    """The writer's running count of today's spans and the steward base (#659), so a call
    rescans neither traces.jsonl nor events.jsonl. A cache, not evidence: missing or invalid
    means one recount of the span lines."""
    import json
    from wuwei import state, workspace
    path = directory / 'traces.digest.json'
    with (directory / 'state.lock').open('a') as lock:
        state.lock_ex(lock, 'state.lock')
        try:
            digest = json.loads(path.read_text(encoding='utf-8'))
            if not (isinstance(digest, dict) and set(digest) == {'tool_calls', 'steward'}
                    and all(type(digest[key]) is int for key in digest)
                    and 0 <= digest['steward'] <= digest['tool_calls']):
                raise ValueError
            digest['tool_calls'] += calls
        except (OSError, ValueError):
            try:
                spans = (directory / 'traces.jsonl').read_bytes().count(b'\n')
            except FileNotFoundError:
                spans = 0
            digest = {'tool_calls': spans, 'steward': 0}
        if steward is not None:
            digest['steward'] = max(digest['steward'], steward)
        workspace.atomic_write(path, json.dumps(digest) + '\n', sync_dir=False)
    return digest


def _record(payload, root, findings=(), transcript_path=None, started=None):
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
        'gen_ai.tool.arguments': json.dumps(redact(payload['tool_input'], prefix=True), allow_nan=False),
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
        bound = None
        if reference is not None:
            def bound(data):
                return [seat for seat in brief.seats(data).values() if seat.get('brief') == reference]
        elif 'agent_id' in payload:
            # #676: an untyped subagent binds to its adhoc seat by its launch prompt; state is
            # written only when a seat matches.
            try:
                prompt = brief.first_prompt(transcript_path)
                digest = brief.prompt_digest(prompt) if isinstance(prompt, str) else None
                if digest and brief.adhoc_seat(state.read_state(root), digest, payload['session_id']):
                    def bound(data):
                        name = brief.adhoc_seat(data, digest, payload['session_id'])
                        return [data['seats'][name]] if name else []
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if bound is not None:
            def bind(data):
                for seat in bound(data):
                    seat['transcript'] = str(transcript_path)  # brief.stuck reads it (#473)
                    sessions = seat.setdefault('trace_sessions', [])
                    if payload['session_id'] not in sessions:
                        sessions.append(payload['session_id'])
            if any(seat.get('transcript') != str(transcript_path)
                   or payload['session_id'] not in seat.get('trace_sessions', ())
                   for seat in bound(state.read_state(root))):
                state._write_state(bind, root, reserved=False)  # once per seat and session (#659)
    try:
        from wuwei import steward
        digest = _digest(directory, calls=1)
        if started is None or (time.monotonic() - started) * 1000 < BUDGET_MS:
            base = steward.maybe_run_for_tool_calls(digest['tool_calls'], root, digest['steward'])
            if base != digest['steward']:
                _digest(directory, steward=base)
    except Exception:
        pass  # The due signal must never turn a recorded tool span into a hook refusal.
    return 0, ''


def _strict(root):
    """The workspace posture is strict; an unreadable one counts as strict."""
    from wuwei import workspace
    try:
        return workspace.posture(workspace.load_config(root))[0] == 'strict'
    except Exception:
        return True


def check(payload):
    started = time.monotonic()
    import sys
    from wuwei import security, state, workspace

    security_data, slow = None, False
    span, session = (payload.get(key) if isinstance(payload, dict) and isinstance(payload.get(key), str)
                     and payload[key] else 'unknown' for key in ('tool_name', 'session_id'))
    try:
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
    except (OSError, ValueError, TypeError, RuntimeError):
        return 2, 'wuwei traces: cannot determine workspace scope; run bin/wuwei doctor, which names the workspace problem'
    inspect = False
    try:
        try:
            step = 'the security material (.wuwei/security.json)'
            security_data = security.load(root)
            step = 'the tool call for canary and honeytoken findings'
            findings = security.trace_findings(payload, root, security_data)
            step = 'the events log (events.jsonl)'
            security.record(findings, root, 'tool_trace')
            step = 'the tool payload for redaction'
            payload = dict(payload)
            transcript_path = payload.get('transcript_path')
            if 'agent_id' in payload:
                from wuwei import brief
                transcript_path = brief.subagent_transcript(payload)
                payload['session_id'] = payload['session_id'] + ':' + payload['agent_id']
            original_session = payload.get('session_id')
            payload = security.redact(payload, security_data)
            if isinstance(original_session, str):
                import hashlib
                from wuwei.redact import redact
                if redact(payload['session_id']) != original_session:
                    payload['session_id'] = hashlib.sha256(original_session.encode()).hexdigest()

        except TimeoutError:
            raise  # did not finish in time is not could not read (#659)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            # #601: never the message, which can carry private details.
            inspect, reason = True, f'wuwei traces: {type(exc).__name__}: could not read {step}'
        else:
            code, reason = _record(payload, root, findings, transcript_path, started)
            if not code:
                return 0, ''
    except BaseException as exc:
        slow, ms = isinstance(exc, TimeoutError), round((time.monotonic() - started) * 1000)
        reason = (f'wuwei traces: did not finish in time after {ms} ms (TimeoutError); the tool ran and its span '
                  'may be missing; run bin/wuwei doctor' if slow
                  else f'wuwei traces: {type(exc).__name__}: could not record the tool span in traces.jsonl')
    if not slow:
        reason += _mismatch(root) + '; run bin/wuwei doctor, which names the fix'
    print(reason, file=sys.stderr)
    kind = 'traces.slow' if slow else 'traces.gap'
    try:
        import hashlib
        from wuwei.redact import redact
        if redact(session) != session:  # a session id that carries a credential, as in check above
            session = hashlib.sha256(session.encode()).hexdigest()
        record = {'reason': reason, 'span': redact(span), 'session': session}
        # A slow hook must not wait another 30 s to say so.
        state.append_event(kind, {**record, 'elapsed_ms': ms} if slow else record, root, timeout=1 if slow else 30)
    except BaseException as exc:
        print(f'wuwei traces: {type(exc).__name__}: could not log {kind}; run bin/wuwei doctor',
              file=sys.stderr)
    # #601: below strict the reason and the event are the warning; strict refuses.
    code = 2 if slow or inspect or security_data is not None else 0
    return (code, reason) if code and _strict(root) else (0, '')


def _mismatch(root):
    """'; this hook runs A but .wuwei/executable names B' when they differ, else ''."""
    from pathlib import Path
    from wuwei import integrity
    here, recorded = integrity.PLUGIN / 'bin/wuwei', integrity.recorded(root)
    try:
        if not recorded or Path(recorded).resolve() == here.resolve():
            return ''
    except (OSError, RuntimeError):
        pass
    return f'; this hook runs {here} but .wuwei/executable names {recorded}'


GUARDS = [Guard('PostToolUse', None, check)]
