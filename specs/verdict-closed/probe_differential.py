"""verdict-closed probe: the main-versus-head differential for a hook.py change (AGENTS.md "Testing the guards").

Run it with pytest against a tree made by `git archive <sha>`, once for main and once for the head:

    PROBE_OUT=<out.json> pytest -q -p no:cacheprovider -c <tree>/pyproject.toml --rootdir <tree> <this file>

It writes one JSON file per tree: every route in tests/fixtures/routes.json read through guards.bash and through
the PreToolUse hook, every payload fixture replayed through the hook, and a generated matrix of verdict hand-backs
(body x files already in the folder x the name handed back x root or worktree x SubagentStop or SubagentHandback).
For each refusal that names a file to write next, it writes a good verdict there and records whether it attests.
compare.py reads the two files and prints the moved rows.
"""

import hashlib
import itertools
import json
import os
from pathlib import Path
import re

from conftest import HEAD, make_pr, verdict_text
from wuwei import guards, hook, ws

TREE = Path(guards.__file__).resolve().parents[2]
CORPUS = TREE / 'tests' / 'fixtures' / 'routes.json'
CLOSED = 'Previous findings at e418c1d: all closed.'
BODIES = {'good': verdict_text(), 'closed-in-probes': verdict_text() + f'\n## Probes\n{CLOSED}\n',
          'closed-in-findings': verdict_text(findings=CLOSED), 'short-head': verdict_text(head='abc1234')}
HELD = {'none': {}, 'file-2': {'-2': 'file'}, 'dangling-2': {'-2': 'dangling'}, 'link-2': {'-2': 'link'},
        'file-2-3': {'-2': 'file', '-3': 'file'}, 'other-base': {'': 'other'}}
NAMED = ('', '-2')
STEM = 'quality-abc1234'


def decision(out):
    if out is None:
        return None
    inner = out.get('hookSpecificOutput', out)
    return [inner.get('permissionDecision', inner.get('decision')), inner.get('permissionDecisionReason', inner.get('reason'))]


def scrub(text, *paths):
    for path in paths:
        text = text.replace(str(path), '<' + path.name + '>')
    return text


def test_routes(root, fake, monkeypatch):
    from test_guards import branch
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'o/r')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
    fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
    branch(fake, ('src/app.py',))
    rows = {}
    for route in json.loads(CORPUS.read_text(encoding='utf-8'))['routes']:
        command = route['command']
        pre = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'cwd': '/repo', 'tool_name': 'Bash',
                                               'tool_input': {'command': command}})
        rows[command] = {'guards': decision(guards.bash(root, command, '/repo', 's1')), 'hook': decision(pre)}
    save('routes', {'sha256': hashlib.sha256(CORPUS.read_bytes()).hexdigest(), 'rows': rows})


def test_payloads(tmp_path_factory):
    rows = {}
    for path in sorted((TREE / 'tests' / 'fixtures' / 'payloads').glob('*.json')):
        root = tmp_path_factory.mktemp('payload')
        (root / ws.DIR).mkdir()
        payload = json.loads(path.read_text(encoding='utf-8'))
        out = hook.handle(root, payload['hook_event_name'], payload)
        rows[path.name] = {'out': decision(out), 'kinds': sorted({r['kind'] for r in ws.rows(root)})}
    save('payloads', rows)


def handback(root, event, message, agent='rev1'):
    common = {'session_id': 's1', 'agent_id': agent, 'agent_type': 'wuwei:sentinel-quality', 'cwd': str(root)}
    if event == 'SubagentStop':
        return hook.handle(root, event, {**common, 'stop_hook_active': False, 'last_assistant_message': message,
                                         'agent_transcript_path': '/nowhere/agent.jsonl'})
    return hook.handle(root, 'PreToolUse', {**common, 'tool_name': 'SubagentHandback', 'tool_input': {'message': message}})


def test_handbacks(tmp_path_factory):
    rows = {}
    for body, held, named, where, event in itertools.product(BODIES, HELD, NAMED, ('root', 'worktree'),
                                                             ('SubagentStop', 'SubagentHandback')):
        root = tmp_path_factory.mktemp('ws')
        (root / ws.DIR).mkdir()
        folder = root / ws.DIR / 'verdicts' / 'I-1'
        folder.mkdir(parents=True)
        outside = tmp_path_factory.mktemp('outside') / 'target.md'
        outside.write_text('outside\n')
        for suffix, kind in HELD[held].items():
            target = folder / f'{STEM}{suffix}.md'
            if kind in ('dangling', 'link'):
                target.symlink_to(outside if kind == 'link' else outside.with_name('gone.md'))
            else:
                target.write_text(verdict_text(verdict='FIX', findings='- [high] src/app.py:9 blocks: yes. Failure: x')
                                  if kind == 'other' else verdict_text(verdict='FIX', findings='- [low] blocks: no. kept'))
        if held == 'other-base':  # another seat's attested verdict at the base name
            handback(root, 'SubagentStop', f'Verdict file: {folder / (STEM + ".md")}', agent='rev0')
        wt = tmp_path_factory.mktemp('wt')
        mine = (folder if where == 'root' else wt / ws.DIR / 'verdicts' / 'I-1')
        mine.mkdir(parents=True, exist_ok=True)
        written = mine / f'{STEM}{named}.md'
        if written.is_symlink():
            continue  # a seat never writes through a link it was told about
        written.write_text(BODIES[body])
        out = decision(handback(root, event, f'Verdict file: {written}'))
        row = {'out': out and [out[0], scrub(out[1], root.resolve(), wt, outside)],
               'outside': outside.read_text(), 'attested': len(ws.rows(root, 'attest'))}
        if out and (m := re.search(r'(?:corrected verdict to|Write yours to|beside it as) (\S+?\.md)\b', out[1])):
            nxt, row['named'] = mine / m[1], m[1]
            held_at_root = (folder / m[1]).is_symlink() or (folder / m[1]).exists()
            nxt.write_text(BODIES['closed-in-probes'])
            again = decision(handback(root, event, f'Verdict file: {nxt}'))
            row['next'] = {'free_at_root': not held_at_root, 'attests': again is None,
                           'again': again and scrub(again[1], root.resolve(), wt, outside)[:200]}
        rows[f'{body} {held} {STEM}{named}.md {where} {event}'] = row
    save('handbacks', rows)


def save(part, value):
    out = Path(os.environ['PROBE_OUT'])
    data = json.loads(out.read_text()) if out.exists() else {}
    data[part] = value
    out.write_text(json.dumps(data, indent=1, sort_keys=True))
