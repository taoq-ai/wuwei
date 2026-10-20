"""The hooks: teach at the moment, hold the few doors, remind once, and record. A hook that fails
lets the work go on and records why; a door call it fails on is refused."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from wuwei import agents, board, evidence, guards, plan, sync, verdict, view, ws


def transcript(payload):
    """The seat's last report, its input plus output tokens, and whether a hand-back ended its run, read from its
    transcript ('', None and False when unreadable)."""
    found, total, ended = '', None, False
    try:
        for line in Path(payload.get('agent_transcript_path')).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
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
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    return found, total, bool(ended)


def last_text(payload):
    return text if isinstance(text := payload.get('last_assistant_message'), str) and text.strip() else transcript(payload)[0]


def context(event, text):
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def running(root):
    """Seats launched today, by agent id, with no stop under the same id."""
    ids = {kind: {a for row in ws.rows(root, kind, ws.today()) if isinstance(a := row['data'].get('agent'), str)}
           for kind in ('seat.started', 'seat.stopped')}
    return len(ids['seat.started'] - ids['seat.stopped'])


def pre_tool(root, payload):
    try:  # the doctor's hooks row reads it; a failed stamp never changes the guards' decision
        ws.cache_put(root, 'hook-seen', ws.now().timestamp())
    except Exception as exc:
        print(f'wuwei hook PreToolUse: the hook-seen stamp failed: {exc}'[:300], file=sys.stderr)
    role = str(payload.get('agent_type', '')).rsplit(':', 1)[-1]  # the harness's, never the message's
    problem = payload.get('tool_name') == 'SubagentHandback' and role.startswith('sentinel-') and _verdict_problem(
        root, {**payload, 'last_assistant_message': str((payload.get('tool_input') or {}).get('message', ''))}, role)
    found = {'decision': 'deny', 'reason': problem + '\nThen hand back again.'} if problem else guards.pre_tool(root, payload)
    if found is None:
        return advise(root, payload.get('tool_input') or {}) if payload.get('tool_name') in ('Agent', 'Task') else None
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
    """The item the brief names, the effort asked for (the call's, else the brief's Model: line) and its Model reason: line."""
    item, line, reason = (re.search(p, str(data.get('prompt', '')), re.M) for p in (
        r'\bItem:[ \t]*`?([\w.-]+)', r'^Model:.*?\b(low|medium|high|xhigh|max)\b', r'^Model reason:[ \t]*(\S.*)$'))
    return item and item[1].rstrip('.'), str(data.get('effort') or '') or line and line[1], reason and reason[1].strip()[:200]


def advise(root, data):
    """A note on a launch that departs from agents.TABLE or the owner's models rows; never a refusal or a rewrite."""
    role, (item_id, effort, reason) = str(data.get('subagent_type', '')).rsplit(':', 1)[-1], asked(data)
    if role not in agents.TABLE or not data.get('prompt'):  # a Codex spawn carries no brief and no model
        return None
    item, table, rows = (plan.find(root, item_id) if item_id else None) or {}, agents.TABLE[role], ws.config(root)['models']
    tier, repo = item.get('tier', 'standard'), str(item.get('repo', ''))
    if repo and ws.cache_get(root, 'budget-' + repo.replace('/', '__'), 86400) and evidence.budget(root, repo)['raised']:
        tier = evidence.RAISE.get(tier, tier)  # the cached rate only: a launch never waits on the code host
    allowed = [(own, '')] if (own := rows.get(f'{role} {tier}') or rows.get(role)) else [
        (table.get(tier, table['']), '')] + [(setting, when) for when, setting in table.items() if ' ' in when]
    fam = lambda name: (re.findall('fable|opus|sonnet|haiku', name.lower()) or [name.lower()])[0]  # noqa: E731
    model, effort = str(data.get('model') or table[''].rsplit(' ', 1)[0]), effort or table[''].rsplit(' ', 1)[1]
    named = str([raw.get(k) for k in (f'{role} {tier}', role)] if isinstance(raw := ws.raw_config(root).get('models'), dict) else '')
    floor = role.startswith('sentinel-') and (fam(model) == 'haiku' or 'haiku' in named.lower())  # a row, even one config() drops
    if not floor and (reason or any((os.environ.get('CLAUDE_CODE_SUBAGENT_MODEL') or fam(s.rsplit(' ', 1)[0]) == fam(model)) and
                                    (os.environ.get('CLAUDE_CODE_EFFORT_LEVEL') or s.rsplit(' ', 1)[1] == effort) for s, _ in allowed)):
        return None
    return context('PreToolUse', f"WUWEI: table says {allowed[0][0]} for {role} at {tier}; record a 'Model reason:' line in the "
                   f"brief (asked: {model} {effort}" + ''.join(f'; the row also allows {s} {when}' for s, when in allowed[1:]) + ').' + (
                       " Haiku 5.5 never runs a gate on risky, owner or contract paths, and neither a reason nor a models row "
                       "covers that: it is an exception: for the owner." if floor else ''))


def closed(root):
    marks = [row['kind'] for row in ws.ledger(root)
             if row.get('kind') in ('day.closed', 'plan.pass') and row.get('ts', '').startswith(ws.today())]
    return bool(marks) and marks[-1] == 'day.closed'


def stop(root, payload):
    if payload.get('stop_hook_active') or closed(root) or board.running(root, payload.get('session_id')):
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
    held = f'\nLeft out: {waiting} waiting on CI, the owner, plan approval or an andon.' if waiting else ''
    return {'decision': 'block', 'reason': 'WUWEI: open work you can close now:\n' + shown + more + held +
            '\nThe plan is your mandate: do not ask the owner whether to continue. Close these, or say in '
        'one line why each waits, then stop.'}


def _settled(payload):
    """The seat's last message, rereading a transcript the harness may still be writing (about 2 s)."""
    text, path = last_text(payload), payload.get('agent_transcript_path')
    for _ in range(8):
        if text.strip() or not path or not Path(path).is_file():
            break
        time.sleep(0.25)
        text = last_text(payload)
    return text


def subagent_stop(root, payload):
    payload = {**payload, 'last_assistant_message': _settled(payload)}
    role, (_, tokens, ended) = str(payload.get('agent_type', '')).rsplit(':', 1)[-1], transcript(payload)
    out = _seat_stop(root, payload, role, tokens, ended)
    if out is None and not ended and role in agents.TABLE and payload['last_assistant_message'].strip() \
            and Path(str(payload.get('agent_transcript_path') or '')).is_file():  # a Claude seat ends: keep what the harness drops
        name = '--'.join(re.sub(r'[^\w-]', '', str(v or '')) for v in (payload.get('session_id'), payload.get('agent_id'), role))
        ws.atomic_write(Path(root) / ws.DIR / 'reports' / 'pending' / f'{name}--{time.time_ns()}.md',
                        payload['last_assistant_message'], Path(root))
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
        return f'the verdict must be a readable file under {verdicts}/ (got {match[1]}).'
    rel, sha = str(path.relative_to(Path(root).resolve())), hashlib.sha256(body).hexdigest()
    earlier = [row['data'] for row in ws.rows(root, 'attest') if row['data'].get('path') == rel]
    if any(row.get('sha256') == sha for row in earlier):
        return None
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
    response = payload.get('tool_response') if tool in ('Agent', 'Task') else None  # runs only for an accepted launch
    if isinstance(response, dict) and isinstance(response.get('agentId'), str) and response['agentId']:
        item, effort, reason = asked(data)  # what ran, what was asked for, and why it departs
        ws.record(root, 'seat.started', {'role': str(data.get('subagent_type', '')).rsplit(':', 1)[-1],
                                         'description': str(data.get('description', ''))[:120], 'session': payload.get('session_id'),
                                         'agent': response['agentId'], 'model': str(response.get('resolvedModel') or 'unmeasured'),
                                         'asked': str(data.get('model') or 'unrecorded'), 'effort': effort or 'unrecorded', 'reason': reason, 'item': item})
    if tool == 'AskUserQuestion':
        return _answers(root, data, payload.get('tool_response'))
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
    """Close every owed reply whose place this send landed in: a Slack thread link names its channel
    and thread ts; any other place must appear as given."""
    closed = []
    for item in plan.items(root):
        if item.get('kind') != 'reply' or item.get('status') != 'open':
            continue
        thread = re.search(r'/archives/([A-Z0-9]+)/p([0-9]{10})([0-9]{6})', item['where'])
        keys = [thread[1], f'{thread[2]}.{thread[3]}'] if thread else [item['where']]
        if all(key in sent for key in keys):
            plan.mark(root, item['id'], 'done', f'replied via {tool}')
            ws.record(root, 'reply.sent', {'id': item['id'], 'tool': tool})
            closed.append(item['id'])
    if closed:
        ws.cache_put(root, 'board', None)
        return context('PostToolUse', f'WUWEI: reply recorded, closed {", ".join(closed)}.')
    return None


def _answers(root, data, response):
    questions = [q.get('question', '') for q in data.get('questions') or () if isinstance(q, dict)]
    answers = response.get('answers', {}) if isinstance(response, dict) else {}
    ws.record(root, 'prompt', {'questions': questions, 'answers': answers if isinstance(answers, dict) else str(answers)[:500]})
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
            notes.append('WUWEI: record this one-way decision as an ADR (context, decision, consequences) in the '
                         "repository's docs/adr/ through the item's PR, quoting the owner's answer.")
    return context('PostToolUse', '\n'.join(notes)) if notes else None


REF = re.compile(r'(?:([\w.-]+/[\w.-]+))?#([0-9]+) at ([0-9a-f]{7,40})\b')
SESSION_CAP = 10000  # Claude Code's additionalContext cap; a longer one reaches the session as a file path


def exception_refs(question):
    """([(repo, number, head)], gap) from "exception: owner/repo#n at <sha> [and #m at <sha>]: <gap>. ..."."""
    if not question.lower().startswith('exception:'):
        return [], ''
    refs, repo = [], ''
    matches = list(REF.finditer(question))
    for match in matches:
        repo = match[1] or repo
        if repo:
            refs.append((repo, match[2], match[3]))
    tail = question[matches[-1].end():].lstrip(' :') if matches else ''
    return refs, re.split(r'\.\s|\?', tail, maxsplit=1)[0].strip().rstrip('.')


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
    try:
        found, cut = board.rows(root), 0
        lines, items = board.text(found, root).split('\n'), tuple(f'- {row["item"]} ' for row in found)
        while len('\n\n'.join(parts + ['\n'.join(lines + left(cut))])) >= SESSION_CAP and (at := [n for n, x in enumerate(lines) if x.startswith(items)]):
            lines, cut = lines[:at[-1]], cut + 1  # the last item goes whole, with the lines its title's newlines make
        parts.append('\n'.join(lines + left(cut)))
    except Exception as exc:  # the board is orientation; a session never waits on it
        parts.append(f'Board unreadable: {exc}')
    return context('SessionStart', '\n\n'.join(parts)[:SESSION_CAP])  # only a board with no item left to drop reaches the cut


HANDLERS = {'PreToolUse': pre_tool, 'PostToolUse': post_tool, 'Stop': stop, 'SubagentStop': subagent_stop,
            'SessionStart': session_start}


PATCHED = re.compile(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$', re.M)


def codex(payload):
    """Codex's tool payloads in the shapes the guards read: apply_patch as an edit of the files it
    names, spawn_agent as a seat launch, request_user_input as an owner question."""
    tool, data = payload.get('tool_name'), payload.get('tool_input') or {}
    if tool == 'apply_patch':
        paths = [(m[1] or m[2]).strip() for m in PATCHED.finditer(str(data.get('command', '')))]
        return {**payload, 'tool_name': 'Edit', 'tool_input': {'file_paths': paths}}
    if tool == 'spawn_agent':
        spawned = re.search(r'"agent_id"\s*:\s*"([^"]+)"', json.dumps(payload.get('tool_response')).replace('\\"', '"'))
        return {**payload, 'tool_name': 'Agent', 'tool_response': {'agentId': spawned and spawned[1]},
                'tool_input': {'subagent_type': data.get('agent_type') or '', 'description': data.get('task_name') or ''}}
    if tool == 'request_user_input':
        ids = {q.get('id'): q.get('question', '') for q in data.get('questions') or () if isinstance(q, dict)}
        response = payload.get('tool_response')
        answers = response.get('answers') if isinstance(response, dict) else None
        if isinstance(answers, dict):
            response = {'answers': {ids.get(key, key): ', '.join(value.get('answers', [])) if isinstance(value, dict)
                                    else str(value) for key, value in answers.items()}}
        return {**payload, 'tool_name': 'AskUserQuestion', 'tool_response': response}
    return payload


def deliver(root, event, payload, out):
    """Seat reports the harness kept from the planner (SubagentHandback runs only in auto mode, and plain text never
    reaches the caller), given once on the planner's next tool call or stop and kept under .wuwei/reports (#1160)."""
    spec, data = (out or {}).get('hookSpecificOutput', {}), payload.get('tool_input') or {}
    if payload.get('agent_id') or event not in ('PreToolUse', 'PostToolUse', 'Stop') or out and 'additionalContext' not in spec \
            and event != 'Stop':  # a decision stays as it is; the next call carries the reports
        return out
    pending, found = Path(root) / ws.DIR / 'reports' / 'pending', []
    session = re.sub(r'[^\w-]', '', str(payload.get('session_id') or ''))
    for path in sorted(pending.glob(f'{session}--*.md')) if pending.is_dir() else ():
        try:
            os.replace(path, kept := pending.parent / path.name)  # one hook wins a race; the other skips it
        except OSError:
            continue
        _, agent, role, _ = kept.stem.split('--', 3)
        found.append((agent, f'## {role} {agent} (kept at {kept})\n{kept.read_text(encoding="utf-8")}'))
    if not found:
        return out
    note = ("WUWEI: SubagentHandback runs only in auto mode, so these seats' reports never reached you; their last "
            'messages:\n\n' + '\n\n'.join(text for _, text in found))
    if event == 'Stop':
        return {'decision': 'block', 'reason': ((out or {}).get('reason', '') + '\n\n' + note).strip()}
    if payload.get('tool_name') == 'SendMessage' and any(agent and agent in str(data.get('to', '')) for agent, _ in found):
        return {'hookSpecificOutput': {'hookEventName': event, 'permissionDecision': 'deny',
                                       'permissionDecisionReason': note + '\n\nNot sent: the report is above.'}}
    return context(event, (spec.get('additionalContext', '') + '\n\n' + note).strip())


def handle(root, event, payload):
    if (handler := HANDLERS.get(event)) is None:
        return None
    try:
        out = handler(root, codex(payload))
    except Exception as exc:  # fail open: work goes on, the audit records why; a door that cannot judge stays shut
        message = f'{type(exc).__name__}: {exc}'[:300]
        print(f'wuwei hook {event}: {message}', file=sys.stderr)
        try:
            ws.record(root, 'hook.error', {'event': event, 'error': message})
        except Exception:
            pass
        if event == 'PreToolUse' and door(payload):
            return {'hookSpecificOutput': {'hookEventName': event, 'permissionDecision': 'deny', 'permissionDecisionReason':
                    f'WUWEI: this call names a door and the hook failed while checking it ({message}); fix the cause and retry.'}}
        return None
    try:  # a delivery that fails never changes the decision
        return deliver(root, event, payload, out)
    except Exception as exc:
        print(f'wuwei hook {event}: report delivery failed: {exc}'[:300], file=sys.stderr)
        return out


def door(payload):
    """An edit (guards.DOORS, or a Codex apply_patch), any MCP tool (the leak check), or a Bash command naming a door
    program (guards.DOOR_WORDS) or a network program, read with its quotes and backslashes removed."""
    tool, data = str(payload.get('tool_name') or ''), payload.get('tool_input')
    command = re.sub(r'[\'"\\]', '', str(data.get('command', ''))) if isinstance(data, dict) else ''
    network = rf'(^|[\s;&|(`/])({"|".join(guards.NETWORK)})(\s|$)'
    return tool in (*guards.DOORS['edit'], 'apply_patch') or tool.startswith('mcp__') or tool == 'Bash' and (any(
        all(re.search(w, command) for w in words) for words in guards.DOOR_WORDS) or re.search(network, command))


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
