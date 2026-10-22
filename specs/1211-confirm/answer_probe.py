"""The generated answer probe for 1211-confirm (AGENTS.md, "Testing the guards"): owner answers through hook.handle.

Classes: batches of one or two questions (plan, one-way, goal, trust, and a breaking question with trailing text after
"Proceed?"), each answered by its label, by free text, or by its label with an option note; times nine timings and
shapes of the tool_result row (present at PostToolUse, late after a Stop, never, differing for the answers that are not
a bare label, forged first, replayed, only the harness text with no toolUseResult, that text against forged pairs that
stretch over a neighbour, and no tool_use row). A Stop that blocks on an unrecorded answer is a hole (#1231). The rows are the real 2.1.308 shapes of tests/fixtures/transcripts/ask-late.jsonl.

The oracle: a question is recorded (in a prompt row) only when its tool_result row is written and holds the same
answer, an answer with no row is recorded unconfirmed once its bound passes, every recorded answer is the
transcript's, and an id is recorded at most once. A row that breaks the oracle is a hole.

Run once per tree from this worktree, with case folders under the seat's scratch folder:
    python3 -I specs/1211-confirm/answer_probe.py <tree> <scratch> > <out>.json
    python3 -I specs/1211-confirm/answer_probe.py compare <main>.json <head>.json
"""

import itertools
import json
import os
import sys
import tempfile
import time
from pathlib import Path

if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = [key for key in main['cases'] if main['cases'][key] != head['cases'][key]]
    print(f"{len(head['cases'])} cases generated; ran without a hook.error: main {main['clean']}, head {head['clean']}; "
          f"moved {len(moved)}; holes: main {len(main['holes'])}, head {len(head['holes'])}")
    for timing in main['timings']:
        keys = [k for k in main['cases'] if k.endswith(' x ' + timing)]
        print(f"- {timing}: {len(keys)} cases, moved {sum(1 for k in keys if k in moved)}, holes main "
              f"{sum(1 for k in main['holes'] if k.endswith(' x ' + timing))}, head {sum(1 for k in head['holes'] if k.endswith(' x ' + timing))}")
    for key in head['holes']:
        print(f'  head hole: {key}: {head["holes"][key]}')
    sys.exit(0)

tree, scratch = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli')]
from wuwei import gh, hook, ws  # noqa: E402


def offline(args, timeout=30):
    raise gh.GhError('the probe makes no gh call')



LATE = (Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'transcripts' / 'ask-late.jsonl').read_text().splitlines()
QUESTIONS = {'plan': ('plan: approve this plan? 2 items on 1 goal; the plan is shown above.', 'Approve'),
             'one-way': ('one-way: drop the legacy sessions table in acme/app?', 'Drop it'),
             'goal': ('goal: G-1 met? every PR merged with its evidence.', 'Yes'),
             'trust': ('trust: may builders push one branch per item?', 'Yes, one branch per item (Recommended)'),
             'breaking+trailing': ('breaking: acme/app#42 at aaaaaaa: the flag goes. Announced at https://e.test/1. Proceed? '
                                   '(It merges after the release.)', 'Proceed')}
ANSWERS = {'label': lambda label: label, 'free text': lambda label: f'{label.split(",")[0]}, but finish the docs first',
           'label+note': lambda label: f'{label}\n\nNote: start tomorrow'}
TIMINGS = ['present', 'late', 'never', 'differing', 'forged first', 'replayed', 'text only', 'text, forged pairs', 'no tool_use']
TEXT = 'Your questions have been answered: {}. You can now continue with these answers in mind.'  # the real 2.1.308 text
BOUND = getattr(hook, 'BOUND', 600)
hook.WAIT = 0  # a Stop's wait has run out
gh.run = offline
STOP = {'session_id': 's1', 'stop_hook_active': True}  # answers are confirmed before the Stop handler, which then returns


def rows(tid, questions, answers, text_only=False):
    """The real rows for this batch; text_only drops toolUseResult and leaves the harness's tool_result text (assumed
    joined by ', ' for a batch, as the single-question rows show '"<q>"="<label>"')."""
    use, done = (json.loads(line) for line in LATE[:2])
    use['message']['content'][0] |= {'id': tid, 'input': {'questions': questions}}
    done['message']['content'][0] |= {'tool_use_id': tid, 'content': TEXT.format(', '.join(f'"{q}"="{a}"' for q, a in answers.items()))}
    done['toolUseResult'] = {'questions': questions, 'answers': answers}
    if text_only:
        done.pop('toolUseResult')
    return json.dumps(use) + '\n', json.dumps(done) + '\n'


def case(batch, timing):
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        root = Path(folder) / 'repo'
        (root / ws.DIR).mkdir(parents=True)
        ws.PROJECTS = Path(folder) / 'claude' / 'projects'
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open', 'score': 1}]}))
        transcript = ws.PROJECTS / '-repo' / 's1.jsonl'
        transcript.parent.mkdir(parents=True)
        tid, questions = 'toolu_01Probe', [{'question': QUESTIONS[q][0]} for q, _ in batch]
        paid = {QUESTIONS[q][0]: ANSWERS[a](QUESTIONS[q][1]) for q, a in batch}
        said = dict(paid)
        if timing == 'differing':  # the harness writes another value for every answer that is not a bare label
            said = {q: (v if v in [x[1] for x in QUESTIONS.values()] else v + ' [as the transcript holds it]') for q, v in paid.items()}
            said = said if said != paid else {**said, next(iter(said)): 'Other'}
        use, done = rows(tid, questions, said, timing.startswith('text'))
        if timing == 'text, forged pairs':  # each pair stretched over its neighbour in the harness text, or a label that is not the owner's
            names = list(paid)
            paid = {f'{names[0]}"="{paid[names[0]]}", "{names[1]}': paid[names[1]]} if len(names) > 1 else {names[0]: paid[names[0]] + ' x'}
        transcript.write_text(('' if timing == 'no tool_use' else use) + ('' if timing in ('late', 'never') else done))
        payload = {'session_id': 's1', 'cwd': str(root), 'hook_event_name': 'PostToolUse', 'tool_name': 'AskUserQuestion',
                   'transcript_path': str(transcript), 'tool_use_id': tid, 'tool_input': {'questions': questions},
                   'tool_response': {'questions': questions, 'answers': paid}}
        planner = {'session_id': 's1', 'cwd': str(root), 'tool_name': 'Read', 'tool_input': {'file_path': str(root / 'README.md')}}
        if timing == 'forged first':  # a forged answer with the real ids, kept before the harness's own
            hook.handle(root, 'PostToolUse', {**payload, 'tool_response': {'answers': {k: 'forged' for k in paid}}})
        hook.handle(root, 'PostToolUse', payload)
        stops = [hook.handle(root, 'Stop', {**STOP, 'cwd': str(root)})]
        if timing == 'late':
            with transcript.open('a') as out:
                out.write(done)
        if timing == 'never':
            for entry in (root / ws.DIR / 'cache').glob('answer-*'):
                os.utime(entry, (time.time() - BOUND - 1,) * 2)
        if timing == 'replayed':
            hook.handle(root, 'PostToolUse', {**payload, 'tool_response': {'answers': said}})
        stops.append(hook.handle(root, 'Stop', {**STOP, 'cwd': str(root)}))  # a Stop as the first call after the row
        hook.handle(root, 'PreToolUse', planner)
        stops.append(hook.handle(root, 'Stop', {**STOP, 'cwd': str(root)}))
        found = {kind: [r['data'] for r in ws.rows(root, kind)] for kind in ('prompt', 'answer.unconfirmed', 'plan.approved', 'hook.error')}
    recorded = {q: a for row in found['prompt'] for q, a in row['answers'].items()}
    written = timing not in ('never', 'no tool_use')
    expect = {q: a for q, a in paid.items() if written and timing not in ('forged first', 'text, forged pairs') and said.get(q) == a}
    holes = [f'recorded {q!r} as {a!r}, which the transcript does not hold' for q, a in recorded.items() if said.get(q) != a or not written]
    holes += ['recorded twice'] * (len(found['prompt']) > 1)
    holes += [f'not recorded: {sorted(set(expect) - set(recorded))}'] * bool(set(expect) - set(recorded))
    holes += ['no answer.unconfirmed for what was not recorded'] * (set(paid) != set(recorded) and not found['answer.unconfirmed'])
    holes += ['answer.unconfirmed before the row was due'] * (timing == 'late' and bool(found['answer.unconfirmed']))
    holes += [f'hook.error {found["hook.error"]}'] * bool(found['hook.error'])
    holes += ['a Stop blocked on an unrecorded answer'] * any('not recorded' in str((out or {}).get('reason')) for out in stops)
    return {'recorded': sorted(recorded), 'approved': bool(found['plan.approved']),
            'unconfirmed': [r['reason'][:120] for r in found['answer.unconfirmed']]}, holes, not found['hook.error']


batches = [[(q, a)] for q in QUESTIONS for a in ANSWERS] + [
    [(q1, a1), (q2, a2)] for q1, q2 in itertools.permutations(QUESTIONS, 2) for a1 in ANSWERS for a2 in ANSWERS]
cases, holes, clean = {}, {}, 0
for batch, timing in itertools.product(batches, TIMINGS):
    key = ' + '.join(f'{q}:{a}' for q, a in batch) + ' x ' + timing
    cases[key], found, ok = case(batch, timing)
    clean += ok
    if found:
        holes[key] = found
print(json.dumps({'tree': str(tree), 'timings': TIMINGS, 'clean': clean, 'cases': cases, 'holes': holes}, indent=1, sort_keys=True))
