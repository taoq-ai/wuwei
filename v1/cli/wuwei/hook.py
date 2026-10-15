"""The hooks: teach at the moment, hold the few doors, remind once, and record. A hook that fails
lets the work go on and records why."""

import hashlib
import json
from pathlib import Path
import re
import sys

from wuwei import board, evidence, guards, verdict, ws

WAY = '''WUWEI is this workspace's process auditor. It does not tell you which command to run; it reads
what you produced and tells you what is still missing.
- Work the plan (.wuwei/plan.json, highest score first). The planner, lead, builder, sentinels,
  shepherd and steward follow their charters. Decide alone what the charters, standards and goals
  answer; record two-way choices under Assumptions. Ask the owner only for a one-way door, a change
  of scope or goals, a trust-boundary question or an owner review, with your recommendation, and
  start the question with its class: one-way:, scope:, goal:, trust:, infra: or owner review:.
  The plan is your mandate: never ask whether to continue planned work.
- Done means evidence: a PR naming its item (WUWEI-Item: <id>), a test in the diff, the gates the
  tier needs passing at the head (light: quality; standard: arch, quality, security; full: + goal),
  green CI, every review thread answered, a reviewer requested, owner review on owner_paths.
- Reviewers write verdict files under .wuwei/verdicts/<item>/ and end with "Verdict file: <path>".
- WUWEI refuses only: a merge with gaps, force or default-branch pushes, admin bypasses and
  protection writes, secrets in outward calls, and edits to its ledger. Infrastructure asks the owner.
- Plan again whenever the day changes: /wuwei-plan adds, drops or re-ranks. /wuwei-close checkpoints
  the day with the report and retro; planning again reopens it.'''


def _hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def last_text(payload):
    text = payload.get('last_assistant_message')
    if isinstance(text, str) and text.strip():
        return text
    path = payload.get('agent_transcript_path')
    found = ''
    try:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row.get('type') != 'assistant':
                continue
            for part in row.get('message', {}).get('content', []):
                if part.get('type') == 'text' and part.get('text', '').strip():
                    found = part['text']
                elif part.get('type') == 'tool_use' and isinstance(part.get('input', {}).get('message'), str):
                    found = part['input']['message']
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    return found


def context(event, text):
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def pre_tool(root, payload):
    found = guards.pre_tool(root, payload)
    if found is None:
        return None
    kind = {'deny': 'refused', 'ask': 'asked', 'note': 'note'}[found['decision']]
    ws.record(root, kind, {'tool': payload.get('tool_name'), 'reason': found['reason'][:500],
                           'session': payload.get('session_id')})
    if found['decision'] == 'note':
        return context('PreToolUse', found['reason'])
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': found['decision'],
                                   'permissionDecisionReason': 'WUWEI: ' + found['reason']}}


def closed(root):
    today = ws.today()
    marks = [row['kind'] for row in ws.ledger(root)
             if row.get('kind') in ('day.closed', 'plan.pass') and row.get('ts', '').startswith(today)]
    return bool(marks) and marks[-1] == 'day.closed'


def stop(root, payload):
    if payload.get('stop_hook_active') or closed(root):
        return None
    open_work = [f'{row["item"]}{" (" + row["pr"] + ")" if row["pr"] else ""}: {gap["text"]}'
                 for row in board.rows(root) for gap in row['gaps'] if gap['actionable']]
    if not open_work:
        return None
    name = f'stop-{payload.get("session_id", "")}'
    key = _hash('\n'.join(sorted(open_work)))
    if ws.cache_get(root, name, 7 * 86400) == key:
        return None
    ws.cache_put(root, name, key)
    ws.record(root, 'stop.reminded', {'open': len(open_work), 'session': payload.get('session_id')})
    return {'decision': 'block', 'reason': 'WUWEI: open work you can close now:\n' + '\n'.join(
        '- ' + line for line in open_work) + '\nThe plan is your mandate: do not ask the owner whether to continue. Close these, or say in '
        'one line why each waits, then stop.'}


def subagent_stop(root, payload):
    role = str(payload.get('agent_type', '')).rsplit(':', 1)[-1]
    ws.record(root, 'seat.stopped', {'role': role, 'agent': payload.get('agent_id'),
                                     'session': payload.get('session_id')})
    if not role.startswith('sentinel-'):
        return None
    problem = _verdict_problem(root, payload, role)
    if problem is None:
        return None
    if payload.get('stop_hook_active'):
        ws.record(root, 'verdict.missing', {'role': role, 'agent': payload.get('agent_id'), 'problem': problem[:300]})
        return None
    return {'decision': 'block', 'reason': 'WUWEI: ' + problem}


def _verdict_problem(root, payload, role):
    match = re.search(r'^Verdict file:\s*(\S+)\s*$', last_text(payload), re.M)
    if match is None:
        return f'end your report with a line "Verdict file: <path>" naming the verdict you wrote under .wuwei/verdicts/.'
    path = Path(match[1]) if Path(match[1]).is_absolute() else Path(root) / match[1]
    verdicts = (Path(root) / ws.DIR / 'verdicts').resolve()
    try:
        path = path.resolve()
        path.relative_to(verdicts)
        body = path.read_bytes()
    except (OSError, ValueError):
        return f'the verdict must be a readable file under .wuwei/verdicts/ (got {match[1]}).'
    parsed = verdict.parse(body.decode('utf-8', 'replace'))
    if parsed['errors']:
        return ('the verdict does not hold its shape:\n' + '\n'.join('- ' + e for e in parsed['errors'])
                + '\nRewrite it in this shape:\n' + verdict.FORMAT)
    gate = role.removeprefix('sentinel-')
    if parsed['gate'] != gate:
        return f'you are {role}; your verdict must say Gate: {gate}.'
    ws.record(root, 'attest', {'path': str(path.relative_to(Path(root).resolve())), 'sha256': hashlib.sha256(body).hexdigest(),
                               'gate': gate, 'item': parsed['item'], 'head': parsed['head'],
                               'pr': f'{parsed["repo"]}#{parsed["pr"]}', 'verdict': parsed['verdict'],
                               'role': role, 'agent': payload.get('agent_id'),
                               'transcript': payload.get('agent_transcript_path')})
    return None


def post_tool(root, payload):
    tool = payload.get('tool_name', '')
    data = payload.get('tool_input') or {}
    if ws.config(root)['telemetry']:
        target = data.get('command') or data.get('file_path') or data.get('url') or ''
        ws.trace(root, {'session': payload.get('session_id'), 'agent': payload.get('agent_id'), 'tool': tool,
                        'target': guards.SECRETS.sub('***', str(target))[:160],
                        'duration_ms': payload.get('duration_ms')})
    if tool == 'AskUserQuestion':
        return _answers(root, data, payload.get('tool_response'))
    if tool == 'Bash' and any(argv[:1] == ['gh'] and argv[1:3] == ['pr', 'create']
                              for argv, _ in guards.segments(str(data.get('command', '')))):
        match = re.search(r'https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)', json.dumps(payload.get('tool_response')))
        if match:
            gaps = evidence.gaps(root, match[1], int(match[2]))
            ws.cache_put(root, 'board', None)
            note = 'ready to merge once reviewed' if not gaps else 'still needs: ' + '; '.join(g['text'] for g in gaps)
            return context('PostToolUse', f'WUWEI: {match[1]}#{match[2]} {note}')
    return None


def _answers(root, data, response):
    questions = [q.get('question', '') for q in data.get('questions') or () if isinstance(q, dict)]
    answers = response.get('answers', {}) if isinstance(response, dict) else {}
    ws.record(root, 'prompt', {'questions': questions, 'answers': answers if isinstance(answers, dict) else str(answers)[:500]})
    for question in questions:
        match = re.search(r'owner review: ([\w.-]+/[\w.-]+)#(\d+) at ([0-9a-f]{7,40})', question)
        answer = str(answers.get(question, '')) if isinstance(answers, dict) else ''
        if match and answer:
            ws.record(root, 'ruling', {'pr': f'{match[1]}#{match[2]}', 'head': match[3],
                                       'approved': answer.strip().lower().startswith(('yes', 'approve')),
                                       'question': question, 'answer': answer})
    return None


PLUGIN = Path(__file__).resolve().parents[2]


def session_start(root, payload):
    parts = [WAY] + [(PLUGIN / 'charters' / name).read_text(encoding='utf-8').strip()
                     for name in ('_common.md', 'planner.md') if (PLUGIN / 'charters' / name).is_file()]
    for name in ('goals.md', 'standards.md'):
        path = Path(root) / ws.DIR / name
        if path.is_file() and path.read_text(encoding='utf-8').strip():
            parts.append(f'{name}:\n' + path.read_text(encoding='utf-8').strip()[:3000])
    try:
        parts.append(board.text(board.rows(root)))
    except Exception as exc:  # the board is orientation; a session never waits on it
        parts.append(f'Board unreadable: {exc}')
    return context('SessionStart', '\n\n'.join(parts))


HANDLERS = {'PreToolUse': pre_tool, 'PostToolUse': post_tool, 'Stop': stop, 'SubagentStop': subagent_stop,
            'SessionStart': session_start}


def handle(root, event, payload):
    handler = HANDLERS.get(event)
    if handler is None:
        return None
    try:
        return handler(root, payload)
    except Exception as exc:  # fail open: work goes on, the audit records why
        message = f'{type(exc).__name__}: {exc}'[:300]
        print(f'wuwei hook {event}: {message}', file=sys.stderr)
        try:
            ws.record(root, 'hook.error', {'event': event, 'error': message})
        except Exception:
            pass
        return None


def main(event):
    try:
        payload = json.loads(sys.stdin.read() or '{}')
    except ValueError:
        return 0
    root = ws.find(payload.get('cwd'))
    if root is not None:
        out = handle(root, event, payload)
        if out:
            print(json.dumps(out))
    return 0
