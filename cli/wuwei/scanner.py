"""S2 trace response and mandatory S4 security measurement."""

import re
import sys

from wuwei import redact, registry, security, state, workspace
from wuwei.exits import ADAPTER_DATA


# Static checks for secrets, unvalidated input, execution and data exposure.
TRUST_RULES = {'SA001', 'SA002', 'SA003', 'SA007', 'SA008', 'SA009', 'SA010'}


def rows(tree, item, flags, config, root):
    if workspace.guard_scope({'cwd': str(tree)}) != root:
        raise OSError('scanner: unmeasured: reviewed worktree is outside the workspace; write the gate brief with --worktree inside the workspace')
    scanner = registry.load('scanner', config)
    audit = scanner.audit(str(tree), root=root)
    if audit.exit not in (0, 1):
        raise OSError('scanner: unmeasured: ' + audit.reason + '; run bin/wuwei doctor')
    threshold = config['scanner']['severity_threshold']
    gate = scanner.gate(audit.data, threshold, root=root)
    if gate.exit not in (0, 1):
        raise OSError('scanner: unmeasured: ' + gate.reason + '; run bin/wuwei doctor')
    levels = ('critical', 'high', 'medium', 'low')
    markers = security.load(root)
    result = []
    for finding in audit.data['findings']:
        try:
            source = (tree / finding['file']).resolve(strict=True)
            location = source.relative_to(tree.resolve())
            with source.open(encoding='utf-8') as stream:
                stream.read()
        except (OSError, ValueError):
            raise OSError('scanner: unmeasured: finding source is unreadable or outside worktree; run bin/wuwei doctor, which tests the scanner') from None
        blocks = (flags['trust_surface'] or flags['boundary_relevant']
                  or finding.get('trust_boundary', False)
                  or finding['rule'] in TRUST_RULES
                  or levels.index(finding['severity']) <= levels.index(threshold))
        rule, location, message = redact.redact(security.redact(
            [finding['rule'], str(location), finding['message']], markers))
        message = re.sub(r'[^a-zA-Z0-9 .,:()/=_-]', ' ', message)
        result.append(f"- {finding['severity']} | {location}:{finding['line']} | "
                      f"ZIRAN {rule} scenario: {message} | "
                      f"blocks: {'yes' if blocks else 'no'}")
        state.append_event('scanner.finding', {
            'source': 'ziran', 'item': item, 'rule': rule,
            'severity': finding['severity'], 'blocks': blocks,
        }, root)
    return result


def merge(text, findings):
    if not findings:
        return text
    if any(finding.endswith('blocks: yes') for finding in findings):
        text = re.sub(r'^(?:## |- )?Verdict:? *PASS\b', 'Verdict: FIX', text, flags=re.M)
    return text + '\n\n## ZIRAN findings\n' + '\n'.join(findings) + '\nProbe: ziran audit\n'


def _trace_response(finding, root):
    """Seats: page and park the affected items. A registered session: one silent traces.noted
    per day. Unknown: one traces.unmatched per day (#352). Returns True when the finding paged."""
    import hashlib
    from wuwei import brief, sessions, watch

    session = finding['session_id']
    digest = hashlib.sha256(session.encode()).hexdigest()
    data = state.read_state(root)
    # #676: an adhoc seat is the audit record, not an item seat; its session keeps its launcher's rule.
    seat = any(session in seat.get('trace_sessions', []) for seat in brief.seats(data).values()
               if seat['role'] != 'adhoc')
    role = None if seat else sessions.registered(data, session)
    if not seat:
        kind = 'traces.noted' if role else 'traces.unmatched'
        if not any(row['kind'] == kind and row['payload'].get('session_digest') == digest
                   for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
            extra = {'role': role, 'summary': f'traces: {role} session, chain noted'} if role else {}
            state.append_event(kind, {'session_digest': digest, 'chain': finding['chain'], **extra}, root)
        return False
    state.append_event('scanner.finding', finding, root)
    reason = 'scanner chain ' + ' -> '.join(finding['chain'])

    def update(data):
        items = {seat['item'] for seat in brief.seats(data).values()
                 if finding['session_id'] in seat.get('trace_sessions', [])}
        for name in items:
            item = data['items'].get(name)
            if item is not None and 'parked' in state.PHASES[item['phase']]:
                item.update(phase='parked', status='blocked', disposition={'kind': 'parked', 'reason': reason})

    state._write_state(update, root)
    return True


def trace_sweep(root, config):
    """Page and park on today's scanner chains (dispatch receive and close run it); returns the
    counts, including empty-day status."""
    counts = {'scanner': 'unmeasured', 'scanner_owed': 0, 'unreadable': 0}
    try:
        path = workspace.day_dir(root) / 'traces.jsonl'
        try:
            with path.open(encoding='utf-8') as stream:
                has_sessions = any(line.strip() for line in stream)
        except FileNotFoundError:
            if path.is_symlink():
                raise ValueError(f'unreadable trace input; {ADAPTER_DATA}') from None
            has_sessions = False
        if not has_sessions:
            counts['scanner'] = 'no sessions'
            return counts
        if config['adapters']['scanner'] == 'none':
            counts['scanner'] = 'not configured'
            return counts
        result = registry.load('scanner', config).traces(str(path), root=root)
        if type(result.exit) is not int or result.exit not in (0, 1):
            raise ValueError(result.reason or 'scanner unavailable; retry; if it repeats, run bin/wuwei doctor')
        markers = security.load(root)
        owed = 0
        for finding in result.data['findings']:
            safe = redact.redact(security.redact(finding, markers))
            # Match the recorder's identity when redaction changes an opaque session id.
            if safe['session_id'] != finding['session_id']:
                import hashlib
                safe['session_id'] = hashlib.sha256(finding['session_id'].encode()).hexdigest()
            owed += _trace_response(safe, root)
        counts.update(scanner='measured', scanner_owed=owed)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        counts['unreadable'] = 1
        print(f'scanner: unmeasured: {type(exc).__name__}; run bin/wuwei doctor', file=sys.stderr)
    return counts
