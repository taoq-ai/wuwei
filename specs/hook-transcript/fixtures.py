"""Build tests/fixtures/transcripts from a real Claude Code session transcript, redacted.

Usage: python3 -I specs/hook-transcript/fixtures.py <session>.jsonl <ask tool_use id> <agent tool_use id> <agent meta.json> <out dir>

Kept: every row's keys, ids, uuids, parent links, timestamps and order. Replaced: the question and its
answer (by an owner review question), the brief, and local paths (the workspace is /repo, the home ~).
"""

import json
from pathlib import Path
import sys

QUESTION = 'owner review: acme/app#42 at aaaaaaa. Merge it?'
ANSWER = 'Yes'


def redact(value, home, cwd):
    if isinstance(value, dict):
        return {k: redact(v, home, cwd) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, home, cwd) for v in value]
    if isinstance(value, str):
        return value.replace(cwd, '/repo').replace(home, '~').replace(cwd.replace('/', '-'), '-repo')
    return value


def ask(row):
    """The AskUserQuestion rows with the question, options and answer replaced."""
    asked = [{'question': QUESTION, 'header': 'owner review', 'multiSelect': False,
              'options': [{'label': 'Yes', 'description': 'Merge it.'}, {'label': 'No', 'description': 'Hold it.'}]}]
    for part in (row.get('message') or {}).get('content') or ():
        if isinstance(part, dict) and part.get('type') == 'tool_use':
            part['input'] = {'questions': asked}
            row['wireToolInputs'] = {part['id']: {'questions': asked}}
        if isinstance(part, dict) and part.get('type') == 'tool_result':
            part['content'] = f'Your questions have been answered: "{QUESTION}"="{ANSWER}". You can now continue.'
            row['toolUseResult'] = {'questions': asked, 'answers': {QUESTION: ANSWER}}
    if row.get('type') == 'attachment':
        row['attachment'] = {**row['attachment'], 'stdout': '', 'content': [] if row['attachment'].get('type') ==
                             'hook_additional_context' else ''}
        row.pop('rendered', None)  # the hook's text, which named the real question
    return row


def launch(row):
    """The Agent launch rows with the brief replaced."""
    for part in (row.get('message') or {}).get('content') or ():
        if isinstance(part, dict) and part.get('type') == 'tool_use':
            part['input'] = {**part['input'], 'prompt': 'Item: I-1\nBuild it.'}
            row['wireToolInputs'] = {part['id']: part['input']}
        if isinstance(part, dict) and part.get('type') == 'tool_result':
            part['content'] = [{'type': 'text', 'text': 'Async agent launched successfully.'}]
    if isinstance(row.get('toolUseResult'), dict):
        row['toolUseResult'] |= {'prompt': 'Item: I-1\nBuild it.', 'outputFile': f'~/tasks/{row["toolUseResult"]["agentId"]}.output'}
    return row


def main(transcript, ask_id, agent_id, meta, out):
    home, cwd, out = str(Path.home()), None, Path(out)
    rows = [json.loads(line) for line in Path(transcript).read_text(encoding='utf-8').splitlines()]
    cwd = next(r['cwd'] for r in rows if r.get('cwd'))
    for name, key, edit in (('ask-flow.jsonl', ask_id, ask), ('agent-launch.jsonl', agent_id, launch)):
        found = [edit(redact(r, home, cwd)) for r in rows if key in json.dumps(r)]
        for row in found:
            row.pop('serverClassifierContext', None)  # the machine's git state: not part of the flow
        (out / name).write_text(''.join(json.dumps(r) + '\n' for r in found), encoding='utf-8')
    (out / Path(meta).name).write_text(Path(meta).read_text(encoding='utf-8'), encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:])
