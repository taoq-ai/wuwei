"""The model table at runtime: agent frontmatter, the hook's advice and record, the owner's rows,
the doctor and the report (item models-record)."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import launched, make_pr, verdict_text, write_plan
from test_charters import PATHS, _model_table, _models_section, _setting
from wuwei import agents, hook, report, setup, ws

PLUGIN = Path(__file__).resolve().parents[1]
ROLES = json.loads((PLUGIN / 'agents' / 'allowlist.json').read_text(encoding='utf-8'))


@pytest.fixture(autouse=True)
def no_effort_or_model_variable(monkeypatch):
    """A session that sets either variable turns that half of the advice off; these tests start with neither."""
    monkeypatch.delenv('CLAUDE_CODE_EFFORT_LEVEL', raising=False)
    monkeypatch.delenv('CLAUDE_CODE_SUBAGENT_MODEL', raising=False)


def plan_item(root, tier='standard', repo='acme/app'):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': repo, 'tier': tier, 'status': 'open', 'score': 3}])


def launch(root, role, model=None, effort=None, prompt='Item: I-1\nBuild it.', tool='Agent'):
    data = {'subagent_type': f'wuwei:{role}', 'description': role, 'prompt': prompt,
            **({'model': model} if model else {}), **({'effort': effort} if effort else {})}
    return hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': tool, 'cwd': str(root), 'tool_input': data})


def advice(out):
    assert out is not None and set(out['hookSpecificOutput']) == {'hookEventName', 'additionalContext'}, out
    return out['hookSpecificOutput']['additionalContext']


# US1: the agent files and the table


def test_every_agent_file_carries_the_tables_default_model_and_effort():
    assert not hasattr(agents, 'MODELS')
    for role in ROLES:
        head = (PLUGIN / 'agents' / f'{role}.md').read_text(encoding='utf-8').split('\n---\n', 1)[0]
        model, effort = agents.TABLE[role][''].rsplit(' ', 1)
        assert f'\nmodel: claude-{model.lower().replace(" ", "-").replace(".", "-")}\n' in head + '\n', role
        assert f'\neffort: {effort}\n' in head + '\n', role
    assert '\nmodel: claude-opus-5-5\neffort: medium' in (PLUGIN / 'agents' / 'builder.md').read_text(encoding='utf-8')


def test_the_runtime_table_is_the_planner_table_at_every_tier_on_and_off_the_paths():
    rows = _model_table()
    assert set(agents.TABLE) == set(rows) - {'lookups and searches'} == set(ROLES)
    for role, table in agents.TABLE.items():
        for tier in ('light', 'standard', 'full'):
            for paths in (False, True):
                got = table[agents.PATHS] if paths and agents.PATHS in table else table.get(tier, table[''])
                assert got == ' '.join(_setting(rows[role], tier, paths)), (role, tier, paths)
    assert rows['shepherd'].endswith(f'; {agents.TABLE["shepherd"][agents.CONFLICT]} {agents.CONFLICT}')
    assert set(agents.TABLE['shepherd']) == {'', agents.CONFLICT} and agents.PATHS == f'on {PATHS}'


def test_the_planner_and_the_page_say_the_hook_notes_a_departure_and_never_refuses():
    text = ' '.join(_models_section().split())
    assert "On a departure with no reason line the hook adds a note naming the table's setting; it never refuses the call." in text
    assert 'A `models` row is not that exception: only the owner\'s `exception:` answer is.' in text
    page = ' '.join((PLUGIN / 'docs' / 'site' / 'concepts' / 'models.md').read_text(encoding='utf-8').split())
    assert "it adds a note naming the table's setting; it never refuses or rewrites the call." in page
    assert 'A `models` row that puts Haiku 5.5 on a gate does not break the floor: only your `exception:` answer does.' in page


def test_a_codex_role_file_names_native_defaults_without_changing_claude_generation():
    role = tomllib.loads(agents.render_codex(PLUGIN, 'builder'))
    assert (role['model'], role['model_reasoning_effort']) == ('gpt-6.1-sol', 'medium')
    assert 'model: claude-opus-5-5\neffort: medium' in agents.render(PLUGIN, 'builder', [])


# US2: the advice


def test_a_departure_gets_advice_naming_the_table_setting_and_the_reason_line(root):
    plan_item(root, 'standard')
    text = advice(launch(root, 'sentinel-goal', model='opus'))
    assert "table says Sonnet 5.5 high for sentinel-goal at standard; record a 'Model reason:' line in the brief" in text
    assert ws.rows(root, 'refused') == [] and ws.rows(root, 'hook.error') == []


@pytest.mark.parametrize('role, tier, model, effort', [
    ('sentinel-goal', 'standard', 'sonnet', 'high'), ('sentinel-goal', 'standard', 'claude-sonnet-5-5', 'high'),
    ('sentinel-goal', 'standard', None, None),  # the agent file's own setting
    ('builder', 'full', 'opus', 'high'), ('builder', 'light', 'sonnet', 'medium'),
    ('builder', 'standard', 'opus', 'high'),  # the row's setting on risky, owner or contract paths
    ('sentinel-quality', 'light', 'opus', 'high'), ('shepherd', 'standard', 'opus', 'high'),
    ('lead', 'full', 'claude-opus-5-5', 'xhigh')])
def test_a_launch_the_table_allows_gets_nothing(root, role, tier, model, effort):
    plan_item(root, tier)
    assert launch(root, role, model, effort) is None


@pytest.mark.parametrize('role, tier, model, effort, said', [
    ('sentinel-goal', 'standard', 'sonnet', 'low', 'Sonnet 5.5 high for sentinel-goal at standard'),
    ('builder', 'full', 'opus', 'medium', 'Opus 5.5 high for builder at full'),
    ('builder', 'light', 'opus', 'medium', 'Sonnet 5.5 medium for builder at light'),
    ('sentinel-security', 'standard', None, 'medium', 'Opus 5.5 high for sentinel-security at standard')])
def test_a_launch_outside_the_table_is_advised(root, role, tier, model, effort, said):
    plan_item(root, tier)
    assert f'table says {said};' in advice(launch(root, role, model, effort))


def test_the_advice_names_the_paths_setting_too(root):
    plan_item(root, 'standard')
    assert '(asked: sonnet low; the row also allows Opus 5.5 high on risky, owner or contract paths).' in advice(launch(root, 'builder', 'sonnet', 'low'))


def test_the_briefs_model_line_gives_the_effort_when_the_call_has_none(root):
    plan_item(root, 'standard')
    prompt = 'Model: claude-sonnet-5-5 low (sentinel-goal)\nItem: I-1'
    assert 'Sonnet 5.5 high' in advice(launch(root, 'sentinel-goal', 'sonnet', prompt=prompt))
    assert launch(root, 'sentinel-goal', 'sonnet', prompt=prompt.replace(' low ', ' high ')) is None


def test_a_model_reason_line_ends_the_advice(root):
    plan_item(root, 'standard')
    assert launch(root, 'sentinel-goal', 'opus', 'high', prompt='Item: I-1\nModel reason: second family') is None


FLOOR = ('Haiku 5.5 never runs a gate on risky, owner or contract paths, and neither a reason nor a models row covers '
         'that: it is an exception: for the owner.')


def test_a_haiku_gate_is_advised_even_with_a_reason_or_a_models_row(root, monkeypatch):
    plan_item(root, 'standard')
    assert FLOOR in advice(launch(root, 'sentinel-quality', 'haiku', 'low', prompt='Item: I-1\nModel reason: cheap'))
    ws.set_config(root, 'models', 'sentinel-quality=claude-haiku-5-5 low')  # any seat can write config.toml
    assert FLOOR in advice(launch(root, 'sentinel-quality', 'haiku', 'low', prompt='Item: I-1\nModel reason: cheap'))
    assert FLOOR in advice(launch(root, 'sentinel-quality', 'claude-opus-5-5', 'high'))  # the row itself puts Haiku on the gate
    monkeypatch.setenv('CLAUDE_CODE_SUBAGENT_MODEL', 'claude-haiku-5-5')
    assert FLOOR in advice(launch(root, 'sentinel-quality', 'haiku', 'low'))


@pytest.mark.parametrize('row', ['["claude-haiku-5-5", "low"]', '{model = "haiku", effort = "low"}', '["haiku"]', '"Haiku"'])
def test_a_malformed_models_row_cannot_silence_the_haiku_floor(root, row):
    plan_item(root, 'standard')
    (root / ws.DIR / 'config.toml').write_text(f'models = {{"sentinel-quality" = {row}}}\n')  # a seat can write any TOML here
    assert FLOOR in advice(launch(root, 'sentinel-quality', 'claude-sonnet-5-5', 'high'))  # the table's own setting


def test_the_haiku_floor_is_for_gates_only(root):
    plan_item(root, 'standard')
    assert launch(root, 'builder', 'haiku', 'low', prompt='Item: I-1\nModel reason: a typo fix') is None
    assert 'Haiku 5.5 never' not in advice(launch(root, 'builder', 'haiku', 'low'))


def test_an_owner_row_for_the_role_and_tier_replaces_the_table(root):
    plan_item(root, 'light')
    assert 'Sonnet 5.5 medium' in advice(launch(root, 'builder', 'opus', 'medium'))
    (root / ws.DIR / 'config.toml').write_text('repos = ["acme/app"]\nmodels = {"builder light" = "opus medium"}\n')
    assert launch(root, 'builder', 'opus', 'medium') is None
    assert "table says opus medium for builder at light" in advice(launch(root, 'builder', 'opus', 'high'))
    plan_item(root, 'standard')
    assert launch(root, 'builder', 'opus', 'medium') is None  # the standard row is the table's


def test_an_owner_row_for_the_role_alone_replaces_the_table_at_every_tier(root):
    plan_item(root, 'standard')
    assert 'Sonnet 5.5 medium' in advice(launch(root, 'shepherd', 'opus', 'low'))
    (root / ws.DIR / 'config.toml').write_text('repos = ["acme/app"]\nmodels = {"shepherd" = "opus low"}\n')
    for tier in ('light', 'standard', 'full'):
        plan_item(root, tier)
        assert launch(root, 'shepherd', 'opus', 'low') is None


def test_a_tier_raised_by_the_cached_budget_is_the_one_advised_on(root, fake):
    plan_item(root, 'light')
    assert launch(root, 'builder', 'opus', 'medium') is not None and fake.calls == []  # no cache: no code host read
    ws.cache_put(root, 'budget-acme__app', {'cfr': 0.5, 'merged': 6})
    assert launch(root, 'builder', 'opus', 'medium') is None
    assert 'for builder at standard' in advice(launch(root, 'builder', 'sonnet', 'medium'))
    assert fake.calls == []


def test_the_item_is_read_from_a_wuwei_item_line_and_a_brief_without_one_reads_as_standard(root):
    plan_item(root, 'full')
    assert launch(root, 'builder', 'opus', 'high', prompt='WUWEI-Item: I-1') is None
    assert 'for builder at standard' in advice(launch(root, 'builder', 'sonnet', 'high', prompt='Build the thing.'))


def test_the_task_tool_name_is_advised_too(root):
    plan_item(root, 'standard')
    assert 'Sonnet 5.5 high' in advice(launch(root, 'sentinel-goal', 'opus', tool='Task'))


@pytest.mark.parametrize('prompt, item, reason', [
    ('Item: I-1\nModel reason:\nBuild it.', 'I-1', None), ('Item:\nModel: claude-opus-5-5 high', None, None),
    ('Item: I-1.\nModel reason: \t second family ', 'I-1', 'second family'), ('Build Item: `I-1`, then stop.', 'I-1', None)])
def test_the_brief_lines_are_read_within_their_own_line(root, prompt, item, reason):
    assert hook.asked({'prompt': prompt})[0::2] == (item, reason)


def test_an_empty_model_reason_line_does_not_end_the_advice(root):
    plan_item(root, 'full')
    assert 'for builder at full' in advice(launch(root, 'builder', 'sonnet', 'low', prompt='Item: I-1.\nModel reason:\nBuild it.'))


@pytest.mark.parametrize('variable, model, effort', [('CLAUDE_CODE_EFFORT_LEVEL', 'sonnet', 'low'),
                                                     ('CLAUDE_CODE_SUBAGENT_MODEL', 'opus', 'high')])
def test_an_environment_variable_turns_its_half_of_the_advice_off(root, monkeypatch, variable, model, effort):
    plan_item(root, 'standard')
    assert launch(root, 'sentinel-goal', model, effort) is not None
    monkeypatch.setenv(variable, 'low' if 'EFFORT' in variable else 'claude-sonnet-5-5')
    assert launch(root, 'sentinel-goal', model, effort) is None


def test_codex_advice_names_policy_requests_and_capability_limits(root):
    plan_item(root, 'full')
    spawn = {'session_id': 's1', 'tool_name': 'spawn_agent', 'cwd': str(root),
             'tool_input': {'agent_type': 'builder', 'task_name': 'build I-1', 'message': 'Item: I-1'}}
    text = advice(hook.handle(root, 'PreToolUse', spawn))
    assert 'gpt-6.1-sol high for builder at full' in text
    assert 'requested: unrecorded unrecorded' in text and 'active schema' in text
    ws.set_config(root, 'models', 'builder=gpt-6-astra ultra')
    spawn['tool_input'].update(model='unavailable-model', reasoning_effort='low', fork_turns='all')
    text = advice(hook.handle(root, 'PreToolUse', spawn))
    assert 'gpt-6-astra ultra for builder at full' in text
    assert 'requested: unavailable-model low' in text and 'fork policy: inherit' in text
    spawn['tool_input']['fork_turns'] = 'none'
    assert 'fork policy: fresh' in advice(hook.handle(root, 'PreToolUse', spawn))
    assert launch(root, 'Explore', 'haiku', 'low') is None
    assert ws.rows(root, 'hook.error') == []


# US3: the record


def started(root, data, response):
    return hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'Agent', 'cwd': str(root),
                                             'tool_input': data, 'tool_response': response})


def test_a_launch_records_what_ran_what_was_asked_and_the_reason_and_the_attest_copies_it(root, fake):
    plan_item(root, 'light')
    fake.prs['42'] = make_pr()
    assert started(root, {'subagent_type': 'wuwei:sentinel-quality', 'model': 'opus', 'effort': 'high',
                          'prompt': 'Item: I-1\nModel reason: conflict in logic'},
                   {'agentId': 'rev1', 'resolvedModel': 'claude-opus-5-5'}) is None
    [row] = ws.rows(root, 'seat.started')
    assert {k: row['data'][k] for k in ('model', 'asked', 'effort', 'reason', 'item')} == {
        'model': 'claude-opus-5-5', 'asked': 'opus', 'effort': 'high', 'reason': 'conflict in logic', 'item': 'I-1'}
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text(verdict='FIX', findings='- [high] src/app.py:9 blocks: yes. Failure: it drops a row'))
    assert hook.handle(root, 'SubagentStop', launched({'session_id': 's1', 'agent_id': 'rev1', 'agent_type': 'wuwei:sentinel-quality',
                                                       'last_assistant_message': 'Verdict file: .wuwei/verdicts/I-1/quality.md',
                                                       'effort': {'level': 'high'}, 'cwd': str(root)})) is None
    [attest] = ws.rows(root, 'attest')
    assert (attest['data']['model'], attest['data']['effort'], attest['data']['blocking']) == ('claude-opus-5-5', 'high', 1)


def test_the_attest_copies_the_launch_with_its_own_agent_id(root, fake):
    plan_item(root, 'standard')
    fake.prs['42'] = make_pr()
    for agent, model, effort in (('rev1', 'claude-sonnet-5-5', 'high'), ('rev2', 'claude-opus-5-5', 'xhigh')):
        started(root, {'subagent_type': 'wuwei:sentinel-quality', 'effort': effort, 'prompt': 'Item: I-1'},
                {'agentId': agent, 'resolvedModel': model})
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text(verdict='PASS'))
    assert hook.handle(root, 'SubagentStop', launched({'session_id': 's1', 'agent_id': 'rev1', 'agent_type': 'wuwei:sentinel-quality',
                                                       'last_assistant_message': 'Verdict file: .wuwei/verdicts/I-1/quality.md',
                                                       'cwd': str(root)})) is None
    [attest] = ws.rows(root, 'attest')
    assert (attest['data']['agent'], attest['data']['model'], attest['data']['effort']) == ('rev1', 'claude-sonnet-5-5', 'high')


def test_a_launch_with_nothing_readable_records_unrecorded_and_unmeasured(root):
    started(root, {'subagent_type': 'wuwei:builder', 'description': 'build'}, {'agentId': 'b1'})
    data = ws.rows(root, 'seat.started')[0]['data']
    assert (data['model'], data['asked'], data['effort'], data['reason'], data['item']) == (
        'unmeasured', 'unrecorded', 'unrecorded', None, None)


def test_the_briefs_model_line_is_the_recorded_effort_when_the_call_has_none(root):
    started(root, {'subagent_type': 'builder', 'model': 'opus', 'prompt': 'Model: claude-opus-5-5 high (builder)\nItem: I-1'},
            {'agentId': 'b1', 'resolvedModel': 'claude-opus-5-5'})
    assert ws.rows(root, 'seat.started')[0]['data']['effort'] == 'high'


def test_a_codex_spawn_is_recorded_as_unmeasured(root):
    payload = json.loads((PLUGIN / 'tests' / 'fixtures' / 'payloads' / 'codex-spawn-agent-post.json').read_text())
    hook.handle(root, 'PostToolUse', payload)
    data = ws.rows(root, 'seat.started')[0]['data']
    assert (data['model'], data['asked'], data['effort']) == ('unmeasured', 'unrecorded', 'unrecorded')


def test_the_transcript_launch_with_model_and_effort_records_both(root):
    payload = json.loads((PLUGIN / 'tests' / 'fixtures' / 'payloads' / 'claude-agent-post-model-effort.json').read_text())
    assert hook.handle(root, payload['hook_event_name'], payload) is None
    data = ws.rows(root, 'seat.started')[0]['data']
    assert (data['model'], data['asked'], data['effort'], data['item'], data['role']) == (
        'claude-sonnet-5-5', 'sonnet', 'high', 'X-1', 'sentinel-goal')
    pre = {**payload, 'hook_event_name': 'PreToolUse'}
    del pre['tool_response']
    assert hook.handle(root, 'PreToolUse', pre) is None  # the table's own setting for a goal gate


@pytest.mark.parametrize('data', [{'subagent_type': ['builder'], 'prompt': 'Item: I-1'},
                                  {'subagent_type': 'builder', 'model': ['opus'], 'effort': {'x': 1}, 'prompt': ['Item: I-1']},
                                  {'subagent_type': 'builder', 'model': '', 'effort': '', 'prompt': 'Item: \nModel: \nModel reason: '},
                                  {'subagent_type': 'sentinel-goal', 'model': 'opus', 'prompt': 'Item: NOPE'}])
def test_a_malformed_launch_is_never_refused_and_never_a_hook_error(root, data):
    plan_item(root, 'bogus-tier')
    out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'tool_name': 'Agent', 'cwd': str(root), 'tool_input': data})
    assert out is None or set(out['hookSpecificOutput']) == {'hookEventName', 'additionalContext'}
    hook.handle(root, 'PostToolUse', {'tool_name': 'Agent', 'cwd': str(root), 'tool_input': data,
                                      'tool_response': {'agentId': 'a1', 'resolvedModel': ['x']}})
    assert ws.rows(root, 'hook.error') == [] and len(ws.rows(root, 'seat.started')) == 1


# US4: the sixth key


def test_the_models_key_is_set_kept_and_written_as_toml(root):
    import tomllib
    data = ws.set_config(root, 'models', 'builder light=opus medium, shepherd = sonnet high, junk')
    assert data['models'] == {'builder light': 'opus medium', 'shepherd': 'sonnet high'}
    text = (root / ws.DIR / 'config.toml').read_text()
    assert tomllib.loads(text)['models'] == data['models'] == ws.config(root)['models']
    assert ws.retired(root) == [] and len(ws.DEFAULTS) == 6


def test_an_empty_models_key_is_not_written(root):
    """An older plugin's wuwei init lists models as retired and rewrites the config without it."""
    ws.set_config(root, 'telemetry', 'false')
    assert 'models' not in (root / ws.DIR / 'config.toml').read_text()
    ws.set_config(root, 'models', 'lead=opus high')
    ws.set_config(root, 'models', '')
    assert 'models' not in (root / ws.DIR / 'config.toml').read_text() and ws.config(root)['models'] == {}


def test_a_blank_or_repeated_models_value_sets_what_it_can(root):
    assert ws.set_config(root, 'models', '')['models'] == {}
    assert ws.set_config(root, 'models', 'lead=opus high, lead=opus xhigh, =opus low')['models'] == {'lead': 'opus xhigh'}


def test_a_malformed_models_value_is_dropped(root):
    (root / ws.DIR / 'config.toml').write_text('models = {"builder" = "opus", "lead" = 3, "steward" = "opus high"}\n')
    assert ws.config(root)['models'] == {'steward': 'opus high'}
    (root / ws.DIR / 'config.toml').write_text('models = "opus high"\n')
    assert ws.config(root)['models'] == {}


# US5: the doctor and the report


@pytest.mark.parametrize('variable, half', [('CLAUDE_CODE_EFFORT_LEVEL', 'effort'), ('CLAUDE_CODE_SUBAGENT_MODEL', 'model')])
def test_the_doctor_names_a_variable_that_turns_advice_off(tmp_path, monkeypatch, variable, half):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    setup.init(tmp_path)
    assert not any(name.startswith('CLAUDE_CODE_') for name, _, _ in setup.doctor(tmp_path))
    monkeypatch.setenv(variable, 'low')
    rows = {name: (status, detail) for name, status, detail in setup.doctor(tmp_path)}
    assert rows[variable][0] == 'note' and f'{half} advice is off' in rows[variable][1] and 'low' in rows[variable][1]


@pytest.mark.parametrize('variable', ['CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_SUBAGENT_MODEL'])
@pytest.mark.parametrize('others', ['ok', 'warn', 'fail'])
def test_the_doctor_prints_the_variable_and_keeps_its_exit_code(tmp_path, monkeypatch, capsys, variable, others):
    from wuwei import __main__
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    setup.init(tmp_path)
    real = setup.doctor  # the variable's real row beside one row of the given status
    monkeypatch.setattr(setup, 'doctor', lambda root: [('other', others, 'x')] + [r for r in real(root) if r[0] == variable])
    monkeypatch.setattr(__main__.ws, 'find', lambda: tmp_path)
    unset = __main__.main(['doctor'])
    monkeypatch.setenv(variable, 'low')
    assert __main__.main(['doctor']) == unset == {'ok': 0, 'warn': 1, 'fail': 2}[others]
    assert f'{variable}: set to low' in capsys.readouterr().out


def test_learning_shows_each_seat_by_model_and_effort(root, fake):
    now = ws.now().isoformat(timespec='seconds')
    for number, title in ((40, 'feat: login'), (41, 'Revert "feat: login"')):
        pr = make_pr(number=number, state='MERGED')
        pr.update(title=title, mergedAt=now)
        fake.prs[str(number)] = pr
    seats = [('q1', 'sentinel-quality', 'claude-sonnet-5-5', 'high', 'I-1'), ('q2', 'sentinel-quality', 'claude-sonnet-5-5', 'high', 'I-1'),
             ('q3', 'sentinel-quality', 'claude-opus-5-5', 'high', 'I-2'), ('b1', 'builder', 'unmeasured', 'unrecorded', 'I-1'),
             ('q4', 'sentinel-quality', 'claude-sonnet-5-5', 'high', 'I-2'), ('q5', 'sentinel-quality', 'claude-sonnet-5-5', 'high', 'I-2'),
             ('g1', 'sentinel-goal', 'unmeasured', 'high', 'I-1')]
    for agent, role, model, effort, item in seats:
        ws.record(root, 'seat.started', {'role': role, 'agent': agent, 'model': model, 'effort': effort, 'item': item})
        ws.record(root, 'seat.stopped', {'role': role, 'agent': agent, 'tokens': 100})
    ws.record(root, 'seat.started', {'role': 'shepherd', 'agent': 's1'})  # a row from before this item
    ws.record(root, 'attest', {'agent': 'q1', 'gate': 'quality', 'verdict': 'FIX', 'blocking': 2, 'pr': 'acme/app#42'})
    ws.record(root, 'attest', {'agent': 'q2', 'gate': 'quality', 'verdict': 'PASS', 'blocking': 0, 'pr': 'acme/app#42'})
    ws.record(root, 'attest', {'agent': 'q3', 'gate': 'quality', 'verdict': 'PASS', 'pr': 'acme/app#40'})
    ws.record(root, 'attest', {'agent': 'q4', 'gate': 'quality', 'verdict': 'FIX', 'pr': 'acme/app#43'})  # from before this item
    text = report.day(root)
    assert ('- seat sentinel-quality claude-sonnet-5-5 high: 4 launches, 1.0 fix rounds per item, 3 blocking findings, '
            '0 escapes, 400 tokens') in text
    assert ('- seat sentinel-quality claude-opus-5-5 high: 1 launches, 0.0 fix rounds per item, 0 blocking findings, '
            '1 escapes, 100 tokens') in text
    assert '- seat builder unmeasured unrecorded: 1 launches' in text
    assert '- seat sentinel-goal unmeasured high: 1 launches' in text
    assert '- model or effort unrecorded on 3 launches' in text


@pytest.mark.parametrize('tier, rows, expected', [
    ('standard', {}, ('gpt-6.1-sol', 'medium')),
    ('light', {}, ('gpt-6-luna', 'medium')),
    ('full', {}, ('gpt-6.1-sol', 'high')),
    ('full', {'builder': 'gpt-6-astra max'}, ('gpt-6-astra', 'max')),
    ('full', {'builder': 'gpt-6-astra max', 'builder full': 'gpt-6.1-sol ultra'}, ('gpt-6.1-sol', 'ultra')),
    ('standard', {'builder': 'unavailable-provider-model high'}, ('unavailable-provider-model', 'high')),
    ('standard', {'builder': '  gpt-6.1-sol  high  '}, ('gpt-6.1-sol', 'high')),
])
def test_codex_role_settings_use_native_mapping_and_owner_tier_precedence(tier, rows, expected):
    role = tomllib.loads(agents.render_codex(PLUGIN, 'builder', rows, tier))
    assert (role['model'], role['model_reasoning_effort']) == expected
    assert 'Builder charter' in role['developer_instructions']


@pytest.mark.parametrize('fork, policy', [('all', 'inherit'), ('none', 'fresh'), (None, 'unmeasured')])
@pytest.mark.parametrize('resolved', [None, 'provider-child-model'])
def test_native_report_separates_requests_parent_turn_and_child_resolution(root, fork, policy, resolved):
    payload = json.loads((PLUGIN / 'tests/fixtures/payloads/codex/native-spawn-agent-post.json').read_text())
    payload.update(cwd=str(root), model='parent-turn-model', effort={'level': 'medium'})
    payload['tool_input'].update(model='unavailable-child-model', reasoning_effort='ultra')
    if fork:
        payload['tool_input']['fork_turns'] = fork
    payload['tool_response'] = {'task_name': '/root/native'}
    if resolved:
        payload['tool_response']['resolvedModel'] = resolved
    hook.handle(root, 'PostToolUse', payload)
    row = ws.rows(root, 'seat.started')[0]['data']
    assert (row['asked'], row['effort'], row['model']) == ('unavailable-child-model', 'ultra', resolved or 'unmeasured')
    assert (row['turn_model'], row['turn_effort'], row['fork_policy']) == ('parent-turn-model', 'medium', policy)
    text = report.day(root)
    assert 'requested: unavailable-child-model ultra' in text
    assert f'resolved child: {resolved or "unmeasured"}' in text
    assert 'launching parent turn: parent-turn-model medium' in text
    assert f'fork policy: {policy}' in text
    assert ws.rows(root, 'attest') == []


def test_native_request_from_brief_does_not_measure_an_unavailable_override(root):
    payload = {'session_id': 's1', 'tool_name': 'spawn_agent', 'cwd': str(root),
               'tool_input': {'agent_type': 'builder', 'message': 'Item: I-1\nModel: gpt-6-astra ultra (requested; schema has no overrides)'},
               'tool_response': {'task_name': '/root/no-overrides'}}
    hook.handle(root, 'PostToolUse', payload)
    row = ws.rows(root, 'seat.started')[0]['data']
    assert (row['asked'], row['effort'], row['model']) == ('gpt-6-astra', 'ultra', 'unmeasured')
    text = report.day(root)
    assert 'requested: gpt-6-astra ultra' in text and 'launching parent turn: unmeasured unmeasured' in text
    assert 'fork policy: unmeasured' in text


@pytest.mark.parametrize('turn_effort, fork', [(None, ''), ('high', []), ({}, 'unknown'), ({'level': ''}, None)])
def test_missing_or_malformed_native_metadata_stays_unmeasured(root, turn_effort, fork):
    hook.handle(root, 'PostToolUse', {'tool_name': 'spawn_agent', 'cwd': str(root), 'effort': turn_effort,
                                      'tool_input': {'agent_type': 'builder', 'fork_turns': fork},
                                      'tool_response': {'task_name': '/root/metadata'}})
    assert ws.rows(root, 'hook.error') == []
    row = ws.rows(root, 'seat.started')[0]['data']
    assert (row['turn_model'], row['turn_effort'], row['fork_policy'], row['model']) == ('unmeasured',) * 4


@pytest.mark.parametrize('padding', [0, 110, 190, 199, 210])
@pytest.mark.parametrize('kind', ['credential', 'canary'])
def test_native_new_metadata_is_scrubbed_before_brief_extraction_and_report(root, padding, kind):
    canary = 'wuwei private marker'
    (root / ws.DIR / 'canary').write_text(canary + '\n')
    token = ('ghp_' + 'a' * 36) if kind == 'credential' else canary
    prefix = 'x' * padding
    hook.handle(root, 'PostToolUse', {
        'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
        'model': prefix + token + ' parent', 'effort': {'level': prefix + token + ' effort'},
        'tool_input': {'agent_type': 'builder', 'message': f'Item: I-1\nModel: {prefix}{token} high\nModel reason: {prefix}{token}'},
        'tool_response': {'task_name': '/root/metadata-redaction'},
    })
    assert ws.rows(root, 'hook.error') == []
    row = ws.rows(root, 'seat.started')[0]['data']
    assert row['asked'] == prefix + '***'
    assert row['turn_model'] == prefix + '*** parent'
    assert row['turn_effort'] == prefix + '*** effort'
    persisted = json.dumps(row) + report.day(root)
    assert token not in persisted and 'wuwei' not in row['asked']
    assert (prefix + '***')[:200] == row['reason']


@pytest.mark.parametrize('field', ['model', 'effort'])
@pytest.mark.parametrize('shape', ['dict', 'list', 'number', 'bool', 'blank', 'none'])
def test_review_1261_invalid_parent_settings_stay_unmeasured(root, field, shape):
    token, canary = 'ghp_' + 'Z' * 36, 'wuwei-canary-nested-1261'
    (root / ws.DIR / 'canary').write_text(canary)
    value = {'dict': {'unexpected': [token, canary]}, 'list': [token, {'nested': canary}],
             'number': 7, 'bool': False, 'blank': ' \t ', 'none': None}[shape]
    payload = {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
               'tool_input': {'agent_type': 'builder', 'message': 'Item: I-1'},
               'tool_response': {'task_name': '/root/review'}}
    payload[field] = value if field == 'model' else {'level': value}
    hook.handle(root, 'PostToolUse', payload)
    assert ws.rows(root, 'hook.error') == []
    row = ws.rows(root, 'seat.started')[0]['data']
    assert row['turn_' + field] == 'unmeasured'
    persisted = json.dumps(ws.rows(root, 'seat.started')) + report.day(root)
    assert token not in persisted and canary not in persisted
    assert (row['model'], row['asked'], row['effort']) == ('unmeasured', 'unrecorded', 'unrecorded')


@pytest.mark.parametrize('model, effort', [('gpt-6-ultra', 'low'), ('provider-high-model', 'low'),
                                         ('local-max', 'low'), ('gpt-max-ultra-high', 'xhigh'), ('gpt-6-astra', 'ultra')])
def test_review_1261_model_id_effort_words_do_not_replace_requested_effort(root, model, effort):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
                                      'tool_input': {'agent_type': 'builder', 'message': f'Item: I-1\nModel: {model} {effort}'},
                                      'tool_response': {'task_name': '/root/review'}})
    row = ws.rows(root, 'seat.started')[0]['data']
    assert (row['asked'], row['effort'], row['model']) == (model, effort, 'unmeasured')
    assert f'requested: {model} {effort}' in report.day(root)


@pytest.mark.parametrize('model, effort', [('Opus 5.5', 'high'), ('Sonnet 5.5', 'medium'),
                                         ('claude-opus-5-5', 'xhigh'), ('Fable 5.1', 'max')])
def test_review_1261_claude_family_brief_lines_keep_separate_effort_token(root, model, effort):
    started(root, {'subagent_type': 'builder', 'prompt': f'Item: I-1\nModel: {model} {effort} (builder)'}, {'agentId': 'b1'})
    assert ws.rows(root, 'seat.started')[0]['data']['effort'] == effort


def test_review_1261_brief_only_requested_model_is_visible_before_launch(root):
    out = hook.handle(root, 'PreToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
                                          'tool_input': {'agent_type': 'builder', 'message': 'Item: I-1\nModel: gpt-6-astra ultra'}})
    assert 'requested: gpt-6-astra ultra' in advice(out)


@pytest.mark.parametrize('model_line', ['x' * 64000, 'short' + ' ' * 64000], ids=['token', 'space-tail'])
@pytest.mark.parametrize('effort', ['', 'high'])
def test_review_1261_long_model_lines_keep_native_launch_bounded(root, model_line, effort):
    code = '''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from wuwei import hook
root = Path(sys.argv[2])
out = hook.handle(root, 'PreToolUse', {
    'session_id': 'bounded-model', 'cwd': str(root), 'tool_name': 'spawn_agent',
    'tool_input': {'agent_type': 'builder', 'message': 'Item: I-1\\nModel: ' + json.load(sys.stdin)}})
print(json.dumps(out))
'''
    result = subprocess.run([sys.executable, '-c', code, str(PLUGIN / 'cli'), str(root)],
                            input=json.dumps(model_line + (' ' + effort if effort else '')),
                            capture_output=True, text=True, timeout=2, check=True)
    text = advice(json.loads(result.stdout))
    assert f"requested: {model_line.split()[0]} {effort or 'unrecorded'};" in text


@pytest.mark.parametrize('tail, expected', [(' high(extra)', 'high'), ('\thigh', 'high'),
                                          (' highish', None), ('\vhigh', None), ('\fhigh', None),
                                          ('\v high', 'high'), ('\f high', 'high')])
def test_review_1261_model_effort_keeps_horizontal_token_boundaries(tail, expected):
    assert hook.asked({'prompt': 'Model: gpt-6-ultra' + tail})[1] == expected
