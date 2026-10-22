"""Build the 1211-confirm fixtures from two real AskUserQuestion flows of one Claude Code session (2.1.308, 2026-10-22).

Usage (the rows come on stdin, the guard's read route for a session transcript):
    grep -E '<plan id>|<trust id>' <session>.jsonl | python3 -I specs/1211-confirm/fixtures.py <plan id> <trust id> <tests/fixtures>

Kept: every row's keys, ids, uuids, parent links, timestamps and order. Replaced: each question, its options and its
answer (by a plan question answered Approve and a trust question answered with its first label), and local paths
(the workspace is /repo, the home ~). Dropped: serverClassifierContext (the machine's git state) and any row that is
not the tool_use or the tool_result of the two ids (hook rows name the ids in their text only).

Writes transcripts/ask-late.jsonl (the four rows), payloads/claude-ask-post-plan.json (the plan question's PostToolUse
payload, from its tool_use input and toolUseResult, as claude-ask-post.json is built) and
payloads/claude-ask-post-free-text.json (reconstructed: no real free-text answer was recorded).
"""

import json
import sys
from pathlib import Path

SESSION = '00000000-0000-4000-8000-000000001211'
PLAN = {'question': 'plan: approve this plan? 2 items on 1 goal, about 3 build hours; the plan is shown above.',
        'header': 'plan', 'multiSelect': False,
        'options': [{'label': 'Approve', 'description': 'Start the 2 items.'},
                    {'label': 'Change', 'description': 'Say what to change; the planner applies it and re-asks.'}]}
TRUST = {'question': 'trust: may builders push one branch per item, each with its own draft PR?', 'header': 'trust',
         'multiSelect': False, 'options': [{'label': 'Yes, one branch per item (Recommended)', 'description': 'One draft PR per item.'},
                                           {'label': 'No, only the session branch', 'description': 'One PR at a time.'}]}
ONE_WAY = {'question': 'one-way: drop the legacy sessions table in acme/app?', 'header': 'one-way', 'multiSelect': False,
           'options': [{'label': 'Drop it', 'description': 'The migration deletes the table.'},
                       {'label': 'Keep it', 'description': 'The table stays.'}]}
FREE = 'Keep it until the export job stops reading it, then drop it'  # what an owner types in the Other field


def redact(value, home, cwd):
    if isinstance(value, dict):
        return {k: redact(v, home, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, home, cwd) for v in value]
    if isinstance(value, str):
        return value.replace(cwd, '/repo').replace(home, '~').replace(cwd.replace('/', '-'), '-repo')
    return value


def ask(row, asked):
    """The AskUserQuestion rows with the question, options and answer replaced, in the order the harness writes them."""
    answer = asked['options'][0]['label']
    for part in (row.get('message') or {}).get('content') or ():
        if isinstance(part, dict) and part.get('type') == 'tool_use':
            part['input'] = {'questions': [asked]}
            row['wireToolInputs'] = {part['id']: {'questions': [asked]}}
        if isinstance(part, dict) and part.get('type') == 'tool_result':
            part['content'] = (f'Your questions have been answered: "{asked["question"]}"="{answer}". '
                               'You can now continue with these answers in mind.')
            row['toolUseResult'] = {'questions': [{k: asked[k] for k in ('header', 'multiSelect', 'options', 'question')}],
                                    'answers': {asked['question']: answer}}
    row.pop('serverClassifierContext', None)
    return {**row, 'sessionId': SESSION, 'gitBranch': 'main'}


def payload(tool_use_id, questions, answers):
    return {'session_id': SESSION, 'transcript_path': f'~/.claude/projects/-repo/{SESSION}.jsonl', 'cwd': '/repo',
            'permission_mode': 'auto', 'hook_event_name': 'PostToolUse', 'tool_name': 'AskUserQuestion',
            'tool_input': {'questions': questions}, 'tool_response': {'questions': questions, 'answers': answers},
            'tool_use_id': tool_use_id}


def main(plan_id, trust_id, out):
    home, out = str(Path.home()), Path(out)
    rows = [json.loads(line) for line in sys.stdin.read().splitlines() if line.strip()]
    cwd = next(r['cwd'] for r in rows if r.get('cwd'))
    kept = []
    for row in rows:
        parts = [p for p in (row.get('message') or {}).get('content') or () if isinstance(p, dict)]
        tid = next((p.get('id') or p.get('tool_use_id') for p in parts if p.get('type') in ('tool_use', 'tool_result')), None)
        if tid in (plan_id, trust_id):
            kept.append(ask(redact(row, home, cwd), PLAN if tid == plan_id else TRUST))
    assert len(kept) == 4, f'{len(kept)} rows: expected the tool_use and tool_result of each id'
    (out / 'transcripts' / 'ask-late.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in kept), encoding='utf-8')
    for name, data in (('claude-ask-post-plan.json', payload(plan_id, [PLAN], {PLAN['question']: 'Approve'})),
                       ('claude-ask-post-free-text.json', payload('toolu_01FreeTextReconstructed0001', [ONE_WAY, PLAN],
                                                                  {ONE_WAY['question']: FREE, PLAN['question']: 'Approve'}))):
        (out / 'payloads' / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:])
