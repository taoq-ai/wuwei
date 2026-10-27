"""The hooks: teach at the moment, hold the few doors, remind once, and record. A hook that fails
lets the work go on and records why; a door call it fails on is refused."""

import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
from stat import S_ISREG
import sys
import time

from wuwei import agents, board, evidence, guards, plan, sync, verdict, view, ws


def transcript(payload):
    """The seat's last report, its input plus output tokens, whether a hand-back ended its run, and every report it wrote,
    read from its transcript under ws.PROJECTS ('', None, False and [] when unreadable)."""
    found, total, ended, said = '', None, False, []
    try:
        for row in transcript_rows(payload.get('agent_transcript_path'), '') or ():
            if usage := row.get('message', {}).get('usage') or {}:
                total = (total or 0) + usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            content = row.get('message', {}).get('content', [])
            if ended and row.get('type') == 'user' and isinstance(content, list) and any(
                    isinstance(p, dict) and p.get('is_error') and p.get('tool_use_id') == ended for p in content):
                ended = False  # the harness refused it (outside auto mode): it delivered nothing
            for part in content if row.get('type') == 'assistant' else ():
                if part.get('type') == 'text' and part.get('text', '').strip():
                    found, ended = part['text'], False
                elif part.get('type') == 'tool_use' and isinstance(part.get('input', {}).get('message'), str):
                    found, ended = part['input']['message'], part.get('name') == 'SubagentHandback' and (part.get('id') or True)
                said.append(found)
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    return found, total, bool(ended), said


def last_text(payload):
    return text if isinstance(text := payload.get('last_assistant_message'), str) and text.strip() else transcript(payload)[0]


def context(event, text):
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def pre_tool(root, payload):
    try:  # the doctor's hooks row reads it; a failed stamp never changes the guards' decision
        ws.cache_put(root, 'hook-seen', ws.now().timestamp())
        ws.cache_put(root, 'hook-python', f'{sys.executable} {sys.version.split()[0]}')  # the doctor names the launcher's choice
    except Exception as exc:
        print(f'wuwei hook PreToolUse: the hook-seen stamp failed: {exc}'[:300], file=sys.stderr)
    role = str(payload.get('agent_type', '')).rsplit(':', 1)[-1]  # the harness's, never the message's
    report = payload.get('tool_name') == 'SubagentHandback' and role.startswith('sentinel-') and _report(
        root, payload, str((payload.get('tool_input') or {}).get('message', '')))
    problem = isinstance(report, str) and _verdict_problem(root, {**payload, 'last_assistant_message': report}, role)
    away = payload.get('tool_name') == 'SubagentHandback' and payload.get('permission_mode') in ('default', 'plan', 'acceptEdits', 'dontAsk', 'bypassPermissions')
    item = payload.get('tool_name') in ('Agent', 'Task') and asked(payload.get('tool_input') or {})[0]  # as seat.started records it: so here, not in guards
    held = next((guards.deny(f'item {item} is held by session {s["session"]} ({s.get("role")} seat {s.get("agent")} running): leave it to that session, or launch after its seat stops.')
                 for s in (board.running(root) if item else ()) if str(s.get('item') or '').lower() == item.lower() and s['session'] != payload.get('session_id')), None)
    found = {'decision': 'deny', 'reason': (problem + '\n' if problem else '') + (AWAY if away else 'Then hand back again.')} \
        if problem or away else guards.pre_tool(root, payload) or held
    if found is None:
        return advise(root, payload.get('tool_input') or {}, crowded(root, payload)) if payload.get('tool_name') in ('Agent', 'Task') else None
    kind = {'deny': 'refused', 'ask': 'asked', 'note': 'note'}[found['decision']]
    try:  # the decision stands even when its record fails
        ws.record(root, kind, {'tool': payload.get('tool_name'), 'reason': found['reason'][:500], 'session': payload.get('session_id')})
    except Exception as exc:
        print(f'wuwei hook PreToolUse: the {kind} record failed: {exc}'[:300], file=sys.stderr)
    if found['decision'] == 'note':
        return context('PreToolUse', found['reason'])
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': found['decision'],
                                   'permissionDecisionReason': 'WUWEI: ' + found['reason']}}


def asked(data):
    """The item the brief names (its first Item: line, list or bold too, else its first Item:), the effort asked for (the call's, else the brief's Model: line) and its Model reason: line."""
    item, line, reason = (re.search(p, str(data.get('prompt', '')), re.M) for p in (
        r'\A(?:[\s\S]*?^[ \t]*(?:[-*+][ \t]+)?\**|[\s\S]*?\b)Item:\**[ \t]*`?([\w.-]+)', r'^Model:[ \t]*\S+[^\r\n]*?[ \t]+(low|medium|high|xhigh|max|ultra)(?=[ \t\r(]|$)', r'^Model reason:[ \t]*(\S.*)$'))
    return item and item[1].rstrip('.'), str(data.get('effort') or '') or line and line[1], reason and reason[1].strip()[:200]


def requested(data):
    return data.get('model') or ((re.findall(r'^Model:[ \t]*(\S+)', str(data.get('prompt', '')), re.M) or [None])[0] if 'agent_type' in data else None)


def crowded(root, payload):  # advice on a launch past the seat ceiling, never a door
    seats, ceiling = [s['session'] for s in board.running(root)].count(payload.get('session_id')), board.limit(root, 'Seat ceiling', 8)
    return (f'WUWEI: seat {seats + 1} running in this session, over the ceiling of {ceiling}: turns slow and rate limits come sooner. '
            'Tell the owner once; start it if the owner asked.') if seats >= ceiling else ''


def advise(root, data, note=''):
    """A note on a launch that departs from agents.TABLE or the owner's models rows, after the seat ceiling's note; never a refusal or a rewrite."""
    role, (item_id, effort, reason) = str(data.get('subagent_type', '')).rsplit(':', 1)[-1], asked(data)
    if role not in agents.TABLE or not data.get('prompt'):
        return context('PreToolUse', note) if note else None
    item, table, rows = (plan.find(root, item_id) if item_id else None) or {}, agents.TABLE[role], ws.config(root)['models']
    tier, repo = item.get('tier', 'standard'), str(item.get('repo', ''))
    if repo and ws.cache_get(root, 'budget-' + repo.replace('/', '__'), 86400) and evidence.budget(root, repo)['raised']:
        tier = evidence.RAISE.get(tier, tier)  # the cached rate only: a launch never waits on the code host
    if 'agent_type' in data:
        return context('PreToolUse', note + f"\nWUWEI: Codex table says {' '.join(agents.codex_setting(role, rows, tier))} for {role} at {tier}; "
                       f"requested: {requested(data) or 'unrecorded'} {effort or 'unrecorded'}; fork policy: {dict(all='inherit', none='fresh').get(str(data.get('fork_turns')), 'unmeasured')}. "
                       'Resolved child model is unmeasured until provider metadata; use overrides only when the active schema supports them.')
    allowed = [(own, '')] if (own := rows.get(f'{role} {tier}') or rows.get(role)) else [
        (table.get(tier, table['']), '')] + [(setting, when) for when, setting in table.items() if ' ' in when]
    fam = lambda name: (re.findall('fable|opus|sonnet|haiku', name.lower()) or [name.lower()])[0]  # noqa: E731
    model, effort = str(data.get('model') or table[''].rsplit(' ', 1)[0]), effort or table[''].rsplit(' ', 1)[1]
    named = str([raw.get(k) for k in (f'{role} {tier}', role)] if isinstance(raw := ws.raw_config(root).get('models'), dict) else '')
    floor = role.startswith('sentinel-') and (fam(model) == 'haiku' or 'haiku' in named.lower())  # a row, even one config() drops
    if not floor and (reason or any((os.environ.get('CLAUDE_CODE_SUBAGENT_MODEL') or fam(s.rsplit(' ', 1)[0]) == fam(model)) and
                                    (os.environ.get('CLAUDE_CODE_EFFORT_LEVEL') or s.rsplit(' ', 1)[1] == effort) for s, _ in allowed)):
        return context('PreToolUse', note) if note else None
    return context('PreToolUse', note + '\n' * bool(note) + f"WUWEI: table says {allowed[0][0]} for {role} at {tier}; record a 'Model reason:' line in the "
                   f"brief (asked: {model} {effort}" + ''.join(f'; the row also allows {s} {when}' for s, when in allowed[1:]) + ').' + (
                       " Haiku 5.5 never runs a gate on risky, owner or contract paths, and neither a reason nor a models row "
                       "covers that: it is an exception: for the owner." if floor else ''))


def closed(root):
    marks = [row['kind'] for row in ws.ledger(root)
             if row.get('kind') in ('day.closed', 'plan.pass') and row.get('ts', '').startswith(ws.today())]
    return bool(marks) and marks[-1] == 'day.closed'


def stop(root, payload):
    if payload.get('stop_hook_active') or closed(root) or any(s['session'] == payload.get('session_id') for s in board.running(root)):
        return None  # a running seat's completion wakes the planner anyway
    rows = board.rows(root)
    open_work = [f'{row["item"]}{" (" + row["pr"] + ")" if row["pr"] else ""}: {gap["text"]}'
                 for row in rows for gap in row['gaps'] if gap['actionable']]
    waiting = sum(1 for row in rows for gap in row['gaps'] if not gap['actionable'])
    recent = (ws.now() - datetime.timedelta(hours=1)).isoformat(timespec='seconds')
    if not open_work and waiting and not any(r['ts'] >= recent for r in ws.rows(root, 'watch.pass')):
        open_work = ['nothing will wake this session for the waiting work unless a check-in or PR subscription is armed, which WUWEI '
                     'cannot see: arm /wuwei-watch on a schedule (/loop 20m /wuwei-watch locally; in the cloud both)']
    elif not rows and (Path(root) / ws.DIR / 'goals.md').is_file():  # the flow never waits on the owner's nudge
        open_work = ['the queue is empty: run a plan pass from the goals (/wuwei-run)']
    if not open_work:
        return None
    name, last = f'stop-{payload.get("session_id", "")}', ws.cache_get(root, f'stop-{payload.get("session_id", "")}', 7 * 86400)
    seen, since = (last.get('lines', []), last.get('ts', '')) if isinstance(last, dict) else ([], '')
    new = [line for line in open_work if line not in seen]  # only what changed since the last reminder (#1099)
    ws.cache_put(root, name, {'lines': open_work, 'ts': ws.now().isoformat(timespec='minutes') if new else since})
    if not new:
        return None
    ws.record(root, 'stop.reminded', {'open': len(open_work), 'session': payload.get('session_id')})
    shown = '\n'.join('- ' + line for line in new[:10])
    more = f'\nand {len(new) - 10} more (wuwei status lists all)' if len(new) > 10 else ''
    more += f'\n{len(open_work) - len(new)} more unchanged since {since} (wuwei status lists all)' if len(new) < len(open_work) else ''
    held = f'\nLeft out: {waiting} waiting on CI, the owner, plan approval, an andon or the WIP limit.' if waiting else ''
    return {'decision': 'block', 'reason': 'WUWEI: open work you can close now:\n' + shown + more + held +
            '\nThe plan is your mandate: do not ask the owner whether to continue. Close these, or say in '
        'one line why each waits, then stop.'}


def transcript_rows(path, key):  # the rows naming key in a regular file under ws.PROJECTS, links resolved (None: not one)
    try:  # split on newlines only: a JSON string may hold U+2028 and kin raw, and str.splitlines() splits there
        real = Path(path).resolve(strict=True)
        return [json.loads(line) for line in real.read_bytes().splitlines() if key.encode() in line] if real.is_relative_to(
            ws.PROJECTS.resolve()) and real.is_file() else None
    except (OSError, TypeError, ValueError, RuntimeError, AttributeError):  # AttributeError: a key that is no string
        return None


def parts(rows, kind):
    return [p for r in rows for p in (r.get('message') or {}).get('content') or () if isinstance(p, dict) and p.get('type') == kind]


def _report(root, payload, text):
    """The seat's report as its own transcript holds it (#962): the text the payload carries, else its last. The transcript is
    read only when the harness shows the launch: the meta file beside it names the seat's type and an Agent tool_use the
    session transcript holds. One the harness may still be writing is reread (about 2 s). Else seat.unconfirmed, and None."""
    agent, role, text = payload.get('agent_id'), str(payload.get('agent_type', '')).rsplit(':', 1)[-1], text if text.strip() else ''
    path = str(payload.get('agent_transcript_path') or  # a PreToolUse payload names the session's: the seat's lies beside it
               Path(str(payload.get('transcript_path')).removesuffix('.jsonl'), 'subagents', f'agent-{agent}.jsonl'))
    meta = (transcript_rows(path.removesuffix('.jsonl') + '.meta.json', 'toolUseId') or [{}])[0] if Path(path).name == f'agent-{agent}.jsonl' else {}
    use = meta.get('toolUseId') if str(meta.get('agentType')).rsplit(':', 1)[-1] == role else None
    why = f'the session transcript shows no {role} launch for agent {agent}'
    if use and any(p.get('id') == use and p.get('name') in ('Agent', 'Task')
                   for p in parts(transcript_rows(payload.get('transcript_path'), use) or [], 'tool_use')):
        for _ in range(9):
            found, _, _, said = transcript({'agent_transcript_path': path})
            if (text == found if text else found.strip()) or not Path(path).is_file():
                break
            time.sleep(0.25)
        if not text or text == found:  # only the seat's last report: an earlier one replayed would attest what it named then
            return text or found
        why = f'the payload of {role} {agent} replays an earlier report, not its last' if text in said else \
            f'the transcript of {role} {agent} does not hold the report its payload carries'
    ws.record(root, 'seat.unconfirmed', {'role': role, 'agent': agent, 'session': payload.get('session_id'), 'reason': why})
    return None


def _kept_report(path, folder):
    try:
        if path.name.count('--') != 3 or not re.fullmatch(
                r'[\w-]+--[\w-]+--(?:' + '|'.join(agents.TABLE) + r')--[1-9][0-9]*\.md', path.name) or not S_ISREG(path.stat(follow_symlinks=False).st_mode):
            return None
        text = path.read_bytes().decode('utf-8')
        return (path, text) if text.strip() else None
    except FileNotFoundError:
        return _kept_report(folder / path.name, folder) if path.parent != folder else None
    except (OSError, UnicodeError):
        return None


def subagent_stop(root, payload):
    """A stop counts only when the seat's own transcript holds its report (_report); else seat.unconfirmed, and nothing more."""
    role, text = str(payload.get('agent_type', '')).rsplit(':', 1)[-1], payload.get('last_assistant_message')
    if (report := _report(root, payload, text if isinstance(text, str) else '')) is None:
        return None
    payload = {**payload, 'last_assistant_message': report}
    _, tokens, ended, _ = transcript(payload)
    out = _seat_stop(root, payload, role, tokens, ended)
    if out is None and not ended and role in agents.TABLE and payload['last_assistant_message'].strip():  # keep what the harness drops
        name = '--'.join(re.sub(r'[^\w-]', '', str(v or '')) for v in (payload.get('session_id'), payload.get('agent_id'), role))
        folder = Path(root) / ws.DIR / 'reports'
        kept = max((r for d in (folder / 'pending', folder) for p in d.glob(f'{name}--*.md') if (r := _kept_report(p, folder))),
                   key=lambda r: int(r[0].stem.rsplit('--', 1)[-1]), default=None)
        if kept is None or kept[1] != payload['last_assistant_message']:  # only the latest valid version can repeat
            ws.atomic_write(folder / 'pending' / f'{name}--{time.time_ns()}.md', payload['last_assistant_message'], Path(root))
    return out


def _seat_stop(root, payload, role, tokens, ended):
    ws.record(root, 'seat.stopped', {'role': role, 'agent': payload.get('agent_id'), 'tokens': tokens,
                                     'confidence': (m := re.search(r'^Confidence:\s*(low|medium|high)\b', last_text(payload), re.M | re.I)) and m[1].lower(),
                                     'session': payload.get('session_id')})
    if not role.startswith('sentinel-'):
        if payload['last_assistant_message'].strip():
            return None
        if payload.get('stop_hook_active'):
            ws.record(root, 'seat.silent', {'role': role, 'agent': payload.get('agent_id')})
            return None
        return {'decision': 'block', 'reason': 'WUWEI: you ended without a report. End with it as plain text '
                '(what you did, Blocked:, Gap:); when SubagentHandback is refused, the last message is the report.'}
    if (problem := _verdict_problem(root, payload, role)) is None:
        return None
    if payload.get('stop_hook_active') or ended:  # a block after either reaches no one: record it instead
        ws.record(root, 'verdict.missing', {'role': role, 'agent': payload.get('agent_id'), 'problem': problem[:300]})
        return None
    return {'decision': 'block', 'reason': 'WUWEI: ' + problem}


def _verdict_problem(root, payload, role):
    if (match := re.search(r'^Verdict file:\s*(\S+)\s*$', last_text(payload), re.M)) is None:
        return f'end your report with a line "Verdict file: <path>" naming the verdict you wrote under .wuwei/verdicts/.'
    path = Path(match[1]) if Path(match[1]).is_absolute() else Path(root) / match[1]
    verdicts = Path(root) / ws.DIR / 'verdicts'
    def free(p):  # the next <stem>-N.md beside p that no file or link holds, the folder listed once
        try:
            return next(n for held in [{q.name for q in p.parent.iterdir()}] for i in range(2, 999)
                        if (n := re.sub(r'(?<=[0-9a-f]{7})-[0-9]+$', '', p.stem) + f'-{i}.md') not in held) + ' beside it (the next free number)'
        except (OSError, StopIteration):
            return f'a new name of your own beside it (none of -2 to -998 is free, or {p.parent} cannot be listed)'
    try:
        verdicts, path = verdicts.resolve(), path.resolve()  # a loop raises RuntimeError on 3.11 and 3.12
        if not path.is_relative_to(verdicts) and '/.wuwei/verdicts/' in path.as_posix():  # written in a worktree: copied in
            copy, body = Path(root).resolve() / ws.DIR / 'verdicts' / path.as_posix().split('/.wuwei/verdicts/', 1)[1], path.read_bytes()
            if link := next((p for p in (copy, *copy.parents) if p.is_symlink()), None):  # it would carry the write out
                return f'{link} is a symlink on the way to {copy}: leave it, and report it under Blocked: for the owner.'
            if copy.exists() and copy.read_bytes() != body:
                return f'{copy} already holds another verdict: write yours as {free(copy)}.'
            ws.atomic_write(copy, body, Path(root).resolve())  # no folder swapped for a link after the check is followed
            path = copy
        path.relative_to(verdicts)
        body = path.read_bytes()
    except (OSError, ValueError, RuntimeError):
        return f'the verdict must be a readable file under {verdicts.as_posix()}/ (got {match[1]}).'
    rel, sha = path.relative_to(Path(root).resolve()).as_posix(), hashlib.sha256(body).hexdigest()  # / on every OS
    earlier = [row['data'] for row in ws.rows(root, 'attest') if row['data'].get('path') == rel]
    if any(row.get('sha256') == sha for row in earlier):
        return None
    if mine := [row for row in earlier if payload.get('agent_id') and row.get('agent') == payload.get('agent_id')]:  # its first sha binds it
        ws.record(root, 'verdict.rewritten', {'path': rel, 'sha256': sha, 'first': mine[0].get('sha256'), 'role': role, 'agent': payload.get('agent_id')})
        return (f'you attested {rel} before and it has changed since: recorded as verdict.rewritten, it does not count. Write the new '
                f'verdict to {free(path)} and end with its Verdict file: line.')
    if others := [row for row in earlier if row.get('agent') != payload.get('agent_id')]:
        return (f'{rel} held the {others[-1].get("verdict")} verdict another seat wrote; yours replaced it, and theirs still '
                f'counts as recorded. Write yours to {free(path)} and end with its Verdict file: line.')
    parsed = verdict.parse(body.decode('utf-8', 'replace'), strict=True)
    if parsed['errors']:
        return ('the verdict does not hold its shape:\n' + '\n'.join('- ' + e for e in parsed['errors'])
                + f'\nWrite the corrected verdict to {free(path)} in this shape:\n' + verdict.FORMAT)
    gate = role.removeprefix('sentinel-')
    if parsed['gate'] != gate:
        return f'you are {role}; your verdict must say Gate: {gate}.'
    seat = next((r['data'] for r in reversed(ws.rows(root, 'seat.started')) if r['data'].get('agent') == payload.get('agent_id')), {})
    ws.record(root, 'attest', {'path': rel, 'sha256': sha, 'gate': gate, 'item': parsed['item'], 'head': parsed['head'],
                               'pr': f'{parsed["repo"]}#{parsed["pr"]}' if parsed['pr'] else parsed['repo'], 'verdict': parsed['verdict'],
                               'confidence': parsed['confidence'], 'role': role, 'agent': payload.get('agent_id'),
                               'transcript': payload.get('agent_transcript_path'), 'model': seat.get('model', 'unrecorded'),
                               'effort': seat.get('effort', 'unrecorded'), 'blocking': sum(1 for f in parsed['findings'] if f['blocks'])})
    return None


def post_tool(root, payload):
    tool, data = payload.get('tool_name', ''), payload.get('tool_input') or {}
    if ws.config(root)['telemetry']:
        target = data.get('command') or data.get('file_path') or data.get('url') or ''
        ws.trace(root, {'session': payload.get('session_id'), 'agent': payload.get('agent_id'), 'tool': tool,
                        'role': str(payload.get('agent_type', '')).rsplit(':', 1)[-1],
                        'target': guards.SECRETS.sub('***', str(target))[:160],
                        'duration_ms': payload.get('duration_ms')})
    response = payload.get('tool_response') if tool in ('Agent', 'Task', 'codex_spawn_unconfirmed') else None
    if isinstance(response, dict) and isinstance(response.get('agentId'), str) and response['agentId']:
        canary = path.read_text(encoding='utf-8').strip() if (path := Path(root) / ws.DIR / 'canary').is_file() else ''
        redact = lambda value: guards.SECRETS.sub('***', value).replace(canary or '\0', '***')  # before clipping, including partial tokens
        item, effort, reason = asked({**data, 'prompt': (prompt := redact(str(data.get('prompt', ''))))})
        reason = 'Codex spawn_agent role unmeasured: active schema needs a known agent_type; prompt text cannot supply it.' if tool == 'codex_spawn_unconfirmed' else reason
        measured = lambda value: value if isinstance(value, str) and value.strip() else 'unmeasured'
        seat = {'role': str(data.get('subagent_type', '')).rsplit(':', 1)[-1], 'description': redact(str(data.get('description', '')))[:120],
                'session': payload.get('session_id'), 'agent': response['agentId'], 'model': str(response.get('resolvedModel') or 'unmeasured'),
                'asked': str(requested({**data, 'prompt': prompt}) or 'unrecorded'), 'effort': effort or 'unrecorded', 'reason': reason, 'item': item,
                **({'turn_model': measured(payload.get('model')), 'turn_effort': measured((payload.get('effort') if isinstance(payload.get('effort'), dict) else {}).get('level')),
                    'fork_policy': {'all': 'inherit', 'none': 'fresh'}.get(str(data.get('fork_turns')), 'unmeasured')} if 'agent_type' in data else {})}
        ws.record(root, 'seat.unconfirmed' if tool == 'codex_spawn_unconfirmed' else 'seat.started',
                  {k: redact(v) if isinstance(v, str) else v for k, v in seat.items()})
        return context('PostToolUse', 'WUWEI: ' + reason) if tool == 'codex_spawn_unconfirmed' else None
    if tool == 'AskUserQuestion':  # recorded once the session transcript shows it (_confirm)
        answers = response.get('answers', {}) if isinstance(response := payload.get('tool_response'), dict) else {}
        kept = {'id': str(payload.get('tool_use_id') or ''), 'path': payload.get('transcript_path'), 'answers': answers,
                'questions': [s for q in data.get('questions') or () if isinstance(q, dict) and isinstance(s := q.get('question'), str)]}
        if transcript_rows(kept['path'], kept['id'] or '\0') is None:
            return context('PostToolUse', _unconfirmed(root, kept, _shown(kept)[1]))
        ws.record(root, 'answer.pending', kept)  # never a silent drop: with no later prompt or answer.unconfirmed it reads as unconfirmed
        name = '--'.join(re.sub(r'[^\w-]', '', str(v or '')) for v in (payload.get('session_id'), kept['id']))  # no \ in an f-string on 3.11
        if ws.cache_get(root, 'answer-' + name, 7 * 86400) is None:  # the first entry for these ids stays: a forged repeat cannot replace it
            ws.cache_put(root, 'answer-' + name, kept)
    if tool.startswith('mcp__') and re.search(r'send|post|reply|comment|write', tool.lower()) \
            and not re.search(r'read|get|list|search|fetch', tool.lower()):
        if named := sorted(evidence.refs(json.dumps(data))):
            ws.record(root, 'sent', {'tool': tool, 'refs': named})
            ws.cache_put(root, 'board', None)
        return _replied(root, tool, json.dumps(data))
    if tool == 'Bash' and any(argv[:1] == ['gh'] and argv[1:3] == ['pr', 'create']
                              for argv, _ in guards.segments(str(data.get('command', ''))) or ()):
        if match := re.search(r'https://github\.com/([\w.-]+/[\w.-]+)/pull/([0-9]+)', json.dumps(payload.get('tool_response'))):
            gaps = evidence.visible(evidence.gaps(root, match[1], int(match[2])))
            ws.cache_put(root, 'board', None)
            if gaps:
                return context('PostToolUse', f'WUWEI: {match[1]}#{match[2]} still needs: ' + '; '.join(g['text'] for g in gaps))
    return None


def _replied(root, tool, sent):
    """Close every owed reply whose place this send landed in: a Slack link closes when the send names its channel and
    its message ts, or the thread_ts it sits in, each as a whole JSON value, never text; any other place must appear as given."""
    closed = []
    for item in plan.items(root):
        if item.get('kind') != 'reply' or item.get('status') != 'open':
            continue
        thread = re.search(r'/archives/([A-Z0-9]+)/p([0-9]{10})([0-9]{6})(?:\?\S*?\bthread_ts=([0-9]{10}\.[0-9]{6}))?', item['where'])
        keys = [[f'"{thread[1]}"', f'"{ts}"'] for ts in (f'{thread[2]}.{thread[3]}', thread[4]) if ts] if thread else [[item['where']]]
        if any(all(key in sent for key in place) for place in keys):
            plan.mark(root, item['id'], 'done', f'replied via {tool}')
            ws.record(root, 'reply.sent', {'id': item['id'], 'tool': tool})
            closed.append(item['id'])
    if closed:
        ws.cache_put(root, 'board', None)
        return context('PostToolUse', f'WUWEI: reply recorded, closed {", ".join(closed)}.')
    return None


def _shown(kept):  # (the answers the transcript shows for this AskUserQuestion id, why the rest are not), or None before its tool_result
    if (rows := transcript_rows(kept.get('path'), tid := str(kept.get('id') or '\0'))) is None:
        return {}, f'{kept.get("path")} is not a transcript under {ws.PROJECTS}'
    if not any(p.get('id') == tid and p.get('name') == 'AskUserQuestion' for p in parts(rows, 'tool_use')):
        return {}, f'the transcript holds no AskUserQuestion tool_use {tid}'
    if not (done := [r.get('toolUseResult') for r in rows if any(p.get('tool_use_id') == tid for p in parts([r], 'tool_result'))]):
        return None
    if not isinstance(said := done[-1].get('answers') if isinstance(done[-1], dict) else None, dict):  # never the row's text: model-written
        return {}, f'the tool_result has no toolUseResult answers ({type(done[-1]).__name__})'  # questions, labels and deny reasons fill it
    mine = a if isinstance(a := kept.get('answers'), dict) else {}
    same = {q: a for q, a in mine.items() if q in said and said[q] == a}  # each question on its own: one differing answer voids no other
    why = '; '.join(f'the transcript answers {q[:60]!r} with {str(said.get(q))[:60]!r}, not {str(a)[:60]!r}' for q, a in mine.items() if q not in same)
    return same, why or ('' if same else 'the payload holds no answer')


def _unconfirmed(root, kept, why, same=()):
    ws.record(root, 'answer.unconfirmed', {**kept, 'questions': (left := [q for q in kept.get('questions') or () if q not in same]), 'reason': why[:600]})
    return f'WUWEI: the answer to {left} is not recorded: {why}.'[:1000]


def _confirm(root, payload, final):
    """Notes for the answers this session asked, each recorded once the transcript shows it (the harness writes the row after
    PostToolUse returns; a Stop rereads for WAIT seconds), else answer.unconfirmed. A racing hook skips one claimed."""
    notes, end, session = [], time.monotonic() + WAIT * final, re.sub(r'[^\w-]', '', str(payload.get('session_id') or ''))
    for path in sorted((Path(root) / ws.DIR / 'cache').glob(f'answer-{session}--*.json')):
        if ws._cached(root, path.stem) != path:  # a linked cache folder or entry: never read or deleted through
            continue
        kept = entry if isinstance(entry := ws.cache_get(root, path.stem, 7 * 86400), dict) else {}  # a planted [1] reads as nothing
        fresh = ws.cache_get(root, path.stem, BOUND) is not None  # kept less than BOUND seconds ago: a Stop waits for its row
        while (shown := _shown(kept)) is None and fresh and time.monotonic() < end:
            time.sleep(0.1)
        same, why = shown or ({}, f'no tool_result row in {BOUND // 60} minutes')
        if why and (final or shown is None and fresh):  # with no row a later call rereads it;
            continue  # a Stop leaves an unrecorded answer to the next call, so its note never blocks the stop (#1231)
        try:
            ws.take(root, path)  # of two racing hooks, one records the answer
        except OSError:
            continue
        notes += [_unconfirmed(root, kept, why, same)] if why else []
        if same and all(r['data'].get('id') != kept['id'] for r in ws.rows(root, 'prompt')):  # a replayed answer records nothing more
            notes += _answers(root, {**kept, 'answers': same, 'questions': [q for q in kept.get('questions') or () if q in same]})
    return notes


def _answers(root, kept):
    questions, answers = kept.get('questions') or [], kept.get('answers') or {}
    ws.record(root, 'prompt', {'id': kept.get('id'), 'questions': questions, 'answers': answers if isinstance(answers, dict) else str(answers)[:500]})
    notes = []
    for question in questions:
        answer = str(answers.get(question, '')) if isinstance(answers, dict) else ''
        yes = answer.strip().lower().startswith(('yes', 'approve', 'accept', 'proceed'))
        found = re.match(r'\s*(?i:owner review|(breaking)):\s*' + REF.pattern, question)
        if answer and found and found[2]:
            ws.record(root, 'ruling', {**({'kind': 'breaking'} if found[1] else {}), 'pr': f'{found[2]}#{found[3]}',
                                       'head': found[4], 'approved': yes, 'question': question, 'answer': answer})
        refs, gap_text = exception_refs(question)
        if refs and gap_text and answer:
            for repo, number, head in refs:
                ref = f'{repo}#{number}'
                ws.record(root, 'ruling', {'kind': 'exception', 'pr': ref, 'head': head, 'gap': gap_text,
                                           'approved': yes, 'question': question, 'answer': answer})
                if yes:
                    item = plan.followup(root, f'Close the exception on {ref}: {gap_text}', repo,
                                         _goal(root, ref, repo), f'owner accepted it at {head}')
                    notes.append(f'WUWEI: exception recorded on {ref}; {item["id"]} in the plan closes it later.')
        if question.lower().startswith('plan:') and answer:
            if yes:
                plan.approve(root, answer)
                ws.cache_put(root, 'board', None)
                notes.append('WUWEI: plan approved; start the work, highest score first.')
            else:
                ws.record(root, 'plan.change', {'answer': answer})
                notes.append('WUWEI: the owner asked for a change: apply it, show the view again and re-ask.')
        if (goal := re.match(r'\s*goal: *(G-[0-9]+) met\?', question, re.I)) and answer:  # what the plan pass asks (#975)
            name, outcome = goal[1].upper(), {k.upper(): v[0] for k, v in view.goals(root).items()}.get(goal[1].upper(), '')  # the goal answered
            ws.record(root, 'ruling', {'kind': 'goal.met', 'goal': name, 'outcome': outcome, 'approved': yes, 'question': question, 'answer': answer})
            notes.append(f'WUWEI: goal {name} recorded as ' + ('met.' if yes else 'open; the plan pass offers it again once its date moves.'))
        if question.lower().startswith('one-way:') and answer:
            notes.append("WUWEI: record this one-way decision as an ADR (context, decision, consequences, the owner's answer) through the item's PR, "
                         "where the repository keeps its ADRs: an existing docs/adr/ or docs/decisions/, else the item's spec folder. "
                         'When the answer re-confirms an existing ADR, amend that ADR instead of adding a file.')
    return notes


REF = re.compile(r'(?:([\w.-]+/[\w.-]+))?#([0-9]+) at ([0-9a-f]{7,40})\b')
SESSION_CAP = 10000  # Claude Code's additionalContext cap; a longer one reaches the session as a file path
WAIT, BOUND = 1.5, 600  # seconds a Stop rereads a transcript the harness may still be writing, and an answer waits for its row
HANDED = 'This agent\'s report was delivered to you as a message from "{}" (its SubagentHandback call)'  # the harness's words
AWAY = ('This session is not in auto mode, so the harness refuses SubagentHandback: do not call it again. End now with your '
        'report as plain text; WUWEI keeps it and passes it on, and your stop attests a verdict file it names.')


def exception_refs(question):
    """([(repo, number, head)], gap) from "exception: owner/repo#n at <sha> [and #m at <sha>]: <gap>. ..."; a gap that holds a
    finding row (": |") runs to the row's end, its last | before a ". ", "?" or the end, so a | in the question is not the row's."""
    if not question.lower().startswith('exception:'):
        return [], ''
    refs, repo = [], ''
    matches = list(REF.finditer(question))
    for match in matches:
        repo = match[1] or repo
        if repo:
            refs.append((repo, match[2], match[3]))
    tail = question[matches[-1].end():].lstrip(' :') if matches else ''
    first = re.split(r'\.\s|\?', tail, maxsplit=1)[0]  # a row's ": |" is before its first break
    cut = max((m.end() for m in re.finditer(r'\|(?=\s*(?:[.?]|$))', tail)), default=0) if ': |' in first else 0
    return refs, (tail[:cut] + re.split(r'\.\s|\?', tail[cut:], maxsplit=1)[0]).strip().rstrip('.')


def _goal(root, ref, repo):
    item_ids = {row['data'].get('item') for row in ws.rows(root, 'attest') if row['data'].get('pr') == ref}
    found = [i for i in plan.items(root) if i['id'] in item_ids] or [i for i in plan.items(root) if i.get('repo') == repo]
    return found[0]['goal'] if found else 'unplanned'


def session_start(root, payload):
    """Orientation under Claude Code's 10,000-character additionalContext cap; what does not fit is named, not inlined."""
    cli, charters = str(ws.PLUGIN / 'bin' / 'wuwei'), ws.PLUGIN / 'charters'
    ws.atomic_write(Path(root) / ws.DIR / 'executable', cli + '\n')
    read = lambda name: (charters / name).read_text(encoding='utf-8') if (charters / name).is_file() else ''  # noqa: E731
    parts = [f'WUWEI CLI: {cli} (call it by this path; it is not on PATH)', read('_way.md').strip(), '_common.md, Decisions and Done:\n'
             + ''.join(re.findall(r'^## (?:Decisions|Done)\n.*?(?=^## |\Z)', read('_common.md'), re.S | re.M)).strip(),
             f'Read before the first plan pass: your charter {charters / "planner.md"}, the rest of {charters / "_common.md"}, '
             f'and the goals and standards in {Path(root) / ws.DIR}.']
    left = lambda cut: [f'{cut} more item{"s" if cut > 1 else ""} left out; `wuwei status` lists them all.'] * (cut > 0)  # noqa: E731
    try:  # the owner's answers, the latest 12 (a bounded share: the board's items give way to them); then the board to the cap
        if said := ws.answers(root)[1]:
            more = [f'{len(said) - 12} older left out.'] * (len(said) > 12)
            parts.append('Owner answers, last 7 days (act on them; never ask again):\n' + '\n'.join(said[:12] + more))
        found, cut = board.rows(root), 0
        lines, items = board.text(found, root).split('\n'), tuple(f'- {row["item"]} ' for row in found)
        while len('\n\n'.join(parts + ['\n'.join(lines + left(cut))])) >= SESSION_CAP and (at := [n for n, x in enumerate(lines) if x.startswith(items)]):
            lines, cut = lines[:at[-1]], cut + 1  # the last item goes whole, with the lines its title's newlines make
        parts.append('\n'.join(lines + left(cut)))
    except Exception as exc:  # the board is orientation; a session never waits on it
        parts.append(f'Answers or board unreadable: {exc}')
    return context('SessionStart', '\n\n'.join(parts)[:SESSION_CAP])  # only a board with no item left to drop reaches the cut


HANDLERS = {'PreToolUse': pre_tool, 'PostToolUse': post_tool, 'Stop': stop, 'SubagentStop': subagent_stop,
            'SessionStart': session_start}


PATCHED = re.compile(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$', re.M)


def codex(payload, event='PostToolUse'):
    """Codex's tool payloads in the shapes the guards read: apply_patch as an edit of the files it
    names, spawn_agent as a seat launch, request_user_input as an owner question."""
    tool, data = payload.get('tool_name'), payload.get('tool_input') or {}
    if tool == 'apply_patch':
        paths = [(m[1] or m[2]).strip() for m in PATCHED.finditer(str(data.get('command', '')))]
        return {**payload, 'tool_name': 'Edit', 'tool_input': {'file_paths': paths}}
    if tool in ('spawn_agent', 'collaborationspawn_agent'):
        response = json.loads(raw) if isinstance(raw := payload.get('tool_response'), str) else raw
        spawned = response.get('agent_id', response.get('task_name')) if isinstance(response, dict) else None
        if event == 'PostToolUse' and (not isinstance(spawned, str) or not spawned.strip()):
            raise ValueError('Codex spawn_agent response needs a nonblank string agent_id or task_name')
        role = str(data.get('agent_type') or '').removeprefix('wuwei:')
        return {**payload, 'tool_name': 'Agent' if role in agents.TABLE else 'codex_spawn_unconfirmed',
                'tool_response': {**(response or {}), 'agentId': spawned}, 'tool_input': {**data, 'subagent_type': role if role in agents.TABLE else '',
                'description': data.get('task_name') or '', 'prompt': data.get('message') or '', 'effort': data.get('reasoning_effort')}}
    if tool == 'request_user_input':
        ids = {q.get('id'): q.get('question', '') for q in data.get('questions') or () if isinstance(q, dict)}
        response = payload.get('tool_response')
        answers = response.get('answers') if isinstance(response, dict) else None
        if isinstance(answers, dict):
            response = {'answers': {ids.get(key, key): ', '.join(value.get('answers', [])) if isinstance(value, dict)
                                    else str(value) for key, value in answers.items()}}
        return {**payload, 'tool_name': 'AskUserQuestion', 'tool_response': response}
    return payload


def deliver(root, event, payload, out, said):
    """Seat reports the harness kept from the planner and owner answers' notes (said), once on its next call or stop (#1160)."""
    spec, data = (out or {}).get('hookSpecificOutput', {}), payload.get('tool_input') or {}
    if said and 'permissionDecisionReason' in spec:  # a refused call still carries the notes of the answers recorded on it
        spec['permissionDecisionReason'] += '\n\n' + '\n'.join(said)
    if payload.get('agent_id') or event not in ('PreToolUse', 'PostToolUse', 'Stop') or out and 'additionalContext' not in spec \
            and event != 'Stop':  # a decision stays as it is; the next call carries the reports
        return out
    pending, found, session, latest = Path(root) / ws.DIR / 'reports' / 'pending', [], re.sub(r'[^\w-]', '', str(payload.get('session_id') or '')), {}
    paths = [*pending.glob(f'{session}--*.md'), *pending.parent.glob(f'{session}--*.md')]  # pending first: a claim cannot disappear
    for path, text in sorted((r for p in paths if (r := _kept_report(p, pending.parent))),
                             key=lambda r: int(r[0].stem.rsplit('--', 1)[-1]), reverse=True):
        try:
            seat = tuple(path.stem.split('--', 3)[:2])
            if latest.setdefault(seat, path.name) != path.name or path.parent != pending:
                if path.parent == pending:
                    os.replace(path, pending.parent / path.name)  # keep every version beside the latest report's kept path
                continue
            _, agent, role, _ = path.stem.split('--', 3)
            rows = [r for r in transcript_rows(payload.get('transcript_path'), f'<task-id>{agent}</task-id>') or () if isinstance(r, dict)
                    and re.match(rf'<task-notification>\s*<task-id>{re.escape(agent)}</task-id>', str(r.get('content')))]  # its own frame
            gone = [r['content'] for r in rows if r.get('reason') == 'cleared_on_cancel']  # a cleared queue showed the planner nothing
            at = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat(timespec='milliseconds')  # older rows told older stops
            told = any(c not in gone and (html.unescape(b) == text or b.startswith(HANDED.format(agent))) for c in [r['content'] for r in rows
                       if r.get('operation') == 'enqueue' and str(r.get('timestamp') or '') >= at] for b in re.findall(r'<result>(.*?)</result>', c, re.S))
            if told and event == 'Stop' or os.replace(path, kept := pending.parent / path.name):  # one hook wins a race
                continue  # one its own uncleared notification or hand-back gave (#1222) is a pointer on a call, never a Stop block
        except OSError:
            continue
        found.append((agent, f'## {role} {agent}: report already notified; kept at {kept}' if told else f'## {role} {agent} (kept at {kept})\n{text}'))
    if not said and not found:  # a notified report is a pointer, never lost (#1198)
        return out
    note = '\n'.join(said + ["WUWEI: the hook kept these seats' last messages, which no task notification gave you (one it gave, "
                             'by its path only):\n\n' + '\n\n'.join(text for _, text in found)] * bool(found))
    if event == 'Stop':
        return {'decision': 'block', 'reason': ((out or {}).get('reason', '') + '\n\n' + note).strip()}
    if payload.get('tool_name') == 'SendMessage' and any(agent and agent in str(data.get('to', '')) for agent, _ in found):
        return {'hookSpecificOutput': {'hookEventName': event, 'permissionDecision': 'deny',
                                       'permissionDecisionReason': note + '\n\nNot sent: the report is above.'}}
    return context(event, (spec.get('additionalContext', '') + '\n\n' + note).strip())


def handle(root, event, payload):
    if (handler := HANDLERS.get(event)) is None:
        return None
    planner, said = not payload.get('agent_id') and event in ('PreToolUse', 'PostToolUse', 'Stop'), []
    try:  # answers are recorded before a door reads the ledger; when that fails the doors still judge
        said = _confirm(root, payload, event == 'Stop') if planner and event != 'PostToolUse' else []
    except Exception as exc:
        _failed(root, event, exc)
    try:  # at PostToolUse the answers are recorded after it kept its own
        out = handler(root, codex(payload, event))
        said += _confirm(root, payload, False) if planner and event == 'PostToolUse' else []
    except Exception as exc:  # a door that cannot judge stays shut
        message = _failed(root, event, exc)
        if event == 'PreToolUse' and door(payload):
            return {'hookSpecificOutput': {'hookEventName': event, 'permissionDecision': 'deny', 'permissionDecisionReason':
                    f'WUWEI: this call names a door and the hook failed while checking it ({message}); fix the cause and retry.'}}
        return None
    try:  # a delivery that fails never changes the decision
        return deliver(root, event, payload, out, said)
    except Exception as exc:
        print(f'wuwei hook {event}: report delivery failed: {exc}'[:300], file=sys.stderr)
        return out


def _failed(root, event, exc):  # fail open: work goes on, the audit records why
    message = f'{type(exc).__name__}: {exc}'[:300]
    print(f'wuwei hook {event}: {message}', file=sys.stderr)
    try:
        ws.record(root, 'hook.error', {'event': event, 'error': message})
    except Exception:
        pass
    return message


def door(payload):
    """An edit (guards.DOORS, or a Codex apply_patch), any MCP tool (the leak check), or a Bash command naming a door
    program (guards.DOOR_WORDS) or a network program, read with its quotes and backslashes removed."""
    tool, data = str(payload.get('tool_name') or ''), payload.get('tool_input')
    command = re.sub(r'[\'"\\]', '', str(data.get('command', ''))) if isinstance(data, dict) else ''
    network = rf'(^|[\s;&|(`/])({"|".join(guards.NETWORK)})(\.exe)?(\s|$)'  # in any case, as macOS and Windows run it
    return tool in (*guards.DOORS['edit'], 'apply_patch') or tool.startswith('mcp__') or tool == 'Bash' and (any(
        all(re.search(w, command, re.I) for w in words) for words in guards.DOOR_WORDS) or re.search(network, command, re.I))


VENDORED = ws.PLUGIN.parent.name == '.claude'  # copied into a repository by wuwei init --cloud


def _sync(step, arg):
    try:
        return step(arg)
    except Exception as exc:  # the state sync fails open; the next Stop tries again
        print(f'wuwei sync: {exc}'[:300], file=sys.stderr)
        return None


def main(event):
    if VENDORED and not sync.remote():
        return 0  # on a machine the installed plugin serves; the vendored copy is for cloud sessions
    try:
        payload = json.loads(sys.stdin.read() or '{}')
    except ValueError:
        return 0
    root = ws.find(payload.get('cwd'))
    if sync.remote() and event == 'SessionStart':
        root = _sync(sync.restore, payload.get('cwd')) or root
    if root is not None:
        if out := handle(root, event, payload):
            print(json.dumps(out))
        if sync.remote() and event == 'Stop':
            _sync(sync.push, root)
    return 0
