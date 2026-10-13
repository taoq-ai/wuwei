"""Record completed tool calls in the OTLP JSONL shape consumed by ZIRAN."""

import time

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
                role = payload.get('agent_type', '').rsplit(':', 1)[-1]
                if digest and brief.adhoc_seat(state.read_state(root), digest, payload['session_id'], role=role):
                    def bound(data):
                        name = brief.adhoc_seat(data, digest, payload['session_id'], role=role)
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
                state._write_state(bind, root)  # once per seat and session (#659)
    return 0, ''


def seat_session(payload):
    """#878: the session id check binds to a seat: the subagent suffix, hashed when redaction changes it."""
    import hashlib
    from wuwei.redact import redact
    session = payload['session_id'] + (':' + payload['agent_id'] if 'agent_id' in payload else '')
    return session if redact(session) == session else hashlib.sha256(session.encode()).hexdigest()


def _claim_created_pr(payload, root):
    """Record a successful gh PR creation from its observed URL, without a host lookup."""
    import re
    from pathlib import Path
    from wuwei import state, workspace

    if payload.get('tool_name') != 'Bash':
        return
    command = payload.get('tool_input', {}).get('command', '')
    response = payload.get('tool_response', {})
    if not isinstance(command, str) or not isinstance(response, dict):
        return
    if response.get('exitCode', response.get('exit_code', 0)) != 0 or response.get('isError'):
        return
    output = response.get('stdout', '')
    if not isinstance(output, str):
        return
    urls = list(re.finditer(r'(?mi)^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?$',
                            output.strip()))
    if not urls:
        return
    from wuwei.guards import edges
    segments = edges.segments(command, payload['cwd'])
    creates = []
    other = False
    for argv, _, cwd in segments:
        if Path(argv[0]).name == 'cd':
            continue
        if Path(argv[0]).name != 'gh':
            other = True
            continue
        repo, args = edges._gh(argv[1:])
        if args[:2] != ['pr', 'create']:
            other = True
        else:
            creates.append((repo, args, cwd))
    if not creates or any('--dry-run' in args[2:] or '--web' in args[2:]
                          for _, args, _ in creates):
        return
    config = workspace.load_config(root)
    if len(creates) != 1 or len(urls) != 1 or other:
        for url in urls:
            configured = next((row['name'] for row in config['repos']
                               if row['name'].casefold() == url[1].casefold()), None)
            if configured:
                state.append_event('pr.unclaimed', {'pr': f'{configured}#{url[2]}',
                    'url': f'https://github.com/{configured}/pull/{url[2]}',
                    'reason': 'ambiguous gh pr create output; verify before claiming'}, root)
        return
    match = urls[0]
    configured = next((row['name'] for row in config['repos']
                       if row['name'].casefold() == match[1].casefold()), None)
    if configured is None:
        return
    ref = f'{configured}#{match[2]}'
    repo, args, cwd = creates[0]
    if repo is None or repo.casefold() == configured.casefold():
        _, values = edges._scan(args[2:], edges.GH_VALUED)
        branch = edges._last(values, '-H', '--head')
        data = state.read_state(root)
        found = None
        if branch:
            linked = edges._recorded(root, config, repo=configured, branch=branch)
            found = linked[0] if linked and linked[0] in data['approved_items'] else None
        else:
            trees = [(len((root / row['worktree']).parts), name)
                     for name, row in data['items'].items()
                     if name in data['approved_items'] and row.get('worktree')
                     and cwd.resolve().is_relative_to((root / row['worktree']).resolve())
                     and row.get('repo', configured).casefold() == configured.casefold()]
            found = max(trees)[1] if trees else None
        if found and data['items'][found].get('pr') == ref:
            return
        reason = None
        if found:
            row = data['items'][found]
            if row['phase'] == 'planned' or not any(key.startswith(found + ':')
                                                    for key in data['gate_verdicts']):
                reason = f'{found}: pre-PR gates not passed; run the item gates before claiming this PR'
            else:
                try:
                    from wuwei import merge, registry
                    tree = (root / row['worktree']).resolve()
                    code, reason = merge.gate_check(root, tree, config, item=found)
                    if code == 0:
                        branch = branch or registry.data(registry.load('vcs', config).branch(
                            str(tree), root=root))['name']
                        state.record_pr(root, found, ref, raised=False, branch=branch)
                        return
                except TimeoutError:
                    raise
                except Exception as exc:
                    from wuwei.redact import redact
                    reason = redact(str(exc))
                    state.append_event('pr.autoclaim_error', {'pr': ref, 'error': type(exc).__name__}, root)
        if ref not in data['claimed_prs'] + data['raised_prs']:
            state.append_event('pr.unclaimed', {'pr': ref,
                                                'url': f'https://github.com/{configured}/pull/{match[2]}',
                                                **({'item': found} if found else {}),
                                                **({'reason': reason} if reason else {})}, root)
        return
    state.append_event('pr.unclaimed', {'pr': ref,
        'url': f'https://github.com/{configured}/pull/{match[2]}',
        'reason': 'command repository differs from PR URL; verify before claiming'}, root)


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
        print('wuwei traces: cannot determine workspace scope; run bin/wuwei doctor, which names the '
              'workspace problem', file=sys.stderr)
        return 0, ''
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
            original = payload
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
            code, reason = _record(payload, root, findings, transcript_path)
            if not code and 'honeytoken' in findings:  # #878: after _record binds the session to its seat
                try:
                    from wuwei import scanner
                    scanner.honeytoken(payload['session_id'], root)
                except Exception as exc:  # the span is written and the close holds
                    code, reason = 1, f'wuwei traces: {type(exc).__name__}: could not park the item of a honeytoken read (the span is recorded)'
            if not code:
                try:
                    _claim_created_pr(original, root)
                except TimeoutError:
                    raise
                except Exception as exc:
                    state.append_event('pr.autoclaim_error', {'error': type(exc).__name__}, root)
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
    return 0, ''  # #601, #837: the reason and the event are the warning; recording never refuses


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
