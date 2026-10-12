"""S2 trace response and mandatory S4 security measurement."""

import json
from pathlib import Path
import re
import sys

from wuwei import redact, registry, security, state, workspace
from wuwei.exits import ADAPTER_DATA


# Static checks for secrets, unvalidated input, execution and data exposure.
TRUST_RULES = {'SA001', 'SA002', 'SA003', 'SA007', 'SA008', 'SA009', 'SA010'}
# P1: the fix for a scanner that cannot measure today; doctor never runs ZIRAN.
OFF = "bin/wuwei config set adapters.scanner '\"none\"'"
# Tools that stay on the machine; Bash egress and deploys are the edges guards' (#870).
LOCAL = frozenset({'Read', 'Grep', 'Glob', 'Edit', 'MultiEdit', 'Write', 'NotebookEdit', 'Bash'})


def rows(tree, item, flags, config, root, changed):
    """The S4 rows of findings in the item's changed files (S8: findings already on main in
    files it did not change are the morning discovery's, not this item's)."""
    if workspace.guard_scope({'cwd': str(tree)}) != root:
        raise OSError('scanner: unmeasured: reviewed worktree is outside the workspace; write the gate brief with --worktree inside the workspace')
    scanner = registry.load('scanner', config)
    audit = scanner.audit(str(tree), root=root)
    if audit.exit not in (0, 1):
        raise _unmeasured(tree, item, audit.reason)
    threshold = config['scanner']['severity_threshold']
    gate = scanner.gate(audit.data, threshold, root=root)
    if gate.exit not in (0, 1):
        raise _unmeasured(tree, item, gate.reason)
    if audit.data['files_analyzed'] == 0:  # F5: measured, but ZIRAN covered nothing here
        return [NOTHING]
    levels = ('critical', 'high', 'medium', 'low')
    markers = security.load(root)
    result = []
    for finding in audit.data['findings']:
        try:
            source = (tree / finding['file']).resolve(strict=True)
            location = source.relative_to(tree.resolve())
            # F2: ZIRAN names a symlink by its own path; the diff names the link, not its target.
            raw = Path(finding['file'])
            raw = str(raw.relative_to(tree.resolve()) if raw.is_absolute() else raw)
            with source.open(encoding='utf-8') as stream:
                stream.read()
        except (OSError, ValueError):
            raise _unmeasured(tree, item, 'a finding source is unreadable or outside the worktree') from None
        if str(location) not in changed and raw not in changed:
            continue
        blocks = (flags['trust_surface'] or flags['boundary_relevant']
                  or finding.get('trust_boundary', False)
                  or finding['rule'] in TRUST_RULES
                  or levels.index(finding['severity']) <= levels.index(threshold))
        rule, location, message = redact.redact(security.redact(
            [finding['rule'], str(location), finding['message']], markers))
        message = re.sub(r'[^a-zA-Z0-9 .,:()/=_-]', ' ', message)
        # S1: a file-level finding (SA002, line null) is the file's line 1, the file:line a verdict needs.
        result.append(f"- {finding['severity']} | {location}:{finding['line'] or 1} | "
                      f"ZIRAN {rule} scenario: {message} | "
                      f"blocks: {'yes' if blocks else 'no'}")
        state.append_event('scanner.finding', {
            'source': 'ziran', 'item': item, 'rule': rule,
            'severity': finding['severity'], 'blocks': blocks,
        }, root)
    return result


def _unmeasured(tree, item, reason):
    """P1: the worktree and the fix; an agent_surface item needs a measured scanner."""
    return OSError(f'scanner: unmeasured: {tree}: {reason}; rerun bin/wuwei dispatch receive, '
                   f'or park the item with bin/wuwei plan park {item} --reason "<why>"')


NOTHING = 'Note: ZIRAN analyzed no file in this worktree (no Python or agent file), so it measured nothing here.'


def merge(text, findings):
    if not findings:
        return text
    if any(finding.endswith('blocks: yes') for finding in findings):
        text = re.sub(r'^(?:## |- )?Verdict:? *PASS\b', 'Verdict: FIX', text, flags=re.M)
    return text + '\n\n## ZIRAN findings\n' + '\n'.join(findings) + '\nProbe: ziran audit\n'


# #870: where credentials live; redact's broader name check stays for redaction only.
CREDENTIAL_PARTS = ('.ssh', '.netrc', '.npmrc', '.pypirc', '.git-credentials', '.gnupg')
CREDENTIAL_ENDS = ('.aws/credentials', 'gh/hosts.yml', '.pem', '.key', '.wuwei/env')


# ponytail: a name match on recorded arguments; globs (cred*), quote splitting (cred''entials),
# python string building, base64, `gh auth token`, and what the recorder's redaction hides
# (heredoc bodies, curl -d @file, the tail of commands over 2048 chars) pass. The canary, honeytoken and edges stay the floor;
# a read check at PreToolUse is the upgrade.
def _credential_path(text):
    """A path-like word (a '/', or a leading '~' or '.') naming a credential location."""
    for word in re.split(r'[\s\'"=@<>|;&()]+', text.replace('\\', '/').lower()):
        if '/' not in word and not word.startswith(('~', '.')):
            continue
        parts = word.split('/')
        if (any(part in CREDENTIAL_PARTS or part == '.env' or part.startswith('.env.')
                and not part.endswith(('example', 'sample', 'template')) for part in parts)
                or word.endswith(CREDENTIAL_ENDS)):
            return True
    return False


def _spans(line):
    """#870, S9: the (session id, tool) of each span of one trace line and whether a span names
    a credential location in a path or shell command; nothing for a line that is not a recorder span."""
    spans, private = [], False
    try:
        for resource in json.loads(line)['resourceSpans']:
            for scope in resource['scopeSpans']:
                for span in scope['spans']:
                    found = {row['key']: row['value']['stringValue'] for row in span['attributes']}
                    if isinstance(found['session.id'], str):
                        spans.append((found['session.id'], found.get('gen_ai.tool.name')))
                    arguments = json.loads(found['gen_ai.tool.arguments'])
                    private = private or any(isinstance(arguments.get(key), str) and _credential_path(arguments[key])
                                             for key in ('file_path', 'path', 'command'))
    except (ValueError, KeyError, TypeError, AttributeError):
        pass  # not a recorder span; ZIRAN skips it too
    return spans, private


def _trace_response(finding, root, sweep):
    """Seats: page and park the affected items. A registered session: one silent traces.noted
    per day. Unknown: one traces.unmatched per day (#352). Returns True when the finding paged.
    sweep holds the day's events, state and credential reads, read once per sweep (S9)."""
    import hashlib
    from wuwei import brief, sessions

    session = finding['session_id']
    digest = hashlib.sha256(session.encode()).hexdigest()
    data, events = sweep['data'], sweep['events']
    # #676: an adhoc seat is the audit record, not an item seat; its session keeps its launcher's rule.
    seat = any(session in seat.get('trace_sessions', []) for seat in brief.seats(data).values()
               if seat['role'] != 'adhoc')
    role = None if seat else sessions.registered(data, session)
    if not seat:
        kind = 'traces.noted' if role else 'traces.unmatched'
        if not any(row['kind'] == kind and row['payload'].get('session_digest') == digest for row in events):
            extra = {'role': role, 'summary': f'traces: {role} session, chain noted'} if role else {}
            payload = {'session_digest': digest, 'chain': finding['chain'], **extra}
            state.append_event(kind, payload, root)
            events.append({'kind': kind, 'payload': payload})
        return False
    mine = [row['payload'] for row in events
            if row['kind'] == 'scanner.finding' and row['payload'].get('session_id') == session]
    # S6, S9: the sweep reads only new spans, so a chain recorded in this window (a retry after a
    # failed park) never parks twice, and the same chain in later spans after a resume parks again.
    # A finding recorded before #896 has no since and keeps the day-long dedup.
    if any(row.get('chain') == finding['chain'] and row.get('since', finding['since']) == finding['since']
           for row in mine):
        return False
    # Review F1: a window carries the last span of each tool the session used before it, so a
    # recorded chain parks again only when its source and sink both ran in this window's new spans.
    if (any(row.get('chain') == finding['chain'] for row in mine)
            and not {finding['chain'][0], finding['chain'][-1]} <= sweep['new'].get(session, set())):
        return False
    reason = 'scanner chain ' + ' -> '.join(finding['chain'])
    # #870: a chain of local file and shell tools only is the builder loop (edit, test, write),
    # unless the session touched a private file (a credential read, then curl from Bash).
    # Review D1: a resumed credential park covers the read for the chain the owner saw only.
    # ponytail: a write outside the worktree is not told apart; check the spans' paths if it must park.
    read = sweep['credential'].get(session, -1)
    if LOCAL.issuperset(finding['chain']):
        seen = max((row['until'] for row in mine if type(row.get('until')) is int
                    and row.get('chain') == finding['chain']
                    and str(row.get('reason', '')).endswith('after a credential read')), default=0)
        if read < seen:
            return False
    if read >= 0:  # review D2: any park names a credential read today, so the owner resumes knowing
        reason += ' after a credential read'
    _park(finding, reason, root)
    events.append({'kind': 'scanner.finding', 'payload': {**finding, 'reason': reason}})
    return True


def honeytoken(session, root, timeout=30):
    """#878: an item seat's honeytoken read parks its items and holds the close
    (closing.scanner_hold) like a critical chain; other sessions keep the security page."""
    from wuwei import brief
    finding, reason = {'chain': ['security.honeytoken'], 'risk_level': 'critical', 'session_id': session}, 'security.honeytoken read'
    try:
        if any(session in seat.get('trace_sessions', []) for seat in brief.seats(state.read_state(root)).values()
               if seat['role'] != 'adhoc'):
            _park(finding, reason, root, timeout)
    except Exception:
        # Fail closed: the close holds when the seat check or the park failed; the same payload is one card.
        state.append_event('scanner.finding', {**finding, 'reason': reason}, root, timeout=timeout)
        raise


def _park(finding, reason, root, timeout=30):
    """#862 F3: the finding and the park are one write, so the S6 dedup never sees a finding
    whose park failed."""
    from wuwei import brief

    def update(data):
        items = {seat['item'] for seat in brief.seats(data).values()
                 if finding['session_id'] in seat.get('trace_sessions', [])}
        for name in items:
            item = data['items'].get(name)
            if item is not None and 'parked' in state.PHASES[item['phase']]:
                item.update(phase='parked', status='blocked', disposition={'kind': 'parked', 'reason': reason})

    state._write_state(update, root, kind='scanner.finding', payload={**finding, 'reason': reason}, timeout=timeout)


SWEEP = 'trace-sweep.json'
# S9: ZIRAN enumerates paths and cycles over each session's tool multigraph, so its time grows
# steeply with a session's spans (ZIRAN 0.40.0, 40 sessions of varied tools: 1000 spans 3.9 s,
# 2000 spans 56 s). 20 per session plus the carried spans keeps a day of 3000 such spans at about 24 s.
PER_SESSION = 20


def _offset(day, data):
    """The stored sweep mark {offset, credential, carry, unmeasured?} when it fits today's spans:
    credential {session: line start of its last credential read}, carry {session: {tool: [start,
    end]}} of each tool's last span before the offset. A damaged one starts the day again."""
    def line(start, end, limit):
        return (type(start) is type(end) is int and 0 <= start < end <= limit and data[end - 1:end] == b'\n'
                and (start == 0 or data[start - 1:start] == b'\n'))
    try:
        mark = json.loads((day / SWEEP).read_text(encoding='utf-8'))
        offset, credential, carry = mark['offset'], mark.get('credential', {}), mark.get('carry', {})
        if (type(offset) is int and 0 <= offset <= len(data) and (offset == 0 or data[offset - 1:offset] == b'\n')
                and all(isinstance(name, str) and type(start) is int and 0 <= start < offset
                        for name, start in credential.items())
                and all(isinstance(name, str) and isinstance(tool, str) and line(*span, offset)
                        for name, tools in carry.items() for tool, span in tools.items())):
            return {'offset': offset, 'credential': credential, 'carry': carry,
                    **({'unmeasured': mark['unmeasured']} if isinstance(mark.get('unmeasured'), str) else {})}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return {'offset': 0, 'credential': {}, 'carry': {}}


def trace_sweep(root, config):
    """Page and park on today's scanner chains (dispatch receive and close run it); returns the
    counts, including empty-day status. S9: only the lines since the last measured sweep are
    parsed and given to ZIRAN, in windows of at most PER_SESSION new spans per session; review
    F1: each window starts with the last span of every tool its sessions used before it, so a path
    from any earlier tool into the new spans stays in the graph.
    ponytail: two sweeps at once may both page one window; ZIRAN bounding its chain search is the upgrade."""
    import hashlib
    import tempfile
    counts = {'scanner': 'unmeasured', 'scanner_owed': 0, 'unreadable': 0}
    day = workspace.day_dir(root)
    data, mark, failed = b'', {'offset': 0, 'credential': {}, 'carry': {}}, None
    try:
        path = day / 'traces.jsonl'
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if path.is_symlink():
                raise ValueError(f'unreadable trace input; {ADAPTER_DATA}') from None
        mark = _offset(day, data)  # a truncated, replaced or forged mark reads the day again
        if not data.strip():
            counts['scanner'] = 'no sessions'
            return counts
        if config['adapters']['scanner'] == 'none':
            counts['scanner'] = 'not configured'
            return counts
        credential, carry = dict(mark['credential']), {name: dict(tools) for name, tools in mark['carry'].items()}
        window, windows, seen, start = [], [], {}, mark['offset']
        for line in data[start:data.rfind(b'\n') + 1].split(b'\n')[:-1]:  # a partial last line waits
            line += b'\n'
            spans, private = _spans(line)
            names = {name for name, _ in spans}
            for name in names if private else ():
                credential[name] = start
            if window and any(seen.get(name, 0) >= PER_SESSION for name in names):
                windows.append(window)
                window, seen = [], {}
            window.append((start, line, spans))
            seen.update((name, seen.get(name, 0) + 1) for name in names)
            start += len(line)
        windows += [window] if window else []
        hashed = {hashlib.sha256(name.encode()).hexdigest(): start for name, start in credential.items()}
        scanner, markers, owed = registry.load('scanner', config), security.load(root), 0
        sweep = {'credential': {**credential, **hashed}}
        for window in windows:
            since, until = window[0][0], window[-1][0] + len(window[-1][1])
            new = {}
            for _, _, spans in window:
                for name, tool in spans:
                    new.setdefault(name, set()).add(tool)
            head = sorted({tuple(span) for name in new for span in carry.get(name, {}).values()})
            with tempfile.TemporaryDirectory(prefix='wuwei-sweep-') as directory:
                file = Path(directory) / 'window.jsonl'
                file.write_bytes(b''.join(data[a:b] for a, b in head) + b''.join(line for _, line, _ in window))
                result = scanner.traces(str(file), root=root)
            if type(result.exit) is not int or result.exit not in (0, 1):
                failed = result.reason or 'scanner unavailable; retry at the next receive or close'
                raise ValueError(failed)
            sweep['new'] = {**new, **{hashlib.sha256(name.encode()).hexdigest(): tools for name, tools in new.items()}}
            for finding in result.data['findings']:
                safe = redact.redact(security.redact(finding, markers))
                # Match the recorder's identity when redaction changes an opaque session id.
                if safe['session_id'] != finding['session_id']:
                    safe['session_id'] = hashlib.sha256(finding['session_id'].encode()).hexdigest()
                if 'events' not in sweep:
                    from wuwei import watch
                    sweep.update(events=watch.records(day / 'events.jsonl'), data=state.read_state(root))
                owed += _trace_response({**safe, 'since': since, 'until': until}, root, sweep)
            for start, line, spans in window:
                for name, tool in spans:
                    if isinstance(tool, str):
                        carry.setdefault(name, {})[tool] = [start, start + len(line)]
            mark = {'offset': until, 'credential': {name: at for name, at in credential.items() if at < until},
                    'carry': carry}
            workspace.atomic_write(day / SWEEP, json.dumps(mark))
        if 'unmeasured' in mark:
            mark.pop('unmeasured')
            workspace.atomic_write(day / SWEEP, json.dumps(mark))
        counts.update(scanner='measured', scanner_owed=owed)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        counts['unreadable'] = 1
        detail = str(exc) if type(exc) is ValueError else type(exc).__name__  # CLI-authored reasons only
        print(f"scanner: unmeasured: today's trace sweep: {detail}; retry at the next receive or close, "
              f'or run {OFF} to switch the scanner off', file=sys.stderr)
        try:  # doctor reads the mark; one scanner.unmeasured event per distinct scanner failure
            if failed and failed != mark.get('unmeasured'):
                state.append_event('scanner.unmeasured', {'source': 'traces', 'reason': failed}, root)
            workspace.atomic_write(day / SWEEP, json.dumps({**mark, 'unmeasured': detail}))
        except (OSError, ValueError):
            pass
    return counts
