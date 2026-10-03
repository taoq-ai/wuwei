"""wuwei why (#312): the item chain, the refusal and the decision views, from records only."""

import json

import pytest

from test_decision import VALID
from wuwei import state
from wuwei.__main__ import main

DAY = '2026-10-02'


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', f'{DAY}T12:00:00+00:00')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def day_of(root, day=DAY):
    return root / '.wuwei/days' / day


def events(root, day=DAY):
    path = day_of(root, day) / 'events.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines()]


def save(root, text, name='D-3', day=DAY):
    path = day_of(root, day) / 'decisions' / f'{name}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def answer(root, monkeypatch, option, text=VALID.replace('Reversibility: two-way', 'Reversibility: one-way')):
    save(root, text)
    assert main(['decision', 'route', 'D-3']) == 0
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert main(['decision', 'outcome', 'D-3', option]) == 0
    return events(root)[-1]


def test_owner_outcome_names_its_decider(root, monkeypatch):
    last = answer(root, monkeypatch, 'B')
    assert last['kind'] == 'decision.decided' and last['payload']['decided_by'] == 'owner'


def test_owner_reversal_names_its_decider(root, monkeypatch):
    last = answer(root, monkeypatch, 'B', VALID)
    assert last['kind'] == 'decision.reversed' and last['payload']['decided_by'] == 'owner'


QUALITY = '''Verdict: FIX
- P1 src/login.py:12 the token is logged in plain text
  blocks: yes
- P3 src/login.py:40 a long function
  blocks: no
'''
SCORE = {'value': 8, 'time': 5, 'risk': 3, 'job_size': 2}
HEAD = 'abcdef1234567890'


def merged_item(root, *, skip=(), phase='merged', proposal=True):
    """The acceptance day for fix-login (acme/app#7): every producer record, minus `skip`."""
    day = day_of(root)
    (day / 'decisions').mkdir(parents=True, exist_ok=True)
    if proposal:
        (day / 'proposal.json').write_text(json.dumps({'candidates': [
            {'id': 'fix-login', 'goal': 'ship-login', 'score': SCORE}]}))
    files = {}
    for role, verdict in (('arch', 'PASS'), ('quality', 'FIX'), ('security', 'PASS')):
        path = day / 'decisions' / f'gate-fix-login-{role}.md'
        path.write_text(QUALITY if role == 'quality' else f'Verdict: {verdict}\n')
        files[role] = str(path.relative_to(root))
    save(root, VALID.replace('Which fix?', 'Which fix for fix-login?'), 'D-3')
    save(root, VALID.replace('Which fix?', 'Merge fix-login now?')
         .replace('Reversibility: two-way', 'Reversibility: one-way'), 'D-4')
    (day / 'state.json').write_text(json.dumps({
        'items': {'fix-login': {'goal': 'ship-login', 'phase': phase,
                                'status': 'done' if phase == 'merged' else 'running',
                                'pr': 'acme/app#7', 'flags': {'trust_surface': True}}},
        'raised_prs': ['acme/app#7'], 'approved_items': ['fix-login'], 'gate_approved': True,
        'gate_verdicts': {f'fix-login:{role}:initial': {
            'item': 'fix-login', 'role': role, 'round': 'initial', 'verdict': verdict,
            'file': files[role]} for role, verdict in (('arch', 'PASS'), ('quality', 'FIX'),
                                                       ('security', 'PASS'))}}))
    rows = [
        ('plan.approved', {'items': ['fix-login'], 'approved_items': ['fix-login'], 'flags': {}}),
        ('state.transition', {'item': 'fix-login', 'phase': 'implement',
                              'phase_changes': {'fix-login': 'implement'}}),
        ('state.transition', {'item': 'fix-login', 'phase': 'gate',
                              'phase_changes': {'fix-login': 'gate'}}),
        ('gate.tiered', {'item': 'fix-login', 'tier': 'standard', 'computed': 'standard',
                         'reasons': ['lead flag trust_surface', 'floor standard'],
                         'roles': ['arch', 'quality', 'security']}),
        *(('gate.received', {'item': 'fix-login', 'role': role, 'round': 'initial', 'verdict': verdict})
          for role, verdict in (('arch', 'PASS'), ('quality', 'FIX'), ('security', 'PASS'))),
        ('decision.decided', {'id': 'D-3', 'option': 'A', 'decided_by': 'seat'}),
        ('pr.raised', {'pr': 'acme/app#7', 'item': 'fix-login',
                       'phase_changes': {'fix-login': 'raised'}}),
        ('decision.decided', {'id': 'D-4', 'option': 'B', 'decided_by': 'owner'}),
        ('merge.auto', {'pr': 'acme/app#7', 'head': HEAD, 'status': 'accepted', 'evidence': {
            'head': HEAD, 'checks': [{'name': 'test', 'conclusion': 'success'}],
            'approvals': ['alice'], 'verdicts': [{'path': files[role]} for role in files]}}),
        ('pr.action', {'pr': 'acme/app#7', 'phase_changes': {'fix-login': 'merged'}}),
    ]
    for kind, payload in rows:
        if kind not in skip:
            state.append_event(kind, payload, directory=day)
    return files


BRIEF = [
    'queued: goal ship-login, score value 8, time 5, risk 3, job_size 2',
    'tier: standard (lead flag trust_surface; floor standard)',
    'gate arch initial: PASS',
    'gate quality initial: FIX, blocking: - P1 src/login.py:12 the token is logged in plain text',
    'gate security initial: PASS',
    'decision D-3: Which fix for fix-login?: A by seat',
    'decision D-4: Merge fix-login now?: B by owner',
    'phase implement by wuwei state transition',
    'phase gate by wuwei state transition',
    'phase raised by wuwei pr raise',
    'phase merged by wuwei pr state',
    'merge acme/app#7: cleared by the merge policy at head abcdef123456, checks test success, approvals alice',
    'now: merged (done)',
]


def why(capsys, *argv):
    capsys.readouterr()
    code = main(['why', *argv])
    out = capsys.readouterr()
    return code, out.out.splitlines(), out.err


def full(root):
    files = merged_item(root)
    rel = f'.wuwei/days/{DAY}'
    ids = [f'event {DAY}:{n}' for n in (1, 4, 5, 6, 7, 8, 10, 2, 3, 9, 12, 11)]
    tails = [f'{ids[0]}; {rel}/proposal.json', ids[1],
             f'{ids[2]}; {files["arch"]}', f'{ids[3]}; {files["quality"]}',
             f'{ids[4]}; {files["security"]}', f'{ids[5]}; {rel}/decisions/D-3.md',
             f'{ids[6]}; {rel}/decisions/D-4.md', *ids[7:11],
             f'{ids[11]}; ' + '; '.join(files.values()),
             f'event not recorded; {rel}/state.json']
    return [f'{line} ({tail})' for line, tail in zip(BRIEF, tails)]


def test_item_chain_lists_every_recorded_step(root, capsys):
    merged_item(root)
    assert why(capsys, 'fix-login') == (0, BRIEF, '')


def test_item_chain_full_names_event_ids_and_paths(root, capsys):
    expected = full(root)
    assert why(capsys, 'fix-login', '--full') == (0, expected, '')


@pytest.mark.parametrize('level', ['full', 'standard'])
def test_item_chain_follows_report_verbosity(root, capsys, level):
    expected = full(root) if level == 'full' else (merged_item(root), BRIEF)[1]
    (root / '.wuwei/config.toml').write_text(f'[owner.verbosity]\nreport = "{level}"\n')
    assert why(capsys, 'fix-login') == (0, expected, '')


def test_pull_request_ref_reads_its_item(root, capsys):
    merged_item(root)
    assert why(capsys, 'acme/app#7') == (0, BRIEF, '')


def test_why_writes_nothing(root, capsys):
    merged_item(root)
    tree = lambda: {str(p): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}
    before = tree()
    why(capsys, 'fix-login')
    why(capsys, 'fix-login', '--full')
    assert tree() == before


@pytest.mark.parametrize('kind,line', [
    ('gate.tiered', 'tier: not recorded'),
    ('plan.approved', 'queued: not recorded'),
    ('gate.received', 'gate verdicts: not recorded'),
    ('merge.auto', 'merge policy check: not recorded'),
])
def test_missing_required_step_says_not_recorded(root, capsys, kind, line):
    merged_item(root, skip=(kind,))
    code, lines, _ = why(capsys, 'fix-login')
    assert code == 0 and line in lines
    assert f'{line} (event not recorded)' in why(capsys, 'fix-login', '--full')[1]


def test_unmerged_item_has_no_merge_line(root, capsys):
    merged_item(root, skip=('merge.auto', 'pr.action'), phase='raised')
    lines = why(capsys, 'fix-login')[1]
    assert not any(line.startswith('merge') for line in lines)
    assert lines[-1] == 'now: raised (running)'


def test_missing_details_say_not_recorded(root, capsys):
    files = merged_item(root, proposal=False)
    (root / files['quality']).unlink()
    save(root, VALID.replace('Which fix?', 'Retry fix-login?'), 'D-5')
    state.append_event('decision.decided', {'id': 'D-4', 'option': 'A'}, directory=day_of(root))
    lines = why(capsys, 'fix-login')[1]
    assert lines[0] == 'queued: goal ship-login, score not recorded'
    assert 'gate quality initial: FIX, blocking findings not recorded' in lines
    assert 'decision D-4: Merge fix-login now?: A by not recorded' in lines
    assert 'decision D-5: Retry fix-login?: decided not recorded' in lines


def write_state(root, data, day=DAY):
    day_of(root, day).mkdir(parents=True, exist_ok=True)
    (day_of(root, day) / 'state.json').write_text(json.dumps(data))


def test_item_carried_from_an_earlier_day_reads_both_days(root, capsys):
    yesterday = '2026-10-01'
    write_state(root, {'items': {'old': {'goal': 'g', 'phase': 'implement'}}}, yesterday)
    (day_of(root, yesterday) / 'proposal.json').write_text(json.dumps({'candidates': [
        {'id': 'old', 'score': {'value': 1}}]}))
    state.append_event('plan.approved', {'items': ['old'], 'approved_items': ['old']},
                       directory=day_of(root, yesterday))
    state.append_event('gate.tiered', {'item': 'old', 'tier': 'light', 'reasons': []},
                       directory=day_of(root, yesterday))
    write_state(root, {'items': {'old': {'goal': 'g'}}})
    state.append_event('state.import', {'items': ['old'], 'approved_items': []}, directory=day_of(root))
    code, lines, _ = why(capsys, 'old', '--full')
    assert code == 0 and lines[:3] == [
        f'queued: goal g, score value 1 (event 2026-10-01:1; .wuwei/days/2026-10-01/proposal.json)',
        f'queued: carried over from an earlier day, goal g (event {DAY}:1)',
        'tier: light (event 2026-10-01:2)']
    assert lines[-1] == f'now: planned (queued) (event not recorded; .wuwei/days/{DAY}/state.json)'


@pytest.mark.parametrize('row,now', [
    ({'phase': 'parked', 'status': 'blocked', 'resume_phase': 'implement', 'decision': 'D-5'},
     'now: parked (blocked), waiting on decision D-5'),
    ({'phase': 'escalated', 'status': 'blocked', 'resume_phase': 'implement'},
     'now: escalated (blocked), waiting on: not recorded'),
    ({'phase': 'implement', 'assumption': {'decision': 'D-6', 'status': 'waiting'}},
     'now: implement (queued), waiting on external confirmation D-6'),
    ({'phase': 'raised', 'pr': 'acme/app#7'}, 'now: raised (queued), waiting on start a fix round'),
    ({'phase': 'raised'}, 'now: raised (queued)'),
])
def test_now_names_what_the_item_waits_on(root, capsys, row, now):
    write_state(root, {'items': {'x': row},
                       'watch': {'actions': {'acme/app#7': {'action': 'start a fix round'}}}})
    assert why(capsys, 'x')[1][-1] == now


def test_intraday_item_takes_its_score_from_discovery(root, capsys):
    write_state(root, {'items': {'x': {'goal': 'g'}},
                       'discovery_candidates': {'x': {'score': {'value': 3}}}})
    state.append_event('plan.added', {'item': 'x'}, directory=day_of(root))
    assert why(capsys, 'x', '--full')[1][0] == (
        f'queued: goal g, score value 3 (event {DAY}:1; .wuwei/days/{DAY}/state.json)')


@pytest.mark.parametrize('target,code,err', [
    ('nope', 1, "wuwei why: no recorded item nope; run bin/wuwei status for today's items\n"),
    ('acme/app#9', 1, 'wuwei why: no item links acme/app#9; run bin/wuwei pr state for the PRs owned today\n'),
    ('acme#x', 2, 'wuwei why: expected owner/repo#number; pass owner/repo#number\n'),
])
def test_missing_targets_exit_one_and_bad_refs_two(root, capsys, target, code, err):
    merged_item(root)
    assert why(capsys, target) == (code, [], err)


def test_corrupt_events_exit_two(root, capsys):
    merged_item(root)
    path = day_of(root) / 'events.jsonl'
    path.chmod(0o644)
    with path.open('a') as stream:
        stream.write('{not json\n')
    code, lines, err = why(capsys, 'fix-login')
    assert (code, lines) == (2, []) and err.startswith('wuwei why:')


def test_outside_a_workspace_exits_two(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    code, _, err = why(capsys, 'fix-login')
    assert code == 2 and 'No .wuwei/ found' in err


def refusal(root, payload, day=DAY, kind='hook.refusal'):
    state.append_event(kind, payload, directory=day_of(root, day))
    return f'{day}:{len(events(root, day))}'


NEW = {'reason': 'force-push is refused; push a branch instead',
       'refusals': [{'guard': 'commit_push', 'reason': 'force-push is refused; push a branch instead'}],
       'target': 'git push --force'}
REFUSAL = ['command: git push --force', 'guard: commit_push', 'rule: force-push is refused',
           'fix: push a branch instead']


def test_refusal_by_event_id(root, capsys):
    refusal(root, {'reason': 'other'}, kind='gate.tiered')
    ident = refusal(root, NEW)
    code, lines, _ = why(capsys, ident)
    assert code == 0 and lines == [f'refusal at {DAY}T12:00:00+00:00', *REFUSAL]
    assert why(capsys, ident, '--full')[1] == [f'{line} (event {ident})' for line in lines]


@pytest.mark.parametrize('ident', [f'{DAY}:1', f'{DAY}:3', '2026-09-01:1'])
def test_refusal_id_that_names_no_refusal_exits_one(root, capsys, ident):
    refusal(root, {'reason': 'other'}, kind='gate.tiered')
    refusal(root, NEW)
    assert why(capsys, ident) == (1, [], f'wuwei why: no recorded refusal {ident}; run bin/wuwei why last refusal for the latest one\n')


def test_older_refusal_record_says_not_recorded(root, capsys):
    refusal(root, {'reason': 'push to the default branch is refused'})
    assert why(capsys, 'last', 'refusal')[1][1:] == [
        'command: not recorded', 'guard: not recorded',
        'rule: push to the default branch is refused', 'fix: not recorded']


def test_last_refusal_is_the_newest_across_days(root, capsys):
    assert why(capsys, 'last', 'refusal') == (1, [], 'wuwei why: no recorded refusal; nothing was refused today, so run bin/wuwei status for the day\n')
    refusal(root, NEW, '2026-10-01')
    assert why(capsys, 'last refusal')[1][1:] == REFUSAL
    refusal(root, {'reason': 'today'})
    refusal(root, {'reason': 'later'}, kind='gate.tiered')
    assert why(capsys, 'last refusal')[1][3] == 'rule: today'


DECIDED = ['D-3: Which fix?', 'A: Implement fix (score 86)', 'B: Defer until tomorrow (score 30)',
           'Recommended: A, ahead of B on Correctness.', 'weights: Correctness 10, Speed 2',
           'margin: 0.47', 'class: not recorded']


def test_decision_view_after_an_owner_answer(root, monkeypatch, capsys):
    answer(root, monkeypatch, 'B')
    ident = f'{DAY}:{len(events(root))}'
    assert why(capsys, 'D-3') == (0, [*DECIDED, 'level: not recorded', 'decided: B by owner'], '')
    lines = why(capsys, 'D-3', '--full')[1]
    assert lines[0] == f'D-3: Which fix? (event not recorded; .wuwei/days/{DAY}/decisions/D-3.md)'
    assert lines[-1] == f'decided: B by owner (event {ident})'


def test_decision_view_reads_class_and_cruise_level(root, capsys):
    save(root, 'Class: retry\n' + VALID)
    assert why(capsys, 'D-3')[1][-3:] == ['class: retry', 'level: not recorded', 'decided: not recorded']
    state.append_event('decision.decided', {'id': 'D-3', 'option': 'A', 'decided_by': 'cruise retry@L2'},
                       directory=day_of(root))
    assert why(capsys, 'D-3')[1][-2:] == ['level: L2', 'decided: A by cruise retry@L2']


def test_decision_view_without_a_record_exits_one(root, capsys):
    assert why(capsys, 'D-9') == (1, [], 'wuwei why: no decision record D-9 today; run bin/wuwei nudges for open decisions\n')


TOKEN = 'ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8'


@pytest.mark.parametrize('argv', [('fix-login',), ('fix-login', '--full'), ('D-3',), ('D-3', '--full')])
def test_recorded_credentials_are_redacted(root, capsys, argv):
    merged_item(root)
    save(root, VALID.replace('Which fix?', f'Which fix for fix-login with {TOKEN}?'), 'D-3')
    code, lines, _ = why(capsys, *argv)
    assert code == 0 and '[REDACTED]' in '\n'.join(lines) and TOKEN not in '\n'.join(lines)


SHADOW = {'guard': 'git', 'reason': 'force-push is refused; push a branch', 'target': 'git push -f',
          'session': 's1', 'item': None}
SHADOWED = [f'would have refused (shadow) at {DAY}T12:00:00+00:00', 'command: git push -f', 'guard: git',
            'rule: force-push is refused', 'fix: push a branch']


def test_shadow_refusal_is_explained(root, capsys):
    ident = refusal(root, SHADOW, kind='guard.would_refuse')
    assert why(capsys, 'last refusal') == (0, SHADOWED, '')
    assert why(capsys, ident) == (0, SHADOWED, '')


def test_posture_warning_names_area_level_and_posture(root, capsys):
    # #331: a warning names the area, its level and the posture that produced it.
    refusal(root, {**SHADOW, 'area': 'publish', 'level': 'warn', 'posture': 'observe'},
            kind='guard.would_refuse')
    assert why(capsys, 'last refusal') == (0, [*SHADOWED, 'posture: publish = warn (observe)'], '')
